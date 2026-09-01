from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from evaluation.engine import DEFAULT_POLICY


_mem_policies: dict[str, dict] = {}
_mem_runs: dict[str, dict] = {}
_mem_incidents: dict[str, dict] = {}
_mem_investigations: dict[str, dict] = {}
_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def policy_version(value: dict) -> str:
    effective = {key: value.get(key, default) for key, default in DEFAULT_POLICY.items() if key != 'version'}
    digest = hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest()[:16]
    return f'evaluation-policy-v2-{digest}'


async def _collections():
    from session import _ensure_mongo
    if not await _ensure_mongo():
        return None
    import session
    db = session._client[session.config.MONGODB_DB]
    return db["evaluation_policies"], db["evaluation_runs"], db["evaluation_incidents"]


def _public(value: dict) -> dict:
    result = deepcopy(value)
    result.pop("_id", None)
    result.pop('lease_token', None)
    for key, item in list(result.items()):
        if isinstance(item, datetime):
            result[key] = item.isoformat()
    return result


async def ensure_evaluation_indexes() -> None:
    cols = await _collections()
    if not cols:
        return
    policies, runs, incidents = cols
    await policies.create_index("campaign_id", unique=True)
    await runs.create_index([("campaign_id", 1), ("created_at", -1)])
    await runs.create_index(
        [("campaign_id", 1), ("dataset_revision", 1), ("policy_version", 1)]
    )
    await incidents.create_index("incident_id", unique=True)
    await incidents.create_index("dedup_key", unique=True)
    await incidents.create_index([("campaign_id", 1), ("updated_at", -1)])
    import session
    await session._client[session.config.MONGODB_DB]['evaluation_investigations'].create_index(
        [('campaign_id', 1), ('incident_id', 1), ('created_at', -1)])


async def get_policy(campaign_id: str) -> dict:
    cols = await _collections()
    if cols:
        doc = await cols[0].find_one({"campaign_id": campaign_id})
    else:
        doc = _mem_policies.get(campaign_id)
    if doc:
        return _public({**DEFAULT_POLICY, **doc, 'version': policy_version(doc)})
    value = {
        "campaign_id": campaign_id, **DEFAULT_POLICY,
        "updated_at": _now(),
        "next_run_at": _now() + timedelta(minutes=DEFAULT_POLICY["schedule_minutes"]),
    }
    value['version'] = policy_version(value)
    if cols:
        await cols[0].update_one(
            {"campaign_id": campaign_id}, {"$setOnInsert": value}, upsert=True,
        )
    else:
        _mem_policies.setdefault(campaign_id, value)
    return _public(value)


async def save_policy(campaign_id: str, updates: dict) -> dict:
    allowed = set(DEFAULT_POLICY) - {"version"}
    cols = await _collections()
    if cols:
        current = await cols[0].find_one({"campaign_id": campaign_id}) or {}
    else:
        current = _mem_policies.get(campaign_id) or {}
    current.pop("_id", None)
    policy = {
        **DEFAULT_POLICY, **current,
        **{key: value for key, value in updates.items() if key in allowed},
    }
    policy.update({
        "campaign_id": campaign_id, "version": policy_version(policy),
        "updated_at": _now(),
        "next_run_at": _now() + timedelta(minutes=int(policy["schedule_minutes"])),
    })
    if cols:
        await cols[0].update_one({'campaign_id': campaign_id}, {'$set': {k: v for k, v in policy.items() if not k.startswith('lease_')}}, upsert=True)
    else:
        _mem_policies[campaign_id] = policy
    return _public(policy)


