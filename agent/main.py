"""
E4b Agent Backend — FastAPI app entry point.
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import config

app = FastAPI(
    title="Camp Ads Agent",
    version="1.0.0",
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
        "model": config.LLM_MODEL,
        "backend": config.BACKEND_URL,
        "db": config.MONGODB_DB,
    }


# Import router after app is created to avoid circular imports
from router import agent_router  # noqa: E402
app.include_router(agent_router, prefix="/api/agent")


if __name__ == "__main__":
    uvicorn.run("main:app", host=config.AGENT_HOST, port=config.AGENT_PORT, reload=True)
