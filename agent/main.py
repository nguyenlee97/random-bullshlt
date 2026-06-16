"""
E4b Agent Backend — FastAPI app entry point.
"""
import uvicorn
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import config

# ── Build version ─────────────────────────────────────────────────────────────
# Bump this manually (or via deploy script) whenever code changes are deployed.
# Format: YYYY-MM-DD.N  (N = deploy count for that day, starting at 1)
BUILD_VERSION = "2026-06-16.9"
BUILD_FEATURES = [
    "system-logs",
    "step-tool-rules",
    "brief-rules",
    "auto-confirm-apply",
    "auto-step-advance",
    "next-step-redirect",
    "3-level-tool-fallback",
    "confirmation-detection",
    "force-text-no-tools",
    "empty-response-guard",
    "frontend-console-log",
    "full-brief-update",
    "skip-update-workspace-llm",
    "dmp-recommend-fix",
    "audience-entry-recommend",
    "retry-last-chat",
    "persist-workspace-on-confirm",   # brief persisted to MongoDB on auto-apply/pending confirm
    "audience-entry-single-fire",     # removed double-fire of audience-entry trigger
]

app = FastAPI(
    title="Camp Ads Agent",
    version=BUILD_VERSION,
    description="AI Agent for autonomous ad campaign planning (E4b)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
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


@app.get("/api/version")
async def version():
    """Quick version check — curl https://agent-api.pawgrammers.io.vn/api/version"""
    return {"version": BUILD_VERSION, "features": BUILD_FEATURES}


# Import router after app is created to avoid circular imports
from router import agent_router  # noqa: E402
app.include_router(agent_router, prefix="/api/agent")

print(f"\n🚀 Camp Ads Agent v{BUILD_VERSION} starting on port {config.AGENT_PORT}")
print(f"   Features: {', '.join(BUILD_FEATURES)}\n")

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.AGENT_HOST, port=config.AGENT_PORT, reload=True)
