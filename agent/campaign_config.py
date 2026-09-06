"""Revisioned, ownership-gated edits for launched campaign configuration."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any

import httpx
from pymongo.errors import DuplicateKeyError

from config import config


EDITABLE_FIELDS = {"objective", "budget", "daily", "startDate", "endDate"}
_mem_revisions: dict[str, list[dict]] = {}
_mem_requests: dict[tuple[str, str], dict] = {}
_locks: dict[str, asyncio.Lock] = {}


class ConfigConflict(Exception):
    pass


class ConfigValidationError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lock(campaign_id: str) -> asyncio.Lock:
    return _locks.setdefault(campaign_id, asyncio.Lock())


async def _collection():
    from session import _ensure_mongo
    if not await _ensure_mongo():
        return None
    import session
    return session._client[config.MONGODB_DB]["campaign_config_revisions"]


async def ensure_campaign_config_indexes() -> None:
    collection = await _collection()
    if collection is None:
        return
    await collection.create_index(
        [("campaign_id", 1), ("revision", 1)], unique=True,
        name="campaign_config_revision_unique",
    )
    await collection.create_index(
        [("campaign_id", 1), ("request_id", 1)], unique=True,
        name="campaign_config_request_unique",
    )


def _public(value: dict) -> dict:
    result = deepcopy(value)
    result.pop("_id", None)
    result.pop("actor", None)
    for key, item in list(result.items()):
        if isinstance(item, datetime):
            result[key] = item.isoformat()
    return result


def _snapshot(order: dict) -> dict:
    return {
        key: deepcopy(order.get(key))
        for key in (
            "brand", "advertiser", "objective", "status", "budget", "daily",
            "startDate", "endDate", "placements", "placementSnapshots",
            "creative", "creatives", "targeting", "dmp", "warnings",
        )
    }


def _parse_date(value: object, field: str) -> str:
    raw = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError as exc:
        raise ConfigValidationError(f"{field} must be an ISO date") from exc


def _normalize_patch(patch: dict, current: dict) -> dict:
    unknown = set(patch) - EDITABLE_FIELDS
    if unknown:
        raise ConfigValidationError(
            f"unsupported config fields: {', '.join(sorted(unknown))}"
        )
    clean: dict[str, Any] = {}
    if "objective" in patch:
        objective = str(patch["objective"] or "").strip().lower()
        if objective not in {"awareness", "consideration", "conversion", "retention"}:
            raise ConfigValidationError("objective is not supported")
        clean["objective"] = objective
    for field in ("budget", "daily"):
        if field in patch:
            try:
                value = round(float(patch[field]))
            except (TypeError, ValueError) as exc:
                raise ConfigValidationError(f"{field} must be numeric") from exc
            if value < 0 or (field == "budget" and value == 0):
                raise ConfigValidationError(
                    "budget must be positive" if field == "budget" else "daily cannot be negative"
                )
            clean[field] = value
    for field in ("startDate", "endDate"):
        if field in patch:
            clean[field] = _parse_date(patch[field], field)
    start = _parse_date(clean.get("startDate", current.get("startDate")), "startDate")
    end = _parse_date(clean.get("endDate", current.get("endDate")), "endDate")
    if start > end:
        raise ConfigValidationError("startDate cannot be after endDate")
    return clean


async def _history(campaign_id: str) -> list[dict]:
    collection = await _collection()
    if collection is not None:
        values = await collection.find({
            "campaign_id": campaign_id, "status": "completed",
        }).sort("revision", -1).to_list(50)
    else:
        values = sorted(
            _mem_revisions.get(campaign_id, []),
            key=lambda item: item["revision"], reverse=True,
        )[:50]
    return [_public(item) for item in values]


async def get_campaign_config(campaign_id: str) -> dict:
    from tools.order_api import fetch_order
    order = await fetch_order(campaign_id)
    history = await _history(campaign_id)
    return {
        "campaign_id": campaign_id,
        "revision": history[0]["revision"] if history else 0,
        "config": _snapshot(order),
        "editable_fields": sorted(EDITABLE_FIELDS),
        "history": history,
    }


async def _find_request(campaign_id: str, request_id: str) -> dict | None:
    collection = await _collection()
    if collection is not None:
        return await collection.find_one({
            "campaign_id": campaign_id, "request_id": request_id,
        })
    return _mem_requests.get((campaign_id, request_id))


async def _insert(record: dict) -> dict:
    collection = await _collection()
    if collection is not None:
        try:
            await collection.insert_one(record)
        except DuplicateKeyError as exc:
            raise ConfigConflict("config revision changed; reload before saving") from exc
    else:
        key = (record["campaign_id"], record["request_id"])
        if key in _mem_requests:
            return _mem_requests[key]
        _mem_revisions.setdefault(record["campaign_id"], []).append(record)
        _mem_requests[key] = record
    return record


async def _complete(record: dict, after: dict) -> dict:
    now = _now()
    changes = {
        key: {"before": record["before"].get(key), "after": after.get(key)}
        for key in record["patch"]
        if record["before"].get(key) != after.get(key)
    }
    collection = await _collection()
    if collection is not None:
        await collection.update_one(
            {"campaign_id": record["campaign_id"], "request_id": record["request_id"]},
            {"$set": {
                "status": "completed", "after": after, "changes": changes,
                "completed_at": now,
            }},
        )
        record = await collection.find_one({
            "campaign_id": record["campaign_id"], "request_id": record["request_id"],
        })
    else:
        record.update({
            "status": "completed", "after": after, "changes": changes,
            "completed_at": now,
        })
    return record


async def _discard(record: dict) -> None:
    """Remove a mutation rejected before the backend changed campaign truth."""
    collection = await _collection()
    query = {
        "campaign_id": record["campaign_id"], "request_id": record["request_id"],
        "status": "pending",
    }
    if collection is not None:
        await collection.delete_one(query)
        return
    key = (record["campaign_id"], record["request_id"])
    _mem_requests.pop(key, None)
    rows = _mem_revisions.get(record["campaign_id"], [])
    _mem_revisions[record["campaign_id"]] = [
        item for item in rows if item.get("request_id") != record["request_id"]
    ]


async def update_campaign_config(
    campaign_id: str, *, actor: dict, expected_revision: int,
    request_id: str, patch: dict, note: str = "",
) -> dict:
    from tools.order_api import fetch_order, update_order

    clean_request_id = str(request_id or "").strip()
    if len(clean_request_id) < 8 or len(clean_request_id) > 128:
        raise ConfigValidationError("request_id must contain 8 to 128 characters")
    async with _lock(campaign_id):
        existing = await _find_request(campaign_id, clean_request_id)
        if existing and existing.get("status") == "completed":
            return _public(existing)

        current = await fetch_order(campaign_id)
        history = await _history(campaign_id)
        current_revision = history[0]["revision"] if history else 0
        if int(expected_revision) != int(current_revision):
            raise ConfigConflict(
                f"expected revision {expected_revision}, current revision is {current_revision}"
            )
        clean_patch = _normalize_patch(patch, current)
        changed_patch = {
            key: value for key, value in clean_patch.items()
            if current.get(key) != value
        }
        if not changed_patch:
            raise ConfigValidationError("config contains no changes")

        record = existing or await _insert({
            "campaign_id": campaign_id,
            "revision": current_revision + 1,
            "request_id": clean_request_id,
            "status": "pending",
            "patch": changed_patch,
            "before": _snapshot(current),
            "note": str(note or "").strip()[:500],
            "actor": {
                "user_id": actor.get("user_id"),
                "anonymous_id": None if actor.get("user_id") else actor.get("anonymous_id"),
            },
            "created_at": _now(),
        })
        if existing and all(current.get(key) == value for key, value in record["patch"].items()):
            return _public(await _complete(record, _snapshot(current)))
        try:
            updated = await update_order(campaign_id, record["patch"])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                await _discard(record)
                try:
                    payload = exc.response.json()
                except ValueError:
                    payload = {}
                raise ConfigValidationError(
                    str(payload.get("error") or "campaign config was rejected")
                ) from exc
            raise
        return _public(await _complete(record, _snapshot(updated)))
