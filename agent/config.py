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
    # Provider resilience. The SDK performs at most one retry inside the
    # request deadline; the circuit breaker prevents a failing provider from
    # stalling every request during an outage.
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "1"))
    LLM_CIRCUIT_FAILURE_THRESHOLD: int = int(
        os.getenv("LLM_CIRCUIT_FAILURE_THRESHOLD", "3")
    )
    LLM_CIRCUIT_COOLDOWN_SECONDS: float = float(
        os.getenv("LLM_CIRCUIT_COOLDOWN_SECONDS", "30")
    )
    # Cross-provider fallback is opt-in because prompts can contain campaign
    # and customer data. Both the switch and classification allow-list must
    # permit it. Blank endpoint/model means no fallback client exists.
    ALLOW_OFFSHORE_LLM_FALLBACK: bool = (
        os.getenv("ALLOW_OFFSHORE_LLM_FALLBACK", "false").lower() == "true"
    )
    DATA_CLASSIFICATION: str = os.getenv("DATA_CLASSIFICATION", "confidential").lower()
    LLM_FALLBACK_ALLOWED_CLASSIFICATIONS: tuple[str, ...] = tuple(
        item.strip().lower()
        for item in os.getenv(
            "LLM_FALLBACK_ALLOWED_CLASSIFICATIONS", "public,internal"
        ).split(",")
        if item.strip()
    )
    LLM_FALLBACK_BASE_URL: str = os.getenv("LLM_FALLBACK_BASE_URL", "")
    LLM_FALLBACK_API_KEY: str = os.getenv("LLM_FALLBACK_API_KEY", "")
    LLM_FALLBACK_MODEL: str = os.getenv("LLM_FALLBACK_MODEL", "")

    # ── VPS Backend API ───────────────────────────────────────────────────────
    BACKEND_URL: str = os.getenv("BACKEND_URL", "https://api.pawgrammers.io.vn")

    # ── MongoDB (VPS, Option A: port exposed) ─────────────────────────────────
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "camp_ads")
    # Separates local/staging judge artifacts from any real campaign namespace.
    DEMO_NAMESPACE: str = os.getenv("DEMO_NAMESPACE", "local-demo")

    # ── Session ───────────────────────────────────────────────────────────────
    # Matches n8n prototype contextWindowLength: 18
    CONTEXT_WINDOW: int = int(os.getenv("CONTEXT_WINDOW", "18"))

    # ── Agent server ──────────────────────────────────────────────────────────
    AGENT_HOST: str = os.getenv("AGENT_HOST", "0.0.0.0")
    AGENT_PORT: int = int(os.getenv("AGENT_PORT", "8080"))
    MAX_AGENT_REQUEST_BYTES: int = int(
        os.getenv("MAX_AGENT_REQUEST_BYTES", str(2 * 1024 * 1024))
    )
    MAX_CHAT_MESSAGE_CHARS: int = int(os.getenv("MAX_CHAT_MESSAGE_CHARS", "12000"))

    # ── Security (Phase 0) ────────────────────────────────────────────────────
    # Empty AGENT_API_KEY = auth middleware disabled (no-op). Set in .env to enable.
    AGENT_API_KEY: str = os.getenv("AGENT_API_KEY", "")
    # Server-side order budget ceiling in VND — order_guard hard limit.
    MAX_ORDER_BUDGET_VND: int = int(os.getenv("MAX_ORDER_BUDGET_VND", "5000000000"))
    # Session TTL in days (Mongo TTL index on agent_sessions.last_active).
    SESSION_TTL_DAYS: int = int(os.getenv("SESSION_TTL_DAYS", "30"))

    # ── Phase 1: LangGraph (production-plan/02) ───────────────────────────────
    # Strangler flag: false = original freeform.py path (default, safe);
    # true = LangGraph graph path (flip only after parity run passes).
    USE_LANGGRAPH_FREEFORM: bool = os.getenv("USE_LANGGRAPH_FREEFORM", "false").lower() == "true"
    # Hard token cap per chat request — agentic loop can never spend unbounded.
    TOKEN_BUDGET_PER_REQUEST: int = int(os.getenv("TOKEN_BUDGET_PER_REQUEST", "60000"))
    # Durable Campaign Autopilot worker. The API remains available while the
    # flag is false, but no background task is claimed automatically.
    USE_CAMPAIGN_AUTOPILOT: bool = (
        os.getenv("USE_CAMPAIGN_AUTOPILOT", "false").lower() == "true"
    )
    AUTOPILOT_WORKER_POLL_SECONDS: float = float(
        os.getenv("AUTOPILOT_WORKER_POLL_SECONDS", "0.5")
    )
    AUTOPILOT_TASK_LEASE_SECONDS: int = int(
        os.getenv("AUTOPILOT_TASK_LEASE_SECONDS", "90")
    )
    AUTOPILOT_TASK_MAX_ATTEMPTS: int = int(
        os.getenv("AUTOPILOT_TASK_MAX_ATTEMPTS", "3")
    )
    AUTOPILOT_MAX_GENERATED_ASSETS: int = int(
        os.getenv("AUTOPILOT_MAX_GENERATED_ASSETS", "3")
    )
    AUTOPILOT_CREATIVE_GENERATION_CONCURRENCY: int = int(
        os.getenv("AUTOPILOT_CREATIVE_GENERATION_CONCURRENCY", "2")
    )
    # Critic / judge model (different family+provider than generator — see ADR).
    CRITIC_BASE_URL: str = os.getenv("CRITIC_BASE_URL", "")
    CRITIC_API_KEY: str = os.getenv("CRITIC_API_KEY", "") or os.getenv("JUDGE_API_KEY", "")
    CRITIC_MODEL: str = os.getenv("CRITIC_MODEL", "")

    # ── Phase 2: RAG audience recommendation (production-plan/03) ─────────────
    # false = old prompt-stuffing path; true = retrieve→rerank→LLM pipeline.
    USE_RAG_AUDIENCE: bool = os.getenv("USE_RAG_AUDIENCE", "false").lower() == "true"
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    RAG_COLLECTION: str = os.getenv("RAG_COLLECTION", "dmp_segments")
    # fastembed model names (ONNX, CPU-friendly; bge-m3 is the documented upgrade)
    RAG_DENSE_MODEL: str = os.getenv(
        "RAG_DENSE_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    RAG_SPARSE_MODEL: str = os.getenv("RAG_SPARSE_MODEL", "Qdrant/bm25")
    RAG_TOP_RETRIEVE: int = int(os.getenv("RAG_TOP_RETRIEVE", "50"))
    RAG_TOP_FINAL: int = int(os.getenv("RAG_TOP_FINAL", "25"))
    # Keep model-assisted ranking stages independently controllable. Retrieval
    # remains available if a provider regresses or is temporarily unavailable.
    RAG_QUERY_REWRITE: bool = os.getenv("RAG_QUERY_REWRITE", "false").lower() == "true"
    RAG_USE_RERANK: bool = os.getenv("RAG_USE_RERANK", "false").lower() == "true"
    RAG_USE_CRITIC_SELECTOR: bool = (
        os.getenv("RAG_USE_CRITIC_SELECTOR", "false").lower() == "true")
    # GreenNode MaaS reranker (from docs/maas-catalog.md). Empty model = skip rerank.
    RERANK_URL: str = os.getenv("RERANK_URL", "")     # e.g. <LLM_BASE_URL>/rerank
    RERANK_MODEL: str = os.getenv("RERANK_MODEL", "")

    # ── Phase 3: Creative intelligence (production-plan/04) ───────────────────
    # Deterministic pass (PIL) always runs when enabled; VLM pass only if
    # VLM_MODEL set (probe with scripts/probe_vlm.py — needs a vision-capable
    # MaaS model, e.g. google/gemma-4-31b-it if it accepts image_url).
    USE_VLM_CREATIVE: bool = os.getenv("USE_VLM_CREATIVE", "false").lower() == "true"
    VLM_BASE_URL: str = os.getenv("VLM_BASE_URL", "")     # empty = LLM_BASE_URL
    VLM_API_KEY: str = os.getenv("VLM_API_KEY", "")       # empty = AI_PLATFORM_API_KEY
    VLM_MODEL: str = os.getenv("VLM_MODEL", "")           # empty = deterministic-only
    # Below this confidence (or any safety flag) → needs_review, not auto-approve
    VLM_CONFIDENCE_THRESHOLD: float = float(os.getenv("VLM_CONFIDENCE_THRESHOLD", "0.8"))
    CREATIVE_ANALYSIS_TIMEOUT_SECONDS: float = float(
        os.getenv("CREATIVE_ANALYSIS_TIMEOUT_SECONDS", "15"))
    CREATIVE_WORKER_POLL_SECONDS: float = float(
        os.getenv("CREATIVE_WORKER_POLL_SECONDS", "0.5"))
    CREATIVE_WORKER_CONCURRENCY: int = int(
        os.getenv("CREATIVE_WORKER_CONCURRENCY", "6"))
    CREATIVE_JOB_STALE_SECONDS: int = int(
        os.getenv("CREATIVE_JOB_STALE_SECONDS", "90"))

    # ── Debug ─────────────────────────────────────────────────────────────────
    # Set AGENT_DEBUG=true in .env to dump full LLM prompts + responses to stdout.
    # Useful for diagnosing LLM output mismatches. Keep false in production.
    AGENT_DEBUG: bool = os.getenv("AGENT_DEBUG", "false").lower() == "true"

    # ── CORS origins ──────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS",
        "https://agent.pawgrammers.io.vn,"
        "http://localhost:5176,http://localhost:5175,http://localhost:5174,http://localhost:5173,"
        "http://localhost:3000,http://127.0.0.1:5175,http://127.0.0.1:5173",
    ).split(",")
    CORS_ALLOW_TUNNELS: bool = (
        os.getenv("CORS_ALLOW_TUNNELS", "false").lower() == "true"
    )


config = Config()