async def claim_due_policy() -> dict | None:
    now = _now()
    cols = await _collections()
    if cols:
        candidate = await cols[0].find_one(
            {"enabled": True, "next_run_at": {"$lte": now}},
            sort=[("next_run_at", 1)],
        )
        if not candidate:
            return None
        next_run = now + timedelta(minutes=max(5, int(candidate.get("schedule_minutes", 60))))
        doc = await cols[0].find_one_and_update(
            {"_id": candidate["_id"], "next_run_at": candidate["next_run_at"]},
            {"$set": {"next_run_at": next_run, "last_scheduled_at": now}},
            return_document=True,
        )
        return _public(doc) if doc else None
    due = [item for item in _mem_policies.values() if item.get("enabled") and item.get("next_run_at", now) <= now]
    if not due:
        return None
    value = min(due, key=lambda item: item.get("next_run_at", now))
    value["last_scheduled_at"] = now
    value["next_run_at"] = now + timedelta(minutes=max(5, int(value.get("schedule_minutes", 60))))
    return _public(value)


async def find_existing_run(campaign_id: str, dataset_revision: int, policy_version: str) -> dict | None:
    query = {"campaign_id": campaign_id, "dataset_revision": dataset_revision, "policy_version": policy_version, 'status': 'completed'}
    cols = await _collections()
    if cols:
        value = await cols[1].find_one(query)
    else:
        value = next((item for item in _mem_runs.values() if all(item.get(k) == v for k, v in query.items())), None)
    return _public(value) if value else None


async def save_run(campaign_id: str, dataset_revision: int, policy_version: str,
                   issues: list[dict], trigger: str) -> dict:
    run = {
        "run_id": f"EVR-{uuid.uuid4().hex[:10].upper()}", "campaign_id": campaign_id,
        "dataset_revision": dataset_revision, "policy_version": policy_version,
        "trigger": trigger, "status": "running", "issue_count": len(issues),
        "created_at": _now(),
    }
    cols = await _collections()
    if cols:
        await cols[1].insert_one(run)
    else:
        _mem_runs[run["run_id"]] = run
    return _public(run)


async def upsert_incidents(campaign_id: str, run: dict, issues: list[dict]) -> list[dict]:
    results = []
    cols = await _collections()
    for issue in issues:
        raw_key = f'{campaign_id}|{issue["issue_type"]}|{issue["scope"]}'
        dedup_key = hashlib.sha256(raw_key.encode()).hexdigest()
        now = _now()
        update = {
            "campaign_id": campaign_id, "dedup_key": dedup_key,
            **issue, "last_run_id": run["run_id"],
            "dataset_revision": run["dataset_revision"], "updated_at": now,
            "policy_version": run["policy_version"],
        }
        # Migrate the old policy-specific key without duplicating an incident.
        identity = {'campaign_id': campaign_id, 'issue_type': issue['issue_type'], 'scope': issue['scope']}
        if cols:
            existing = await cols[2].find_one(identity)
            if existing and existing.get('investigation') and (
                existing['investigation'].get('dataset_revision') != run['dataset_revision']
                or existing['investigation'].get('policy_version') != run['policy_version']
            ):
                update.update({'investigation': None, 'investigation_state': 'stale'})
            query = {'incident_id': existing['incident_id']} if existing else {'dedup_key': dedup_key}
            doc = await cols[2].find_one_and_update(
                query,
                {"$set": update, "$setOnInsert": {
                    "incident_id": f"INC-{uuid.uuid4().hex[:6].upper()}",
                    "created_at": now, "state": "open",
                    "timeline": [{"state": "detected", "at": now}],
                }}, upsert=True, return_document=True,
            )
        else:
            async with _lock:
                doc = next((item for item in _mem_incidents.values() if all(item.get(k) == v for k, v in identity.items())), None)
                if not doc:
                    doc = {
                        "incident_id": f"INC-{uuid.uuid4().hex[:6].upper()}",
                        "created_at": now, "state": "open",
                        "timeline": [{"state": "detected", "at": now}],
                    }
                if doc.get('investigation') and (
                    doc['investigation'].get('dataset_revision') != run['dataset_revision']
                    or doc['investigation'].get('policy_version') != run['policy_version']
                ):
                    update.update({'investigation': None, 'investigation_state': 'stale'})
                doc.update(update)
                _mem_incidents[doc["incident_id"]] = doc
        if doc.get('state') in {'resolved', 'expired'}:
            doc = await transition_incident(campaign_id, doc['incident_id'], 'open', 'Signal detected again; incident reopened')
        results.append(_public(doc))
    return results


