"""
E4b Agent Backend — FastAPI app entry point.
"""
import uvicorn
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import config

# Build version lives in version.py so handlers can import it without touching
# main.py (kills the main→router→boot→main circular import when running
# `python main.py` directly).
from version import BUILD_VERSION, BUILD_FEATURES

app = FastAPI(
    title="Camp Ads Agent",
    version=BUILD_VERSION,
    description="AI Agent for autonomous ad campaign planning (E4b)",
)

# Phase 0: API-key auth (no-op until AGENT_API_KEY is set in .env).
# NOTE: added BEFORE CORSMiddleware so CORS runs first (Starlette middleware
# executes in reverse registration order) and 401s still carry CORS headers.
from middleware.auth import ApiKeyMiddleware  # noqa: E402
app.add_middleware(ApiKeyMiddleware)

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
    allow_origin_regex=r"https://(.*\.trycloudflare\.com|.*\.ngrok(-free)?\.app|.*\.ngrok\.io)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": BUILD_VERSION,
        "features": BUILD_FEATURES,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "model": config.LLM_MODEL,
        "backend": config.BACKEND_URL,
        "db": config.MONGODB_DB,
    }


# GreenNode AgentBase Runtime Contract: /health must return HTTP 200
@app.get("/health")
async def health_root():
    return {"status": "ok", "version": BUILD_VERSION}


@app.get("/api/version")
async def version():
    """Quick version check — curl https://agent-api.pawgrammers.io.vn/api/version"""
    return {"version": BUILD_VERSION, "features": BUILD_FEATURES}


# Import router after app is created to avoid circular imports
from router import agent_router  # noqa: E402
app.include_router(agent_router, prefix="/api/agent")

print(f"\n🚀 Camp Ads Agent v{BUILD_VERSION} starting on port {config.AGENT_PORT}")
print(f"   GreenNode AgentBase: listening on 0.0.0.0:{config.AGENT_PORT}, health at /health")
print(f"   Features: {', '.join(BUILD_FEATURES)}\n")

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.AGENT_HOST, port=config.AGENT_PORT, reload=True)
