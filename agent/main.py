"""
E4b Agent Backend — FastAPI app entry point.
"""
import sys
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import config


@asynccontextmanager
async def _lifespan(_app):
    from accounts import ensure_account_indexes
    from autopilot.service import ensure_autopilot_indexes
    from identity import ensure_identity_indexes
    from zalo_auth import ensure_zalo_auth_indexes
    from zalo_channel import ensure_zalo_channel_indexes
    await ensure_account_indexes()
    await ensure_autopilot_indexes()
    await ensure_identity_indexes()
    await ensure_zalo_auth_indexes()
    await ensure_zalo_channel_indexes()
    if config.USE_RAG_AUDIENCE:
        from rag.runtime import start_prewarm
        await start_prewarm()
    if config.USE_VLM_CREATIVE:
        from creative_intel.service import start_worker
        await start_worker()
    if config.USE_CAMPAIGN_AUTOPILOT:
        from autopilot.worker import start_worker as start_autopilot_worker
        await start_autopilot_worker()
    if config.ZALO_AGENT_WORKER_ENABLED:
        from zalo_worker import start_worker as start_zalo_worker
        await start_zalo_worker()
    try:
        yield
    finally:
        if config.ZALO_AGENT_WORKER_ENABLED:
            from zalo_worker import stop_worker as stop_zalo_worker
            await stop_zalo_worker()
        if config.USE_RAG_AUDIENCE:
            from rag.runtime import stop_prewarm
            await stop_prewarm()
        if config.USE_CAMPAIGN_AUTOPILOT:
            from autopilot.worker import stop_worker as stop_autopilot_worker
            await stop_autopilot_worker()
        if config.USE_VLM_CREATIVE:
            from creative_intel.service import stop_worker
            await stop_worker()


def _configure_stdio() -> None:
    """Keep Vietnamese/emoji logs from crashing Windows cp1252 consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                pass


_configure_stdio()

# Build version lives in version.py so handlers can import it without touching
# main.py (kills the main→router→boot→main circular import when running
# `python main.py` directly).
from version import BUILD_VERSION, BUILD_FEATURES

app = FastAPI(
    title="Advertising Agent",
    version=BUILD_VERSION,
    description="AI Agent for autonomous ad campaign planning (E4b)",
    lifespan=_lifespan,
)

# Phase 0: API-key auth (no-op until AGENT_API_KEY is set in .env).
# NOTE: added BEFORE CORSMiddleware so CORS runs first (Starlette middleware
# executes in reverse registration order) and 401s still carry CORS headers.
from middleware.auth import ApiKeyMiddleware  # noqa: E402
app.add_middleware(ApiKeyMiddleware)

# Cookie-authenticated browser mutations use one centralized double-submit
# check. API/evaluator calls without browser cookies retain migration behavior.
from middleware.csrf import CSRFMiddleware  # noqa: E402
app.add_middleware(CSRFMiddleware)

# Reject oversized bodies before Pydantic parsing or model/tool execution.
from middleware.request_limits import RequestSizeLimitMiddleware  # noqa: E402
app.add_middleware(RequestSizeLimitMiddleware)

# Phase 0 A2: rate limiting (SlowAPI). Per-route limits are decorated in router.py.
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from ratelimit import limiter, RATE_LIMIT_MESSAGE  # noqa: E402

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request, exc):
    return JSONResponse(status_code=429, content={"error": "rate_limited",
                                                  "detail": RATE_LIMIT_MESSAGE})

app.add_middleware(SlowAPIMiddleware)

# Phase 0 B4: Prometheus /metrics (no-op if prometheus libs missing).
from metrics import setup_metrics  # noqa: E402
setup_metrics(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    # Allow any Cloudflare Quick Tunnel or ngrok URL automatically —
    # removes the chicken-and-egg problem of needing the frontend URL before it exists.
    allow_origin_regex=(
        r"https://(.*\.trycloudflare\.com|.*\.ngrok(-free)?\.app|.*\.ngrok\.io)"
        if config.CORS_ALLOW_TUNNELS else None
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register last so correlation context wraps auth, limits, routing, and errors.
from middleware.request_context import RequestContextMiddleware  # noqa: E402
app.add_middleware(RequestContextMiddleware)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": BUILD_VERSION,
        "features": BUILD_FEATURES,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }


# GreenNode AgentBase Runtime Contract: /health must return HTTP 200
@app.get("/health")
async def health_root():
    return {"status": "ok", "version": BUILD_VERSION}


@app.get("/ready")
async def readiness():
    """Dependency-aware readiness used by Compose and deployment checks."""
    import httpx
    from session import _ensure_mongo

    checks = {"mongo": False, "backend": False}
    try:
        checks["mongo"] = await _ensure_mongo()
    except Exception:
        pass

    if config.USE_RAG_AUDIENCE:
        checks["rag_index"] = False
        checks["rag_runtime"] = False
        try:
            from rag.index import inspect_index
            checks["rag_index"] = (await inspect_index())["ready"]
        except Exception:
            pass
        try:
            from rag.runtime import runtime_status
            checks["rag_runtime"] = runtime_status()["ready"]
        except Exception:
            pass
    if config.USE_VLM_CREATIVE:
        from creative_intel.service import worker_running
        checks["creative_worker"] = worker_running()
    if config.USE_CAMPAIGN_AUTOPILOT:
        from autopilot.worker import worker_running as autopilot_worker_running
        checks["autopilot_worker"] = autopilot_worker_running()
    if config.ZALO_AGENT_WORKER_ENABLED:
        from zalo_worker import worker_running as zalo_worker_running
        checks["zalo_worker"] = zalo_worker_running()
    if config.ZALO_OPENAI_ENABLED:
        from zalo_openai import openai_configured
        checks["zalo_openai"] = openai_configured()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{config.BACKEND_URL.rstrip('/')}/api/health")
            checks["backend"] = response.is_success
    except Exception:
        pass

    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


@app.get("/api/version")
async def version():
    """Quick version check — curl https://agent-api.pawgrammers.io.vn/api/version"""
    return {"version": BUILD_VERSION, "features": BUILD_FEATURES}


# Import router after app is created to avoid circular imports
from router import agent_router  # noqa: E402
from zalo_routes import zalo_router  # noqa: E402
app.include_router(agent_router, prefix="/api/agent")
app.include_router(zalo_router, prefix="/api/agent")


print(f"\n🚀 Advertising Agent v{BUILD_VERSION} starting on port {config.AGENT_PORT}")
print(f"   GreenNode AgentBase: listening on 0.0.0.0:{config.AGENT_PORT}, health at /health")
print(f"   Features: {', '.join(BUILD_FEATURES)}\n")

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.AGENT_HOST, port=config.AGENT_PORT, reload=True)
