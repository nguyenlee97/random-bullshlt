"""Strict, ownership-scoped tools exposed to the Zalo conversational model."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import json
import re
from typing import Any
import unicodedata

from config import config


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
    {"type": "function", "name": "list_report_types",
     "description": "List and explain all six report views. Use this when the user asks for a report but does not name or clearly imply one; never silently choose Daily Ops.",
     "strict": True, "parameters": _schema({}, [])},
    {"type": "function", "name": "get_campaign_report",
     "description": "Show one campaign report as detailed Zalo images, answer a question from its generated analysis, or provide the full PDF. A new show request must explicitly identify the campaign.",
     "strict": True, "parameters": _schema({
         "campaign_reference": {"type": "string"},
         "view": {"type": "string", "enum": REPORT_VIEWS},
         "mode": {"type": "string", "enum": ["show", "question", "pdf"]},
         "question": {"type": ["string", "null"], "description": "The user's report question for mode=question; null for show or pdf."},
     }, ["campaign_reference", "view", "mode", "question"])},
    {"type": "function", "name": "get_campaign_live_view",
     "description": "Capture native Zalo images for one owned campaign. Sends each requested site's ad-zone images followed by its annotated full-site image.",
     "strict": True, "parameters": _schema({
         "campaign_reference": {"type": "string"},
         "site": {"type": "string", "enum": ["all", "baomoi", "znews", "zingmp3"]},
     }, ["campaign_reference", "site"])},
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
    media_parts: list[str | dict] = field(default_factory=list)


def _safe_campaign(item: dict, index: int | None = None) -> dict:
    order = item.get("order") or {}
    value = {
        "campaign_id": item.get("campaign_id"), "brand": order.get("brand"),
        "status": order.get("status"), "objective": order.get("objective"),
    }
    if index is not None:
        value["index"] = index
    return value


async def _campaign_for_reference(
    ctx: ToolExecutionContext, reference: str, *, allow_context_fallback: bool = True,
) -> tuple[dict | None, dict | None]:
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
            allow_context_fallback=allow_context_fallback,
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


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or "").lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").replace("đ", "d")


def _explicit_campaign_signal(message: str, campaigns: list[dict], active_campaign_id: str | None) -> tuple[bool, bool]:
    """Return (has explicit signal, may use active context) from server-seen text."""
    folded = _fold(message)
    lowered = str(message or "").lower()
    for campaign in campaigns:
        campaign_id = str(campaign.get("campaign_id") or "").lower()
        brand = _fold((campaign.get("order") or {}).get("brand") or campaign.get("conversation_title") or "")
        if campaign_id and campaign_id in lowered:
            return True, False
        if brand and len(brand) >= 2 and brand in folded:
            return True, False
    if re.search(r"\b(?:so|thu)\s*(?:[1-8]|mot|hai|ba|bon|tu|nam|sau|bay|tam)\b", folded):
        return True, False
    if any(phrase in folded for phrase in (
        "dau tien", "cuoi cung", "campaign nay", "chien dich nay",
        "campaign do", "chien dich do", "cua no", "cai do",
    )) and active_campaign_id:
        return True, True
    return False, False


def _ordinal_reference(message: str) -> str:
    folded = _fold(message)
    if "dau tien" in folded:
        return "1"
    words = {"mot": 1, "hai": 2, "ba": 3, "bon": 4, "tu": 4, "nam": 5, "sau": 6, "bay": 7, "tam": 8}
    match = re.search(r"\b(?:so|thu)\s*([1-8]|mot|hai|ba|bon|tu|nam|sau|bay|tam)\b", folded)
    if match:
        return str(words.get(match.group(1), match.group(1)))
    return ""


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

    if name == "list_report_types":
        from zalo_reports import report_catalog_for_model
        return {
            "ok": True, "reports": report_catalog_for_model(),
            "instruction": "Ask the user to choose one report. Do not choose for them.",
        }

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

    if name == "get_campaign_report":
        view = arguments.get("view")
        if view not in REPORT_VIEWS:
            return {"ok": False, "error": "report_type_required"}
        mode = arguments.get("mode")
        if mode not in {"show", "question", "pdf"}:
            return {"ok": False, "error": "report_mode_required"}

        campaigns = await owned_campaigns(ctx.thread)
        has_signal, contextual_signal = _explicit_campaign_signal(
            ctx.current_message, campaigns, ctx.thread.get("active_campaign_id"),
        )
        active_report_id = str(ctx.thread.get("active_report_campaign_id") or "")
        active_report_view = str(ctx.thread.get("active_report_view") or "")
        campaign = None
        error = None
        if mode in {"question", "pdf"} and not has_signal and active_report_id:
            campaign = next(
                (item for item in campaigns if str(item.get("campaign_id")) == active_report_id),
                None,
            )
            if campaign:
                view = active_report_view or view
                from zalo_campaign_agent import _select_campaign
                ctx.thread = await _select_campaign(ctx.thread, campaign)
        elif has_signal:
            reference = (
                _ordinal_reference(ctx.current_message)
                or ctx.current_message
            )
            campaign, error = await _campaign_for_reference(
                ctx, reference, allow_context_fallback=contextual_signal,
            )

        if campaign is None:
            pending = {"view": view, "mode": mode, "question": arguments.get("question")}
            ctx.thread = await _update_thread(ctx.thread, {"pending_report_request": pending})
            return {
                "ok": False, "error": "campaign_reference_required" if not error else error.get("error"),
                "message": "Ask one focused question: which campaign should this report use? Never choose one silently.",
                "pending_report": {"view": view, "mode": mode},
                "candidates": [_safe_campaign(item, index) for index, item in enumerate(campaigns[:8], 1)],
            }

        ctx.thread = await _update_thread(ctx.thread, {
            "active_report_campaign_id": campaign["campaign_id"],
            "active_report_view": view,
            "pending_report_request": None,
        })
        from zalo_reports import get_report_bundle
        bundle = await get_report_bundle(
            campaign=campaign, view=view, mode=mode,
            question=str(arguments.get("question") or ctx.current_message),
        )
        image_pages = bundle.pop("image_pages", [])
        image_type = bundle.pop("image_content_type", "image/jpeg")
        suggestions = bundle.pop("suggested_questions", [])
        if image_pages:
            from zalo_campaign_agent import _delivery_image_parts
            for index, image_bytes in enumerate(image_pages, 1):
                ctx.media_parts.extend(await _delivery_image_parts(
                    image_bytes, image_type, label=f"báo cáo {view} trang {index}",
                ))
            if suggestions:
                ctx.media_parts.append(
                    "Bạn có thể hỏi tiếp:\n" + "\n".join(
                        f"• {question}" for question in suggestions[:6]
                    )
                    + "\n\nNếu bạn muốn tải bản PDF đầy đủ, hãy nhắn: "
                      "“Tôi muốn file report PDF”."
                )
            bundle["delivery"] = (
                f"{len(image_pages)} report images and one suggested-question message "
                "were queued exactly once. Do not repeat their content."
            )
        pdf_bytes = bundle.pop("pdf_bytes", None)
        bundle.pop("pdf_content_type", None)
        if pdf_bytes:
            from zalo_campaign_agent import _store_channel_media
            pdf_url = await _store_channel_media(
                pdf_bytes, "application/pdf", filename=f"report-{campaign['campaign_id']}.pdf",
            )
            ttl_minutes = max(1, config.ZALO_MEDIA_TTL_SECONDS // 60)
            ctx.media_parts.append(
                f"Bạn tải file PDF đầy đủ tại đây (liên kết có hiệu lực {ttl_minutes} phút): {pdf_url}"
            )
            bundle["pdf_delivery"] = "One opaque, expiring PDF download link was queued. Do not repeat its URL."
        return {**bundle, "campaign": _safe_campaign(campaign)}

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
    if name == "get_campaign_live_view":
        requested_site = str(arguments.get("site") or "all")
        parts = await _live_response(campaign, requested_site=requested_site)
        ctx.media_parts.extend(parts)
        return {"ok": True, "campaign": _safe_campaign(campaign),
                "requested_site": requested_site,
                "delivery": "Ordered site heading, zone image(s), then full-site image have been queued. Do not repeat raw URLs."}
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
