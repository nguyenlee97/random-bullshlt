"""Mongo-backed append-only quality store with an in-memory test fallback."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import uuid

from pymongo.errors import DuplicateKeyError

from config import config


_mem_interactions: dict[str, dict] = {}
_mem_events: dict[str, dict] = {}
_mem_feedback: dict[str, dict] = {}
_mem_feedback_by_submission: dict[str, str] = {}


def now() -> datetime:
    return datetime.now(timezone.utc)


def expires(days: int) -> datetime:
    return now() + timedelta(days=max(days, 1))


def _feedback_submission_key(item: dict) -> str:
    return (
        f"{(item.get('owner') or {}).get('owner_ref', '')}:"
        f"{item.get('submission_id', '')}"
    )


async def _collections():
    from session import _ensure_mongo

    if not await _ensure_mongo():
        return None, None, None
    import session as session_store

    db = session_store._client[config.MONGODB_DB]
    return (
        db["agent_interactions"],
        db["agent_quality_events"],
        db["agent_feedback"],
    )


async def ensure_quality_indexes() -> None:
    interactions, events, feedback = await _collections()
    if interactions is None:
        return
    await interactions.create_index(
        [("request_id", 1), ("surface", 1)],
        unique=True,
        name="quality_interaction_request_surface_unique",
    )
    await interactions.create_index(
        [("conversation_id", 1), ("created_at", -1)],
        name="quality_interaction_conversation_created",
    )
    await interactions.create_index(
        [("run_id", 1), ("created_at", -1)],
        name="quality_interaction_run_created",
    )
    await interactions.create_index("expires_at", expireAfterSeconds=0)

    await events.create_index(
        [("request_id", 1), ("created_at", -1)],
        name="quality_event_request_created",
    )
    await events.create_index(
        [("run_id", 1), ("created_at", -1)],
        name="quality_event_run_created",
    )
    await events.create_index("expires_at", expireAfterSeconds=0)

    await feedback.create_index(
        [("owner.owner_ref", 1), ("submission_id", 1)],
        unique=True,
        name="feedback_owner_submission_unique",
    )
    await feedback.create_index(
        [("target.run_id", 1), ("created_at", -1)],
        name="feedback_run_created",
    )
    await feedback.create_index(
        [("target.conversation_id", 1), ("created_at", -1)],
        name="feedback_conversation_created",
    )
    await feedback.create_index("expires_at", expireAfterSeconds=0)


async def insert_interaction(doc: dict) -> dict:
    item = deepcopy(doc)
    item.setdefault("_id", f"ai_{uuid.uuid4().hex}")
    interactions, _, _ = await _collections()
    if interactions is not None:
        try:
            await interactions.insert_one(item)
        except DuplicateKeyError:
            existing = await interactions.find_one({
                "request_id": item["request_id"], "surface": item["surface"],
            })
            return deepcopy(existing or item)
    else:
        key = f"{item['request_id']}:{item['surface']}"
        existing = next(
            (
                value for value in _mem_interactions.values()
                if f"{value['request_id']}:{value['surface']}" == key
            ),
            None,
        )
        if existing:
            return deepcopy(existing)
        _mem_interactions[item["_id"]] = deepcopy(item)
    return deepcopy(item)


async def insert_event(doc: dict) -> dict:
    item = deepcopy(doc)
    item.setdefault("_id", f"aqe_{uuid.uuid4().hex}")
    _, events, _ = await _collections()
    if events is not None:
        await events.insert_one(item)
    else:
        _mem_events[item["_id"]] = deepcopy(item)
    return deepcopy(item)


async def insert_feedback(doc: dict) -> tuple[dict, bool]:
    item = deepcopy(doc)
    item.setdefault("_id", f"afb_{uuid.uuid4().hex}")
    _, _, feedback = await _collections()
    query = {
        "owner.owner_ref": (item.get("owner") or {}).get("owner_ref"),
        "submission_id": item["submission_id"],
    }
    if feedback is not None:
        existing = await feedback.find_one(query)
        if existing:
            return deepcopy(existing), False
        try:
            await feedback.insert_one(item)
        except DuplicateKeyError:
            existing = await feedback.find_one(query)
            if existing:
                return deepcopy(existing), False
            raise
    else:
        if not config.QUALITY_FEEDBACK_ALLOW_MEMORY_FALLBACK:
            raise RuntimeError("durable feedback storage is unavailable")
        submission_key = _feedback_submission_key(item)
        existing_id = _mem_feedback_by_submission.get(submission_key)
        if existing_id:
            return deepcopy(_mem_feedback[existing_id]), False
        _mem_feedback[item["_id"]] = deepcopy(item)
        _mem_feedback_by_submission[submission_key] = item["_id"]
    return deepcopy(item), True


async def interaction_belongs_to_session(
    session_id: str, request_id: str,
) -> bool:
    interactions, _, _ = await _collections()
    query = {"session_id": session_id, "request_id": request_id}
    if interactions is not None:
        return await interactions.find_one(query, {"_id": 1}) is not None
    return any(
        item.get("session_id") == session_id
        and item.get("request_id") == request_id
        for item in _mem_interactions.values()
    )


async def delete_quality_for_sessions(session_ids: list[str]) -> dict[str, int]:
    targets = {value for value in session_ids if value}
    if not targets:
        return {"agent_interactions": 0, "agent_quality_events": 0, "agent_feedback": 0}
    interactions, events, feedback = await _collections()
    if interactions is not None:
        results = await __import__("asyncio").gather(
            interactions.delete_many({"session_id": {"$in": list(targets)}}),
            events.delete_many({"session_id": {"$in": list(targets)}}),
            feedback.delete_many({"target.session_id": {"$in": list(targets)}}),
        )
        return {
            "agent_interactions": results[0].deleted_count,
            "agent_quality_events": results[1].deleted_count,
            "agent_feedback": results[2].deleted_count,
        }

    removed = {"agent_interactions": 0, "agent_quality_events": 0, "agent_feedback": 0}
    for collection, key, field in (
        (_mem_interactions, "agent_interactions", "session_id"),
        (_mem_events, "agent_quality_events", "session_id"),
    ):
        ids = [item_id for item_id, item in collection.items() if item.get(field) in targets]
        for item_id in ids:
            collection.pop(item_id, None)
        removed[key] = len(ids)
    feedback_ids = [
        item_id for item_id, item in _mem_feedback.items()
        if (item.get("target") or {}).get("session_id") in targets
    ]
    for item_id in feedback_ids:
        item = _mem_feedback.pop(item_id, None)
        if item:
            _mem_feedback_by_submission.pop(
                _feedback_submission_key(item), None
            )
    removed["agent_feedback"] = len(feedback_ids)
    return removed
