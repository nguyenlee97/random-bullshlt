"""Structured Responses generation owned by the OpenAI campaign component."""
from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel

from agent_logger import alog
from config import config
from openai_campaign.client import get_client, safety_identifier


T = TypeVar("T", bound=BaseModel)


def _usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if hasattr(usage, "model_dump"):
        raw = usage.model_dump(mode="json")
    elif isinstance(usage, dict):
        raw = usage
    else:
        raw = {
            "input_tokens": getattr(usage, "input_tokens", 0),
            "output_tokens": getattr(usage, "output_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }
    return {
        key: int(raw.get(key) or 0)
        for key in ("input_tokens", "output_tokens", "total_tokens")
    }


async def generate_structured(
    *,
    session_id: str,
    instructions: str,
    input_data: str | list[dict],
    schema: type[T],
    schema_name: str,
    max_output_tokens: int = 1600,
    client: Any | None = None,
) -> tuple[T, dict]:
    """Generate one schema-validated result without importing GreenNode code."""
    started = time.perf_counter()
    api = client or get_client()
    response = await api.responses.parse(
        model=config.OPENAI_CAMPAIGN_MODEL,
        instructions=instructions,
        input=input_data,
        text_format=schema,
        reasoning={"effort": config.OPENAI_CAMPAIGN_REASONING_EFFORT},
        max_output_tokens=min(
            max_output_tokens, config.OPENAI_CAMPAIGN_MAX_OUTPUT_TOKENS,
        ),
        store=False,
        safety_identifier=safety_identifier(session_id),
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise RuntimeError(f"OpenAI returned no structured {schema_name}")
    provenance = {
        "provider": "openai",
        "model": config.OPENAI_CAMPAIGN_MODEL,
        "response_id": getattr(response, "id", None),
        "schema": schema_name,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        **_usage(response),
    }
    await alog(session_id, "openai_structured_call", provenance)
    return parsed, provenance
