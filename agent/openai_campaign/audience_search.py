"""OpenAI-only semantic query planning for catalog-backed audience retrieval."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from copy import deepcopy
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from agent_logger import alog
from config import config
from openai_campaign.tracing import trace_responses_call


class AudienceSearchPlan(BaseModel):
    model_config = {"extra": "forbid"}

    information_sufficient: bool = True
    insufficient_reason: str = Field(default="", max_length=240)
    industry_queries: list[str] = Field(default_factory=list, max_length=3)
    buyer_queries: list[str] = Field(default_factory=list, max_length=3)
    product_queries: list[str] = Field(default_factory=list, max_length=3)
    audience_queries: list[str] = Field(default_factory=list, max_length=3)
    excluded_concepts: list[str] = Field(default_factory=list, max_length=6)
    creative_only_concepts: list[str] = Field(default_factory=list, max_length=6)


_client: AsyncOpenAI | None = None
_plan_cache: dict[str, dict] = {}
_GENERIC_BRIEF_FOLDED_TOKENS = {
    "a", "an", "and", "awareness", "brand", "campaign", "customer",
    "customers", "for", "increase", "new", "objective", "people", "product",
    "reach", "suitable", "the", "to", "want",
    "cho", "chien", "dien", "dich", "doi", "gioi", "hang", "hieu", "hop",
    "khach", "moi", "muon", "nam", "nhan", "nhom", "nu", "pham", "phu",
    "quan", "san", "tam", "them", "thich", "tim", "tang", "thuong", "tuoi",
    "tuong",
}


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=config.AUDIENCE_QUERY_PLANNER_TIMEOUT_SECONDS,
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


def _brief_has_specific_signal(brief: dict) -> bool:
    """Reject only obviously content-free briefs before paying for planning.

    This is not a taxonomy alias table. It removes generic campaign boilerplate
    and requires at least two remaining content terms in KPI/notes. A brand
    name alone is deliberately excluded because it is not category evidence.
    """
    text = " ".join(
        str(brief.get(key) or "")
        for key in ("kpi", "notes")
    ).casefold()
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    tokens = [
        token for token in re.findall(r"[^\W_]+", text, flags=re.UNICODE)
        if len(token) > 1 and token not in _GENERIC_BRIEF_FOLDED_TOKENS
        and not token.isdigit()
    ]
    return len(set(tokens)) >= 2


def _queries(plan: AudienceSearchPlan) -> list[str]:
    """Keep the twelve-query budget balanced across every planned signal.

    The former concatenation always spent the budget on industry and buyer
    terms first. A fully populated plan therefore dropped every product or
    technology query, which is especially damaging for niche B2B briefs. The
    dedicated audience group prevents an explicit identity such as "expats"
    from being displaced by product and venue terms.
    """
    if not plan.information_sufficient:
        return []
    groups = (
        plan.product_queries,
        plan.audience_queries,
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
            if len(selected) >= 12:
                return selected
    return selected


def _query_specs(plan: AudienceSearchPlan, queries: list[str]) -> list[dict]:
    kinds: dict[str, str] = {}
    for kind, values in (
        ("product", plan.product_queries),
        ("audience", plan.audience_queries),
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
    if not _brief_has_specific_signal(brief):
        result = {
            "queries": [],
            "query_specs": [],
            "industry_queries": [],
            "buyer_queries": [],
            "product_queries": [],
            "audience_queries": [],
            "excluded_concepts": [],
            "creative_only_concepts": [],
            "information_sufficient": False,
            "insufficient_reason": "brief_missing_product_or_audience_evidence",
            "applied": True,
            "model": None,
            "response_id": None,
            "cache_hit": False,
            "preflight": True,
        }
        await alog(session_id, "openai_audience_search_plan", {
            "model": None,
            "query_count": 0,
            "queries": [],
            "information_sufficient": False,
            "insufficient_reason": result["insufficient_reason"],
            "cache_hit": False,
            "preflight": True,
        })
        return result
    cache_key = _cache_key(brief)
    if client is None and cache_key in _plan_cache:
        cached = deepcopy(_plan_cache[cache_key])
        cached["cache_hit"] = True
        await alog(session_id, "openai_audience_search_plan", {
            "model": cached.get("model"),
            "query_count": len(cached.get("queries") or []),
            "queries": cached.get("query_specs") or cached.get("queries") or [],
            "information_sufficient": cached.get("information_sufficient", True),
            "insufficient_reason": cached.get("insufficient_reason", ""),
            "audience_queries": cached.get("audience_queries") or [],
            "excluded_concepts": cached.get("excluded_concepts") or [],
            "creative_only_concepts": cached.get("creative_only_concepts") or [],
            "cache_hit": True,
        })
        return cached

    instructions = """
Create a compact semantic search plan for an advertising audience catalog.
Understand unrestricted Vietnamese or English wording. Separate the actual
industry, product, buyer roles, and explicitly named audience identities or
behaviors from exclusions and creative-only imagery.

First decide whether the brief contains enough evidence to identify at least
one real product/service, industry, intended buyer/user, or named audience.
Brand name, awareness/conversion objective, generic KPI, "new product", and
"find suitable customers" are not sufficient by themselves. When evidence is
insufficient, set information_sufficient=false, explain briefly, and return all
query lists empty. Never guess a business category from a brand name.

