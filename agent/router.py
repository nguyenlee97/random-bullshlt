from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from models import ChatRequest, AgentResponse, ResponseMeta
from ratelimit import limiter, CHAT_LIMIT, RECOMMEND_LIMIT
from handlers.boot import handle_boot
from handlers.brief import handle_brief
from handlers.creative import handle_creative
from handlers.audience import handle_audience, handle_dmp_recommend, handle_audience_entry
from handlers.setup import handle_setup, handle_zone_recommend_api, handle_setup_entry
from handlers.result import handle_result
# Phase 1 strangler flag: graph path vs original freeform (identical signature).
# ⛔ Flip USE_LANGGRAPH_FREEFORM only after scripts/parity_check.py passes.
from config import config as _cfg
if _cfg.USE_LANGGRAPH_FREEFORM:
    from graph.entry import handle_freeform_graph as handle_freeform
else:
    from handlers.freeform import handle_freeform
from handlers.report import handle_report_entry, handle_report_chat
from handlers.email import handle_email_entry, handle_email_send
from handlers.image_gen import handle_generate_image, get_quota_status, AD_FORMATS
from handlers.screenshot import handle_screenshot, ALLOWED_DOMAINS

agent_router = APIRouter()


def _anonymous_token(request: Request) -> str | None:
    return (
        request.cookies.get("aa_anonymous")
        or request.headers.get("x-anonymous-token")  # one-time legacy/API migration
    )


def _account_token(request: Request) -> str | None:
    return request.cookies.get("aa_account")


async def _request_actor(request: Request, *, require_any: bool = True) -> dict:
    from identity import resolve_actor
    try:
        return await resolve_actor(
            _account_token(request),
            _anonymous_token(request),
            require_any=require_any,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def _assert_session_access(request: Request, session_id: str) -> None:
    from identity import require_session_access
    actor = await _request_actor(request, require_any=False)
    try:
        await require_session_access(actor, session_id)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def _assert_run_access(request: Request, run_id: str) -> dict:
    from autopilot.service import get_run
    try:
        run = await get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await _assert_session_access(request, run["session_id"])
    return run


async def _assert_proposal_access(request: Request, proposal_id: str) -> dict:
    from workspace.service import _get_proposal
    proposal = await _get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="proposal not found")
    await _assert_session_access(request, proposal["session_id"])
    return proposal


class _ConversationCreateRequest(BaseModel):
    title: str = ""
    experience_mode: str | None = None
    conversation_model: str | None = None


class _ConversationDeleteAllRequest(BaseModel):
    confirmation: str


class _WorkflowStepConfirmRequest(BaseModel):
    session_id: str


class _RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str


class _LoginRequest(BaseModel):
    email: str
    password: str


def _set_account_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "aa_account",
        token,
        max_age=_cfg.ACCOUNT_SESSION_MAX_AGE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=_cfg.ACCOUNT_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _set_csrf_cookie(request: Request, response: Response) -> str:
    from middleware.csrf import new_csrf_token, valid_csrf_token
    token = request.cookies.get("aa_csrf")
    if not valid_csrf_token(token):
        token = new_csrf_token()
        response.set_cookie(
            "aa_csrf",
            token,
            max_age=max(
                _cfg.ANONYMOUS_COOKIE_MAX_AGE_DAYS,
                _cfg.ACCOUNT_SESSION_MAX_AGE_DAYS,
            ) * 24 * 60 * 60,
            httponly=False,
            secure=_cfg.ACCOUNT_COOKIE_SECURE,
            samesite="lax",
            path="/",
        )
    return token


def _auth_client_ip(request: Request) -> str:
    proxy_ip = request.headers.get("x-real-ip", "").strip()
    return proxy_ip or (request.client.host if request.client else "unknown")


@agent_router.post("/auth/anonymous")
async def anonymous_bootstrap(request: Request, response: Response):
    from identity import bootstrap_anonymous
    supplied_token = _anonymous_token(request)
    result = await bootstrap_anonymous(supplied_token)
    token = result.pop("token", None) or supplied_token
    if token:
        response.set_cookie(
            "aa_anonymous", token,
            max_age=_cfg.ANONYMOUS_COOKIE_MAX_AGE_DAYS * 24 * 60 * 60,
            httponly=True,
            secure=_cfg.ANONYMOUS_COOKIE_SECURE,
            samesite="lax",
            path="/",
        )
    _set_csrf_cookie(request, response)
    return result


@agent_router.post("/auth/register", status_code=201)
@limiter.limit("5/minute")
async def account_register(request: Request, response: Response, body: _RegisterRequest):
    from accounts import (
        AccountConflict,
        AuthRateLimited,
        ValidationError,
        check_auth_rate_limit,
        create_account_session,
        create_local_account,
    )
    from identity import has_claimable_conversations, resolve_actor
    try:
        await check_auth_rate_limit(
            "register", client_ip=_auth_client_ip(request), email=body.email
        )
        user = await create_local_account(body.email, body.password, body.display_name)
        session = await create_account_session(
            user["user_id"], user_agent_label=request.headers.get("user-agent", "")
        )
    except AccountConflict as exc:
        raise HTTPException(status_code=409, detail="local account already exists") from exc
    except AuthRateLimited as exc:
        raise HTTPException(status_code=429, detail="too many authentication attempts") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _set_account_cookie(response, session.pop("token"))
    _set_csrf_cookie(request, response)
    actor = await resolve_actor(None, _anonymous_token(request), require_any=False)
    actor.update({
        "user_id": user["user_id"],
        "user": user,
        "account_session_id": session["session_id"],
    })
    return {
        "user": user,
        "session": session,
        "has_claimable_conversations": await has_claimable_conversations(actor),
    }


