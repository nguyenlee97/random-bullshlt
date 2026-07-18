"""Bounded time-based context sessions for the permanent Zalo OA thread."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
import uuid

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import config


_mem_sessions: dict[str, dict] = {}
_mem_lock = asyncio.Lock()
_summary_worker_id = f"zalo-summary-{uuid.uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def estimate_tokens(value: str) -> int:
    """Conservative local estimate that works for Vietnamese and JSON text."""
    text = str(value or "")
    if not text:
        return 0
    words = len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))
    return max(1, max((len(text) + 2) // 3, words))


def truncate_tokens(value: str, limit: int) -> str:
    text = str(value or "")
    if estimate_tokens(text) <= limit:
        return text
    # Character slicing is deterministic and avoids a remote tokenizer call.
    return text[-max(1, limit * 3):]


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def _collection():
    from zalo_channel import _collections
    collections = await _collections()
    return collections["chat_sessions"] if collections else None


def _public(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    value = deepcopy(doc)
    value.pop("_id", None)
    return value


def _must_roll(doc: dict, now: datetime) -> str | None:
    started = _aware(doc.get("started_at")) or now
    last = _aware(doc.get("last_activity_at")) or started
    if now >= started + timedelta(minutes=max(1, config.ZALO_CHAT_SESSION_MAX_MINUTES)):
        return "hard_limit"
    if now >= last + timedelta(minutes=max(1, config.ZALO_CHAT_SESSION_IDLE_MINUTES)):
        return "idle_timeout"
    return None


async def _latest_open(thread_id: str) -> dict | None:
    collection = await _collection()
    if collection is not None:
        return await collection.find_one({"thread_id": thread_id, "status": "open"})
    candidates = [
        item for item in _mem_sessions.values()
        if item.get("thread_id") == thread_id and item.get("status") == "open"
    ]
    return max(candidates, key=lambda item: item.get("sequence", 0), default=None)


async def _close(doc: dict, reason: str, now: datetime) -> dict:
    updates = {
        "status": "closed", "closed_at": now, "close_reason": reason,
        "summary_status": "queued", "updated_at": now,
    }
    collection = await _collection()
    if collection is not None:
        result = await collection.find_one_and_update(
            {"_id": doc["_id"], "status": "open"}, {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        return result or {**doc, **updates}
    doc.update(updates)
    return doc


async def _create(thread_id: str, now: datetime) -> dict:
    collection = await _collection()
    if collection is not None:
        latest = await collection.find_one(
            {"thread_id": thread_id}, sort=[("sequence", -1)], projection={"sequence": 1},
        )
        sequence = int((latest or {}).get("sequence", 0)) + 1
    else:
        sequence = max([
            int(item.get("sequence", 0)) for item in _mem_sessions.values()
            if item.get("thread_id") == thread_id
        ] or [0]) + 1
    session_id = f"zcs_{uuid.uuid4().hex}"
    doc = {
        "_id": session_id, "chat_session_id": session_id,
        "thread_id": thread_id, "sequence": sequence, "status": "open",
        "started_at": now, "last_activity_at": now,
        "expires_at": now + timedelta(minutes=max(1, config.ZALO_CHAT_SESSION_MAX_MINUTES)),
        "closed_at": None, "close_reason": None, "messages": [],
        "message_count": 0, "token_estimate": 0,
        "summary": None, "summary_up_to_seq": 0, "summary_status": "idle",
        "summary_attempts": 0, "summary_lease_owner": None,
        "summary_lease_expires_at": None, "summary_error": None,
        "created_at": now, "updated_at": now,
    }
    if collection is not None:
        try:
            await collection.insert_one(doc)
        except DuplicateKeyError:
            winner = await _latest_open(thread_id)
            if winner:
                return winner
            raise
    else:
        _mem_sessions[session_id] = doc
    return doc


async def get_or_roll_chat_session(
    thread: dict, *, now: datetime | None = None,
) -> tuple[dict, bool, dict | None]:
    """Return one open session, atomically rolling an expired session."""
    current_time = now or _now()
    async with _mem_lock:
        current = await _latest_open(thread["thread_id"])
        previous = None
        rolled = False
        if current:
            reason = _must_roll(current, current_time)
            if not reason:
                return _public(current), False, None
            previous = await _close(current, reason, current_time)
            rolled = True
        created = await _create(thread["thread_id"], current_time)
        return _public(created), rolled, _public(previous)


async def append_chat_message(
    chat_session_id: str, role: str, content: str, *, now: datetime | None = None,
) -> dict:
    current_time = now or _now()
    safe_role = "assistant" if role == "assistant" else "user"
    safe_content = truncate_tokens(content, config.ZALO_CONTEXT_MAX_MESSAGE_TOKENS)
    token_count = estimate_tokens(safe_content)
    collection = await _collection()
    if collection is not None:
        doc = await collection.find_one({"_id": chat_session_id})
        if not doc:
            raise KeyError("Zalo chat session not found")
        seq = int(doc.get("message_count", 0)) + 1
        message = {"seq": seq, "role": safe_role, "content": safe_content,
                   "created_at": current_time, "token_estimate": token_count}
        unsummarized_messages = seq - int(doc.get("summary_up_to_seq", 0))
        unsummarized_tokens = sum(
            int(item.get("token_estimate", 0)) for item in doc.get("messages", [])
            if int(item.get("seq", 0)) > int(doc.get("summary_up_to_seq", 0))
        ) + token_count
        update = {"last_activity_at": current_time, "updated_at": current_time}
        if (unsummarized_messages >= config.ZALO_SUMMARY_MESSAGE_INTERVAL
                or unsummarized_tokens >= config.ZALO_SUMMARY_TOKEN_INTERVAL):
            update["summary_status"] = "queued"
        result = await collection.find_one_and_update(
            {"_id": chat_session_id},
            {"$push": {"messages": message}, "$inc": {
                "message_count": 1, "token_estimate": token_count,
            }, "$set": update}, return_document=ReturnDocument.AFTER,
        )
        return _public(result)
    doc = _mem_sessions[chat_session_id]
    seq = int(doc.get("message_count", 0)) + 1
    doc["messages"].append({"seq": seq, "role": safe_role, "content": safe_content,
                            "created_at": current_time, "token_estimate": token_count})
    doc["message_count"] = seq
    doc["token_estimate"] = int(doc.get("token_estimate", 0)) + token_count
    doc["last_activity_at"] = current_time
    doc["updated_at"] = current_time
    unsummarized = [item for item in doc["messages"] if item["seq"] > doc.get("summary_up_to_seq", 0)]
    if (len(unsummarized) >= config.ZALO_SUMMARY_MESSAGE_INTERVAL
            or sum(item["token_estimate"] for item in unsummarized) >= config.ZALO_SUMMARY_TOKEN_INTERVAL):
        doc["summary_status"] = "queued"
    return _public(doc)


async def build_context(thread_id: str, chat_session: dict) -> tuple[list[dict], dict | None]:
    messages = list(chat_session.get("messages") or [])[-config.ZALO_CONTEXT_MAX_MESSAGES:]
    previous = await latest_completed_summary(thread_id, before_sequence=chat_session.get("sequence"))
    # Reserve room for instructions, strict tool schemas, response bookkeeping,
    # and the bridge summary so the configured cap applies to the whole request.
    fixed_reserve = 6000 + estimate_tokens(str(previous or {}))
    budget = max(1000, config.ZALO_CONTEXT_MAX_INPUT_TOKENS - fixed_reserve)
    selected: list[dict] = []
    used = 0
    for item in reversed(messages):
        cost = int(item.get("token_estimate") or estimate_tokens(item.get("content", "")))
        if selected and used + cost > budget:
            break
        selected.append({"role": item.get("role"), "content": item.get("content", "")})
        used += cost
    selected.reverse()
    return selected, previous


async def latest_completed_summary(thread_id: str, before_sequence: int | None = None) -> dict | None:
    query = {"thread_id": thread_id, "summary": {"$ne": None}}
    if before_sequence is not None:
        query["sequence"] = {"$lt": before_sequence}
    collection = await _collection()
    if collection is not None:
        doc = await collection.find_one(query, sort=[("sequence", -1)])
    else:
        docs = [item for item in _mem_sessions.values() if item.get("thread_id") == thread_id
                and item.get("summary") and (before_sequence is None or item.get("sequence", 0) < before_sequence)]
        doc = max(docs, key=lambda item: item.get("sequence", 0), default=None)
    return deepcopy((doc or {}).get("summary")) or None


async def search_memory(thread_id: str, query: str, limit: int = 3) -> list[dict]:
    terms = set(re.findall(r"\w+", str(query or "").lower(), flags=re.UNICODE))
    collection = await _collection()
    if collection is not None:
        docs = await collection.find({"thread_id": thread_id, "summary": {"$ne": None}}).sort("sequence", -1).to_list(length=20)
    else:
        docs = sorted([item for item in _mem_sessions.values() if item.get("thread_id") == thread_id and item.get("summary")], key=lambda item: item.get("sequence", 0), reverse=True)[:20]
    scored = []
    for doc in docs:
        text = str(doc.get("summary") or "").lower()
        score = sum(1 for term in terms if term in text)
        if score or not terms:
            scored.append((score, doc))
    scored.sort(key=lambda pair: (pair[0], pair[1].get("sequence", 0)), reverse=True)
    return [{"sequence": doc.get("sequence"), "summary": deepcopy(doc.get("summary"))} for _, doc in scored[:limit]]


async def process_summary_once() -> bool:
    collection = await _collection()
    now = _now()
    if collection is not None:
        doc = await collection.find_one_and_update(
            {"$or": [
                {"summary_status": "queued"},
                {"summary_status": "processing", "summary_lease_expires_at": {"$lt": now}},
            ]},
            {"$set": {"summary_status": "processing", "summary_lease_owner": _summary_worker_id,
                      "summary_lease_expires_at": now + timedelta(seconds=120), "updated_at": now},
             "$inc": {"summary_attempts": 1}},
            sort=[("last_activity_at", 1)], return_document=ReturnDocument.AFTER,
        )
    else:
        doc = next((item for item in sorted(_mem_sessions.values(), key=lambda value: value.get("last_activity_at", now)) if item.get("summary_status") == "queued"), None)
        if doc:
            doc["summary_status"] = "processing"
            doc["summary_attempts"] = int(doc.get("summary_attempts", 0)) + 1
    if not doc:
        return False
    try:
        from zalo_openai import summarize_zalo_session
        summary = await summarize_zalo_session(
            previous_summary=doc.get("summary"), messages=doc.get("messages") or [],
            thread_id=doc["thread_id"],
        )
        up_to = max([int(item.get("seq", 0)) for item in doc.get("messages", [])] or [0])
        updates = {"summary": summary, "summary_up_to_seq": up_to,
                   "summary_status": "idle" if doc.get("status") == "open" else "completed",
                   "summary_lease_owner": None, "summary_lease_expires_at": None,
                   "summary_error": None, "updated_at": _now()}
    except Exception as exc:
        updates = {"summary_status": "queued" if int(doc.get("summary_attempts", 0)) < 3 else "failed",
                   "summary_lease_owner": None, "summary_lease_expires_at": None,
                   "summary_error": str(exc)[:500], "updated_at": _now()}
    if collection is not None:
        await collection.update_one({"_id": doc["_id"], "summary_lease_owner": _summary_worker_id}, {"$set": updates})
    else:
        doc.update(updates)
    return True


def reset_zalo_sessions_for_test() -> None:
    _mem_sessions.clear()
