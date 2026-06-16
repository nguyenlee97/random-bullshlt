from fastapi import APIRouter
from models import ChatRequest, AgentResponse
from handlers.boot import handle_boot
from handlers.brief import handle_brief
from handlers.creative import handle_creative
from handlers.audience import handle_audience, handle_dmp_recommend, handle_audience_entry
from handlers.setup import handle_setup, handle_zone_recommend_api
from handlers.result import handle_result
from handlers.freeform import handle_freeform

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

    # ── Free-form text → LLM + tools ─────────────────────────────────────────
    if req.message:
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
async def audience_entry(session_id: str = "default"):
    """
    Proactive audience recommendation when user enters step 1.
    Returns Targeting Parameters + DMP Segments (+ optional Advanced Targeting) as chat blocks.
    Returns {skip: true} if brief not set or audience already selected.
    """
    return await handle_audience_entry(session_id)