@agent_router.post("/auth/login")
@limiter.limit("20/minute")
async def account_login(request: Request, response: Response, body: _LoginRequest):
    from accounts import (
        AccountDisabled,
        AuthRateLimited,
        InvalidCredentials,
        ValidationError,
        authenticate_local_account,
        check_auth_rate_limit,
        create_account_session,
    )
    from identity import has_claimable_conversations, resolve_actor
    prior_actor = await _request_actor(request, require_any=False)
    try:
        await check_auth_rate_limit(
            "login", client_ip=_auth_client_ip(request), email=body.email
        )
        user = await authenticate_local_account(body.email, body.password)
        session = await create_account_session(
            user["user_id"], user_agent_label=request.headers.get("user-agent", "")
        )
        if prior_actor.get("user_id") and prior_actor.get("account_session_id"):
            from accounts import revoke_account_session
            await revoke_account_session(
                prior_actor["user_id"], prior_actor["account_session_id"]
            )
    except AuthRateLimited as exc:
        raise HTTPException(status_code=429, detail="too many authentication attempts") from exc
    except (AccountDisabled, InvalidCredentials, ValidationError) as exc:
        raise HTTPException(status_code=401, detail="invalid email or password") from exc
    _set_account_cookie(response, session.pop("token"))
    _set_csrf_cookie(request, response)
    actor = await resolve_actor(None, _anonymous_token(request), require_any=False)
    actor.update({
        "user_id": user["user_id"],
        "user": user,
        "account_session_id": session["session_id"],
    })
    return {
        "user": user,
        "session": session,
        "has_claimable_conversations": await has_claimable_conversations(actor),
    }


@agent_router.post("/auth/logout")
async def account_logout(request: Request, response: Response):
    from accounts import revoke_account_session
    actor = await _request_actor(request, require_any=False)
    if actor.get("user_id") and actor.get("account_session_id"):
        await revoke_account_session(actor["user_id"], actor["account_session_id"])
    response.delete_cookie("aa_account", path="/", samesite="lax")
    return {"ok": True}


@agent_router.get("/auth/me")
async def account_me(request: Request, response: Response):
    from zalo_auth import oauth_ready
    from zalo_channel import channel_ready, get_linked_channel_for_user
    actor = await _request_actor(request, require_any=False)
    _set_csrf_cookie(request, response)
    zalo_channel = (
        await get_linked_channel_for_user(actor["user_id"])
        if actor.get("user_id") else None
    )
    return {
        "authenticated": bool(actor.get("user_id")),
        "user": actor.get("user") if actor.get("user_id") else None,
        "anonymous_identity_present": bool(actor.get("anonymous_id")),
        "auth_methods": {
            "local_test": True,
            "zalo": oauth_ready(),
            "zalo_oa_link": channel_ready(),
        },
        "channels": {"zalo_oa": zalo_channel},
    }


@agent_router.get("/auth/sessions")
async def account_sessions_list(request: Request):
    from accounts import list_account_sessions
    actor = await _request_actor(request)
    if not actor.get("user_id"):
        raise HTTPException(status_code=401, detail="account session is required")
    return {"sessions": await list_account_sessions(
        actor["user_id"], current_session_id=actor["account_session_id"]
    )}


@agent_router.delete("/auth/sessions/{account_session_id}")
async def account_session_revoke(
    account_session_id: str, request: Request, response: Response,
):
    from accounts import revoke_account_session
    actor = await _request_actor(request)
    if not actor.get("user_id"):
        raise HTTPException(status_code=401, detail="account session is required")
    if not await revoke_account_session(actor["user_id"], account_session_id):
        raise HTTPException(status_code=404, detail="account session not found")
    if account_session_id == actor.get("account_session_id"):
        response.delete_cookie("aa_account", path="/", samesite="lax")
    return {"ok": True, "session_id": account_session_id}


@agent_router.get("/conversations")
async def conversations_list(request: Request, include_archived: bool = False):
    from identity import list_conversations
    actor = await _request_actor(request)
    return {
        "conversations": await list_conversations(
            actor, include_archived=include_archived
        )
    }


@agent_router.get("/conversation-models")
async def conversation_models_list():
    from campaign_models import conversation_model_catalog

    return conversation_model_catalog()


@agent_router.post("/conversations", status_code=201)
async def conversations_create(request: Request, body: _ConversationCreateRequest):
    from campaign_models import (
        conversation_model_is_available,
        normalize_conversation_model,
    )
    from identity import create_conversation
    actor = await _request_actor(request)
    selected_model = normalize_conversation_model(
        body.conversation_model, allow_legacy_default=True,
    )
    # Old clients and internal channel callers retain the explicit legacy
    # default. A browser that makes a model selection may only create a run on
    # a ready component; there is never availability-driven fallback.
    if body.conversation_model and not conversation_model_is_available(selected_model):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "conversation_model_unavailable",
                "conversation_model": selected_model,
                "message": "The selected conversation model is temporarily unavailable.",
            },
        )
    return await create_conversation(
        actor, title=body.title,
        experience_mode=body.experience_mode,
        conversation_model=selected_model,
    )


