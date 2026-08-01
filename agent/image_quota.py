"""Durable per-actor GPT Image quota and auditable generation jobs."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from config import config
from pymongo import ReturnDocument


DAILY_LIMIT = max(1, config.OPENAI_IMAGE_DAILY_LIMIT)
# Vietnam has used UTC+07:00 without DST since 1975. A fixed offset keeps the
# product-day boundary portable on minimal Windows/Linux images without tzdata.
QUOTA_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")
_lock = asyncio.Lock()
_mem_jobs: dict[str, dict] = {}
_mem_ledgers: dict[str, dict] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def quota_day(now: datetime | None = None) -> str:
    value = now or _now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(QUOTA_TIMEZONE).date().isoformat()


def actor_keys(actor: dict) -> tuple[str, list[str]]:
    user_id = str(actor.get("user_id") or actor.get("owner_user_id") or "").strip()
    anonymous_ids = [
        str(value).strip() for value in (
            actor.get("anonymous_id"), actor.get("claimed_from_anonymous_id"),
        ) if value
    ]
    anonymous_ids = list(dict.fromkeys(anonymous_ids))
    if user_id:
        return f"user:{user_id}", [f"anon:{value}" for value in anonymous_ids]
    if anonymous_ids:
        return f"anon:{anonymous_ids[0]}", []
    raise PermissionError("image generation requires an account or anonymous identity")


async def actor_for_session(session_id: str) -> dict:
    from identity import conversation_record_for_session
    record = await conversation_record_for_session(session_id)
    if not record:
        # Evaluator/legacy sessions remain isolated rather than sharing quota.
        return {"anonymous_id": f"legacy-session:{session_id}"}
    return {
        "user_id": record.get("owner_user_id"),
        "anonymous_id": record.get("anonymous_id") or record.get("identity_id"),
        "claimed_from_anonymous_id": record.get("claimed_from_anonymous_id"),
    }


async def _collections():
    from session import _ensure_mongo
    if not await _ensure_mongo():
        return None, None
    import session as session_store
    db = session_store._client[config.MONGODB_DB]
    return db["image_generation_jobs"], db["image_daily_quotas"]


async def ensure_indexes() -> None:
    jobs, ledgers = await _collections()
    if jobs is None:
        return
    await jobs.create_index([("actor_key", 1), ("day", 1), ("created_at", -1)], name="image_jobs_actor_day")
    await jobs.create_index(
        [("session_id", 1), ("actor_key", 1), ("created_at", 1)],
        name="image_jobs_session_gallery",
    )
    await jobs.create_index([("status", 1), ("updated_at", 1)], name="image_jobs_reconcile")
    await ledgers.create_index([("day", 1), ("actor_key", 1)], unique=True, name="image_quota_actor_day")


def _ledger_id(actor_key: str, day: str) -> str:
    return f"{day}:{actor_key}"


async def _linked_charged(ledgers, linked_keys: list[str], day: str) -> int:
    if not linked_keys:
        return 0
    if ledgers is None:
        return sum(int(_mem_ledgers.get(_ledger_id(key, day), {}).get("charged", 0)) for key in linked_keys)
    docs = await ledgers.find({"_id": {"$in": [_ledger_id(key, day) for key in linked_keys]}}).to_list(length=100)
    return sum(int(doc.get("charged", 0)) for doc in docs)


async def reserve(actor: dict, job_id: str, *, session_id: str, metadata: dict | None = None) -> dict:
    """Atomically reserve one daily output before calling the paid API."""
    actor_key, linked_keys = actor_keys(actor)
    day = quota_day()
    now = _now()
    jobs, ledgers = await _collections()

    if jobs is None:
        async with _lock:
            existing = _mem_jobs.get(job_id)
            if existing:
                return {**deepcopy(existing), "duplicate": True}
            linked = await _linked_charged(None, linked_keys, day)
            key = _ledger_id(actor_key, day)
            ledger = _mem_ledgers.setdefault(key, {
                "_id": key, "actor_key": actor_key, "day": day,
                "charged": 0, "reserved": 0, "succeeded": 0,
            })
            if int(ledger["charged"]) + linked >= DAILY_LIMIT:
                return {"ok": False, "status": "quota_exhausted", "remaining": 0, "day": day}
            ledger["charged"] += 1
            ledger["reserved"] += 1
            job = {
                "_id": job_id, "job_id": job_id, "actor_key": actor_key,
                "linked_actor_keys": linked_keys, "day": day, "session_id": session_id,
                "status": "reserved", "metadata": deepcopy(metadata or {}),
                "created_at": now, "updated_at": now,
            }
            _mem_jobs[job_id] = job
            return {**deepcopy(job), "ok": True, "remaining": DAILY_LIMIT - ledger["charged"] - linked}

    existing = await jobs.find_one({"_id": job_id})
    if existing:
        existing.pop("_id", None)
        return {**existing, "duplicate": True, "ok": existing.get("status") != "quota_exhausted"}

    linked = await _linked_charged(ledgers, linked_keys, day)
    allowed_primary = max(0, DAILY_LIMIT - linked)
    key = _ledger_id(actor_key, day)
    await ledgers.update_one({"_id": key}, {"$setOnInsert": {
        "actor_key": actor_key, "day": day, "charged": 0,
        "reserved": 0, "succeeded": 0, "created_at": now,
    }}, upsert=True)
    ledger = await ledgers.find_one_and_update(
        {"_id": key, "charged": {"$lt": allowed_primary}},
        {"$inc": {"charged": 1, "reserved": 1}, "$set": {"updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not ledger:
        return {"ok": False, "status": "quota_exhausted", "remaining": 0, "day": day}
    job = {
        "_id": job_id, "job_id": job_id, "actor_key": actor_key,
        "linked_actor_keys": linked_keys, "day": day, "session_id": session_id,
        "status": "reserved", "metadata": deepcopy(metadata or {}),
        "created_at": now, "updated_at": now,
    }
    try:
        await jobs.insert_one(job)
    except Exception:
        existing = await jobs.find_one({"_id": job_id})
        if not existing:
            await ledgers.update_one({"_id": key}, {"$inc": {"charged": -1, "reserved": -1}})
            raise
        await ledgers.update_one({"_id": key}, {"$inc": {"charged": -1, "reserved": -1}})
        existing.pop("_id", None)
        return {**existing, "duplicate": True, "ok": True}
    job.pop("_id", None)
    return {**job, "ok": True, "remaining": max(0, DAILY_LIMIT - int(ledger["charged"]) - linked)}


async def _transition(job_id: str, status: str, *, release_charge: bool = False, result: dict | None = None) -> dict | None:
    now = _now()
    jobs, ledgers = await _collections()
    if jobs is None:
        async with _lock:
            job = _mem_jobs.get(job_id)
            if not job or job.get("status") not in {"reserved", "ambiguous"}:
                return deepcopy(job) if job else None
            ledger = _mem_ledgers[_ledger_id(job["actor_key"], job["day"])]
            ledger["reserved"] = max(0, ledger["reserved"] - 1)
            if release_charge:
                ledger["charged"] = max(0, ledger["charged"] - 1)
            else:
                ledger["succeeded"] += 1
            job.update(status=status, result=deepcopy(result or {}), updated_at=now)
            return deepcopy(job)
    job = await jobs.find_one_and_update(
        {"_id": job_id, "status": {"$in": ["reserved", "ambiguous"]}},
        {"$set": {"status": status, "result": deepcopy(result or {}), "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not job:
        return None
    increments = {"reserved": -1, "charged": -1} if release_charge else {"reserved": -1, "succeeded": 1}
    await ledgers.update_one({"_id": _ledger_id(job["actor_key"], job["day"])}, {"$inc": increments, "$set": {"updated_at": now}})
    job.pop("_id", None)
    return job


async def succeed(job_id: str, result: dict | None = None) -> dict | None:
    return await _transition(job_id, "succeeded", result=result)


def _owner_keys(actor: dict) -> list[str]:
    primary, linked = actor_keys(actor)
    return list(dict.fromkeys([primary, *linked]))


def _public_job(job: dict) -> dict:
    value = deepcopy(job)
    value.pop("_id", None)
    value.pop("actor_key", None)
    value.pop("linked_actor_keys", None)
    return value


async def list_session_jobs(actor: dict, session_id: str, *, limit: int = 100) -> list[dict]:
    """Return only this actor's durable generated-image drafts for a conversation."""
    keys = _owner_keys(actor)
    jobs, _ = await _collections()
    if jobs is None:
        values = [
            _public_job(item) for item in _mem_jobs.values()
            if item.get("session_id") == session_id and item.get("actor_key") in keys
        ]
        return sorted(values, key=lambda item: item.get("created_at") or _now())[:limit]
    cursor = jobs.find({
        "session_id": session_id,
        "actor_key": {"$in": keys},
    }).sort("created_at", 1).limit(max(1, min(limit, 200)))
    return [_public_job(item) for item in await cursor.to_list(length=limit)]


