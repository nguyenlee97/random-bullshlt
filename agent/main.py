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
BUILD_VERSION = "2026-06-17.40"

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
    "report-step",                    # Step 5: AI-generated analytics + tabbed report UI
    "report-context-isolation",       # separate chat context for report step
    "report-polling",                 # frontend polls /api/reports/status every 3s
    "report-order-fetch",             # report-entry fetches real order from backend API for zones
    "report-zero-data-guard",         # regenerates if existing records are all zeros
    "report-debug-endpoint",          # GET /api/reports/debug/:campaignId for diagnostics
    "image-gen",                      # POST /api/agent/generate-image via gpt-image-1
    "image-gen-safe-zone",            # per-format safe-zone prompt constraints for correct crop
    "image-gen-canvas-crop",          # frontend canvas crop+resize to exact pixel dimensions
    "image-gen-quota",                # 10-image per-session limit tracked server-side
    "image-gen-lightbox",             # click-to-zoom lightbox in AI image gallery
    "image-gen-brief-preview",        # collapsible brief+audience preview in generator UI
    "email-step",                     # Step 6: PDF generation + Resend email delivery
    "email-pdf-pdfkit",               # PDF generated server-side via pdfkit (no puppeteer)
    "email-raw-export",               # CSV + JSON download endpoints for analytics records
    "email-resend",                   # email sent via Resend API (onboarding@resend.dev)
    "confirm-trigger-expanded",       # added duyệt/ổn rồi/ok rồi/hợp lý to confirm triggers
    "step-advance-llm-rule",          # LLM explicitly told update_workspace is only way to advance
    "llm-debug-logging",              # AGENT_DEBUG=true dumps full LLM input/output to stdout
    "llm-max-tokens-4096",            # raised LLM_MAX_TOKENS from 2000 to 4096
    "finish-reason-length-retry",     # retries with short context when LLM hits token limit
    "zone-conflict-detection",        # get_zone_list/search_zones annotate is_booked + conflict info
    "zone-date-injection",            # brief dates auto-injected into zone tool args from workspace
    "proposal-block-segment-display", # fixed [object Object] in WorkspaceProposalBlock for segment
    "confirm-segment-count-fix",      # fixed '0 segments' in confirm message when value is JSON string
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
