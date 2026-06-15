"""
MongoDB-backed session store using motor (async driver).
Falls back to in-memory dict when MongoDB is not available (local dev).
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from config import config

# ── State ─────────────────────────────────────────────────────────────────────
_client: AsyncIOMotorClient | None = None
_sessions_col = None
_logs_col = None
_mongo_ok: bool | None = None   # None = not tested yet

# In-memory fallback
_mem: dict[str, dict] = {}       # session_id → session doc
_mem_logs: list = []


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _default_session(sid: str) -> dict:
    return {
        "_id": sid,
        "history": [],
        "form_state": {},
        "current_step": -1,
        "created_order_ids": [],
        "created_at": _now(),
        "updated_at": _now(),
    }


async def _ensure_mongo() -> bool:
    """Try to connect. Returns True if MongoDB available, False otherwise."""
    global _client, _sessions_col, _logs_col, _mongo_ok
    if _mongo_ok is not None:
        return _mongo_ok
    try:
        _client = AsyncIOMotorClient(
            config.MONGODB_URI,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            socketTimeoutMS=5000,
        )
        await asyncio.wait_for(_client.admin.command("ping"), timeout=4.0)
        _db = _client[config.MONGODB_DB]
        _sessions_col = _db["agent_sessions"]
        _logs_col = _db["agent_logs"]
        _mongo_ok = True
        print(f"[session] MongoDB OK: {config.MONGODB_URI}")
    except Exception as e:
        _mongo_ok = False
        print(f"[session] MongoDB unavailable - using in-memory. ({e})")
    return _mongo_ok


# ── Public API ────────────────────────────────────────────────────────────────

async def get_or_create_session(session_id: str) -> dict:
    if await _ensure_mongo():
        doc = await _sessions_col.find_one({"_id": session_id})
        if not doc:
            doc = _default_session(session_id)
            await _sessions_col.insert_one(doc)
        return doc
    else:
        if session_id not in _mem:
            _mem[session_id] = _default_session(session_id)
        return _mem[session_id]


async def update_form_state(session_id: str, key: str, data) -> None:
    if await _ensure_mongo():
        await _sessions_col.update_one(
            {"_id": session_id},
            {"$set": {f"form_state.{key}": data, "updated_at": _now()}},
            upsert=True,
        )
    else:
        s = _mem.setdefault(session_id, _default_session(session_id))
        s["form_state"][key] = data
        s["updated_at"] = _now()


async def update_order_ids(session_id: str, order_ids: list) -> None:
    if await _ensure_mongo():
        await _sessions_col.update_one(
            {"_id": session_id},
            {"$set": {"created_order_ids": order_ids, "updated_at": _now()}},
            upsert=True,
        )
    else:
        s = _mem.setdefault(session_id, _default_session(session_id))
        s["created_order_ids"] = order_ids


async def add_message(session_id: str, role: str, content: str) -> None:
    msg = {"role": role, "content": content, "ts": _now().isoformat()}
    if await _ensure_mongo():
        await _sessions_col.update_one(
            {"_id": session_id},
            {"$push": {"history": msg}, "$set": {"updated_at": _now()}},
            upsert=True,
        )
        doc = await _sessions_col.find_one({"_id": session_id}, {"history": 1})
        if doc and len(doc.get("history", [])) > config.CONTEXT_WINDOW:
            trimmed = doc["history"][-config.CONTEXT_WINDOW:]
            await _sessions_col.update_one({"_id": session_id}, {"$set": {"history": trimmed}})
    else:
        s = _mem.setdefault(session_id, _default_session(session_id))
        s["history"].append(msg)
        if len(s["history"]) > config.CONTEXT_WINDOW:
            s["history"] = s["history"][-config.CONTEXT_WINDOW:]


async def get_history(session_id: str) -> list:
    if await _ensure_mongo():
        doc = await _sessions_col.find_one({"_id": session_id}, {"history": 1})
        if not doc:
            return []
        return [{"role": m["role"], "content": m["content"]} for m in doc.get("history", [])]
    else:
        s = _mem.get(session_id, _default_session(session_id))
        return [{"role": m["role"], "content": m["content"]} for m in s.get("history", [])]


async def log_event(session_id: str, event_type: str, data: dict) -> None:
    entry = {"session_id": session_id, "type": event_type, "data": data, "ts": _now()}
    if await _ensure_mongo():
        try:
            await _logs_col.insert_one(entry)
        except Exception:
            pass  # Non-critical — never crash on log failure
    else:
        _mem_logs.append(entry)
        if len(_mem_logs) > 500:
            _mem_logs.pop(0)
