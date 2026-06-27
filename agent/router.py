from fastapi import APIRouter
from pydantic import BaseModel
from models import ChatRequest, AgentResponse
from handlers.boot import handle_boot
from handlers.brief import handle_brief
from handlers.creative import handle_creative
from handlers.audience import handle_audience, handle_dmp_recommend, handle_audience_entry
from handlers.setup import handle_setup, handle_zone_recommend_api, handle_setup_entry
from handlers.result import handle_result
from handlers.freeform import handle_freeform
from handlers.report import handle_report_entry, handle_report_chat
from handlers.email import handle_email_entry, handle_email_send
from handlers.image_gen import handle_generate_image, get_remaining, AD_FORMATS
from handlers.screenshot import handle_screenshot, ALLOWED_DOMAINS

agent_router = APIRouter()


@agent_router.get("/logs/{session_id}")
async def get_logs(session_id: str, limit: int = 200):
    """Return session logs for debugging. Used by the frontend Export feature."""
    from session import _ensure_mongo, _logs_col, _mem_logs
    use_mongo = await _ensure_mongo()
    if use_mongo:
        cursor = _logs_col.find(
            {"session_id": session_id},
            {"_id": 0},
            sort=[("ts", -1)],
        ).limit(limit)
        logs = await cursor.to_list(length=limit)
        for entry in logs:
            if hasattr(entry.get("ts"), "isoformat"):
                entry["ts"] = entry["ts"].isoformat()
    else:
        raw = [e for e in _mem_logs if e.get("session_id") == session_id][-limit:]
        logs = []
        for e in raw:
            out = dict(e)
            if hasattr(out.get("ts"), "isoformat"):
                out["ts"] = out["ts"].isoformat()
            logs.append(out)

    # Categorize logs for easier debugging
    categorized = {
        "llm_requests":  [l for l in logs if l.get("type") == "llm_request"],
        "llm_responses": [l for l in logs if l.get("type") in ("llm_response_raw", "llm_sanitized")],
        "tool_calls":    [l for l in logs if l.get("type") in ("tool_call", "tool_result")],
        "errors":        [l for l in logs if l.get("type") == "error"],
        "other":         [l for l in logs if l.get("type") not in (
            "llm_request", "llm_response_raw", "llm_sanitized",
            "tool_call", "tool_result", "error",
        )],
    }

    return {
        "session_id": session_id,
        "log_count": len(logs),
        "logs": logs,
        "categorized": categorized,
    }


@agent_router.post("/chat", response_model=AgentResponse)
async def chat(req: ChatRequest) -> AgentResponse:
    sid = req.session_id or "default"

    # ── Boot ──────────────────────────────────────────────────────────────────
    if req.step == -1 or (req.step == 0 and not req.formData and not req.message):
        return await handle_boot()

    # ── Form submission → deterministic handler ───────────────────────────────
    if req.formData:
        fd = req.formData

        if req.step == 0 and fd.brief:
            return await handle_brief(fd.brief, sid)

        # Step order: 0=brief, 1=audience, 2=creative, 3=setup, 4=result
        if req.step == 1 and fd.segment:
            return await handle_audience(fd.segment, sid)

        if req.step == 2 and fd.creative:
            return await handle_creative(fd.creative, sid)

        if req.step == 3 and fd.setup:
            return await handle_setup(fd.setup, sid)

        if req.step == 4:
            return await handle_result(sid)

        if req.step == 5:
            return await handle_report_entry(sid)

        if req.step == 6:
            fd = req.formData
            email = fd.get("email", "") if fd else ""
            if email:
                return await handle_email_send(
                    sid,
                    email=email,
                    cc=fd.get("cc", ""),
                    attach_csv=fd.get("attachCsv", False),
                    attach_json=fd.get("attachJson", False),
                )
            return await handle_email_entry(sid)

    # ── Free-form text → LLM + tools ─────────────────────────────────────────
    if req.message:
        # Step 5 (Report): route to report chat handler with context isolation
        if req.step == 5:
            active_tab = (req.formData or {}).get("activeReportTab", "daily_ops") if req.formData else "daily_ops"
            return await handle_report_chat(req.message, sid, active_tab)

        # Step 6 (Email): pass to email entry for freeform chat
        if req.step == 6:
            return await handle_email_entry(sid)

        return await handle_freeform(
            req.message,
            req.step,
            sid,
            workspace=req.workspace,
            confirmed_steps=req.confirmed_steps,
            workspace_events=req.workspace_events,
        )

    # ── Fallback ──────────────────────────────────────────────────────────────
    return AgentResponse(
        text="Em chưa hiểu yêu cầu. Anh/Chị thử mô tả rõ hơn hoặc tương tác với form ở panel phải nhé!",
        blocks=[],
        meta={"tool": None, "model": "none", "step": req.step},
    )


@agent_router.get("/dmp-recommend")
async def dmp_recommend(session_id: str = "default"):
    """AI picks top DMP segments based on brief + real segment data."""
    return await handle_dmp_recommend(session_id)


@agent_router.get("/zones-recommend")
async def zones_recommend(session_id: str = "default"):
    """AI ranks real zones based on brief objective/budget/KPI + creative files."""
    return await handle_zone_recommend_api(session_id)


