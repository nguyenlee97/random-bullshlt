"""
MongoDB-backed session store using motor (async driver).
Falls back to in-memory dict when MongoDB is not available (local dev).
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from config import config
from security import redact_pii

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
        # Full text transcript for UI resume. ``history`` remains a short LLM
        # context window and may be trimmed independently.
        "display_history": [],
        "form_state": {},
        "current_step": -1,
        "confirmed_steps": [],
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
        # Connection strings commonly contain database credentials. Never emit
        # the URI into logs, traces, or deployment diagnostics.
        print("[session] MongoDB OK")
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
        # Merge defaults: docs created by upsert paths (e.g. set_pending_proposal
        # before any form submit) can lack keys like form_state — every consumer
        # gets the full shape. (Read-side only; stored doc unchanged.)
        return {**_default_session(session_id), **doc}
    else:
        if session_id not in _mem:
            _mem[session_id] = _default_session(session_id)
        return _mem[session_id]


async def update_form_state(
    session_id: str, key: str, data, *, sync_workspace: bool = True
) -> None:
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
    if sync_workspace:
        # Lazy import avoids a module cycle: workspace.service mirrors back to
        # this function with sync_workspace=False after its canonical commit.
        from workspace.service import sync_from_legacy
        await sync_from_legacy(session_id, key, data)


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


async def confirm_workflow_step(session_id: str, step: int) -> list[int]:
    """Persist an explicit operator checkpoint for cross-device resume."""
    if step < 0 or step > 6:
        raise ValueError("workflow step must be between 0 and 6")
    if await _ensure_mongo():
        await _sessions_col.update_one(
            {"_id": session_id},
            {
                "$addToSet": {"confirmed_steps": step},
                "$max": {"current_step": step},
                "$set": {"updated_at": _now()},
            },
            upsert=True,
        )
        doc = await _sessions_col.find_one(
            {"_id": session_id}, {"confirmed_steps": 1}
        )
        return sorted(set((doc or {}).get("confirmed_steps") or []))
    session = _mem.setdefault(session_id, _default_session(session_id))
    session["confirmed_steps"] = sorted(set([
        *(session.get("confirmed_steps") or []), step,
    ]))
    session["current_step"] = max(int(session.get("current_step", -1)), step)
    session["updated_at"] = _now()
    return session["confirmed_steps"]


async def add_message(session_id: str, role: str, content: str) -> None:
    msg = {"role": role, "content": content, "ts": _now().isoformat()}
    if await _ensure_mongo():
        await _sessions_col.update_one(
            {"_id": session_id},
            {
                "$push": {
                    "history": msg,
                    "display_history": {"$each": [msg], "$slice": -500},
                },
                "$set": {"updated_at": _now()},
            },
            upsert=True,
        )
        doc = await _sessions_col.find_one({"_id": session_id}, {"history": 1})
        if doc and len(doc.get("history", [])) > config.CONTEXT_WINDOW:
            trimmed = doc["history"][-config.CONTEXT_WINDOW:]
            await _sessions_col.update_one({"_id": session_id}, {"$set": {"history": trimmed}})
    else:
        s = _mem.setdefault(session_id, _default_session(session_id))
        s["history"].append(msg)
        s.setdefault("display_history", []).append(msg)
        s["display_history"] = s["display_history"][-500:]
        if len(s["history"]) > config.CONTEXT_WINDOW:
            s["history"] = s["history"][-config.CONTEXT_WINDOW:]
    # Conversation history is a read model; failure must never fail the chat.
    try:
        from identity import touch_conversation_for_session
        await touch_conversation_for_session(
            session_id, role=role, content=content,
        )
    except Exception:
        pass


async def get_history(session_id: str) -> list:
    if await _ensure_mongo():
        doc = await _sessions_col.find_one({"_id": session_id}, {"history": 1})
        if not doc:
            return []
        return [{"role": m["role"], "content": m["content"]} for m in doc.get("history", [])]
    else:
        s = _mem.get(session_id, _default_session(session_id))
        return [{"role": m["role"], "content": m["content"]} for m in s.get("history", [])]


async def get_display_history(session_id: str) -> list:
    """Return the durable UI transcript without exposing model-only metadata."""
    if await _ensure_mongo():
        doc = await _sessions_col.find_one(
            {"_id": session_id}, {"display_history": 1, "history": 1}
        )
    else:
        doc = _mem.get(session_id)
    if not doc:
        return []
    # Migration-safe fallback for sessions created before display_history.
    messages = doc.get("display_history") or doc.get("history") or []
    return [
        {
            "role": item.get("role", "assistant"),
            "content": item.get("content", ""),
            "timestamp": item.get("ts"),
        }
        for item in messages
        if item.get("content")
    ]


async def log_event(session_id: str, event_type: str, data: dict) -> None:
    entry = {
        "session_id": session_id,
        "type": event_type,
        "data": redact_pii(data),
        "ts": _now(),
    }
    if await _ensure_mongo():
        try:
            await _logs_col.insert_one(entry)
        except Exception:
            pass  # Non-critical — never crash on log failure
    else:
        _mem_logs.append(entry)
        if len(_mem_logs) > 500:
            _mem_logs.pop(0)


async def delete_session_data(session_id: str) -> dict[str, int]:
    """Delete conversational/agent artifacts for one session, but never orders.

    Campaign orders are business records owned by the Node backend and are
    intentionally outside this lifecycle operation.
    """
    from quality.events import drain_session_quality_tasks

    await drain_session_quality_tasks(session_id)
    deleted: dict[str, int] = {}
    if await _ensure_mongo():
        db = _client[config.MONGODB_DB]
        runs = await db["agent_runs"].find(
            {"session_id": session_id}, {"run_id": 1, "_id": 0}
        ).to_list(None)
        run_ids = [item.get("run_id") for item in runs if item.get("run_id")]
        workspaces = await db["campaign_workspaces"].find(
            {"session_id": session_id}, {"_id": 1}
        ).to_list(None)
        workspace_ids = [item.get("_id") for item in workspaces if item.get("_id")]
        filters = {
            "agent_sessions": {"_id": session_id},
            "agent_logs": {"session_id": session_id},
            "campaign_workspaces": {"session_id": session_id},
            "workspace_proposals": {"session_id": session_id},
            # New events carry session_id. The workspace_id branch also
            # removes events written before that metadata was added.
            "workspace_events": {"$or": [
                {"session_id": session_id},
                {"workspace_id": {"$in": workspace_ids}},
            ]},
            "creative_intel_jobs": {"session_id": session_id},
            "agent_runs": {"session_id": session_id},
            "agent_tasks": {"run_id": {"$in": run_ids}},
            "agent_run_events": {"run_id": {"$in": run_ids}},
            "agent_interactions": {"session_id": session_id},
            "agent_quality_events": {"session_id": session_id},
            "agent_feedback": {"target.session_id": session_id},
            "graph_checkpoints": {
                "thread_id": {"$in": [session_id, f"{session_id}:auto"]}
            },
            "checkpoint_writes": {"thread_id": {"$in": [session_id, f"{session_id}:auto"]}},
        }
        for collection, query in filters.items():
            result = await db[collection].delete_many(query)
            deleted[collection] = result.deleted_count
        return deleted

    _mem.pop(session_id, None)
    before = len(_mem_logs)
    _mem_logs[:] = [entry for entry in _mem_logs if entry.get("session_id") != session_id]
    deleted["agent_sessions"] = 1
    deleted["agent_logs"] = before - len(_mem_logs)

    # Clean the domain-specific in-memory fallbacks used by tests/local outage mode.
    from workspace import service as workspace_store
    workspace_store._mem_workspaces.pop(session_id, None)
    proposal_ids = [
        key for key, value in workspace_store._mem_proposals.items()
        if value.get("session_id") == session_id
    ]
    for key in proposal_ids:
        workspace_store._mem_proposals.pop(key, None)
    deleted["campaign_workspaces"] = 1
    deleted["workspace_proposals"] = len(proposal_ids)

    from creative_intel import service as creative_store
    creative_ids = [
        key for key, value in creative_store._mem.items()
        if value.get("session_id") == session_id
    ]
    for key in creative_ids:
        creative_store._mem.pop(key, None)
    deleted["creative_intel_jobs"] = len(creative_ids)

    from autopilot import service as autopilot_store
    run_ids = [
        key for key, value in autopilot_store._mem_runs.items()
        if value.get("session_id") == session_id
    ]
    task_ids = [
        key for key, value in autopilot_store._mem_tasks.items()
        if value.get("run_id") in run_ids
    ]
    for key in run_ids:
        autopilot_store._mem_runs.pop(key, None)
    for key in task_ids:
        autopilot_store._mem_tasks.pop(key, None)
    before_events = len(autopilot_store._mem_events)
    autopilot_store._mem_events[:] = [
        event for event in autopilot_store._mem_events
        if event.get("run_id") not in run_ids
    ]
    deleted["agent_runs"] = len(run_ids)
    deleted["agent_tasks"] = len(task_ids)
    deleted["agent_run_events"] = before_events - len(autopilot_store._mem_events)

    from quality.store import delete_quality_for_sessions
    deleted.update(await delete_quality_for_sessions([session_id]))
    return deleted


# ── Pending proposal storage ──────────────────────────────────────────────────

async def set_pending_proposal(session_id: str, changes: dict) -> None:
    """Store the last workspace_proposal changes so confirmation can apply them."""
    if await _ensure_mongo():
        await _sessions_col.update_one(
            {"_id": session_id},
            {"$set": {"pending_proposal": changes, "updated_at": _now()}},
            upsert=True,
        )
    else:
        s = _mem.setdefault(session_id, _default_session(session_id))
        s["pending_proposal"] = changes
        s["updated_at"] = _now()


async def get_pending_proposal(session_id: str) -> dict | None:
    """Retrieve the last pending workspace_proposal, or None."""
    if await _ensure_mongo():
        doc = await _sessions_col.find_one({"_id": session_id}, {"pending_proposal": 1})
        return (doc or {}).get("pending_proposal")
    else:
        return _mem.get(session_id, {}).get("pending_proposal")


async def clear_pending_proposal(session_id: str) -> None:
    """Clear the pending proposal after it's been applied or cancelled."""
    if await _ensure_mongo():
        await _sessions_col.update_one(
            {"_id": session_id},
            {"$unset": {"pending_proposal": ""}, "$set": {"updated_at": _now()}},
        )
    else:
        _mem.get(session_id, {}).pop("pending_proposal", None)
