"""HTTP surface for Zalo Login and the Zalo OA linking foundation."""
from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
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

    return {
        "ok": True,
        "service": "advertising-agent-zalo-webhook",
        "configured": channel_ready(),
        "oa_id": config.ZALO_OA_ID or None,
        "oa_name": config.ZALO_OA_NAME or None,
    }


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
        return JSONResponse({
            "ok": True,
            "accepted": False,
            "duplicate": False,
        })
    except ZaloChannelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JSONResponse({
        "ok": True,
        "accepted": outcome["accepted"],
        "duplicate": outcome["duplicate"],
    })