@agent_router.get("/audience-entry")
async def audience_entry(session_id: str = "default", brief_hint: str = ""):
    """
    Proactive audience recommendation when user enters step 1.
    Returns Targeting Parameters + DMP Segments (+ optional Advanced Targeting) as chat blocks.
    Returns {skip: true} if brief not set or audience already selected.
    brief_hint: optional JSON-encoded brief from frontend (used when pending_proposal hasn't been committed yet).
    """
    import json as _j
    hint = None
    if brief_hint:
        try:
            hint = _j.loads(brief_hint)
        except Exception:
            pass
    return await handle_audience_entry(session_id, brief_hint=hint)


@agent_router.get("/setup-entry")
async def setup_entry_endpoint(session_id: str = "default"):
    """
    Proactive zone recommendation when user enters Step 3 (Setup).
    Like audience-entry: ranks zones, annotates conflicts, returns workspace_proposal + chat explanation.
    Returns {skip: true} if zones already selected or brief not set.
    """
    return await handle_setup_entry(session_id)


@agent_router.get("/report-entry")
async def report_entry_endpoint(session_id: str = "default"):
    """
    Called when user enters Report step (step 5).
    Triggers background report generation and returns intro message.
    """
    return await handle_report_entry(session_id)


@agent_router.get("/email-entry")
async def email_entry_endpoint(session_id: str = "default"):
    """
    Called when user enters Email step (step 6).
    Returns intro message with pre-filled email suggestion.
    """
    return await handle_email_entry(session_id)

@agent_router.post("/commit-workspace")
async def commit_workspace(request: dict):
    """
    Commit a workspace field directly to session form_state.
    Called by frontend when user clicks 'Đồng ý' button or footer 'Đồng ý & Tiếp tục',
    bypassing the chat confirm flow (which would require a round-trip LLM call).
    Body: { session_id, field, value }
    """
    import json as _j
    from session import update_form_state, get_pending_proposal, clear_pending_proposal, log_event
    sid = request.get("session_id", "default")
    field = request.get("field", "")
    value = request.get("value")
    if not field:
        return {"ok": False, "error": "field required"}

    # value may arrive as a JSON string if the frontend double-serialized it
    if isinstance(value, str):
        try:
            value = _j.loads(value)
        except Exception:
            pass  # keep as string

    await update_form_state(sid, field, value)

    # Clear pending_proposal for this field if any
    pending = await get_pending_proposal(sid)
    if pending and pending.get("field") == field:
        await clear_pending_proposal(sid)

    # ── Add a history entry so the LLM knows this step was confirmed via button ──
    # Without this, button-based confirms leave no record in MongoDB and the LLM
    # thinks it's still waiting for confirmation on the next user message.
    from session import add_message
    _CONFIRM_MSGS = {
        "brief":    "✅ [Hệ thống] Brief đã được xác nhận qua nút bấm. Chuyển sang bước Audience.",
        "segment":  "✅ [Hệ thống] Audience segments đã được xác nhận qua nút bấm. Chuyển sang bước Creative.",
        "creative": "✅ [Hệ thống] Creative đã được xác nhận qua nút bấm. Chuyển sang bước Setup.",
        "setup":    "✅ [Hệ thống] Ad zones đã được xác nhận qua nút bấm. Tiến hành gán creative và tạo order.",
    }
    if field in _CONFIRM_MSGS:
        await add_message(sid, "assistant", _CONFIRM_MSGS[field])

    value_summary = list(value.keys()) if isinstance(value, dict) else str(value)[:60]
    await log_event(sid, "commit_workspace", {"field": field, "value_keys": value_summary})
    return {"ok": True, "field": field}


# ─── Image generation ─────────────────────────────────────────────────────────

class GenerateImageRequest(BaseModel):
    session_id: str
    brief: dict = {}
    format_id: str
    custom_prompt: str = ""


@agent_router.post("/generate-image")
async def generate_image_route(req: GenerateImageRequest):
    """Generate an ad creative image via gpt-image-1."""
    return await handle_generate_image(
        session_id=req.session_id,
        brief=req.brief,
        format_id=req.format_id,
        custom_prompt=req.custom_prompt,
    )


@agent_router.get("/image-gen-status")
async def image_gen_status_route(session_id: str):
    """Return remaining image generation quota for this session."""
    remaining = get_remaining(session_id)
    return {"remaining": remaining, "max": 10}


@agent_router.get("/image-gen-formats")
async def image_gen_formats_route():
    """Return all available ad format IDs and metadata (no layout description)."""
    return [
        {"id": fid, "label": f["label"], "width": f["width"], "height": f["height"]}
        for fid, f in AD_FORMATS.items()
    ]


# ─── Ad screenshot (headless Playwright) ──────────────────────────────────────────────

@agent_router.get("/screenshot")
async def screenshot_route(
    url: str = "",
    session_id: str = "default",
    zone_ids: str = "",   # comma-separated DOM element IDs, e.g. "ZingNews_Masthead,ZingNews_Halfpage"
):
    """
    Capture a zone-aware screenshot of a live test-site URL using Playwright.
    Only allowed for whitelisted staging domains (znews-stg, baomoi-stg, zingmp3-stg).

    Query params:
        url       — full URL to capture (must be in ALLOWED_DOMAINS)
        session_id — current session (for logging)
        zone_ids  — comma-separated DOM element IDs to capture (from selectedZoneIds).
                     If omitted, all known zones for the site are attempted.

    Returns:
        { ok, full_b64, zones, zone_count, width, height, captured_at, url }  on success
        { ok: false, error }                                                   on failure
    """
    parsed_zone_ids = [z.strip() for z in zone_ids.split(",") if z.strip()] if zone_ids else None
    return await handle_screenshot(url=url, session_id=session_id, zone_ids=parsed_zone_ids)
