"""Strict, ownership-scoped tools exposed to the Zalo conversational model."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import json
from typing import Any


REPORT_VIEWS = [
    "daily_ops", "awareness", "consideration", "conversion", "retention", "executive",
]


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


ZALO_TOOLS = [
    {"type": "function", "name": "list_campaigns",
     "description": "List campaigns owned by this Zalo account. Use when the user asks what campaigns exist or when a campaign reference is unclear.",
     "strict": True, "parameters": _schema({
         "status": {"type": "string", "enum": ["all", "active", "paused"]},
     }, ["status"])},
    {"type": "function", "name": "get_campaign_status",
     "description": "Fetch current status, objective, budget and dates for one owned campaign.",
     "strict": True, "parameters": _schema({
         "campaign_reference": {"type": "string", "description": "Campaign name, ID, ordinal reference, or contextual reference."},
     }, ["campaign_reference"])},
    {"type": "function", "name": "get_campaign_setup",
     "description": "Fetch existing setup including audience, targeting, placements and creative count. This does not edit it.",
     "strict": True, "parameters": _schema({
         "campaign_reference": {"type": "string"},
     }, ["campaign_reference"])},
    {"type": "function", "name": "get_campaign_report",
     "description": "Answer questions from the existing synthetic report module for one campaign and one of its six report views.",
     "strict": True, "parameters": _schema({
         "campaign_reference": {"type": "string"},
         "view": {"type": "string", "enum": REPORT_VIEWS},
         "question": {"type": "string"},
     }, ["campaign_reference", "view", "question"])},
    {"type": "function", "name": "get_campaign_live_view",
     "description": "Fetch live-view links and attempt a current ad screenshot for one owned campaign.",
     "strict": True, "parameters": _schema({
         "campaign_reference": {"type": "string"},
     }, ["campaign_reference"])},
    {"type": "function", "name": "get_autopilot_progress",
     "description": "Fetch progress for the current or referenced Campaign Autopilot run.",
     "strict": True, "parameters": _schema({
         "campaign_reference": {"type": ["string", "null"]},
     }, ["campaign_reference"])},
    {"type": "function", "name": "search_conversation_memory",
     "description": "Search compact summaries of older Zalo chat sessions when the user explicitly refers to an earlier discussion.",
     "strict": True, "parameters": _schema({
         "query": {"type": "string"},
     }, ["query"])},
    {"type": "function", "name": "prepare_pause_campaign",
     "description": "Prepare a pause proposal for an owned campaign. This never pauses immediately and always asks the user for explicit confirmation.",
     "strict": True, "parameters": _schema({
         "campaign_reference": {"type": "string"},
     }, ["campaign_reference"])},
    {"type": "function", "name": "prepare_resume_campaign",
     "description": "Prepare a resume proposal for an owned campaign. This never resumes immediately and always asks the user for explicit confirmation.",
     "strict": True, "parameters": _schema({
         "campaign_reference": {"type": "string"},
     }, ["campaign_reference"])},
    {"type": "function", "name": "begin_autopilot",
     "description": "Begin intake for a new campaign through existing Campaign Autopilot. Existing campaigns cannot be modified by this tool.",
     "strict": True, "parameters": _schema({
         "mode": {"type": "string", "enum": ["fully_automatic", "semi_automatic"]},
     }, ["mode"])},
    {"type": "function", "name": "submit_autopilot_brief",
     "description": "Validate a new-campaign brief and prepare it for explicit confirmation. Use only after the user chose an Autopilot mode.",
     "strict": True, "parameters": _schema({
         "brief_text": {"type": "string"},
     }, ["brief_text"])},
]


@dataclass
class ToolExecutionContext:
    thread: dict
    current_message: str
    history: list[dict]
    media_parts: list[dict] = field(default_factory=list)


def _safe_campaign(item: dict, index: int | None = None) -> dict:
    order = item.get("order") or {}
    value = {
        "campaign_id": item.get("campaign_id"), "brand": order.get("brand"),
        "status": order.get("status"), "objective": order.get("objective"),
    }
    if index is not None:
        value["index"] = index
    return value


async def _campaign_for_reference(ctx: ToolExecutionContext, reference: str) -> tuple[dict | None, dict | None]:
    from zalo_campaign_agent import owned_campaigns, resolve_campaign, _select_campaign
    campaigns = await owned_campaigns(ctx.thread)
    ref = str(reference or "").strip()
    folded = ref.lower()
    if folded.isdigit():
        index = int(folded) - 1
        selected = campaigns[index] if 0 <= index < len(campaigns) else None
        ambiguous = []
    else:
        selected, ambiguous = resolve_campaign(
            ref, campaigns, ctx.thread.get("active_campaign_id"),
            allow_context_fallback=True,
        )
    if selected:
        ctx.thread = await _select_campaign(ctx.thread, selected)
        return selected, None
    if ambiguous:
        return None, {"ok": False, "error": "ambiguous_campaign",
                      "message": "Ask the user which campaign they mean.",
                      "candidates": [_safe_campaign(item, index) for index, item in enumerate(ambiguous[:8], 1)]}
    return None, {"ok": False, "error": "campaign_not_found",
                  "message": "No owned campaign matches that reference. Ask for a name or ID."}


async def execute_zalo_tool(ctx: ToolExecutionContext, name: str, arguments: dict[str, Any]) -> dict:
    """Execute a model request inside the server-owned actor boundary."""
    from zalo_campaign_agent import (
        _answer_report, _extract_brief, _lifecycle_request, _live_response,
        _setup_text, _status_text, _update_thread, owned_campaigns, _now,
    )

    if name == "list_campaigns":
        campaigns = await owned_campaigns(ctx.thread)
        status = arguments.get("status", "all")
        if status == "active":
            campaigns = [item for item in campaigns if str((item.get("order") or {}).get("status", "")).lower() in {"active", "running", "live"}]
        elif status == "paused":
            campaigns = [item for item in campaigns if str((item.get("order") or {}).get("status", "")).lower() == "paused"]
        return {"ok": True, "status_filter": status,
                "campaigns": [_safe_campaign(item, index) for index, item in enumerate(campaigns[:8], 1)]}

    if name == "search_conversation_memory":
        from zalo_sessions import search_memory
        return {"ok": True, "matches": await search_memory(
            ctx.thread["thread_id"], str(arguments.get("query") or ""),
        )}

    if name == "get_autopilot_progress":
        campaign = None
        reference = arguments.get("campaign_reference")
        if reference:
            campaign, error = await _campaign_for_reference(ctx, reference)
            if error:
                return error
        session_id = campaign.get("session_id") if campaign else ctx.thread.get("active_campaign_session_id")
        if not session_id:
            return {"ok": False, "error": "autopilot_run_not_selected",
                    "message": "No current Autopilot run is selected."}
        from autopilot.service import get_latest_run
        run = await get_latest_run(session_id)
        if not run:
            return {"ok": False, "error": "autopilot_run_not_found"}
        tasks = run.get("tasks") or []
        return {"ok": True, "run": {"run_id": run.get("run_id"),
                "status": run.get("status"), "approval_policy": run.get("approval_policy"),
                "tasks": [{"key": item.get("key"), "title": item.get("title"),
                           "status": item.get("status")} for item in tasks]}}

    if name == "begin_autopilot":
        mode = arguments.get("mode")
        if mode not in {"fully_automatic", "semi_automatic"}:
            return {"ok": False, "error": "invalid_autopilot_mode"}
        ctx.thread = await _update_thread(ctx.thread, {"pending_action": {
            "kind": "collect_autopilot_brief", "mode": mode,
            "expires_at": _now() + timedelta(minutes=30),
        }})
        return {"ok": True, "mode": mode, "next": "Ask the user for brand, objective, budget in million VND, start/end dates, and creative message or notes."}

    if name == "submit_autopilot_brief":
        pending = ctx.thread.get("pending_action") or {}
        if pending.get("kind") != "collect_autopilot_brief":
            return {"ok": False, "error": "autopilot_mode_required",
                    "message": "Ask the user to choose fully automatic or semi automatic first."}
        brief, errors = await _extract_brief(
            str(arguments.get("brief_text") or ctx.current_message),
            history=ctx.history, thread_id=ctx.thread["thread_id"],
        )
        if errors:
            return {"ok": False, "error": "incomplete_brief", "missing_or_invalid": errors}
        ctx.thread = await _update_thread(ctx.thread, {"pending_action": {
            "kind": "confirm_autopilot_brief", "mode": pending["mode"],
            "brief": brief, "expires_at": _now() + timedelta(minutes=15),
        }})
        return {"ok": True, "brief": brief,
                "requires_confirmation": True,
                "confirmation_instruction": "Ask the user to reply exactly Xác nhận or Hủy."}

    campaign, error = await _campaign_for_reference(
        ctx, str(arguments.get("campaign_reference") or ""),
    )
    if error:
        return error

    if name == "get_campaign_status":
        return {"ok": True, "campaign": _safe_campaign(campaign),
                "canonical_status_text": _status_text(campaign)}
    if name == "get_campaign_setup":
        return {"ok": True, "campaign": _safe_campaign(campaign),
                "canonical_setup": await _setup_text(campaign)}
    if name == "get_campaign_report":
        view = arguments.get("view") if arguments.get("view") in REPORT_VIEWS else "daily_ops"
        question = str(arguments.get("question") or ctx.current_message)
        text = await _answer_report(f"{question} report_type={view}", campaign)
        return {"ok": True, "data_class": "synthetic_demo", "view": view,
                "campaign": _safe_campaign(campaign), "answer": text}
    if name == "get_campaign_live_view":
        parts = await _live_response(campaign)
        for part in parts[1:]:
            if isinstance(part, dict):
                ctx.media_parts.append(part)
        return {"ok": True, "campaign": _safe_campaign(campaign),
                "live_view": str(parts[0])}
    if name in {"prepare_pause_campaign", "prepare_resume_campaign"}:
        action = "pause" if name == "prepare_pause_campaign" else "resume"
        prompt = await _lifecycle_request(ctx.thread, campaign, action)
        # Re-fetch the updated thread so a later explicit confirmation sees it.
        from zalo_campaign_agent import get_or_create_thread
        ctx.thread = await get_or_create_thread(ctx.thread["external_uid"])
        return {"ok": True, "proposal": action, "requires_confirmation": True,
                "confirmation_prompt": prompt}
    return {"ok": False, "error": "unknown_tool", "tool": name}


def tool_output_json(value: dict) -> str:
    from config import config
    from zalo_sessions import estimate_tokens
    raw = json.dumps(value, ensure_ascii=False, default=str)
    if estimate_tokens(raw) <= config.ZALO_CONTEXT_MAX_TOOL_TOKENS:
        return raw
    # Function outputs are strings, but keeping a valid JSON envelope helps the
    # model distinguish deliberate truncation from a malformed tool response.
    compact = {
        "ok": bool(value.get("ok")), "truncated": True,
        "content_prefix": raw[:max(200, config.ZALO_CONTEXT_MAX_TOOL_TOKENS * 2)],
    }
    return json.dumps(compact, ensure_ascii=False)
