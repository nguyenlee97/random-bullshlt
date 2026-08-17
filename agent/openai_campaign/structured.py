"""Structured Responses generation owned by the OpenAI campaign component."""
from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel

from agent_logger import alog
from config import config
from openai_campaign.client import get_client, safety_identifier
from openai_campaign.tracing import response_usage, trace_responses_call


T = TypeVar("T", bound=BaseModel)


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
    bounded_max_tokens = min(
        max_output_tokens, config.OPENAI_CAMPAIGN_MAX_OUTPUT_TOKENS,
    )
    request = {
        "model": config.OPENAI_CAMPAIGN_MODEL,
        "instructions": instructions,
        "input": input_data,
        "text_format": schema.model_json_schema(),
        "reasoning": {"effort": config.OPENAI_CAMPAIGN_REASONING_EFFORT},
        "max_output_tokens": bounded_max_tokens,
        "store": False,
        "safety_identifier": safety_identifier(session_id),
    }
    response = await trace_responses_call(
        name=f"openai.structured.{schema_name}",
        session_id=session_id,
        model=config.OPENAI_CAMPAIGN_MODEL,
        request=request,
        metadata={"schema": schema_name},
        model_parameters={
            "reasoning_effort": config.OPENAI_CAMPAIGN_REASONING_EFFORT,
            "max_output_tokens": bounded_max_tokens,
            "store": False,
        },
        call=lambda: api.responses.parse(
            model=config.OPENAI_CAMPAIGN_MODEL,
            instructions=instructions,
            input=input_data,
            text_format=schema,
            reasoning={"effort": config.OPENAI_CAMPAIGN_REASONING_EFFORT},
            max_output_tokens=bounded_max_tokens,
            store=False,
            safety_identifier=safety_identifier(session_id),
        ),
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise RuntimeError(f"OpenAI returned no structured {schema_name}")
    usage = response_usage(response)
    provenance = {
        "provider": "openai",
        "model": config.OPENAI_CAMPAIGN_MODEL,
        "response_id": getattr(response, "id", None),
        "schema": schema_name,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "input_tokens": usage["input"],
        "output_tokens": usage["output"],
        "total_tokens": usage["total"],
    }
    await alog(session_id, "openai_structured_call", provenance)
    return parsed, provenance
