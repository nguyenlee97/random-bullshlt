"""HTTP surface for Zalo Login and the Zalo OA linking foundation."""
from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel


zalo_router = APIRouter()


class _ZaloStartRequest(BaseModel):
    intent: str = "login"
    return_to: str = "/"


def _status_redirect(path: str, key: str, value: str) -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    return RedirectResponse(
        f"{path}{separator}{quote(key)}={quote(value)}", status_code=303
    )


@zalo_router.post("/auth/zalo/start")
async def zalo_login_start(request: Request, body: _ZaloStartRequest):
    from router import _request_actor
    from zalo_auth import ZaloOAuthError, start_user_oauth

    actor = await _request_actor(request, require_any=False)
    try:
        return await start_user_oauth(actor, intent=body.intent, return_to=body.return_to)
    except ZaloOAuthError as exc:
        status = 503 if "not configured" in str(exc) else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@zalo_router.get("/auth/zalo/callback")
async def zalo_login_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
):
    from accounts import AccountConflict, AccountDisabled, create_account_session
    from router import _request_actor, _set_account_cookie, _set_csrf_cookie
    from zalo_auth import ZaloOAuthError, finish_user_oauth

    if error:
        return _status_redirect("/", "auth_error", "zalo_denied")
    actor = await _request_actor(request, require_any=False)
    try:
        result = await finish_user_oauth(code, state, actor)
        response = _status_redirect(
            result["return_to"],
            "auth",
            "zalo_linked" if result["intent"] == "link" else "zalo_success",
        )
        if result["intent"] == "login":
            session = await create_account_session(
                result["user"]["user_id"],
                user_agent_label=request.headers.get("user-agent", ""),
            )
            _set_account_cookie(response, session.pop("token"))
        _set_csrf_cookie(request, response)
        return response
    except (AccountConflict, AccountDisabled, ZaloOAuthError):
        # Do not reflect provider errors or authorization codes into the browser.
        return _status_redirect("/", "auth_error", "zalo_failed")


@zalo_router.post("/channel-links/zalo")
async def zalo_channel_link_start(request: Request):
    from router import _request_actor
    from zalo_channel import ZaloChannelError, start_channel_link

    actor = await _request_actor(request)
    if not actor.get("user_id"):
        raise HTTPException(status_code=401, detail="account session is required")
    try:
        return await start_channel_link(actor["user_id"])
    except ZaloChannelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@zalo_router.get("/channel-links/zalo/{attempt_id}")
async def zalo_channel_link_status(attempt_id: str, request: Request):
    from router import _request_actor
    from zalo_channel import get_channel_link

    actor = await _request_actor(request)
    if not actor.get("user_id"):
        raise HTTPException(status_code=401, detail="account session is required")
    try:
        return await get_channel_link(actor["user_id"], attempt_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="channel link not found") from exc


@zalo_router.post("/channel-links/zalo/{attempt_id}/recover-existing-follower")
async def zalo_channel_recover_existing_follower(attempt_id: str, request: Request):
    from router import _request_actor
    from zalo_channel import recover_existing_follower_link

    actor = await _request_actor(request)
    if not actor.get("user_id"):
        raise HTTPException(status_code=401, detail="account session is required")
    result = await recover_existing_follower_link(actor["user_id"], attempt_id)
    print(json.dumps({
        "event": "zalo_existing_follower_recovery",
        "status": result.get("status"),
        "reason": result.get("reason"),
    }, separators=(",", ":")), flush=True)
    return result


@zalo_router.delete("/channel-links/zalo")
async def zalo_channel_unlink(request: Request):
    from router import _request_actor
    from zalo_channel import unlink_channel

    actor = await _request_actor(request)
    if not actor.get("user_id"):
        raise HTTPException(status_code=401, detail="account session is required")
    return {"ok": True, "unlinked": await unlink_channel(actor["user_id"])}


@zalo_router.get("/zalo/webhook")
async def zalo_webhook_health():
    from config import config
    from zalo_channel import channel_ready
    from zalo_worker import worker_running
    from zalo_openai import openai_configured

    return {
        "ok": True,
        "service": "advertising-agent-zalo-webhook",
        "configured": channel_ready(),
        "oa_id": config.ZALO_OA_ID or None,
        "oa_name": config.ZALO_OA_NAME or None,
        "agent_worker_enabled": config.ZALO_AGENT_WORKER_ENABLED,
        "agent_worker_running": worker_running(),
        "outbound_enabled": config.ZALO_OUTBOUND_ENABLED,
        "chat_planner": {
            "enabled": config.ZALO_OPENAI_ENABLED,
            "configured": openai_configured(),
            "model": config.ZALO_CHAT_MODEL if config.ZALO_OPENAI_ENABLED else None,
        },
    }


@zalo_router.get("/zalo/media/{token}")
async def zalo_channel_media(token: str):
    """Serve short-lived opaque channel media for Zalo or user download."""
    from zalo_campaign_agent import get_channel_media_download
    media = await get_channel_media_download(token)
    if not media:
        raise HTTPException(status_code=404, detail="media not found")
    data, content_type, filename = media
    headers = {"Cache-Control": "private, max-age=300, immutable"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(
        content=data, media_type=content_type,
        headers=headers,
    )


@zalo_router.post("/zalo/webhook")
async def zalo_webhook(request: Request):
    from zalo_channel import (
        ZaloChannelError,
        ZaloSignatureError,
        normalize_event,
        record_event,
        verify_webhook,
    )

    raw_body = await request.body()
    try:
        body = json.loads(raw_body)
        if not isinstance(body, dict):
            raise ValueError("object required")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid webhook payload") from exc
    try:
        verify_webhook(raw_body, body, request.headers.get("X-ZEvent-Signature"))
        event = normalize_event(body, raw_body)
        outcome = await record_event(event)
    except ZaloSignatureError:
        # Zalo validates a newly configured webhook with a POST that must receive
        # HTTP 200 before signed event delivery is enabled.  Acknowledge the
        # transport without accepting, normalizing or persisting the payload.
        # Returning the same HTTP status also avoids exposing a signature oracle
        # or triggering provider retry storms for unauthenticated traffic.
        print(json.dumps({
            "event": "zalo_webhook",
            "accepted": False,
            "reason": "invalid_signature",
        }, separators=(",", ":")), flush=True)
        return JSONResponse({
            "ok": True,
            "accepted": False,
            "duplicate": False,
        })
    except ZaloChannelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    link = outcome.get("link") or {}
    reply_context = event.get("reply_context") or {}
    print(json.dumps({
        "event": "zalo_webhook",
        "event_name": event.get("event_name"),
        "accepted": outcome["accepted"],
        "duplicate": outcome["duplicate"],
        "has_external_uid": bool(event.get("external_uid")),
        "has_user_id_by_app": bool(event.get("app_scoped_uid")),
        "reply_context_present": bool(reply_context.get("present")),
        "reply_reference_found": bool(event.get("reply_to_message_id")),
        "reply_reference_source": reply_context.get("source"),
        "reply_candidate_keys": reply_context.get("candidate_keys") or [],
        "message_shape_keys": reply_context.get("message_keys") or [],
        "webhook_shape_keys": reply_context.get("body_keys") or [],
        "link_status": link.get("status"),
        "link_reason": link.get("reason"),
    }, separators=(",", ":")), flush=True)
    return JSONResponse({
        "ok": True,
        "accepted": outcome["accepted"],
        "duplicate": outcome["duplicate"],
    })
