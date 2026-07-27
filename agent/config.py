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
    # The existing GreenNode campaign flow and the new OpenAI flow are
    # independently selectable. Availability flags are explicit so a revoked
    # key can remain visible as temporarily unavailable without being removed.
    GREENNODE_CAMPAIGN_ENABLED: bool = (
        os.getenv("GREENNODE_CAMPAIGN_ENABLED", "true").lower() == "true"
    )
    OPENAI_CAMPAIGN_ENABLED: bool = (
        os.getenv("OPENAI_CAMPAIGN_ENABLED", "false").lower() == "true"
    )
    OPENAI_CAMPAIGN_MODEL: str = os.getenv(
        "OPENAI_CAMPAIGN_MODEL", "gpt-5.4-mini"
    )
    OPENAI_CAMPAIGN_REASONING_EFFORT: str = os.getenv(
        "OPENAI_CAMPAIGN_REASONING_EFFORT", "low"
    )
    OPENAI_CAMPAIGN_MAX_OUTPUT_TOKENS: int = int(
        os.getenv("OPENAI_CAMPAIGN_MAX_OUTPUT_TOKENS", "2000")
    )
    OPENAI_CAMPAIGN_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENAI_CAMPAIGN_TIMEOUT_SECONDS", "45")
    )
    OPENAI_CAMPAIGN_MAX_RETRIES: int = int(
        os.getenv("OPENAI_CAMPAIGN_MAX_RETRIES", "1")
    )
    OPENAI_CAMPAIGN_MAX_TOOL_ROUNDS: int = int(
        os.getenv("OPENAI_CAMPAIGN_MAX_TOOL_ROUNDS", "4")
    )
    OPENAI_CAMPAIGN_MAX_TOOL_CALLS: int = int(
        os.getenv("OPENAI_CAMPAIGN_MAX_TOOL_CALLS", "4")
    )
    # NP-6 placement reranking is an independent, bounded experiment. It does
    # not select or change either campaign conversation engine.
    PLACEMENT_RERANK_ENABLED: bool = (
        os.getenv("PLACEMENT_RERANK_ENABLED", "false").lower() == "true"
    )
    PLACEMENT_RERANK_MODEL: str = os.getenv(
        "PLACEMENT_RERANK_MODEL", "gpt-5.4-nano"
    )
    PLACEMENT_RERANK_REASONING_EFFORT: str = os.getenv(
        "PLACEMENT_RERANK_REASONING_EFFORT", "low"
    )
    PLACEMENT_RERANK_CANDIDATE_LIMIT: int = int(
        os.getenv("PLACEMENT_RERANK_CANDIDATE_LIMIT", "12")
    )
    PLACEMENT_RERANK_MAX_OUTPUT_TOKENS: int = int(
        os.getenv("PLACEMENT_RERANK_MAX_OUTPUT_TOKENS", "3000")
    )
    PLACEMENT_RERANK_TIMEOUT_SECONDS: float = float(
        os.getenv("PLACEMENT_RERANK_TIMEOUT_SECONDS", "20")
    )
    # Placement retrieval is intentionally independent from audience RAG and
    # from both campaign conversation engines. The catalog is small enough to
    # keep a versioned dense+BM25 index in process; failures fall back to the
    # existing deterministic scorer.
    PLACEMENT_RAG_ENABLED: bool = (
        os.getenv("PLACEMENT_RAG_ENABLED", "false").lower() == "true"
    )
    PLACEMENT_RAG_RETRIEVE_LIMIT: int = int(
        os.getenv("PLACEMENT_RAG_RETRIEVE_LIMIT", "30")
    )
    PLACEMENT_RAG_CONTEXT_LIMIT: int = int(
        os.getenv("PLACEMENT_RAG_CONTEXT_LIMIT", "6")
    )
    PLACEMENT_RAG_SEMANTIC_THRESHOLD: float = float(
        os.getenv("PLACEMENT_RAG_SEMANTIC_THRESHOLD", "0.42")
    )
    PLACEMENT_RAG_MAX_QUERIES: int = int(
        os.getenv("PLACEMENT_RAG_MAX_QUERIES", "4")
    )
    PLACEMENT_RAG_EMBEDDING_MODEL: str = os.getenv(
        "PLACEMENT_RAG_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    PLACEMENT_RAG_EMBEDDING_TIMEOUT_SECONDS: float = float(
        os.getenv("PLACEMENT_RAG_EMBEDDING_TIMEOUT_SECONDS", "30")
    )
    PLACEMENT_RAG_TOPIC_RERANK_THRESHOLD: float = float(
        os.getenv("PLACEMENT_RAG_TOPIC_RERANK_THRESHOLD", "0.35")
    )
    OPENAI_IMAGE_ENABLED: bool = (
        os.getenv("OPENAI_IMAGE_ENABLED", "true").lower() == "true"
    )
    OPENAI_IMAGE_MODEL: str = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    OPENAI_IMAGE_QUALITY: str = os.getenv("OPENAI_IMAGE_QUALITY", "medium")
    OPENAI_IMAGE_TIMEOUT_SECONDS: float = float(
        os.getenv("OPENAI_IMAGE_TIMEOUT_SECONDS", "180")
    )
    OPENAI_VLM_MODEL: str = os.getenv("OPENAI_VLM_MODEL", "gpt-5.4-mini")
    DEFAULT_CONVERSATION_MODEL: str = os.getenv(
        "DEFAULT_CONVERSATION_MODEL", "greennode_minimax"
    )

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
    ANONYMOUS_COOKIE_SECURE: bool = (
        os.getenv("ANONYMOUS_COOKIE_SECURE", "false").lower() == "true"
    )
    ANONYMOUS_COOKIE_MAX_AGE_DAYS: int = int(
        os.getenv("ANONYMOUS_COOKIE_MAX_AGE_DAYS", "90")
    )
    ACCOUNT_COOKIE_SECURE: bool = (
        os.getenv(
            "ACCOUNT_COOKIE_SECURE",
            os.getenv("ANONYMOUS_COOKIE_SECURE", "false"),
        ).lower() == "true"
    )
    ACCOUNT_SESSION_MAX_AGE_DAYS: int = int(
        os.getenv("ACCOUNT_SESSION_MAX_AGE_DAYS", "30")
    )
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = int(
        os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300")
    )
    AUTH_REGISTER_IP_LIMIT: int = int(os.getenv("AUTH_REGISTER_IP_LIMIT", "5"))
    AUTH_REGISTER_ACCOUNT_LIMIT: int = int(
        os.getenv("AUTH_REGISTER_ACCOUNT_LIMIT", "3")
    )
    AUTH_LOGIN_IP_LIMIT: int = int(os.getenv("AUTH_LOGIN_IP_LIMIT", "20"))
    AUTH_LOGIN_ACCOUNT_LIMIT: int = int(
        os.getenv("AUTH_LOGIN_ACCOUNT_LIMIT", "10")
    )

    # ── Additive quality data + staged guardrails ─────────────────────────
    # Quality writes never control campaign execution. Existing deterministic
    # guard enforcement remains independently enabled.
    QUALITY_DATA_ENABLED: bool = (
        os.getenv("QUALITY_DATA_ENABLED", "true").lower() == "true"
    )
    QUALITY_EVENT_TIMEOUT_MS: int = int(
        os.getenv("QUALITY_EVENT_TIMEOUT_MS", "250")
    )
    QUALITY_INTERACTION_RETENTION_DAYS: int = int(
        os.getenv("QUALITY_INTERACTION_RETENTION_DAYS", "90")
    )
    QUALITY_EVENT_RETENTION_DAYS: int = int(
        os.getenv("QUALITY_EVENT_RETENTION_DAYS", "90")
    )
    QUALITY_FEEDBACK_RETENTION_DAYS: int = int(
        os.getenv("QUALITY_FEEDBACK_RETENTION_DAYS", "180")
    )
    QUALITY_FEEDBACK_ALLOW_MEMORY_FALLBACK: bool = (
        os.getenv("QUALITY_FEEDBACK_ALLOW_MEMORY_FALLBACK", "false").lower()
        == "true"
    )
    GUARDRAIL_MODE: str = os.getenv("GUARDRAIL_MODE", "enforce").lower()
    GUARDRAIL_POLICY_VERSION: str = os.getenv(
        "GUARDRAIL_POLICY_VERSION", "guard-policy-v1"
    )
    GUARDRAIL_NEW_RULE_MODE: str = os.getenv(
        "GUARDRAIL_NEW_RULE_MODE", "shadow"
    ).lower()
    GUARDRAIL_MAX_FINDINGS: int = int(
        os.getenv("GUARDRAIL_MAX_FINDINGS", "5")
    )
    GUARDRAIL_MAX_EXCERPT_CHARS: int = int(
        os.getenv("GUARDRAIL_MAX_EXCERPT_CHARS", "500")
    )
    GUARDRAIL_TOOL_OUTPUT_SHADOW: bool = (
        os.getenv("GUARDRAIL_TOOL_OUTPUT_SHADOW", "false").lower() == "true"
    )
    GUARDRAIL_FINAL_OUTPUT_SHADOW: bool = (
        os.getenv("GUARDRAIL_FINAL_OUTPUT_SHADOW", "false").lower() == "true"
    )

    # Zalo Login uses the Social OAuth v4 endpoints.  It deliberately mints the
    # same opaque Advertising Agent session as local login; Zalo tokens never
    # become browser/session credentials and are not persisted.
    ZALO_LOGIN_ENABLED: bool = (
        os.getenv("ZALO_LOGIN_ENABLED", "false").lower() == "true"
    )
    ZALO_APP_ID: str = os.getenv("ZALO_APP_ID", "")
    ZALO_APP_SECRET: str = os.getenv("ZALO_APP_SECRET", "")
    ZALO_LOGIN_REDIRECT_URI: str = os.getenv(
        "ZALO_LOGIN_REDIRECT_URI",
        "https://agent.pawgrammers.io.vn/agent/api/agent/auth/zalo/callback",
    )
    ZALO_LOGIN_PERMISSION_URL: str = os.getenv(
        "ZALO_LOGIN_PERMISSION_URL", "https://oauth.zaloapp.com/v4/permission"
    )
    ZALO_LOGIN_TOKEN_URL: str = os.getenv(
        "ZALO_LOGIN_TOKEN_URL", "https://oauth.zaloapp.com/v4/access_token"
    )
    ZALO_PROFILE_URL: str = os.getenv(
        "ZALO_PROFILE_URL", "https://graph.zalo.me/v2.0/me"
    )
    ZALO_OAUTH_ATTEMPT_TTL_SECONDS: int = int(
        os.getenv("ZALO_OAUTH_ATTEMPT_TTL_SECONDS", "600")
    )

    # OA transport is independently gated so Zalo Login can ship before the OA
    # webhook is moved from another application.  Signature verification always
    # fails closed when this switch is enabled and the OA secret is missing.
    ZALO_OA_ENABLED: bool = os.getenv("ZALO_OA_ENABLED", "false").lower() == "true"
    ZALO_OA_ID: str = os.getenv("ZALO_OA_ID", "")
    ZALO_OA_NAME: str = os.getenv("ZALO_OA_NAME", "IOT Generation")
    ZALO_OA_SECRET: str = os.getenv("ZALO_OA_SECRET", "")
    # OA OpenAPI credentials are server-only. The initial pair seeds a
    # root-readable token store; rotated refresh tokens are written there so a
    # process restart never falls back to an already-consumed refresh token.
    ZALO_OA_ACCESS_TOKEN: str = os.getenv("ZALO_OA_ACCESS_TOKEN", "")
    ZALO_OA_REFRESH_TOKEN: str = os.getenv("ZALO_OA_REFRESH_TOKEN", "")
    ZALO_OA_TOKEN_STORE_PATH: str = os.getenv("ZALO_OA_TOKEN_STORE_PATH", "")
    ZALO_OA_TOKEN_URL: str = os.getenv(
        "ZALO_OA_TOKEN_URL", "https://oauth.zaloapp.com/v4/oa/access_token"
    )
    ZALO_OA_API_BASE_URL: str = os.getenv(
        "ZALO_OA_API_BASE_URL", "https://openapi.zalo.me/v3.0/oa"
    ).rstrip("/")
    ZALO_OA_RECOVERY_MAX_USERS: int = int(
        os.getenv("ZALO_OA_RECOVERY_MAX_USERS", "500")
    )
    ZALO_OA_RECOVERY_CONCURRENCY: int = int(
        os.getenv("ZALO_OA_RECOVERY_CONCURRENCY", "6")
    )
    # Durable inbound-turn and outbound-delivery workers. Keep these separate
    # from webhook verification so operators can pause sends while the public
    # endpoint continues acknowledging and queueing signed events.
    ZALO_AGENT_WORKER_ENABLED: bool = (
        os.getenv("ZALO_AGENT_WORKER_ENABLED", "false").lower() == "true"
    )
    ZALO_OUTBOUND_ENABLED: bool = (
        os.getenv("ZALO_OUTBOUND_ENABLED", "false").lower() == "true"
    )
    # Zalo's conversational planner uses the official OpenAI Responses API.
    # This is deliberately separate from the GreenNode model used elsewhere.
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ZALO_OPENAI_ENABLED: bool = (
        os.getenv("ZALO_OPENAI_ENABLED", "false").lower() == "true"
    )
    ZALO_CHAT_MODEL: str = os.getenv("ZALO_CHAT_MODEL", "gpt-5.4-mini")
    # New Zalo-created campaign runs use this explicit channel policy instead
    # of inheriting DEFAULT_CONVERSATION_MODEL. Existing runs keep their lock.
    ZALO_AUTOPILOT_CONVERSATION_MODEL: str = os.getenv(
        "ZALO_AUTOPILOT_CONVERSATION_MODEL", "greennode_minimax"
    )
    ZALO_CHAT_REASONING_EFFORT: str = os.getenv(
        "ZALO_CHAT_REASONING_EFFORT", "low"
    )
    ZALO_CHAT_MAX_OUTPUT_TOKENS: int = int(
        os.getenv("ZALO_CHAT_MAX_OUTPUT_TOKENS", "1200")
    )
    ZALO_CHAT_TIMEOUT_SECONDS: float = float(
        os.getenv("ZALO_CHAT_TIMEOUT_SECONDS", "45")
    )
    ZALO_CHAT_MAX_RETRIES: int = int(
        os.getenv("ZALO_CHAT_MAX_RETRIES", "1")
    )
    # Channel-native conversational context. The permanent OA thread is split
    # into bounded chat sessions without changing the canonical conversation.
    ZALO_CHAT_SESSION_MAX_MINUTES: int = int(
        os.getenv("ZALO_CHAT_SESSION_MAX_MINUTES", "60")
    )
    ZALO_CHAT_SESSION_IDLE_MINUTES: int = int(
        os.getenv("ZALO_CHAT_SESSION_IDLE_MINUTES", "20")
    )
    ZALO_CONTEXT_MAX_MESSAGES: int = int(
        os.getenv("ZALO_CONTEXT_MAX_MESSAGES", "30")
    )
    ZALO_CONTEXT_MAX_INPUT_TOKENS: int = int(
        os.getenv("ZALO_CONTEXT_MAX_INPUT_TOKENS", "24000")
    )
    ZALO_CONTEXT_MAX_MESSAGE_TOKENS: int = int(
        os.getenv("ZALO_CONTEXT_MAX_MESSAGE_TOKENS", "6000")
    )
    ZALO_CONTEXT_MAX_TOOL_TOKENS: int = int(
        os.getenv("ZALO_CONTEXT_MAX_TOOL_TOKENS", "8000")
    )
    ZALO_CONTEXT_MAX_SUMMARY_TOKENS: int = int(
        os.getenv("ZALO_CONTEXT_MAX_SUMMARY_TOKENS", "1200")
    )
    ZALO_CHAT_MAX_TOOL_ROUNDS: int = int(
        os.getenv("ZALO_CHAT_MAX_TOOL_ROUNDS", "5")
    )
    ZALO_CHAT_MAX_TOOL_CALLS: int = int(
        os.getenv("ZALO_CHAT_MAX_TOOL_CALLS", "8")
    )
    ZALO_SUMMARY_MESSAGE_INTERVAL: int = int(
        os.getenv("ZALO_SUMMARY_MESSAGE_INTERVAL", "8")
    )
    ZALO_SUMMARY_TOKEN_INTERVAL: int = int(
        os.getenv("ZALO_SUMMARY_TOKEN_INTERVAL", "4000")
    )
    ZALO_WORKER_POLL_SECONDS: float = float(
        os.getenv("ZALO_WORKER_POLL_SECONDS", "1.0")
    )
    ZALO_WORKER_LEASE_SECONDS: int = int(
        os.getenv("ZALO_WORKER_LEASE_SECONDS", "180")
    )
    ZALO_WORKER_MAX_ATTEMPTS: int = int(
        os.getenv("ZALO_WORKER_MAX_ATTEMPTS", "5")
    )
    ZALO_WEB_WORKSPACE_URL: str = os.getenv(
        "ZALO_WEB_WORKSPACE_URL", "https://agent.pawgrammers.io.vn"
    ).rstrip("/")
    ZALO_PUBLIC_API_URL: str = os.getenv(
        "ZALO_PUBLIC_API_URL",
        "https://agent.pawgrammers.io.vn/agent/api/agent",
    ).rstrip("/")
    ZALO_MEDIA_TTL_SECONDS: int = int(
        os.getenv("ZALO_MEDIA_TTL_SECONDS", "900")
    )
    ZALO_WEBHOOK_MAX_SKEW_SECONDS: int = int(
        os.getenv("ZALO_WEBHOOK_MAX_SKEW_SECONDS", "600")
    )
    ZALO_CHANNEL_LINK_TTL_SECONDS: int = int(
        os.getenv("ZALO_CHANNEL_LINK_TTL_SECONDS", "600")
    )

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
    AUDIENCE_RAG_RETRIEVAL_MODE: str = os.getenv(
        "AUDIENCE_RAG_RETRIEVAL_MODE", "hybrid_dense_bm25"
    )
    AUDIENCE_RERANK_MODE: str = os.getenv(
        "AUDIENCE_RERANK_MODE",
        "legacy" if os.getenv("RAG_USE_RERANK", "false").lower() == "true" else "off",
    ).lower()
    AUDIENCE_NANO_RERANK_MODEL: str = os.getenv(
        "AUDIENCE_NANO_RERANK_MODEL", "gpt-5.4-nano"
    )
    AUDIENCE_NANO_RERANK_REASONING_EFFORT: str = os.getenv(
        "AUDIENCE_NANO_RERANK_REASONING_EFFORT", "low"
    )
    AUDIENCE_NANO_RERANK_CANDIDATE_LIMIT: int = int(
        os.getenv("AUDIENCE_NANO_RERANK_CANDIDATE_LIMIT", "30")
    )
    AUDIENCE_NANO_RERANK_MAX_OUTPUT_TOKENS: int = int(
        os.getenv("AUDIENCE_NANO_RERANK_MAX_OUTPUT_TOKENS", "3500")
    )
    AUDIENCE_NANO_RERANK_TIMEOUT_SECONDS: float = float(
        os.getenv("AUDIENCE_NANO_RERANK_TIMEOUT_SECONDS", "30")
    )
    OPENAI_AUDIENCE_MIN_RELEVANCE_SCORE: float = float(
        os.getenv("OPENAI_AUDIENCE_MIN_RELEVANCE_SCORE", "0.45")
    )
    OPENAI_AUDIENCE_RERANK_CANDIDATE_LIMIT: int = int(
        os.getenv("OPENAI_AUDIENCE_RERANK_CANDIDATE_LIMIT", "50")
    )
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

if config.GUARDRAIL_MODE not in {"off", "shadow", "enforce"}:
    raise ValueError("GUARDRAIL_MODE must be off, shadow, or enforce")
if config.GUARDRAIL_NEW_RULE_MODE not in {"off", "shadow", "enforce"}:
    raise ValueError("GUARDRAIL_NEW_RULE_MODE must be off, shadow, or enforce")
if config.QUALITY_EVENT_TIMEOUT_MS < 10:
    raise ValueError("QUALITY_EVENT_TIMEOUT_MS must be at least 10")
if config.AUDIENCE_RAG_RETRIEVAL_MODE not in {
    "bm25_only", "dense_only", "hybrid_dense_bm25"
}:
    raise ValueError(
        "AUDIENCE_RAG_RETRIEVAL_MODE must be bm25_only, dense_only, "
        "or hybrid_dense_bm25"
    )
if config.AUDIENCE_RERANK_MODE not in {"off", "legacy", "openai_nano"}:
    raise ValueError(
        "AUDIENCE_RERANK_MODE must be off, legacy, or openai_nano"
    )
