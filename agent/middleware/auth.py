"""
Internal API-key authentication for the agent service.

Behavior:
- If AGENT_API_KEY is unset/empty → middleware is a NO-OP (local development:
  turning this on is an explicit .env change, not a surprise lockout).
- Health/version/metrics endpoints and CORS preflights are always exempt.

The browser never receives this key. Nginx injects it while proxying same-origin
``/agent`` requests to the private agent container.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import config

EXEMPT_PATHS = {"/api/health", "/health", "/ready", "/api/version", "/metrics"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key_required = bool(getattr(config, "AGENT_API_KEY", ""))
        if (
            key_required
            and request.url.path not in EXEMPT_PATHS
            and request.method != "OPTIONS"
        ):
            provided = request.headers.get("X-API-Key", "")
            if provided != config.AGENT_API_KEY:
                return JSONResponse(
                    status_code=401,
                    content={"error": "unauthorized", "detail": "missing or invalid X-API-Key"},
                )
        return await call_next(request)
