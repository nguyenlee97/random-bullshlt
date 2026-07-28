"""OpenAI-only semantic query planning for catalog-backed audience retrieval."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from agent_logger import alog
from config import config
from openai_campaign.tracing import trace_responses_call


class AudienceSearchPlan(BaseModel):
    model_config = {"extra": "forbid"}

    industry_queries: list[str] = Field(default_factory=list, max_length=3)
    buyer_queries: list[str] = Field(default_factory=list, max_length=3)
    product_queries: list[str] = Field(default_factory=list, max_length=3)
    excluded_concepts: list[str] = Field(default_factory=list, max_length=6)
    creative_only_concepts: list[str] = Field(default_factory=list, max_length=6)


_client: AsyncOpenAI | None = None
_plan_cache: dict[str, dict] = {}


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=config.AUDIENCE_NANO_RERANK_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _client


def _safety_identifier(session_id: str) -> str:
    return "audience-plan-" + hashlib.sha256(
        session_id.encode("utf-8")
    ).hexdigest()[:24]


def _cache_key(brief: dict) -> str:
    payload = {
        key: brief.get(key)
        for key in ("brand", "objective", "kpi", "notes")
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _queries(plan: AudienceSearchPlan) -> list[str]:
    """Keep the six-query budget balanced across every planned signal.

    The former concatenation always spent the budget on industry and buyer
    terms first. A fully populated plan therefore dropped every product or
    technology query, which is especially damaging for niche B2B briefs.
    """
    groups = (
        plan.product_queries,
        plan.buyer_queries,
        plan.industry_queries,
    )
    selected: list[str] = []
    seen: set[str] = set()
    for index in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if index >= len(group):
                continue
            query = " ".join(str(group[index]).split())
            key = query.casefold()
            if not query or key in seen:
                continue
            seen.add(key)
            selected.append(query)
            if len(selected) >= 6:
                return selected
    return selected


def _query_specs(plan: AudienceSearchPlan, queries: list[str]) -> list[dict]:
    kinds: dict[str, str] = {}
    for kind, values in (
        ("product", plan.product_queries),
        ("buyer", plan.buyer_queries),
        ("industry", plan.industry_queries),
    ):
        for value in values:
            normalized = " ".join(str(value).split())
            if normalized:
                kinds.setdefault(normalized.casefold(), kind)
    return [
        {"query": query, "kind": kinds.get(query.casefold(), "rewrite")}
        for query in queries
    ]


async def plan_audience_search(
    session_id: str,
    brief: dict,
    *,
    client: Any | None = None,
) -> dict:
    """Return catalog search concepts, never selectable segment IDs."""
    if not config.OPENAI_API_KEY and client is None:
        return {"queries": [], "applied": False, "reason": "missing_credentials"}
    cache_key = _cache_key(brief)
    if client is None and cache_key in _plan_cache:
        cached = deepcopy(_plan_cache[cache_key])
        cached["cache_hit"] = True
        await alog(session_id, "openai_audience_search_plan", {
            "model": cached.get("model"),
            "query_count": len(cached.get("queries") or []),
            "queries": cached.get("query_specs") or cached.get("queries") or [],
            "excluded_concepts": cached.get("excluded_concepts") or [],
            "creative_only_concepts": cached.get("creative_only_concepts") or [],
            "cache_hit": True,
        })
        return cached

    instructions = """
Create a compact semantic search plan for an advertising audience catalog.
Understand unrestricted Vietnamese or English wording. Separate the actual
industry, product, and buyer roles from exclusions and creative-only imagery.

Queries must be short bilingual or English catalog concepts, not sentences.
They may describe industries, buyer roles, product categories, or technologies.
Never output audience IDs or claim that a catalog segment exists. Do not use a
creative scene, visual metaphor, location backdrop, or excluded audience as a
positive search query. Preserve explicit B2B versus consumer intent. Output
only the schema.
""".strip()
    payload = {
        "brief": {
            key: brief.get(key)
            for key in (
                "brand", "objective", "kpi", "notes",
            )
        },
    }
    try:
        api = client or _get_client()
        input_data = json.dumps(payload, ensure_ascii=False)
        max_output_tokens = min(
            config.AUDIENCE_NANO_RERANK_MAX_OUTPUT_TOKENS, 900,
        )
        request = {
            "model": config.AUDIENCE_NANO_RERANK_MODEL,
            "instructions": instructions,
            "input": input_data,
            "text_format": AudienceSearchPlan.model_json_schema(),
            "reasoning": {
                "effort": config.AUDIENCE_NANO_RERANK_REASONING_EFFORT,
            },
            "max_output_tokens": max_output_tokens,
            "store": False,
            "safety_identifier": _safety_identifier(session_id),
        }
        response = await trace_responses_call(
            name="openai.audience_search_plan",
            session_id=session_id,
            model=config.AUDIENCE_NANO_RERANK_MODEL,
            request=request,
            metadata={"schema": "audience_search_plan"},
            model_parameters={
                "reasoning_effort": (
                    config.AUDIENCE_NANO_RERANK_REASONING_EFFORT
                ),
                "max_output_tokens": max_output_tokens,
                "store": False,
            },
            call=lambda: api.responses.parse(
                model=config.AUDIENCE_NANO_RERANK_MODEL,
                instructions=instructions,
                input=input_data,
                text_format=AudienceSearchPlan,
                reasoning={
                    "effort": config.AUDIENCE_NANO_RERANK_REASONING_EFFORT,
                },
                max_output_tokens=max_output_tokens,
                store=False,
                safety_identifier=_safety_identifier(session_id),
            ),
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ValueError("missing structured output")
        queries = _queries(parsed)
        result = {
            "queries": queries,
            "query_specs": _query_specs(parsed, queries),
            "industry_queries": parsed.industry_queries,
            "buyer_queries": parsed.buyer_queries,
            "product_queries": parsed.product_queries,
            "excluded_concepts": parsed.excluded_concepts,
            "creative_only_concepts": parsed.creative_only_concepts,
            "applied": True,
            "model": config.AUDIENCE_NANO_RERANK_MODEL,
            "response_id": getattr(response, "id", None),
            "cache_hit": False,
        }
        if client is None:
            if len(_plan_cache) >= 128:
                _plan_cache.pop(next(iter(_plan_cache)))
            _plan_cache[cache_key] = deepcopy(result)
        await alog(session_id, "openai_audience_search_plan", {
            "model": result["model"],
            "query_count": len(result["queries"]),
            "queries": result["query_specs"],
            "industry_queries": result["industry_queries"],
            "buyer_queries": result["buyer_queries"],
            "product_queries": result["product_queries"],
            "excluded_concepts": result["excluded_concepts"],
            "creative_only_concepts": result["creative_only_concepts"],
            "excluded_count": len(result["excluded_concepts"]),
            "creative_only_count": len(result["creative_only_concepts"]),
            "response_id": result["response_id"],
            "cache_hit": False,
        })
        return result
    except Exception as exc:
        await alog(session_id, "warn", {
            "handler": "openai_audience_search_plan",
            "error_type": type(exc).__name__,
            "error": str(exc)[:200],
        })
        return {
            "queries": [],
            "applied": False,
            "reason": "provider_or_validation_failure",
            "error_type": type(exc).__name__,
        }


def reset_audience_search_for_test() -> None:
    global _client
    _client = None
    _plan_cache.clear()