@agent_router.get("/conversations/{conversation_id}")
async def conversations_get(conversation_id: str, request: Request):
    from identity import get_conversation
    actor = await _request_actor(request)
    try:
        return await get_conversation(actor, conversation_id)
    except KeyError as exc:
        # Do not reveal whether another identity owns this ID.
        raise HTTPException(status_code=404, detail="conversation not found") from exc


@agent_router.post("/conversations/{conversation_id}/archive")
async def conversations_archive(conversation_id: str, request: Request):
    from identity import archive_conversation
    actor = await _request_actor(request)
    try:
        return await archive_conversation(actor, conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="conversation not found") from exc


@agent_router.delete("/conversations/{conversation_id}")
async def conversations_delete(conversation_id: str, request: Request):
    from identity import ConversationRunActive, delete_conversation
    actor = await _request_actor(request)
    try:
        return await delete_conversation(actor, conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="conversation not found") from exc
    except ConversationRunActive as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "active_conversations": exc.conversations},
        ) from exc


@agent_router.delete("/conversations")
async def conversations_delete_all(
    request: Request, body: _ConversationDeleteAllRequest,
):
    from identity import ConversationRunActive, delete_all_conversations
    if body.confirmation != "DELETE_ALL":
        raise HTTPException(status_code=422, detail="invalid delete-all confirmation")
    actor = await _request_actor(request)
    try:
        return await delete_all_conversations(actor)
    except ConversationRunActive as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "active_conversations": exc.conversations},
        ) from exc


@agent_router.post("/conversations/{conversation_id}/claim")
async def conversations_claim(conversation_id: str, request: Request):
    from identity import claim_conversation
    actor = await _request_actor(request)
    if not actor.get("user_id") or not actor.get("anonymous_id"):
        raise HTTPException(status_code=401, detail="claim requires account and device identity")
    try:
        return await claim_conversation(actor, conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="conversation not found") from exc


@agent_router.post("/workflow/steps/{step}/confirm")
async def workflow_step_confirm(
    step: int, request: Request, body: _WorkflowStepConfirmRequest,
):
    """Record an explicit operator review checkpoint for an owned session."""
    if step < 0 or step > 6:
        raise HTTPException(status_code=422, detail="invalid workflow step")
    from identity import require_session_access
    actor = await _request_actor(request)
    try:
        conversation = await require_session_access(actor, body.session_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="owned session not found") from exc
    # Unlike legacy evaluator chat routes, an explicit browser workflow
    # checkpoint must belong to a persisted conversation authority.
    if conversation is None:
        raise HTTPException(status_code=404, detail="owned session not found")
    from session import confirm_workflow_step
    confirmed_steps = await confirm_workflow_step(body.session_id, step)
    return {"ok": True, "step": step, "confirmed_steps": confirmed_steps}


@agent_router.get("/logs/{session_id}")
async def get_logs(session_id: str, request: Request, limit: int = 200):
    """Return session logs for debugging. Used by the frontend Export feature."""
    await _assert_session_access(request, session_id)
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


@agent_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    """Delete one user's agent/session artifacts; business orders are retained."""
    from session import delete_session_data
    if not session_id or len(session_id) > 128:
        raise HTTPException(status_code=422, detail="invalid session id")
    await _assert_session_access(request, session_id)
    deleted = await delete_session_data(session_id)
    return {"ok": True, "session_id": session_id, "deleted": deleted}