async def resolve_stale_incidents(campaign_id: str, active_incident_ids: set[str],
                                  run_id: str) -> int:
    now = _now()
    active_states = [
        "detected", "diagnosing", "open", "investigating", "awaiting_approval",
        "recovering", "verifying", "failed",
    ]
    cols = await _collections()
    query = {
        "campaign_id": campaign_id, "state": {"$in": active_states},
        "incident_id": {"$nin": sorted(active_incident_ids)},
    }
    event = {"state": "resolved", "at": now, "note": f"No longer detected in {run_id}"}
    if cols:
        result = await cols[2].update_many(
            query,
            {"$set": {"state": "resolved", "updated_at": now}, "$push": {"timeline": event}},
        )
        return int(result.modified_count)
    count = 0
    for item in _mem_incidents.values():
        if item.get("campaign_id") != campaign_id or item.get("state") not in active_states:
            continue
        if item["incident_id"] in active_incident_ids:
            continue
        item.update({"state": "resolved", "updated_at": now})
        item.setdefault("timeline", []).append(event)
        count += 1
    return count


async def list_incidents(campaign_id: str) -> list[dict]:
    cols = await _collections()
    if cols:
        values = await cols[2].find({"campaign_id": campaign_id}).sort("updated_at", -1).to_list(None)
    else:
        values = [item for item in _mem_incidents.values() if item["campaign_id"] == campaign_id]
        values.sort(key=lambda item: item["updated_at"], reverse=True)
    return [_public(item) for item in values]


async def attach_investigation(campaign_id: str, incident_id: str, bundle: dict) -> dict:
    """Store an L2 evidence bundle and move the incident to ``investigating``.

    Only the newest bundle is kept live; every bundle is also appended to the
    timeline so the investigation history stays auditable.
    """
    now = _now()
    top = (bundle.get("top_hypothesis") or {}).get("hypothesis_id")
    event = {
        "state": "investigating", "at": now,
        "note": f"L2 investigation ({bundle.get('trigger', 'manual')})",
        "investigation": {
            "bundle_version": bundle.get("bundle_version"),
            "top_hypothesis": top,
            "confidence": (bundle.get("top_hypothesis") or {}).get("confidence"),
            "gate_applied": bool((bundle.get("gate") or {}).get("applied")),
        },
    }
    changes = {
        "investigation": bundle, "investigated_at": now,
        "investigation_state": bundle.get('assessment', 'completed') if bundle.get("supported") else "unsupported",
        "updated_at": now,
    }
    cols = await _collections()
    current = await get_incident(campaign_id, incident_id)
    if not current:
        raise KeyError('incident not found')
    if bundle.get('dataset_revision') != current.get('dataset_revision'):
        raise ValueError('dataset revision changed; run evaluation again')
    if current.get('state') in {'resolved', 'dismissed', 'false_positive', 'expired'}:
        raise ValueError('incident closed during investigation')
    if current.get('policy_version') and bundle.get('policy_version') != current['policy_version']:
        raise ValueError('policy version changed; run evaluation again')
    if bundle.get('bundle_id') and (current.get('investigation') or {}).get('bundle_id') == bundle['bundle_id']:
        return current
    bundle_id = bundle.get('bundle_id') or uuid.uuid4().hex
    history_doc = {**deepcopy(bundle), 'bundle_id': bundle_id, 'incident_id': incident_id, 'campaign_id': campaign_id}
    if cols:
        import session
        history = session._client[session.config.MONGODB_DB]['evaluation_investigations']
        await history.update_one({'_id': bundle_id}, {'$setOnInsert': history_doc}, upsert=True)
        doc = await cols[2].find_one_and_update(
            {"campaign_id": campaign_id, "incident_id": incident_id, 'dataset_revision': bundle.get('dataset_revision'),
             'state': {'$nin': ['resolved', 'dismissed', 'false_positive', 'expired']},
             **({'policy_version': bundle['policy_version']} if current.get('policy_version') else {})},
            # An incident already being recovered or verified keeps its state;
            # evidence is additive and must never rewind the lifecycle.
            {"$set": changes, "$push": {"timeline": event}},
            return_document=True,
        )
        if doc and doc.get("state") in {"detected", "diagnosing", "open"}:
            changed = await cols[2].find_one_and_update(
                {"campaign_id": campaign_id, "incident_id": incident_id, 'state': {'$in': ['detected', 'diagnosing', 'open']}},
                {"$set": {"state": "investigating"}}, return_document=True,
            )
            doc = changed or await cols[2].find_one({'campaign_id': campaign_id, 'incident_id': incident_id})
    else:
        _mem_investigations.setdefault(bundle_id, history_doc)
        doc = _mem_incidents.get(incident_id)
        if doc and doc.get("campaign_id") == campaign_id:
            doc.update(changes)
            doc.setdefault("timeline", []).append(event)
            if doc.get("state") in {"detected", "diagnosing", "open"}:
                doc["state"] = "investigating"
    if not doc:
        raise KeyError("incident not found")
    return _public(doc)


