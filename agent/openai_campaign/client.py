"""Official OpenAI client owned only by the independent campaign engine."""
from __future__ import annotations

import hashlib

from openai import AsyncOpenAI

from config import config


_client: AsyncOpenAI | None = None


def configured() -> bool:
    return bool(
        config.OPENAI_CAMPAIGN_ENABLED
        and config.OPENAI_API_KEY
        and config.OPENAI_CAMPAIGN_MODEL
    )


def get_client() -> AsyncOpenAI:
    global _client
    if not configured():
        raise RuntimeError("OpenAI campaign engine is not configured")
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=config.OPENAI_CAMPAIGN_TIMEOUT_SECONDS,
            max_retries=config.OPENAI_CAMPAIGN_MAX_RETRIES,
        )
    return _client


def safety_identifier(session_id: str) -> str:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]
    return f"campaign_{digest}"


def reset_for_test() -> None:
    global _client
    _client = None