@agent_router.post("/chat", response_model=AgentResponse)
@limiter.limit(CHAT_LIMIT)
async def chat(request: Request, req: ChatRequest) -> AgentResponse:
    sid = req.session_id or "default"
    await _assert_session_access(request, sid)

    # Treat every browser-provided string as data, never as control text. A
    # flagged request cannot reach a model or mutation handler.
    from prompt_guard import scan_untrusted_payload
    untrusted = {
        "message": req.message,
        "formData": req.formData.model_dump() if req.formData else None,
        "workspace_events": req.workspace_events,
    }
    injection = scan_untrusted_payload(untrusted, "chat")
    if injection:
        from metrics import INJECTION_FLAGGED
        from session import log_event
        surface, finding = injection
        INJECTION_FLAGGED.labels(surface=surface, rule=finding.rule).inc()
        await log_event(sid, "prompt_injection_blocked", {
            "surface": surface,
            "rule": finding.rule,
        })
        return AgentResponse(
            text=(
                "Em đã chặn nội dung có dấu hiệu cố thay đổi quy tắc hoặc ép hệ thống "
                "thực thi công cụ. Anh/chị hãy gửi lại yêu cầu campaign thuần túy; "
                "workspace chưa bị thay đổi."
            ),
            blocks=[],
            meta=ResponseMeta(tool="prompt_guard", model="none", step=req.step),
        )

    # ── Boot ──────────────────────────────────────────────────────────────────
    if req.step == -1 or (req.step == 0 and not req.formData and not req.message):
        return await handle_boot()

    # ── Form submission → deterministic handler ───────────────────────────────
    if req.formData:
        fd = req.formData

        if req.step == 0 and fd.brief:
            from campaign_engines.dispatcher import dispatch_guided
            from identity import get_conversation_model_for_session
            from openai_campaign.guided import handle_openai_brief

            model_lock = await get_conversation_model_for_session(sid)
            return await dispatch_guided(
                model_lock["conversation_model"],
                greennode_handler=handle_brief,
                openai_handler=handle_openai_brief,
                brief=fd.brief,
                session_id=sid,
            )

        # Step order: 0=brief, 1=audience, 2=creative, 3=setup, 4=result
        if req.step == 1 and fd.segment:
            from campaign_engines.dispatcher import dispatch_guided
            from identity import get_conversation_model_for_session
            from openai_campaign.guided import handle_openai_audience

            model_lock = await get_conversation_model_for_session(sid)
            return await dispatch_guided(
                model_lock["conversation_model"],
                greennode_handler=handle_audience,
                openai_handler=handle_openai_audience,
                segment=fd.segment,
                session_id=sid,
            )

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
        # Autopilot owns mutations during a run. Its chat surface is therefore
        # locked while executing, decision-only at review gates, and read-only
        # after the run has ended.
        from autopilot.chat import route_autopilot_chat
        active_report_tab = (
            (req.formData or {}).get("activeReportTab", "daily_ops")
            if req.formData else "daily_ops"
        )
        autopilot_response = await route_autopilot_chat(
            req.message,
            sid,
            req.step,
            active_report_tab=active_report_tab,
        )
        if autopilot_response is not None:
            return autopilot_response

        # Step 5 (Report): route to report chat handler with context isolation
        if req.step == 5:
            from identity import get_conversation_model_for_session
            model_lock = await get_conversation_model_for_session(sid)
            return await handle_report_chat(
                req.message, sid, active_report_tab,
                conversation_model=model_lock["conversation_model"],
            )

        # Step 6 (Email): pass to email entry for freeform chat
        if req.step == 6:
            return await handle_email_entry(sid)

        from campaign_engines.dispatcher import dispatch_freeform
        from identity import get_conversation_model_for_session

        model_lock = await get_conversation_model_for_session(sid)
        return await dispatch_freeform(
            model_lock["conversation_model"],
            greennode_handler=handle_freeform,
            message=req.message,
            step=req.step,
            session_id=sid,
            workspace=req.workspace,
            workspace_revision=req.workspace_revision,
            confirmed_steps=req.confirmed_steps,
            workspace_events=req.workspace_events,
        )

    # ── Fallback ──────────────────────────────────────────────────────────────
    return AgentResponse(
        text="Em chưa hiểu yêu cầu. Anh/Chị thử mô tả rõ hơn hoặc tương tác với form ở panel phải nhé!",
        blocks=[],
        meta={"tool": None, "model": "none", "step": req.step},
    )


@agent_router.get("/creative-intel")
async def creative_intel(request: Request, session_id: str = "default"):
    """Phase 3: analysis verdicts per uploaded creative (status: analyzing /
    auto_approved / needs_review + deterministic facts + optional VLM result)."""
    await _assert_session_access(request, session_id)
    from creative_intel.service import get_intel
    return {"files": await get_intel(session_id)}