async def get_session_job(actor: dict, session_id: str, job_id: str) -> dict:
    """Return one generated-image job after checking its conversation owner."""
    keys = _owner_keys(actor)
    jobs, _ = await _collections()
    if jobs is None:
        job = _mem_jobs.get(job_id)
        if not job or job.get("session_id") != session_id or job.get("actor_key") not in keys:
            raise KeyError("generated image job not found")
        return _public_job(job)
    job = await jobs.find_one({
        "_id": job_id,
        "session_id": session_id,
        "actor_key": {"$in": keys},
    })
    if not job:
        raise KeyError("generated image job not found")
    return _public_job(job)


async def merge_job_result(
    actor: dict,
    session_id: str,
    job_id: str,
    updates: dict,
) -> dict:
    """Owner-scoped update for crop/finalization metadata on a succeeded job."""
    keys = _owner_keys(actor)
    now = _now()
    jobs, _ = await _collections()
    if jobs is None:
        async with _lock:
            job = _mem_jobs.get(job_id)
            if not job or job.get("session_id") != session_id or job.get("actor_key") not in keys:
                raise KeyError("generated image job not found")
            if job.get("status") != "succeeded":
                raise ValueError("generated image is not ready")
            result = deepcopy(job.get("result") or {})
            result.update(deepcopy(updates))
            job.update(result=result, updated_at=now)
            return _public_job(job)
    job = await jobs.find_one_and_update(
        {
            "_id": job_id,
            "session_id": session_id,
            "actor_key": {"$in": keys},
            "status": "succeeded",
        },
        {"$set": {
            **{f"result.{key}": deepcopy(value) for key, value in updates.items()},
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not job:
        existing = await jobs.find_one({
            "_id": job_id, "session_id": session_id, "actor_key": {"$in": keys},
        })
        if existing:
            raise ValueError("generated image is not ready")
        raise KeyError("generated image job not found")
    return _public_job(job)


async def release(job_id: str, reason: str) -> dict | None:
    return await _transition(job_id, "released", release_charge=True, result={"reason": reason})


async def mark_ambiguous(job_id: str, reason: str) -> None:
    jobs, _ = await _collections()
    now = _now()
    if jobs is None:
        async with _lock:
            if job_id in _mem_jobs and _mem_jobs[job_id].get("status") == "reserved":
                _mem_jobs[job_id].update(status="ambiguous", result={"reason": reason}, updated_at=now)
        return
    await jobs.update_one({"_id": job_id, "status": "reserved"}, {"$set": {
        "status": "ambiguous", "result": {"reason": reason}, "updated_at": now,
    }})


async def status(actor: dict) -> dict:
    actor_key, linked_keys = actor_keys(actor)
    day = quota_day()
    _, ledgers = await _collections()
    linked = await _linked_charged(ledgers, linked_keys, day)
    key = _ledger_id(actor_key, day)
    if ledgers is None:
        ledger = deepcopy(_mem_ledgers.get(key, {}))
    else:
        ledger = await ledgers.find_one({"_id": key}) or {}
    charged = int(ledger.get("charged", 0)) + linked
    return {
        "remaining": max(0, DAILY_LIMIT - charged), "max": DAILY_LIMIT,
        "used": charged, "succeeded": int(ledger.get("succeeded", 0)),
        "reserved": int(ledger.get("reserved", 0)), "day": day,
        "timezone": "Asia/Ho_Chi_Minh", "actor_scope": "account" if actor_key.startswith("user:") else "anonymous",
    }
