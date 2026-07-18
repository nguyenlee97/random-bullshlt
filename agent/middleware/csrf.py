"""Double-submit CSRF protection for browser cookie-authenticated mutations."""
from __future__ import annotations

import hmac
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import config


CSRF_COOKIE = "aa_csrf"
ACCOUNT_COOKIE = "aa_account"
ANONYMOUS_COOKIE = "aa_anonymous"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXEMPT_PATHS = {"/api/agent/auth/anonymous"}


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def valid_csrf_token(value: str | None) -> bool:
    return bool(value and 32 <= len(value) <= 256)


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=max(
            config.ANONYMOUS_COOKIE_MAX_AGE_DAYS,
            config.ACCOUNT_SESSION_MAX_AGE_DAYS,
        ) * 24 * 60 * 60,
        httponly=False,
        secure=config.ACCOUNT_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cookie_authenticated = bool(
            request.cookies.get(ACCOUNT_COOKIE)
            or request.cookies.get(ANONYMOUS_COOKIE)
        )
        if (
            request.method in UNSAFE_METHODS
            and request.url.path.startswith("/api/agent/")
            and request.url.path not in EXEMPT_PATHS
            and cookie_authenticated
        ):
            cookie_token = request.cookies.get(CSRF_COOKIE, "")
            header_token = request.headers.get("X-CSRF-Token", "")
            if (
                not valid_csrf_token(cookie_token)
                or not valid_csrf_token(header_token)
                or not hmac.compare_digest(cookie_token, header_token)
            ):
                response = JSONResponse(
                    status_code=403,
                    content={"error": "csrf_failed", "detail": "invalid CSRF token"},
                )
                # The mutation was rejected before reaching its route, so it is
                # safe for the same-origin client to retry once with a freshly
                # issued double-submit token.
                set_csrf_cookie(response, new_csrf_token())
                return response
        return await call_next(request)
