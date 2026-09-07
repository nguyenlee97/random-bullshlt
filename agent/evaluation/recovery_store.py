"""Durable proposal and audit storage for the guarded L3 recovery slice."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError


_mem_proposals: dict[str, dict] = {}
_mem_events: list[dict] = []
_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _collections():
    from session import _ensure_mongo
    if not await _ensure_mongo():
        return None
    import session
    db = session._client[session.config.MONGODB_DB]
    return db["evaluation_recovery_proposals"], db["evaluation_recovery_events"]


async def durable_available() -> bool:
    return await _collections() is not None


def _serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def public(value: dict | None) -> dict | None:
    if not value:
        return None
    result = deepcopy(value)
    result.pop("_id", None)
    result.pop("approval_nonce_hash", None)
    # Additive v2 read compatibility for proposals persisted by the original
    # restore-config slice. Their approval/execution semantics stay unchanged.
    if result.get("action_id") == "restore_config_revision" and not result.get("kind"):
        result.update({
            "schema_version": "l3-recovery-proposal-v1",
            "kind": "executable_action",
            "label": "Khôi phục campaign config về revision đã duyệt",
            "execution_environment": "production",
            "production_executor": "restore_config_revision",
        })
    return _serialize(result)


async def ensure_recovery_indexes() -> None:
    cols = await _collections()
    if not cols:
        return
    proposals, events = cols
    await proposals.create_index("proposal_id", unique=True)
    await proposals.create_index("request_key", unique=True)
    await proposals.create_index([("campaign_id", 1), ("updated_at", -1)])
    await proposals.create_index("execution_key", unique=True, sparse=True)
    await proposals.create_index(
        [("campaign_id", 1), ("incident_id", 1), ("active", 1)], unique=True,
        partialFilterExpression={"active": True}, name="one_active_recovery_per_incident",
    )
    await events.create_index("event_id", unique=True)
    await events.create_index([("proposal_id", 1), ("created_at", 1)])


async def create_proposal(value: dict) -> tuple[dict, bool]:
    cols = await _collections()
    if cols:
        proposals, _events = cols
        try:
            await proposals.update_one(
                {"request_key": value["request_key"]},
                {"$setOnInsert": value}, upsert=True,
            )
        except DuplicateKeyError:
            active = await proposals.find_one({
                "campaign_id": value["campaign_id"], "incident_id": value["incident_id"],
                "active": True,
            })
            if active:
                return active, False
            raise
        stored = await proposals.find_one({"request_key": value["request_key"]})
        return stored, stored.get("proposal_id") == value.get("proposal_id")
    async with _lock:
        existing = next((item for item in _mem_proposals.values()
                         if item.get("request_key") == value["request_key"]), None)
        if existing:
            return deepcopy(existing), False
        active = next((item for item in _mem_proposals.values()
                       if item.get("campaign_id") == value["campaign_id"]
                       and item.get("incident_id") == value["incident_id"]
                       and item.get("active")), None)
        if active:
            return deepcopy(active), False
        _mem_proposals[value["proposal_id"]] = deepcopy(value)
        return deepcopy(value), True


async def supersede_active(campaign_id: str, incident_id: str, keep_request_key: str) -> int:
    active = [
        "awaiting_approval", "approved", "awaiting_acknowledgement",
        "waiting_operator", "waiting_external", "ready_to_verify",
    ]
    now = _now()
    cols = await _collections()
    if cols:
        result = await cols[0].update_many(
            {"campaign_id": campaign_id, "incident_id": incident_id,
             "request_key": {"$ne": keep_request_key}, "status": {"$in": active}},
            {"$set": {"status": "superseded", "active": False, "updated_at": now}, "$inc": {"version": 1}},
        )
        return int(result.modified_count)
    count = 0
    async with _lock:
        for value in _mem_proposals.values():
            if (value.get("campaign_id") == campaign_id and value.get("incident_id") == incident_id
                    and value.get("request_key") != keep_request_key and value.get("status") in active):
                value.update({"status": "superseded", "active": False, "updated_at": now,
                              "version": int(value.get("version") or 0) + 1})
                count += 1
    return count


async def get_proposal(proposal_id: str) -> dict | None:
    cols = await _collections()
    if cols:
        return await cols[0].find_one({"proposal_id": proposal_id})
    return deepcopy(_mem_proposals.get(proposal_id))


async def list_proposals(campaign_id: str, incident_id: str | None = None) -> list[dict]:
    query = {"campaign_id": campaign_id}
    if incident_id:
        query["incident_id"] = incident_id
    cols = await _collections()
    if cols:
        values = await cols[0].find(query).sort("created_at", -1).to_list(50)
    else:
        values = [item for item in _mem_proposals.values()
                  if all(item.get(key) == expected for key, expected in query.items())]
        values.sort(key=lambda item: item.get("created_at", _now()), reverse=True)
    return [public(item) for item in values]


async def transition(proposal_id: str, *, expected_statuses: set[str], updates: dict,
                     expected_version: int | None = None) -> dict | None:
    changes = {**updates, "updated_at": _now()}
    cols = await _collections()
    if cols:
        query = {"proposal_id": proposal_id, "status": {"$in": sorted(expected_statuses)}}
        if expected_version is not None:
            query["version"] = expected_version
        return await cols[0].find_one_and_update(
            query,
            {"$set": changes, "$inc": {"version": 1}}, return_document=True,
        )
    async with _lock:
        value = _mem_proposals.get(proposal_id)
        if (not value or value.get("status") not in expected_statuses
                or (expected_version is not None and int(value.get("version") or 0) != expected_version)):
            return None
        value.update(changes)
        value["version"] = int(value.get("version") or 0) + 1
        return deepcopy(value)


async def append_event(event: dict) -> None:
    value = {**event, "created_at": event.get("created_at") or _now()}
    cols = await _collections()
    if cols:
        await cols[1].update_one(
            {"event_id": value["event_id"]}, {"$setOnInsert": value}, upsert=True,
        )
        return
    if not any(item.get("event_id") == value["event_id"] for item in _mem_events):
        _mem_events.append(deepcopy(value))


async def proposal_events(proposal_id: str) -> list[dict]:
    cols = await _collections()
    if cols:
        values = await cols[1].find({"proposal_id": proposal_id}).sort("created_at", 1).to_list(100)
    else:
        values = [item for item in _mem_events if item.get("proposal_id") == proposal_id]
    return [_serialize({key: deepcopy(item) for key, item in value.items() if key != "_id"})
            for value in values]