class _AnalyzeFile(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    formatId: str = ""
    intendedFormat: str = ""
    url: str = ""


class _AnalyzeRequest(BaseModel):
    session_id: str = "default"
    files: list[_AnalyzeFile] = []


@agent_router.post("/creative-analyze")
async def creative_analyze(request: Request, req: _AnalyzeRequest):
    """Phase 3 trigger. Called by ConfirmPhase right after files get real URLs
    (the Creative step is frontend-local and never reaches the agent — the KB's
    'upload at step 2' description is outdated). Analysis runs async; results
    land in /creative-intel."""
    await _assert_session_access(request, req.session_id)
    from config import config as _cfg
    if not _cfg.USE_VLM_CREATIVE:
        return {"jobs": [], "note": "USE_VLM_CREATIVE=false"}
    from creative_intel.service import enqueue_analysis
    jobs = await enqueue_analysis(req.session_id, [f.model_dump() for f in req.files])
    return {"jobs": jobs}


class _OverrideRequest(BaseModel):
    session_id: str = "default"
    analysis_id: str
    reason: str
    actor: str = "campaign_operator"


@agent_router.post("/creative-intel/override")
async def creative_intel_override(request: Request, req: _OverrideRequest):
    """Record an explicit, reasoned human approval for a review verdict."""
    await _assert_session_access(request, req.session_id)
    from creative_intel.service import approve_override
    try:
        return await approve_override(
            req.session_id, req.analysis_id, req.reason, req.actor
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@agent_router.get("/dmp-recommend")
@limiter.limit(RECOMMEND_LIMIT)
async def dmp_recommend(request: Request, session_id: str = "default"):
    """AI picks top DMP segments based on brief + real segment data."""
    await _assert_session_access(request, session_id)
    from campaign_engines.dispatcher import dispatch_guided
    from identity import get_conversation_model_for_session
    from openai_campaign.guided import handle_openai_dmp_recommend

    model_lock = await get_conversation_model_for_session(session_id)
    return await dispatch_guided(
        model_lock["conversation_model"],
        greennode_handler=handle_dmp_recommend,
        openai_handler=handle_openai_dmp_recommend,
        session_id=session_id,
    )


@agent_router.get("/zones-recommend")
@limiter.limit(RECOMMEND_LIMIT)
async def zones_recommend(request: Request, session_id: str = "default"):
    """AI ranks real zones based on brief objective/budget/KPI + creative files."""
    await _assert_session_access(request, session_id)
    return await handle_zone_recommend_api(session_id)


@agent_router.get("/audience-entry")
async def audience_entry(request: Request, session_id: str = "default", brief_hint: str = ""):
    """
    Proactive audience recommendation when user enters step 1.
    Returns Targeting Parameters + DMP Segments (+ optional Advanced Targeting) as chat blocks.
    Returns {skip: true} if brief not set or audience already selected.
    brief_hint: optional JSON-encoded brief from frontend (used when pending_proposal hasn't been committed yet).
    """
    await _assert_session_access(request, session_id)
    import json as _j
    hint = None
    if brief_hint:
        try:
            hint = _j.loads(brief_hint)
        except Exception:
            pass
    from campaign_engines.dispatcher import dispatch_guided
    from identity import get_conversation_model_for_session
    from openai_campaign.guided import handle_openai_audience_entry

    model_lock = await get_conversation_model_for_session(session_id)
    return await dispatch_guided(
        model_lock["conversation_model"],
        greennode_handler=handle_audience_entry,
        openai_handler=handle_openai_audience_entry,
        session_id=session_id,
        brief_hint=hint,
    )


@agent_router.get("/setup-entry")
async def setup_entry_endpoint(request: Request, session_id: str = "default"):
    """
    Proactive zone recommendation when user enters Step 3 (Setup).
    Like audience-entry: ranks zones, annotates conflicts, returns workspace_proposal + chat explanation.
    Returns {skip: true} if zones already selected or brief not set.
    """
    await _assert_session_access(request, session_id)
    return await handle_setup_entry(session_id)


@agent_router.get("/report-entry")
async def report_entry_endpoint(request: Request, session_id: str = "default"):
    """
    Called when user enters Report step (step 5).
    Triggers background report generation and returns intro message.
    """
    await _assert_session_access(request, session_id)
    return await handle_report_entry(session_id)


@agent_router.get("/email-entry")
async def email_entry_endpoint(request: Request, session_id: str = "default"):
    """
    Called when user enters Email step (step 6).
    Returns intro message with pre-filled email suggestion.
    """
    await _assert_session_access(request, session_id)
    return await handle_email_entry(session_id)

class _WorkspaceMutationRequest(BaseModel):
    session_id: str = "default"
    field: str
    value: object = None
    base_revision: int | None = None
    actor: str = "campaign_operator"
    reason: str = ""
    idempotency_key: str = ""


class _WorkspaceProposalRequest(_WorkspaceMutationRequest):
    base_revision: int


class _ProposalDecisionRequest(BaseModel):
    actor: str = "campaign_operator"
    reason: str = ""


class _ArtifactResultRequest(BaseModel):
    session_id: str = "default"
    artifact: str
    value: object = None
    task_id: str
    input_revisions: dict[str, int]
    base_artifact_revision: int
    actor: str = "campaign_worker"
    reason: str = ""


class _WorkspacePreferencesRequest(BaseModel):
    session_id: str = "default"
    experience_mode: str | None = None
    approval_policy: str | None = None
    creative_source: str | None = None
    base_revision: int | None = None
    actor: str = "campaign_operator"
    idempotency_key: str = ""


@agent_router.get("/workspace")
async def workspace_get(request: Request, session_id: str = "default"):
    await _assert_session_access(request, session_id)
    from workspace.service import get_workspace
    return await get_workspace(session_id)


@agent_router.post("/workspace/preferences")
async def workspace_preferences(raw_request: Request, request: _WorkspacePreferencesRequest):
    await _assert_session_access(raw_request, request.session_id)
    from workspace.service import WorkspaceConflict, set_preferences
    try:
        return await set_preferences(
            request.session_id,
            experience_mode=request.experience_mode,
            approval_policy=request.approval_policy,
            creative_source=request.creative_source,
            base_revision=request.base_revision,
            actor=request.actor,
            idempotency_key=request.idempotency_key,
        )
    except WorkspaceConflict as exc:
        raise HTTPException(status_code=409, detail={
            "code": "workspace_revision_conflict",
            "expected_revision": exc.expected,
            "actual_revision": exc.actual,
            "workspace": jsonable_encoder(exc.workspace),
        }) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@agent_router.get("/workspace/recompute-plan")
async def workspace_recompute_plan(request: Request, session_id: str = "default"):
    await _assert_session_access(request, session_id)
    from workspace.service import get_recompute_plan
    try:
        return await get_recompute_plan(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@agent_router.get("/workspace/task-context/{artifact}")
async def workspace_task_context(artifact: str, request: Request, session_id: str = "default"):
    await _assert_session_access(request, session_id)
    from workspace.service import get_task_context
    try:
        return await get_task_context(session_id, artifact)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@agent_router.post("/workspace/artifact-results")
async def workspace_artifact_result(raw_request: Request, request: _ArtifactResultRequest):
    await _assert_session_access(raw_request, request.session_id)
    from workspace.service import (
        StaleTaskResult,
        WorkspaceConflict,
        commit_artifact_result,
    )
    try:
        return await commit_artifact_result(
            request.session_id,
            request.artifact,
            request.value,
            task_id=request.task_id,
            input_revisions=request.input_revisions,
            base_artifact_revision=request.base_artifact_revision,
            actor=request.actor,
            reason=request.reason,
        )
    except StaleTaskResult as exc:
        raise HTTPException(status_code=409, detail={
            "code": "stale_task_result",
            "artifact": exc.artifact,
            "mismatches": exc.mismatches,
        }) from exc
    except WorkspaceConflict as exc:
        raise HTTPException(status_code=409, detail={
            "code": "workspace_revision_conflict",
            "expected_revision": exc.expected,
            "actual_revision": exc.actual,
            "workspace": jsonable_encoder(exc.workspace),
        }) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@agent_router.post("/workspace/proposals")
async def workspace_create_proposal(raw_request: Request, request: _WorkspaceProposalRequest):
    await _assert_session_access(raw_request, request.session_id)
    from workspace.intent import resolve_legacy_update
    from workspace.service import WorkspaceConflict, create_proposal, get_workspace
    try:
        workspace = await get_workspace(request.session_id)
        field, value, reason = await resolve_legacy_update(
            request.field, request.value, workspace, request.reason
        )
        return await create_proposal(
            request.session_id,
            field,
            value,
            base_revision=request.base_revision,
            actor=request.actor,
            reason=reason,
        )
    except WorkspaceConflict as exc:
        raise HTTPException(status_code=409, detail={
            "code": "workspace_revision_conflict",
            "expected_revision": exc.expected,
            "actual_revision": exc.actual,
            "workspace": jsonable_encoder(exc.workspace),
        }) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@agent_router.get("/workspace/proposals")
async def workspace_list_pending_proposals(request: Request, session_id: str = "default"):
    await _assert_session_access(request, session_id)
    from workspace.service import list_pending_proposals
    return {"proposals": await list_pending_proposals(session_id)}


@agent_router.post("/workspace/proposals/{proposal_id}/approve")
async def workspace_approve_proposal(
    proposal_id: str, raw_request: Request, request: _ProposalDecisionRequest
):
    await _assert_proposal_access(raw_request, proposal_id)
    from workspace.service import WorkspaceConflict, approve_proposal
    try:
        result = await approve_proposal(proposal_id, actor=request.actor)
        from session import clear_pending_proposal, get_pending_proposal
        pending = await get_pending_proposal(result.get("session_id", "")) if result.get("session_id") else None
        if pending and pending.get("proposal_id") == proposal_id:
            await clear_pending_proposal(result["session_id"])
        from session import add_message, log_event
        await add_message(
            result["session_id"], "assistant",
            f"[Hệ thống] Người dùng đã duyệt đề xuất `{proposal_id}` cho `{result['field']}`.",
        )
        await log_event(result["session_id"], "proposal_confirmed", {
            "proposal_id": proposal_id, "field": result["field"],
            "source": "proposal_api",
        })
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceConflict as exc:
        raise HTTPException(status_code=409, detail={
            "code": "workspace_revision_conflict",
            "expected_revision": exc.expected,
            "actual_revision": exc.actual,
            "workspace": jsonable_encoder(exc.workspace),
        }) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@agent_router.post("/workspace/proposals/{proposal_id}/reject")
async def workspace_reject_proposal(
    proposal_id: str, raw_request: Request, request: _ProposalDecisionRequest
):
    await _assert_proposal_access(raw_request, proposal_id)
    from workspace.service import reject_proposal
    try:
        result = await reject_proposal(
            proposal_id, actor=request.actor, reason=request.reason
        )
        from session import clear_pending_proposal, get_pending_proposal
        pending = await get_pending_proposal(result["session_id"])
        if pending and pending.get("proposal_id") == proposal_id:
            await clear_pending_proposal(result["session_id"])
        from session import add_message, log_event
        text = (
            f"[Hệ thống] Người dùng đã từ chối đề xuất cập nhật `{result['field']}` "
            "qua nút bấm. Không áp dụng thay đổi này."
        )
        await add_message(result["session_id"], "assistant", text)
        await log_event(result["session_id"], "proposal_rejected", {
            "proposal_id": proposal_id, "field": result["field"],
            "reason": request.reason,
        })
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@agent_router.post("/commit-workspace")
async def commit_workspace(raw_request: Request, request: _WorkspaceMutationRequest):
    """
    Commit a workspace field through the canonical revisioned workspace, then
    mirror it to legacy session form_state during migration.
    Called by frontend when user clicks 'Đồng ý' button or footer 'Đồng ý & Tiếp tục',
    bypassing the chat confirm flow (which would require a round-trip LLM call).
    Body: { session_id, field, value, base_revision, idempotency_key }
    """
    import json as _j
    from session import get_pending_proposal, clear_pending_proposal, log_event
    from workspace.service import WorkspaceConflict, apply_mutation
    sid = request.session_id
    await _assert_session_access(raw_request, sid)
    field = request.field
    value = request.value

    # value may arrive as a JSON string if the frontend double-serialized it
    if isinstance(value, str):
        try:
            value = _j.loads(value)
        except Exception:
            pass  # keep as string

    try:
        mutation = await apply_mutation(
            sid,
            field,
            value,
            base_revision=request.base_revision,
            actor=request.actor,
            reason=request.reason,
            idempotency_key=request.idempotency_key,
        )
    except WorkspaceConflict as exc:
        raise HTTPException(status_code=409, detail={
            "code": "workspace_revision_conflict",
            "expected_revision": exc.expected,
            "actual_revision": exc.actual,
            "workspace": jsonable_encoder(exc.workspace),
        }) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if mutation.get("duplicate"):
        return mutation

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
    return mutation


# ─── Durable Campaign Autopilot ──────────────────────────────────────────────

class _AutopilotStartRequest(BaseModel):
    session_id: str = "default"
    approval_policy: str = "critical_only"
    creative_source: str
    actor: str = "campaign_operator"
    idempotency_key: str = ""
    creative_direction: str = ""
    creative_asset_ids: list[str] = []


class _AutopilotActionRequest(BaseModel):
    actor: str = "campaign_operator"
    reason: str = ""


class _AutopilotReviewRequest(_AutopilotActionRequest):
    approved: bool


class _AutopilotStrategyRequest(_AutopilotActionRequest):
    option_id: str


class _AutopilotPlacementRequest(_AutopilotActionRequest):
    zone_ids: list[str]


def _autopilot_error(exc: Exception) -> HTTPException:
    from autopilot.service import RunConflict
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RunConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _require_autopilot_worker() -> None:
    """Fail closed instead of creating a durable run nobody can execute."""
    from autopilot.worker import worker_running

    if not _cfg.USE_CAMPAIGN_AUTOPILOT or not worker_running():
        raise HTTPException(
            status_code=503,
            detail=(
                "Campaign Autopilot worker is unavailable. "
                "Please try again after the service is ready."
            ),
        )


@agent_router.post("/autopilot/runs", status_code=201)
async def autopilot_start(raw_request: Request, request: _AutopilotStartRequest):
    from autopilot.service import RunConflict, create_run
    await _assert_session_access(raw_request, request.session_id)
    actor_identity = await _request_actor(raw_request)
    if request.creative_asset_ids:
        from creative_assets import get_assets
        owned_assets = await get_assets(
            actor_identity, request.creative_asset_ids, request.session_id,
        )
        if len(owned_assets) != len(set(request.creative_asset_ids)):
            raise HTTPException(status_code=404, detail="one or more creative assets were not found")
    _require_autopilot_worker()
    try:
        return await create_run(
            request.session_id,
            approval_policy=request.approval_policy,
            creative_source=request.creative_source,
            actor=request.actor,
            idempotency_key=request.idempotency_key,
            creative_direction=request.creative_direction,
            creative_asset_ids=request.creative_asset_ids,
        )
    except (KeyError, ValueError, RunConflict) as exc:
        raise _autopilot_error(exc) from exc


@agent_router.get("/autopilot/runs/{run_id}")
async def autopilot_get(run_id: str, request: Request):
    from autopilot.service import RunConflict, get_run
    try:
        return await _assert_run_access(request, run_id)
    except (KeyError, ValueError, RunConflict) as exc:
        raise _autopilot_error(exc) from exc


@agent_router.post("/autopilot/runs/{run_id}/pause")
async def autopilot_pause(
    run_id: str, raw_request: Request, request: _AutopilotActionRequest
):
    from autopilot.service import RunConflict, pause_run
    try:
        await _assert_run_access(raw_request, run_id)
        return await pause_run(run_id, actor=request.actor)
    except (KeyError, ValueError, RunConflict) as exc:
        raise _autopilot_error(exc) from exc


@agent_router.post("/autopilot/runs/{run_id}/resume")
async def autopilot_resume(
    run_id: str, raw_request: Request, request: _AutopilotActionRequest
):
    from autopilot.service import RunConflict, resume_run
    try:
        await _assert_run_access(raw_request, run_id)
        return await resume_run(run_id, actor=request.actor)
    except (KeyError, ValueError, RunConflict) as exc:
        raise _autopilot_error(exc) from exc


@agent_router.post("/autopilot/runs/{run_id}/cancel")
async def autopilot_cancel(
    run_id: str, raw_request: Request, request: _AutopilotActionRequest
):
    from autopilot.service import RunConflict, cancel_run
    try:
        await _assert_run_access(raw_request, run_id)
        return await cancel_run(run_id, actor=request.actor)
    except (KeyError, ValueError, RunConflict) as exc:
        raise _autopilot_error(exc) from exc


@agent_router.post("/autopilot/runs/{run_id}/tasks/{task_id}/review")
async def autopilot_review(
    run_id: str, task_id: str, raw_request: Request,
    request: _AutopilotReviewRequest,
):
    from autopilot.service import RunConflict, review_task
    try:
        await _assert_run_access(raw_request, run_id)
        return await review_task(
            run_id, task_id, approved=request.approved,
            actor=request.actor, reason=request.reason,
        )
    except (KeyError, ValueError, RunConflict) as exc:
        raise _autopilot_error(exc) from exc


@agent_router.post("/autopilot/runs/{run_id}/strategy")
async def autopilot_select_strategy(
    run_id: str, raw_request: Request, request: _AutopilotStrategyRequest
):
    from autopilot.service import RunConflict, select_strategy
    try:
        await _assert_run_access(raw_request, run_id)
        return await select_strategy(
            run_id, request.option_id, actor=request.actor, reason=request.reason,
        )
    except (KeyError, ValueError, RunConflict) as exc:
        raise _autopilot_error(exc) from exc


@agent_router.post("/autopilot/runs/{run_id}/placement-intent")
async def autopilot_select_placement_intent(
    run_id: str, raw_request: Request, request: _AutopilotPlacementRequest
):
    from autopilot.service import RunConflict, select_placement_intent
    try:
        await _assert_run_access(raw_request, run_id)
        return await select_placement_intent(
            run_id, request.zone_ids, actor=request.actor, reason=request.reason,
        )
    except (KeyError, ValueError, RunConflict) as exc:
        raise _autopilot_error(exc) from exc


@agent_router.get("/autopilot/runs/{run_id}/events")
async def autopilot_events(run_id: str, request: Request, follow: bool = True):
    """Stream durable run events. ``follow=false`` returns the current backlog."""
    import asyncio
    import json
    from autopilot.service import list_events
    try:
        await _assert_run_access(request, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def stream():
        cursor = None
        while True:
            events = await list_events(run_id, after=cursor)
            for event in events:
                cursor = event["created_at"]
                payload = json.dumps(jsonable_encoder(event), ensure_ascii=False)
                yield f"id: {event['event_id']}\nevent: {event['type']}\ndata: {payload}\n\n"
            if not follow or await request.is_disconnected():
                break
            if not events:
                yield ": keepalive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream")


# ─── Image generation ─────────────────────────────────────────────────────────

class GenerateImageRequest(BaseModel):
    session_id: str
    brief: dict = {}
    format_id: str
    custom_prompt: str = ""
    asset_ids: list[str] = []
    prompt_spec: dict | None = None
    idempotency_key: str = ""
    quality: str = "medium"


class CreativeAssetRequest(BaseModel):
    session_id: str
    name: str
    kind: str = "style_reference"
    use_instruction: str = ""
    required: bool = False
    data_url: str


class CreativePromptRequest(BaseModel):
    session_id: str
    brief: dict = {}
    format_id: str
    asset_ids: list[str] = []
    direction: str = ""


class AudienceReachRequest(BaseModel):
    session_id: str
    selected_segment_ids: list[str] = []


@agent_router.post("/audience/reach")
async def audience_reach_route(request: Request, req: AudienceReachRequest):
    """Return canonical, catalog-grounded unique reach for a DMP selection."""
    await _assert_session_access(request, req.session_id)
    from audience_reach import estimate_unique_reach
    from tools.audience_library import get_all_segments

    selected = {str(value).strip().casefold() for value in req.selected_segment_ids if str(value).strip()}
    catalog = await get_all_segments(limit=500)
    resolved: list[dict] = []
    for segment in catalog:
        identities = {
            str(segment.get(key) or "").strip().casefold()
            for key in ("segmentId", "_id", "code", "fullLabel", "name")
        }
        if selected.intersection(identities):
            resolved.append(segment)
    result = estimate_unique_reach(resolved)
    resolved_ids = {
        str(segment.get("segmentId") or segment.get("_id") or "").strip().casefold()
        for segment in resolved
    }
    result["requested_segment_ids"] = req.selected_segment_ids
    result["unresolved_segment_ids"] = [
        value for value in req.selected_segment_ids
        if str(value).strip().casefold() not in resolved_ids
    ]
    return result


@agent_router.post("/generate-image")
async def generate_image_route(request: Request, req: GenerateImageRequest):
    """Generate one quota-controlled ad creative via direct OpenAI GPT Image 2."""
    await _assert_session_access(request, req.session_id)
    actor = await _request_actor(request)
    from creative_assets import get_assets
    assets = await get_assets(actor, req.asset_ids, req.session_id)
    if len(assets) != len(set(req.asset_ids)):
        raise HTTPException(status_code=404, detail="one or more creative assets were not found")
    return await handle_generate_image(
        session_id=req.session_id,
        brief=req.brief,
        format_id=req.format_id,
        custom_prompt=req.custom_prompt,
        actor=actor,
        assets=assets,
        prompt_spec=req.prompt_spec,
        idempotency_key=req.idempotency_key,
        quality=req.quality,
    )


@agent_router.get("/image-gen-status")
async def image_gen_status_route(request: Request, session_id: str):
    """Return durable per-actor daily quota across every campaign flow."""
    await _assert_session_access(request, session_id)
    actor = await _request_actor(request)
    return await get_quota_status(session_id, actor)


@agent_router.post("/creative/assets", status_code=201)
async def creative_asset_create(request: Request, req: CreativeAssetRequest):
    await _assert_session_access(request, req.session_id)
    actor = await _request_actor(request)
    from creative_assets import create_asset
    try:
        return await create_asset(
            actor, session_id=req.session_id, name=req.name, kind=req.kind,
            use_instruction=req.use_instruction, required=req.required,
            data_url=req.data_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@agent_router.get("/creative/assets")
async def creative_asset_list(request: Request, session_id: str):
    await _assert_session_access(request, session_id)
    from creative_assets import list_assets
    return {
        "assets": await list_assets(await _request_actor(request), session_id),
    }


@agent_router.delete("/creative/assets/{asset_id}")
async def creative_asset_delete(asset_id: str, request: Request, session_id: str):
    await _assert_session_access(request, session_id)
    from creative_assets import delete_asset
    if not await delete_asset(
        await _request_actor(request), asset_id, session_id,
    ):
        raise HTTPException(status_code=404, detail="creative asset not found")
    return {"ok": True, "asset_id": asset_id}


@agent_router.post("/creative/prompt-spec")
async def creative_prompt_spec_route(request: Request, req: CreativePromptRequest):
    await _assert_session_access(request, req.session_id)
    actor = await _request_actor(request)
    from creative_assets import get_assets
    from creative_prompt import compose_prompt_spec
    assets = await get_assets(actor, req.asset_ids, req.session_id)
    if len(assets) != len(set(req.asset_ids)):
        raise HTTPException(status_code=404, detail="one or more creative assets were not found")
    try:
        spec, provenance = await compose_prompt_spec(
            req.session_id, brief=req.brief, format_id=req.format_id,
            assets=assets, direction=req.direction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"prompt_spec": spec, "provenance": provenance, "quota_charged": False}


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
    request: Request,
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
    await _assert_session_access(request, session_id)
    parsed_zone_ids = [z.strip() for z in zone_ids.split(",") if z.strip()] if zone_ids else None
    return await handle_screenshot(url=url, session_id=session_id, zone_ids=parsed_zone_ids)