async def investigation_history(campaign_id: str, incident_id: str) -> list[dict]:
    cols = await _collections()
    if cols:
        import session
        collection = session._client[session.config.MONGODB_DB]['evaluation_investigations']
        values = await collection.find({'campaign_id': campaign_id, 'incident_id': incident_id}).sort('created_at', -1).limit(30).to_list(None)
    else:
        values = sorted([v for v in _mem_investigations.values() if v['campaign_id'] == campaign_id and v['incident_id'] == incident_id], key=lambda v: v.get('created_at', ''), reverse=True)[:30]
    return [_public(value) for value in values]


async def finish_run(run_id: str, status: str, **details) -> dict:
    changes = {'status': status, 'completed_at': _now(), **details}
    cols = await _collections()
    if cols:
        doc = await cols[1].find_one_and_update({'run_id': run_id}, {'$set': changes}, return_document=True)
    else:
        doc = _mem_runs[run_id]
        doc.update(changes)
    return _public(doc)


async def latest_run(campaign_id: str) -> dict | None:
    cols = await _collections()
    if cols:
        doc = await cols[1].find_one({'campaign_id': campaign_id}, sort=[('created_at', -1)])
    else:
        values = [v for v in _mem_runs.values() if v['campaign_id'] == campaign_id]
        doc = max(values, key=lambda v: v['created_at']) if values else None
    return _public(doc) if doc else None


def health_summary(incidents: list[dict], run: dict | None) -> dict:
    closed = {'resolved', 'dismissed', 'false_positive', 'expired'}
    active = [i for i in incidents if i.get('state') not in closed]
    return {
        'status': 'bad' if any(i.get('severity') in {'critical', 'high'} for i in active)
        else 'watch' if active else 'healthy' if run and run.get('status') == 'completed' else 'not_evaluated',
        'open_count': len(active),
        'critical_count': sum(i.get('severity') == 'critical' for i in active),
        'last_evaluated_at': (run or {}).get('completed_at'),
        'last_run_status': (run or {}).get('status'),
    }


async def campaign_health_summaries(campaign_ids: list[str]) -> dict:
    """Batch directory summary; draft cards do not register monitoring."""
    if not campaign_ids:
        return {}
    cols = await _collections()
    if cols:
        incidents = await cols[2].find({'campaign_id': {'$in': campaign_ids}},
                                     {'campaign_id': 1, 'state': 1, 'severity': 1}).to_list(None)
        grouped = await cols[1].aggregate([
            {'$match': {'campaign_id': {'$in': campaign_ids}}},
            {'$sort': {'created_at': -1}},
            {'$group': {'_id': '$campaign_id', 'run': {'$first': '$$ROOT'}}},
        ]).to_list(None)
        runs = {row['_id']: _public(row['run']) for row in grouped}
    else:
        incidents = list(_mem_incidents.values())
        runs = {key: await latest_run(key) for key in campaign_ids}
    return {key: health_summary([i for i in incidents if i['campaign_id'] == key], runs.get(key))
            for key in campaign_ids}