Queries must be short bilingual or English catalog concepts, not sentences.
They may describe industries, buyer roles, product categories, technologies,
or an explicit community/behavior such as expats. Preserve named audience
identities from the brief in audience_queries even when product or venue terms
are also strong. Every positive query must be grounded in supplied brief text;
never invent a product, industry, or buyer persona to fill the schema.
Never output audience IDs or claim that a catalog segment exists. Do not use a
creative scene, visual metaphor, location backdrop, or excluded audience as a
positive search query. Preserve explicit B2B versus consumer intent. Output
only the schema and keep every phrase under 12 words.
""".strip()
    payload = {
        "brief": {
            key: brief.get(key)
            for key in (
                "brand", "objective", "kpi", "notes",
            )
        },
    }
    api = client or _get_client()
    input_data = json.dumps(payload, ensure_ascii=False)
    response = None
    parsed = None
    last_error: Exception | None = None
    for attempt in range(2):
        max_output_tokens = min(
            config.AUDIENCE_QUERY_PLANNER_MAX_OUTPUT_TOKENS,
            1100 if attempt == 0 else 1400,
        )
        attempt_instructions = instructions + (
            "\nRetry: keep the JSON especially compact and complete."
            if attempt else ""
        )
        request = {
            "model": config.AUDIENCE_QUERY_PLANNER_MODEL,
            "instructions": attempt_instructions,
            "input": input_data,
            "text_format": AudienceSearchPlan.model_json_schema(),
            "reasoning": {
                "effort": config.AUDIENCE_QUERY_PLANNER_REASONING_EFFORT,
            },
            "max_output_tokens": max_output_tokens,
            "store": False,
            "safety_identifier": _safety_identifier(session_id),
        }
        try:
            response = await trace_responses_call(
                name=(
                    "openai.audience_search_plan"
                    if attempt == 0
                    else "openai.audience_search_plan_retry"
                ),
                session_id=session_id,
                model=config.AUDIENCE_QUERY_PLANNER_MODEL,
                request=request,
                metadata={
                    "schema": "audience_search_plan",
                    "attempt": attempt + 1,
                },
                model_parameters={
                    "reasoning_effort": (
                        config.AUDIENCE_QUERY_PLANNER_REASONING_EFFORT
                    ),
                    "max_output_tokens": max_output_tokens,
                    "store": False,
                },
                call=lambda: api.responses.parse(
                    model=config.AUDIENCE_QUERY_PLANNER_MODEL,
                    instructions=attempt_instructions,
                    input=input_data,
                    text_format=AudienceSearchPlan,
                    reasoning={
                        "effort": config.AUDIENCE_QUERY_PLANNER_REASONING_EFFORT,
                    },
                    max_output_tokens=max_output_tokens,
                    store=False,
                    safety_identifier=_safety_identifier(session_id),
                ),
            )
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                raise ValueError("missing structured output")
            break
        except Exception as exc:
            last_error = exc
            await alog(session_id, "warn", {
                "handler": "openai_audience_search_plan",
                "attempt": attempt + 1,
                "will_retry": attempt == 0,
                "error_type": type(exc).__name__,
                "error": str(exc)[:200],
            })
    if parsed is None:
        exc = last_error or ValueError("missing structured output")
        return {
            "queries": [],
            "applied": False,
            "reason": "provider_or_validation_failure",
            "error_type": type(exc).__name__,
        }
    try:
        # The deterministic preflight above already established concrete
        # product/audience evidence. A smaller planner can occasionally ignore
        # Vietnamese notes and return a contradictory false negative. In that
        # case retain the model's diagnostics but allow the existing focused
        # brief query to reach retrieval instead of turning the run into an
        # empty, unapprovable checkpoint.
        planner_information_sufficient = parsed.information_sufficient
        planner_insufficient_reason = parsed.insufficient_reason
        sufficiency_overridden = not planner_information_sufficient
        if sufficiency_overridden:
            parsed = parsed.model_copy(update={
                "information_sufficient": True,
                "insufficient_reason": "",
            })
        queries = _queries(parsed)
        result = {
            "queries": queries,
            "query_specs": _query_specs(parsed, queries),
            "industry_queries": parsed.industry_queries,
            "buyer_queries": parsed.buyer_queries,
            "product_queries": parsed.product_queries,
            "audience_queries": parsed.audience_queries,
            "excluded_concepts": parsed.excluded_concepts,
            "creative_only_concepts": parsed.creative_only_concepts,
            "information_sufficient": parsed.information_sufficient,
            "insufficient_reason": parsed.insufficient_reason,
            "planner_information_sufficient": planner_information_sufficient,
            "planner_insufficient_reason": planner_insufficient_reason,
            "sufficiency_overridden": sufficiency_overridden,
            "applied": True,
            "model": config.AUDIENCE_QUERY_PLANNER_MODEL,
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
            "audience_queries": result["audience_queries"],
            "information_sufficient": result["information_sufficient"],
            "insufficient_reason": result["insufficient_reason"],
            "planner_information_sufficient": (
                result["planner_information_sufficient"]
            ),
            "planner_insufficient_reason": result["planner_insufficient_reason"],
            "sufficiency_overridden": result["sufficiency_overridden"],
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


def invalidate_audience_search_cache(brief: dict | None = None) -> None:
    """Bypass cached planning when an operator explicitly asks to rerun."""
    if brief is None:
        _plan_cache.clear()
        return
    _plan_cache.pop(_cache_key(brief), None)
