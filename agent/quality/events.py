"""Best-effort quality event and interaction capture."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import time
from typing import Any

from config import config
from metrics import QUALITY_EVENT_WRITES
from quality.models import QUALITY_EVENT_TYPES
from quality.store import expires, insert_event, insert_interaction, now
from quality.versioning import get_version_manifest
from request_context import get_request_id
from security import redact_pii


MAX_EVENT_BYTES = 16 * 1024
_BACKGROUND_TASKS: set[asyncio.Task] = set()
_BACKGROUND_TASK_SESSIONS: dict[asyncio.Task, str | None] = {}


def _forget_background_task(task: asyncio.Task) -> None:
    _BACKGROUND_TASKS.discard(task)
    _BACKGROUND_TASK_SESSIONS.pop(task, None)


def _track_background_task(task: asyncio.Task, session_id: str | None) -> None:
    _BACKGROUND_TASKS.add(task)
    _BACKGROUND_TASK_SESSIONS[task] = session_id
    task.add_done_callback(_forget_background_task)


def _bounded_payload(payload: dict) -> dict:
    safe = redact_pii(payload)
    encoded = json.dumps(safe, ensure_ascii=False, default=str)
    if len(encoded.encode("utf-8")) <= MAX_EVENT_BYTES:
        return safe
    return {
        "truncated": True,
        "preview": encoded[:4000],
        "original_bytes": len(encoded.encode("utf-8")),
    }


async def emit_quality_event(
    event_type: str,
    *,
    session_id: str | None = None,
    conversation_id: str | None = None,
    run_id: str | None = None,
    surface: str,
    payload: dict | None = None,
    request_id: str | None = None,
    model: str | None = None,
    engine: str | None = None,
    approval_policy: str | None = None,
) -> dict | None:
    if not config.QUALITY_DATA_ENABLED:
        return None
    if event_type not in QUALITY_EVENT_TYPES:
        raise ValueError(f"unsupported quality event type: {event_type}")
    doc = {
        "schema_version": "quality-event-v1",
        "event_type": event_type,
        "request_id": request_id or get_request_id(),
        "conversation_id": conversation_id,
        "session_id": session_id,
        "run_id": run_id,
        "surface": surface,
        "payload": _bounded_payload(payload or {}),
        "version_manifest": get_version_manifest(
            model=model, engine=engine, approval_policy=approval_policy
        ),
        "created_at": now(),
        "expires_at": expires(config.QUALITY_EVENT_RETENTION_DAYS),
    }
    try:
        result = await asyncio.wait_for(
            insert_event(doc), timeout=config.QUALITY_EVENT_TIMEOUT_MS / 1000
        )
    except Exception as exc:
        QUALITY_EVENT_WRITES.labels(event_type=event_type, outcome="error").inc()
        print(f"[quality] event write failed: {event_type}: {type(exc).__name__}")
        return None
    QUALITY_EVENT_WRITES.labels(event_type=event_type, outcome="ok").inc()
    return result


def enqueue_quality_event(event_type: str, **kwargs) -> None:
    """Write optional event evidence outside the response critical path."""
    if not config.QUALITY_DATA_ENABLED:
        return
    task = asyncio.create_task(emit_quality_event(event_type, **kwargs))
    _track_background_task(task, kwargs.get("session_id"))


def _response_meta(response: Any) -> dict:
    raw = getattr(response, "meta", None)
    if hasattr(raw, "model_dump"):
        return raw.model_dump()
    return dict(raw or {})


async def _record_chat_interaction(
    *,
    session_id: str,
    step: int,
    response: Any,
    started_at: float,
    workspace_revision_before: int | None,
    guard_summary: dict | None,
) -> dict | None:
    if not config.QUALITY_DATA_ENABLED:
        return None
    meta = _response_meta(response)
    request_id = get_request_id()
    conversation_id = None
    try:
        from identity import conversation_record_for_session
        conversation = await conversation_record_for_session(session_id)
        conversation_id = (conversation or {}).get("conversation_id")
    except Exception:
        pass

    workspace_revision_after = workspace_revision_before
    try:
        from workspace.service import get_workspace
        workspace_revision_after = (await get_workspace(session_id)).get("revision")
    except Exception:
        pass

    tool = meta.get("tool")
    outcome = (
        "rejected_by_guardrail" if tool == "prompt_guard"
        else "provider_failed" if tool in {"error", "agent_unavailable"}
        else "succeeded"
    )
    model = meta.get("model")
    engine = (
        "openai" if model and str(model).lower().startswith(("gpt-", "o1", "o3", "o4"))
        else "greennode" if model and model != "none"
        else None
    )
    now_value = now()
    doc = {
        "schema_version": "quality-v1",
        "request_id": request_id,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "run_id": None,
        "task_id": None,
        "surface": "chat",
        "step": step,
        "started_at": datetime.fromtimestamp(started_at, timezone.utc),
        "completed_at": now_value,
        "duration_ms": max(0, round((time.time() - started_at) * 1000)),
        "outcome": outcome,
        "response_kind": tool or "text",
        "workspace_revision_before": workspace_revision_before,
        "workspace_revision_after": workspace_revision_after,
        "mutated_workspace": bool(
            workspace_revision_after is not None
            and workspace_revision_before is not None
            and workspace_revision_after != workspace_revision_before
        ),
        "proposal_created": any(
            item.get("type") == "workspace_proposal"
            for item in (getattr(response, "blocks", None) or [])
        ),
        "review_required": False,
        "fallback_level": None,
        "tool_summary": {
            "called": [tool] if tool else [],
            "failed": [],
            "count": 1 if tool else 0,
        },
        "guard_summary": guard_summary or {
            "decision": "allow", "finding_count": 0,
            "policy_version": config.GUARDRAIL_POLICY_VERSION,
        },
        "version_manifest": get_version_manifest(model=model, engine=engine),
        "created_at": now_value,
        "expires_at": expires(config.QUALITY_INTERACTION_RETENTION_DAYS),
    }
    return await insert_interaction(doc)


async def record_chat_interaction(
    *,
    session_id: str,
    step: int,
    response: Any,
    started_at: float,
    workspace_revision_before: int | None,
    guard_summary: dict | None,
) -> dict | None:
    """Capture one interaction without allowing telemetry to delay the user flow."""
    if not config.QUALITY_DATA_ENABLED:
        return None
    try:
        result = await asyncio.wait_for(
            _record_chat_interaction(
                session_id=session_id,
                step=step,
                response=response,
                started_at=started_at,
                workspace_revision_before=workspace_revision_before,
                guard_summary=guard_summary,
            ),
            timeout=config.QUALITY_EVENT_TIMEOUT_MS / 1000,
        )
    except Exception as exc:
        QUALITY_EVENT_WRITES.labels(
            event_type="interaction_completed", outcome="error"
        ).inc()
        print(f"[quality] interaction write failed: {type(exc).__name__}")
        return None
    QUALITY_EVENT_WRITES.labels(
        event_type="interaction_completed", outcome="ok"
    ).inc()
    return result


def enqueue_chat_interaction(**kwargs) -> None:
    """Start best-effort capture after the response is ready to return."""
    if not config.QUALITY_DATA_ENABLED:
        return
    task = asyncio.create_task(record_chat_interaction(**kwargs))
    _track_background_task(task, kwargs.get("session_id"))


async def drain_session_quality_tasks(session_id: str) -> None:
    """Finish pending writes before deleting a conversation's quality data."""
    tasks = [
        task
        for task, task_session_id in tuple(_BACKGROUND_TASK_SESSIONS.items())
        if task_session_id == session_id
    ]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
