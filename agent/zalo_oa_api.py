"""Server-only Zalo OA OpenAPI client for existing-follower recovery.

Zalo Login exposes an app-scoped subject while OA APIs use an OA-scoped
``user_id``. V3 ``user/getlist`` plus ``user/detail`` is the provider-backed
bridge: detail responses include both identifiers and the live follow state.

OA refresh tokens rotate on every use. The initial deployment secrets seed a
root-readable JSON store; every refreshed pair replaces that file atomically.
Tokens are never returned to callers or written to logs.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import time

import httpx

from config import config


class ZaloOAAPIError(Exception):
    """Provider or credential failure safe to translate to a generic status."""


_token_lock = asyncio.Lock()
_scan_lock = asyncio.Lock()
_token_state: dict | None = None
_follower_cache: dict[str, tuple[float, dict | None]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def oa_recovery_configured() -> bool:
    path = str(config.ZALO_OA_TOKEN_STORE_PATH or "").strip()
    persisted = bool(path and Path(path).is_file())
    seeded = bool(config.ZALO_OA_ACCESS_TOKEN and config.ZALO_OA_REFRESH_TOKEN)
    return bool(
        config.ZALO_OA_ENABLED
        and config.ZALO_APP_ID
        and config.ZALO_APP_SECRET
        and config.ZALO_OA_ID
        and path
        and (persisted or seeded)
    )


def _parse_expiry(value: object) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return _now() - timedelta(seconds=1)


def _normalize_state(value: dict) -> dict:
    access_token = str(value.get("access_token") or "").strip()
    refresh_token = str(value.get("refresh_token") or "").strip()
    if not access_token or not refresh_token:
        raise ZaloOAAPIError("Zalo OA API credentials are unavailable")
    oa_id = str(value.get("oa_id") or config.ZALO_OA_ID).strip()
    if oa_id != config.ZALO_OA_ID:
        raise ZaloOAAPIError("Zalo OA token store belongs to another OA")
    return {
        "oa_id": oa_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": _parse_expiry(value.get("expires_at")),
    }


def _load_state() -> dict:
    path = Path(str(config.ZALO_OA_TOKEN_STORE_PATH or "").strip())
    if path.is_file():
        try:
            return _normalize_state(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise ZaloOAAPIError("Zalo OA token store is unreadable") from exc
    if not config.ZALO_OA_ACCESS_TOKEN or not config.ZALO_OA_REFRESH_TOKEN:
        raise ZaloOAAPIError("Zalo OA API credentials are unavailable")
    # API Explorer credentials are expected to be freshly issued during
    # deployment. Use a conservative 23h window; provider auth failures still
    # trigger one guarded refresh below.
    return {
        "oa_id": config.ZALO_OA_ID,
        "access_token": config.ZALO_OA_ACCESS_TOKEN,
        "refresh_token": config.ZALO_OA_REFRESH_TOKEN,
        "expires_at": _now() + timedelta(hours=23),
    }


def _write_state(state: dict) -> None:
    path_value = str(config.ZALO_OA_TOKEN_STORE_PATH or "").strip()
    if not path_value:
        raise ZaloOAAPIError("Zalo OA token store path is not configured")
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    payload = {
        "oa_id": config.ZALO_OA_ID,
        "access_token": state["access_token"],
        "refresh_token": state["refresh_token"],
        "expires_at": state["expires_at"].isoformat(),
        "updated_at": _now().isoformat(),
    }
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump(payload, temporary, separators=(",", ":"))
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    except OSError as exc:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise ZaloOAAPIError("Zalo OA token store could not be updated") from exc


async def _refresh_state(current: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                config.ZALO_OA_TOKEN_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "secret_key": config.ZALO_APP_SECRET,
                },
                data={
                    "refresh_token": current["refresh_token"],
                    "app_id": config.ZALO_APP_ID,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ZaloOAAPIError("Zalo OA credentials could not be refreshed") from exc
    if not isinstance(payload, dict) or not payload.get("access_token") or not payload.get("refresh_token"):
        raise ZaloOAAPIError("Zalo OA refresh response was invalid")
    try:
        expires_in = max(300, int(payload.get("expires_in") or 90000))
    except (TypeError, ValueError):
        expires_in = 90000
    refreshed = {
        "oa_id": config.ZALO_OA_ID,
        "access_token": str(payload["access_token"]),
        "refresh_token": str(payload["refresh_token"]),
        "expires_at": _now() + timedelta(seconds=expires_in),
    }
    _write_state(refreshed)
    return refreshed


async def _access_token(*, force_refresh: bool = False, stale_token: str = "") -> str:
    global _token_state
    async with _token_lock:
        if _token_state is None:
            _token_state = _load_state()
            # Persist the initial pair before it can rotate.
            _write_state(_token_state)
        if force_refresh and stale_token and _token_state["access_token"] != stale_token:
            return _token_state["access_token"]
        if force_refresh or _token_state["expires_at"] <= _now() + timedelta(minutes=2):
            _token_state = await _refresh_state(_token_state)
        return _token_state["access_token"]


def _auth_error(payload: dict, status_code: int) -> bool:
    if status_code in {401, 403}:
        return True
    message = str(payload.get("message") or "").lower()
    try:
        code = int(payload.get("error"))
    except (TypeError, ValueError):
        code = 0
    return code in {-216, -201, -124} or "access token" in message or "access_token" in message


async def _api_get(
    path: str,
    data: dict,
    *,
    retry: bool = True,
    rate_limit_retries: int = 3,
) -> dict:
    token = await _access_token()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{config.ZALO_OA_API_BASE_URL}/{path.lstrip('/')}",
                headers={"access_token": token},
                params={"data": json.dumps(data, separators=(",", ":"))},
            )
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ZaloOAAPIError("Zalo OA API request failed") from exc
    if not isinstance(payload, dict):
        raise ZaloOAAPIError("Zalo OA API returned an invalid response")
    if retry and _auth_error(payload, response.status_code):
        await _access_token(force_refresh=True, stale_token=token)
        return await _api_get(
            path,
            data,
            retry=False,
            rate_limit_retries=rate_limit_retries,
        )
    try:
        error_code = int(payload.get("error") or 0)
    except (TypeError, ValueError):
        error_code = -1
    # OA detail lookups are subject to a fairly small burst quota. Zalo returns
    # HTTP 200 with provider error -32, so retry it explicitly instead of
    # misclassifying a real follower as absent.
    if error_code == -32 and rate_limit_retries > 0:
        await asyncio.sleep(1.0)
        return await _api_get(
            path,
            data,
            retry=retry,
            rate_limit_retries=rate_limit_retries - 1,
        )
    if response.status_code >= 400 or error_code != 0:
        raise ZaloOAAPIError("Zalo OA API rejected the request")
    result = payload.get("data")
    if not isinstance(result, dict):
        raise ZaloOAAPIError("Zalo OA API response data was invalid")
    return result


async def _api_post(path: str, data: dict, *, retry: bool = True) -> dict:
    """Call a V3 OA mutation without exposing the rotating access token."""
    token = await _access_token()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{config.ZALO_OA_API_BASE_URL}/{path.lstrip('/')}",
                headers={"access_token": token, "Content-Type": "application/json"},
                json=data,
            )
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ZaloOAAPIError("Zalo OA API request failed") from exc
    if not isinstance(payload, dict):
        raise ZaloOAAPIError("Zalo OA API returned an invalid response")
    if retry and _auth_error(payload, response.status_code):
        await _access_token(force_refresh=True, stale_token=token)
        return await _api_post(path, data, retry=False)
    try:
        error_code = int(payload.get("error") or 0)
    except (TypeError, ValueError):
        error_code = -1
    if response.status_code >= 400 or error_code != 0:
        error = ZaloOAAPIError("Zalo OA API rejected the request")
        error.provider_code = error_code
        error.retryable = response.status_code >= 500 or error_code in {-32, -201}
        raise error
    result = payload.get("data")
    return result if isinstance(result, dict) else {}


async def send_text(external_uid: str, text: str) -> dict:
    """Send one customer-service text reply to a verified OA-scoped UID."""
    recipient = str(external_uid or "").strip()
    content = str(text or "").strip()
    if not recipient or not content:
        raise ValueError("Zalo recipient and text are required")
    if not config.ZALO_OUTBOUND_ENABLED:
        raise ZaloOAAPIError("Zalo outbound delivery is disabled")
    return await _api_post("message/cs", {
        "recipient": {"user_id": recipient},
        "message": {"text": content[:2000]},
    })


async def send_image(external_uid: str, image_url: str) -> dict:
    """Send one HTTPS image using the proven OA media-template contract."""
    recipient = str(external_uid or "").strip()
    url = str(image_url or "").strip()
    if not recipient or not url.startswith("https://"):
        raise ValueError("Zalo recipient and HTTPS image URL are required")
    if not config.ZALO_OUTBOUND_ENABLED:
        raise ZaloOAAPIError("Zalo outbound delivery is disabled")
    return await _api_post("message/cs", {
        "recipient": {"user_id": recipient},
        "message": {"attachment": {"type": "template", "payload": {
            "template_type": "media", "elements": [{
                "media_type": "image", "url": url,
            }],
        }}},
    })


async def _user_detail(external_uid: str, semaphore: asyncio.Semaphore) -> dict | None:
    async with semaphore:
        try:
            return await _api_get("user/detail", {"user_id": external_uid})
        except ZaloOAAPIError:
            return None


async def find_existing_follower(app_scoped_uid: str) -> dict | None:
    """Resolve a current OA follower by the authenticated Zalo Login subject."""
    clean_uid = str(app_scoped_uid or "").strip()
    if not clean_uid:
        raise ZaloOAAPIError("Zalo Login identity is unavailable")
    if not oa_recovery_configured():
        raise ZaloOAAPIError("Zalo OA follower recovery is not configured")
    cached = _follower_cache.get(clean_uid)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    async with _scan_lock:
        cached = _follower_cache.get(clean_uid)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        max_users = max(1, min(10000, int(config.ZALO_OA_RECOVERY_MAX_USERS)))
        concurrency = max(1, min(12, int(config.ZALO_OA_RECOVERY_CONCURRENCY)))
        semaphore = asyncio.Semaphore(concurrency)
        offset = 0
        match = None
        while offset < max_users:
            count = min(50, max_users - offset)
            page = await _api_get(
                "user/getlist",
                {"offset": offset, "count": count, "is_follower": "true"},
            )
            users = page.get("users") if isinstance(page.get("users"), list) else []
            external_uids = [
                str(item.get("user_id") or "").strip()
                for item in users if isinstance(item, dict) and item.get("user_id")
            ]
            details = await asyncio.gather(*(
                _user_detail(external_uid, semaphore) for external_uid in external_uids
            ))
            for external_uid, detail in zip(external_uids, details):
                if not detail:
                    continue
                if (
                    str(detail.get("user_id_by_app") or "").strip() == clean_uid
                    and detail.get("user_is_follower") is True
                ):
                    match = {
                        "external_uid": str(detail.get("user_id") or external_uid),
                        "app_scoped_uid": clean_uid,
                    }
                    break
            if match:
                break
            total = max(0, int(page.get("total") or 0))
            offset += len(users)
            if not users or offset >= total:
                break
        # Cache only positive provider evidence. A miss can be caused by a
        # transient per-user API failure, and must remain immediately
        # retryable from the UI.
        if match:
            _follower_cache[clean_uid] = (time.monotonic() + 600, match)
        return match


def reset_oa_api_state_for_test() -> None:
    global _token_state
    _token_state = None
    _follower_cache.clear()
