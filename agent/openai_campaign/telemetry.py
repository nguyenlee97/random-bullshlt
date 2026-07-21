"""Structured telemetry helpers for the independent OpenAI campaign engine."""
from __future__ import annotations

from typing import Any

from agent_logger import alog


async def record_decision(
    session_id: str, *, decision: Any, duration_ms: int,
) -> None:
    payload = decision.model_dump(mode="json")
    await alog(session_id, "openai_turn_decision", {
        "duration_ms": duration_ms,
        "turn_type": payload.get("turn_type"),
        "workflow_action": payload.get("workflow_action"),
        "faq_scope": payload.get("faq_scope"),
        "confidence": payload.get("confidence"),
        "would_mutate_workspace": payload.get("would_mutate_workspace"),
        "subrequests": payload.get("subrequests", []),
    })


async def record_completion(
    session_id: str,
    *,
    duration_ms: int,
    tool_names: list[str],
    response_id: str | None,
    output_chars: int,
    proposal_created: bool,
) -> None:
    await alog(session_id, "openai_turn_complete", {
        "duration_ms": duration_ms,
        "tools": tool_names,
        "response_id": response_id,
        "output_chars": output_chars,
        "proposal_created": proposal_created,
    })