async def acquire_campaign_lease(campaign_id: str) -> str | None:
    await get_policy(campaign_id)
    now, token = _now(), uuid.uuid4().hex
    fields = {'lease_token': token, 'lease_until': now + timedelta(minutes=30)}
    cols = await _collections()
    if cols:
        doc = await cols[0].find_one_and_update({'campaign_id': campaign_id, '$or': [{'lease_until': {'$exists': False}}, {'lease_until': {'$lte': now}}]}, {'$set': fields}, return_document=True)
        return token if doc else None
    async with _lock:
        doc = _mem_policies[campaign_id]
        if doc.get('lease_until', now) > now:
            return None
        doc.update(fields)
        return token


async def release_campaign_lease(campaign_id: str, token: str) -> None:
    cols = await _collections()
    if cols:
        await cols[0].update_one({'campaign_id': campaign_id, 'lease_token': token}, {'$unset': {'lease_token': '', 'lease_until': ''}})
    else:
        doc = _mem_policies.get(campaign_id, {})
        if doc.get('lease_token') == token:
            doc.pop('lease_token', None)
            doc.pop('lease_until', None)


async def renew_campaign_lease(campaign_id: str, token: str) -> bool:
    now = _now()
    cols = await _collections()
    if cols:
        doc = await cols[0].find_one_and_update(
            {'campaign_id': campaign_id, 'lease_token': token, 'lease_until': {'$gt': now}},
            {'$set': {'lease_until': now + timedelta(minutes=30)}}, return_document=True)
        return bool(doc)
    doc = _mem_policies.get(campaign_id, {})
    if doc.get('lease_token') != token or doc.get('lease_until', now) <= now:
        return False
    doc['lease_until'] = now + timedelta(minutes=30)
    return True


async def schedule_retry(campaign_id: str) -> None:
    retry_at = _now() + timedelta(minutes=5)
    cols = await _collections()
    if cols:
        await cols[0].update_one({'campaign_id': campaign_id}, {'$min': {'next_run_at': retry_at}})
    else:
        doc = _mem_policies.get(campaign_id, {})
        doc['next_run_at'] = min(doc.get('next_run_at', retry_at), retry_at)


async def get_incident(campaign_id: str, incident_id: str) -> dict | None:
    cols = await _collections()
    if cols:
        doc = await cols[2].find_one({"campaign_id": campaign_id, "incident_id": incident_id})
    else:
        doc = _mem_incidents.get(incident_id)
        if doc and doc.get("campaign_id") != campaign_id:
            doc = None
    return _public(doc) if doc else None


async def transition_incident(campaign_id: str, incident_id: str, state: str,
                              note: str = "") -> dict:
    allowed = {
        "investigating", "awaiting_approval", "recovering", "verifying",
        "resolved", "dismissed", "false_positive", "failed", "expired", "open",
    }
    if state not in allowed:
        raise ValueError("invalid incident state")
    now = _now()
    event = {"state": state, "at": now, "note": note}
    cols = await _collections()
    if cols:
        doc = await cols[2].find_one_and_update(
            {"campaign_id": campaign_id, "incident_id": incident_id},
            {"$set": {"state": state, "updated_at": now}, "$push": {"timeline": event}},
            return_document=True,
        )
    else:
        doc = _mem_incidents.get(incident_id)
        if doc and doc.get("campaign_id") == campaign_id:
            doc.update({"state": state, "updated_at": now})
            doc.setdefault("timeline", []).append(event)
        else:
            doc = None
    if not doc:
        raise KeyError("incident not found")
    return _public(doc)
