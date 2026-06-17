"""
E4b Agent Backend — Configuration
All settings loaded from environment variables / .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── GreenNode MaaS (LLM) ─────────────────────────────────────────────────
    AI_PLATFORM_API_KEY: str = os.getenv("AI_PLATFORM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv(
        "LLM_BASE_URL",
        "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1",
    )
    LLM_MODEL: str = os.getenv("LLM_MODEL", "minimax/minimax-m2.5")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))

    # ── VPS Backend API ───────────────────────────────────────────────────────
    BACKEND_URL: str = os.getenv("BACKEND_URL", "https://api.pawgrammers.io.vn")

    # ── MongoDB (VPS, Option A: port exposed) ─────────────────────────────────
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "camp_ads")

    # ── Session ───────────────────────────────────────────────────────────────
    # Matches n8n prototype contextWindowLength: 18
    CONTEXT_WINDOW: int = int(os.getenv("CONTEXT_WINDOW", "18"))

    # ── Agent server ──────────────────────────────────────────────────────────
    AGENT_HOST: str = os.getenv("AGENT_HOST", "0.0.0.0")
    AGENT_PORT: int = int(os.getenv("AGENT_PORT", "8080"))

    # ── CORS origins ──────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS",
        "https://agent.pawgrammers.io.vn,"
        "http://localhost:5176,http://localhost:5175,http://localhost:5174,http://localhost:5173,"
        "http://localhost:3000,http://127.0.0.1:5175,http://127.0.0.1:5173",
    ).split(",")


config = Config()
