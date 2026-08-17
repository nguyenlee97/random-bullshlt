"""Zalo Social OAuth v4 mapped onto the existing FE-2B account sessions.

Only short-lived PKCE attempts are persisted.  Zalo authorization/access tokens
exist in request-local memory long enough to fetch the profile and are never
returned, logged, or stored.  The resulting identity uses the same internal
``user_id`` and opaque ``aa_account`` session as every other provider.
"""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
from config import config


class ZaloOAuthError(Exception):
    """A non-secret, user-safe OAuth failure."""


_mem_attempts: dict[str, dict] = {}
_attempt_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_return_to(value: str | None) -> str:
    candidate = (value or "/").strip()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or len(candidate) > 500
    ):
        return "/"
    return candidate


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


async def _collection():
    from session import _ensure_mongo

    if not await _ensure_mongo():
        return None
    import session as session_store

    return session_store._client[config.MONGODB_DB]["oauth_login_attempts"]


async def ensure_zalo_auth_indexes() -> None:
    collection = await _collection()
    if collection is None:
        return
    await collection.create_index("expires_at", expireAfterSeconds=0, name="oauth_attempt_expiry_ttl")
    await collection.create_index(
        [("provider", 1), ("created_at", -1)], name="oauth_attempt_provider_time"
    )


def oauth_ready() -> bool:
    return bool(
        config.ZALO_LOGIN_ENABLED
        and config.ZALO_APP_ID
        and config.ZALO_APP_SECRET
        and config.ZALO_LOGIN_REDIRECT_URI
    )


async def start_user_oauth(actor: dict, *, intent: str, return_to: str = "/") -> dict:
    if not oauth_ready():
        raise ZaloOAuthError("zalo login is not configured")
    if intent not in {"login", "link"}:
        raise ZaloOAuthError("invalid oauth intent")
    if intent == "login":
        if actor.get("user_id"):
            raise ZaloOAuthError("use the explicit link action while signed in")
        if not actor.get("anonymous_id"):
            raise ZaloOAuthError("anonymous browser identity is required")
    elif not actor.get("user_id") or not actor.get("account_session_id"):
        raise ZaloOAuthError("account session is required to link Zalo")

    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(32)
    state_hash = _hash(state)
    now = _now()
    expires_at = now + timedelta(
        seconds=max(120, int(config.ZALO_OAUTH_ATTEMPT_TTL_SECONDS))
    )
    doc = {
        "_id": state_hash,
        "provider": "zalo",
        "intent": intent,
        "code_verifier": verifier,
        "anonymous_id": actor.get("anonymous_id"),
        "user_id": actor.get("user_id"),
        "account_session_id": actor.get("account_session_id"),
        "return_to": _safe_return_to(return_to),
        "created_at": now,
        "expires_at": expires_at,
    }
    collection = await _collection()
    if collection is not None:
        await collection.insert_one(doc)
    else:
        async with _attempt_lock:
            _mem_attempts[state_hash] = doc

    query = urlencode({
        "app_id": config.ZALO_APP_ID,
        "redirect_uri": config.ZALO_LOGIN_REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    })
    return {
        "authorization_url": f"{config.ZALO_LOGIN_PERMISSION_URL}?{query}",
        "expires_in": max(120, int(config.ZALO_OAUTH_ATTEMPT_TTL_SECONDS)),
    }


async def _consume_attempt(state: str) -> dict:
    supplied = (state or "").strip()
    if not 20 <= len(supplied) <= 256:
        raise ZaloOAuthError("invalid or expired oauth state")
    state_hash = _hash(supplied)
    now = _now()
    collection = await _collection()
    if collection is not None:
        doc = await collection.find_one_and_delete({
            "_id": state_hash,
            "provider": "zalo",
            "expires_at": {"$gt": now},
        })
    else:
        async with _attempt_lock:
            doc = _mem_attempts.pop(state_hash, None)
        if doc and doc.get("expires_at") <= now:
            doc = None
    if not doc:
        raise ZaloOAuthError("invalid or expired oauth state")
    return doc


def _assert_browser_binding(attempt: dict, actor: dict) -> None:
    if attempt.get("intent") == "login":
        if not actor.get("anonymous_id") or actor.get("anonymous_id") != attempt.get("anonymous_id"):
            raise ZaloOAuthError("oauth browser identity changed")
        return
    if (
        not actor.get("user_id")
        or actor.get("user_id") != attempt.get("user_id")
        or actor.get("account_session_id") != attempt.get("account_session_id")
    ):
        raise ZaloOAuthError("account session changed during Zalo linking")


async def _zalo_profile(code: str, verifier: str) -> dict:
    if not code or len(code) > 4096:
        raise ZaloOAuthError("authorization code is missing")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await client.post(
                config.ZALO_LOGIN_TOKEN_URL,
                headers={
                    "secret_key": config.ZALO_APP_SECRET,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "app_id": config.ZALO_APP_ID,
                    "code": code,
                    "code_verifier": verifier,
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise ZaloOAuthError("Zalo did not issue an access token")
            profile_response = await client.get(
                config.ZALO_PROFILE_URL,
                params={"fields": "id,name,picture"},
                headers={"access_token": access_token},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
    except ZaloOAuthError:
        raise
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise ZaloOAuthError("Zalo authentication could not be completed") from exc
    subject = str(profile.get("id") or "").strip()
    name = " ".join(str(profile.get("name") or "Zalo user").split())
    picture = profile.get("picture") or {}
    avatar_url = ((picture.get("data") or {}).get("url") if isinstance(picture, dict) else None)
    if not subject:
        raise ZaloOAuthError("Zalo profile did not include an identity")
    return {"subject": subject, "display_name": name[:80], "avatar_url": avatar_url}


async def finish_user_oauth(code: str, state: str, actor: dict) -> dict:
    """Consume a one-time OAuth attempt and resolve/link the internal account."""
    attempt = await _consume_attempt(state)
    _assert_browser_binding(attempt, actor)
    profile = await _zalo_profile(code, attempt["code_verifier"])
    from accounts import authenticate_zalo_account

    user = await authenticate_zalo_account(
        profile["subject"],
        profile["display_name"],
        avatar_url=profile.get("avatar_url"),
        link_user_id=attempt.get("user_id") if attempt.get("intent") == "link" else None,
    )
    return {
        "intent": attempt["intent"],
        "return_to": attempt.get("return_to") or "/",
        "user": user,
    }


async def get_zalo_auth_storage_for_test() -> list[dict]:
    collection = await _collection()
    if collection is not None:
        return await collection.find({}).to_list(length=None)
    return list(_mem_attempts.values())
