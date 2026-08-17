"""Immutable conversational-model identities and public selection catalog."""
from __future__ import annotations

from datetime import datetime, timezone


GREENNODE_MINIMAX = "greennode_minimax"
OPENAI_GPT_5_4_MINI = "openai_gpt_5_4_mini"
SUPPORTED_CONVERSATION_MODELS = (
    GREENNODE_MINIMAX,
    OPENAI_GPT_5_4_MINI,
)
LEGACY_CONVERSATION_MODEL = GREENNODE_MINIMAX


def normalize_conversation_model(
    value: str | None, *, allow_legacy_default: bool = False,
) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized and allow_legacy_default:
        return LEGACY_CONVERSATION_MODEL
    if normalized not in SUPPORTED_CONVERSATION_MODELS:
        raise ValueError("unsupported conversation_model")
    return normalized


def conversation_model_version(model: str) -> str:
    """Resolve the deployment model ID stored when a conversation is created."""
    from config import config

    normalized = normalize_conversation_model(model)
    if normalized == OPENAI_GPT_5_4_MINI:
        return config.OPENAI_CAMPAIGN_MODEL
    return config.LLM_MODEL


def locked_model_fields(model: str, *, locked_at: datetime | None = None) -> dict:
    normalized = normalize_conversation_model(model)
    return {
        "conversation_model": normalized,
        "conversation_model_locked_at": locked_at or datetime.now(timezone.utc),
        "conversation_model_version": conversation_model_version(normalized),
    }


def conversation_model_catalog() -> dict:
    """Return public readiness without exposing provider credentials."""
    from config import config

    greennode_available = bool(
        config.GREENNODE_CAMPAIGN_ENABLED and config.AI_PLATFORM_API_KEY
    )
    # The OpenAI option stays unavailable until the independent engine marks
    # itself implemented as well as configured. This prevents a selectable
    # conversation from falling through to GreenNode while the new path is built.
    try:
        from openai_campaign.engine import openai_campaign_ready
        openai_available = bool(openai_campaign_ready())
    except Exception:
        openai_available = False

    models = [
        {
            "id": GREENNODE_MINIMAX,
            "label": "GreenNode — MiniMax M2.5",
            "description": "Luồng GreenNode hiện tại, được giữ nguyên độc lập.",
            "available": greennode_available,
            "status": "available" if greennode_available else "temporarily_unavailable",
            "reason": None if greennode_available else "provider_disabled",
        },
        {
            "id": OPENAI_GPT_5_4_MINI,
            "label": "OpenAI — GPT-5.4 mini",
            "description": "Luồng OpenAI độc lập cho toàn bộ hội thoại campaign.",
            "available": openai_available,
            "status": "available" if openai_available else "coming_soon",
            "reason": None if openai_available else "engine_not_ready",
        },
    ]
    configured_default = normalize_conversation_model(
        config.DEFAULT_CONVERSATION_MODEL, allow_legacy_default=True,
    )
    selectable_ids = {item["id"] for item in models if item["available"]}
    default_model = (
        configured_default if configured_default in selectable_ids
        else next((item["id"] for item in models if item["available"]), None)
    )
    return {"models": models, "default_model": default_model}


def conversation_model_is_available(model: str) -> bool:
    normalized = normalize_conversation_model(model)
    catalog = conversation_model_catalog()
    return any(
        item["id"] == normalized and item["available"]
        for item in catalog["models"]
    )
