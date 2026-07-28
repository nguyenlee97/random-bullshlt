"""Bounded GPT-5.4-nano reranker for catalog-backed audience candidates.

This is a fixed relevance specialist, not a campaign conversation engine. It
may only reorder known DMP segment IDs and fails open to the retrieval order.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from config import config
from metrics import RAG_RERANK
from openai_campaign.tracing import trace_responses_call


class AudienceRerankItem(BaseModel):
    candidate_index: int = Field(ge=0, le=49)
    relevance_score: float = Field(ge=0, le=1)
    match_tier: Literal["recommended", "adjacent", "unrelated"] = "unrelated"
    matched_signals: list[str] = Field(default_factory=list, max_length=6)
    missing_signals: list[str] = Field(default_factory=list, max_length=6)
    limitation: str = Field(default="", max_length=320)


class AudienceRerankResult(BaseModel):
    items: list[AudienceRerankItem] = Field(min_length=1, max_length=50)


_client: AsyncOpenAI | None = None
_rerank_cache: dict[str, dict] = {}


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=config.AUDIENCE_NANO_RERANK_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _client


def _safety_identifier(query: str) -> str:
    return "audience-rerank-" + hashlib.sha256(
        query.encode("utf-8")
    ).hexdigest()[:24]


def _candidate_id(candidate: dict) -> str:
    return str(
        candidate.get("segmentId")
        or candidate.get("_id")
        or candidate.get("fullLabel")
        or candidate.get("name")
        or ""
    ).strip()


def _cache_key(query: str, candidates: list[dict], limit: int) -> str:
    payload = {
        "query": query,
        "model": config.AUDIENCE_NANO_RERANK_MODEL,
        "candidates": sorted(
            (
                {
                    "id": _candidate_id(candidate),
                    "type": candidate.get("type"),
                    "category": candidate.get("category"),
                    "subcategory": candidate.get("subcategory"),
                    "label": candidate.get("fullLabel") or candidate.get("name"),
                    "context": candidate.get("context"),
                }
                for candidate in candidates[:limit]
            ),
            key=lambda item: item["id"],
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def _order_from_scores(ids: list[str], scores: dict[str, float]) -> list[int]:
    return sorted(
        range(len(ids)),
        key=lambda index: (-float(scores.get(ids[index], -1)), index),
    )


async def rerank_candidates(
    query: str,
    candidates: list[dict],
    *,
    client: Any | None = None,
    candidate_limit: int | None = None,
    session_id: str = "audience-rerank",
) -> tuple[list[int] | None, dict]:
    """Return a complete index order for the bounded candidates.

    Unknown IDs are rejected. Duplicate IDs are normalized and any omitted
    known candidates are appended in their original retrieval order.
    """
    limit = min(
        candidate_limit or config.AUDIENCE_NANO_RERANK_CANDIDATE_LIMIT,
        50,
        len(candidates),
    )
    bounded = candidates[:limit]
    ids = [_candidate_id(candidate) for candidate in bounded]
    if not config.OPENAI_API_KEY or not bounded or any(not value for value in ids):
        RAG_RERANK.labels(outcome="nano_disabled").inc()
        return None, {
            "applied": False,
            "mode": "openai_nano",
            "reason": "missing_credentials_or_candidates",
        }

    cache_key = _cache_key(query, candidates, limit)
    if client is None and cache_key in _rerank_cache:
        cached = deepcopy(_rerank_cache[cache_key])
        cached["cache_hit"] = True
        return _order_from_scores(ids, cached.get("scores") or {}), cached

    payload = {
        "campaign_context": query,
        "candidate_segments": [
            {
                "segment_id": ids[index],
                "candidate_index": index,
                "type": candidate.get("type"),
                "category": candidate.get("category"),
                "subcategory": candidate.get("subcategory"),
                "full_label": candidate.get("fullLabel") or candidate.get("name"),
                "context": candidate.get("context"),
                "retrieval_rank": index + 1,
            }
            for index, candidate in enumerate(bounded)
        ],
    }
    instructions = (
        "Rerank the supplied advertising audience segments by relevance to the "
        "campaign context. Respect explicit inclusion and exclusion language. "
        "Prefer specific catalog evidence over generic demographic guesses. "
        "Separate the actual product, industry, and buyer from creative-only "
        "imagery, metaphors, props, and backdrops; creative-only concepts must "
        "not become target audiences. Score explicitly excluded concepts near "
        "zero. For B2B campaigns, prefer relevant industries, business types, "
        "and professional buyer roles over consumer hobby proxies. A consumer "
        "interest is high-relevance only when that audience is an actual buyer "
        "or user described by the brief. "
        "Classify each candidate into exactly one tier. Use recommended only "
        "when the catalog label or taxonomy directly represents an intended "
        "buyer, user, industry, product interest, or behavior in the brief. "
        "Use adjacent when it is a defensible broad proxy or expansion signal "
        "but misses a decisive buyer, industry, or product signal. Use unrelated "
        "for incidental words, generic digital activity, conflicting consumer "
        "behavior, or a creative-only association. A high numeric score cannot "
        "turn an adjacent proxy into recommended. State short matched_signals, "
        "missing_signals, and a concrete limitation; do not invent catalog "
        "properties. "
        "A campaign city or store location is not travel/aviation intent unless "
        "the product itself is explicitly travel or transportation. When the "
        "product and target are explicitly gender- or life-stage-specific, "
        "score contradictory gender/life-stage segments near zero unless the "
        "brief says the offer is inclusive. "
        "Use only supplied zero-based candidate_index values, return every "
        "candidate exactly "
        "once, and never infer sensitive personal traits. Assign relevance "
        "scores from 0 to 1."
    )

    try:
        api = client or _get_client()
        input_data = json.dumps(payload, ensure_ascii=False)
        request = {
            "model": config.AUDIENCE_NANO_RERANK_MODEL,
            "instructions": instructions,
            "input": input_data,
            "text_format": AudienceRerankResult.model_json_schema(),
            "reasoning": {
                "effort": config.AUDIENCE_NANO_RERANK_REASONING_EFFORT,
            },
            "max_output_tokens": config.AUDIENCE_NANO_RERANK_MAX_OUTPUT_TOKENS,
            "store": False,
            "safety_identifier": _safety_identifier(query),
        }
        response = await trace_responses_call(
            name="openai.audience_nano_rerank",
            session_id=session_id,
            model=config.AUDIENCE_NANO_RERANK_MODEL,
            request=request,
            metadata={
                "schema": "audience_rerank",
                "candidate_count": len(bounded),
            },
            model_parameters={
                "reasoning_effort": (
                    config.AUDIENCE_NANO_RERANK_REASONING_EFFORT
                ),
                "max_output_tokens": (
                    config.AUDIENCE_NANO_RERANK_MAX_OUTPUT_TOKENS
                ),
                "store": False,
            },
            call=lambda: api.responses.parse(
                model=config.AUDIENCE_NANO_RERANK_MODEL,
                instructions=instructions,
                input=input_data,
                text_format=AudienceRerankResult,
                reasoning={
                    "effort": config.AUDIENCE_NANO_RERANK_REASONING_EFFORT,
                },
                max_output_tokens=(
                    config.AUDIENCE_NANO_RERANK_MAX_OUTPUT_TOKENS
                ),
                store=False,
                safety_identifier=_safety_identifier(query),
            ),
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ValueError("missing structured output")
        raw_indexes = [item.candidate_index for item in parsed.items]
        if any(index >= len(ids) for index in raw_indexes):
            raise ValueError("reranker introduced an unknown candidate index")

        score_by_id: dict[str, float] = {}
        assessment_by_id: dict[str, dict] = {}
        returned: list[str] = []
        for item in parsed.items:
            segment_id = ids[item.candidate_index]
            if segment_id in score_by_id:
                if item.relevance_score > score_by_id[segment_id]:
                    score_by_id[segment_id] = item.relevance_score
                    assessment_by_id[segment_id] = {
                        "match_tier": getattr(item, "match_tier", None),
                        "matched_signals": getattr(item, "matched_signals", []),
                        "missing_signals": getattr(item, "missing_signals", []),
                        "limitation": getattr(item, "limitation", ""),
                    }
                continue
            score_by_id[segment_id] = item.relevance_score
            assessment_by_id[segment_id] = {
                "match_tier": getattr(item, "match_tier", None),
                "matched_signals": getattr(item, "matched_signals", []),
                "missing_signals": getattr(item, "missing_signals", []),
                "limitation": getattr(item, "limitation", ""),
            }
            returned.append(segment_id)
        index_by_id = {value: index for index, value in enumerate(ids)}
        returned.sort(
            key=lambda value: (-score_by_id[value], index_by_id[value])
        )
        omitted = [value for value in ids if value not in score_by_id]
        complete = returned + omitted
        order = [index_by_id[value] for value in complete]
        RAG_RERANK.labels(outcome="nano_ok").inc()
        metadata = {
            "applied": True,
            "mode": "openai_nano",
            "model": config.AUDIENCE_NANO_RERANK_MODEL,
            "candidate_count": len(bounded),
            "duplicate_count": len(raw_indexes) - len(set(raw_indexes)),
            "omitted_count": len(omitted),
            "scores": score_by_id,
            "assessments": assessment_by_id,
            "response_id": getattr(response, "id", None),
            "cache_hit": False,
        }
        if client is None:
            if len(_rerank_cache) >= 128:
                _rerank_cache.pop(next(iter(_rerank_cache)))
            _rerank_cache[cache_key] = deepcopy(metadata)
        return order, metadata
    except Exception as exc:
        RAG_RERANK.labels(outcome="nano_error").inc()
        return None, {
            "applied": False,
            "mode": "openai_nano",
            "reason": "provider_or_validation_failure",
            "error_type": type(exc).__name__,
            "error_detail": str(exc)[:160],
        }


def reset_nano_rerank_for_test() -> None:
    global _client
    _client = None
    _rerank_cache.clear()
