from fastapi import APIRouter
from models import ChatRequest, AgentResponse
from handlers.boot import handle_boot
from handlers.brief import handle_brief
from handlers.creative import handle_creative
from handlers.audience import handle_audience, handle_dmp_recommend
from handlers.setup import handle_setup, handle_zone_recommend_api
from handlers.result import handle_result
from handlers.freeform import handle_freeform

agent_router = APIRouter()


@agent_router.get("/logs/{session_id}")
async def get_logs(session_id: str, limit: int = 100):
    """Return session logs for debugging. Used by the frontend Export feature."""
    from session import _ensure_mongo, _logs_col, _mem_logs, _mem_sessions
    use_mongo = await _ensure_mongo()
    if use_mongo:
        cursor = _logs_col.find(
            {"session_id": session_id},
            {"_id": 0},
            sort=[("ts", -1)],
        ).limit(limit)
        logs = await cursor.to_list(length=limit)
        # Serialize datetime → str
        for entry in logs:
            if hasattr(entry.get("ts"), "isoformat"):
                entry["ts"] = entry["ts"].isoformat()
        session = await _mem_sessions.get(session_id) if not use_mongo else None
    else:
        logs = [e for e in _mem_logs if e.get("session_id") == session_id][-limit:]
        logs_out = []
        for e in logs:
            out = dict(e)
            if hasattr(out.get("ts"), "isoformat"):
                out["ts"] = out["ts"].isoformat()
            logs_out.append(out)
        logs = logs_out
        session = _mem_sessions.get(session_id, {})

    return {
        "session_id": session_id,
        "log_count": len(logs),
        "logs": logs,
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

        if req.step == 1 and fd.creative:
            return await handle_creative(fd.creative, sid)

        if req.step == 2 and fd.segment:
            return await handle_audience(fd.segment, sid)

        if req.step == 3 and fd.setup:
            return await handle_setup(fd.setup, sid)

        if req.step == 4:
            return await handle_result(sid)

    # ── Free-form text → LLM + tools ─────────────────────────────────────────
    if req.message:
        return await handle_freeform(req.message, req.step, sid)

    # ── Fallback ──────────────────────────────────────────────────────────────
    return AgentResponse(
        text="Em chưa hiểu yêu cầu. Anh thử mô tả rõ hơn hoặc tương tác với form ở panel phải nhé!",
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
