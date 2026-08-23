from __future__ import annotations

import asyncio
import hashlib
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from evaluation.engine import DEFAULT_POLICY


_mem_policies: dict[str, dict] = {}
_mem_runs: dict[str, dict] = {}
_mem_incidents: dict[str, dict] = {}
_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


async def get_policy(campaign_id: str) -> dict:
    cols = await _collections()
    if cols:
        doc = await cols[0].find_one({"campaign_id": campaign_id})
    else:
        doc = _mem_policies.get(campaign_id)
    if doc:
        return _public(doc)
    value = {
        "campaign_id": campaign_id, **DEFAULT_POLICY,
        "updated_at": _now(),
        "next_run_at": _now() + timedelta(minutes=DEFAULT_POLICY["schedule_minutes"]),
    }
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
        "campaign_id": campaign_id, "version": "evaluation-policy-v1",
        "updated_at": _now(),
        "next_run_at": _now() + timedelta(minutes=int(policy["schedule_minutes"])),
    })
    if cols:
        await cols[0].replace_one({"campaign_id": campaign_id}, policy, upsert=True)
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
    query = {"campaign_id": campaign_id, "dataset_revision": dataset_revision, "policy_version": policy_version}
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
        "trigger": trigger, "status": "completed", "issue_count": len(issues),
        "created_at": _now(), "completed_at": _now(),
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
        raw_key = f'{campaign_id}|{issue["issue_type"]}|{issue["scope"]}|{run["policy_version"]}'
        dedup_key = hashlib.sha256(raw_key.encode()).hexdigest()
        now = _now()
        update = {
            "campaign_id": campaign_id, "dedup_key": dedup_key,
            **issue, "last_run_id": run["run_id"],
            "dataset_revision": run["dataset_revision"], "updated_at": now,
        }
        if cols:
            doc = await cols[2].find_one_and_update(
                {"dedup_key": dedup_key},
                {"$set": update, "$setOnInsert": {
                    "incident_id": f"INC-{uuid.uuid4().hex[:6].upper()}",
                    "created_at": now, "state": "open",
                    "timeline": [{"state": "detected", "at": now}],
                }}, upsert=True, return_document=True,
            )
        else:
            async with _lock:
                doc = next((item for item in _mem_incidents.values() if item["dedup_key"] == dedup_key), None)
                if not doc:
                    doc = {
                        "incident_id": f"INC-{uuid.uuid4().hex[:6].upper()}",
                        "created_at": now, "state": "open",
                        "timeline": [{"state": "detected", "at": now}],
                    }
                doc.update(update)
                _mem_incidents[doc["incident_id"]] = doc
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
    if not doc:
        raise KeyError("incident not found")
    return _public(doc)
