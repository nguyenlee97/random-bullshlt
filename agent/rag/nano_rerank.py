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
    segment_id: str = Field(min_length=1, max_length=160)
    relevance_score: float = Field(ge=0, le=1)
    match_tier: Literal["recommended", "adjacent", "unrelated"] = "unrelated"
    match_basis: Literal[
        "exact_product",
        "exact_industry",
        "exact_buyer",
        "exact_user_interest",
        "broad_parent",
        "proxy",
        "unrelated",
    ]
    has_conflict: bool
    matched_signals: list[str] = Field(default_factory=list, max_length=6)
    missing_signals: list[str] = Field(default_factory=list, max_length=6)
    limitation: str = Field(default="", max_length=320)


class AudienceRerankResult(BaseModel):
    items: list[AudienceRerankItem] = Field(min_length=1, max_length=50)


_client: AsyncOpenAI | None = None
_rerank_cache: dict[str, dict] = {}
_RERANK_SCHEMA_VERSION = 2


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
        "schema_version": _RERANK_SCHEMA_VERSION,
        "candidates": sorted(
            (
                {
                    "id": _candidate_id(candidate),
                    "type": candidate.get("type"),
                    "category": candidate.get("category"),
                    "subcategory": candidate.get("subcategory"),
                    "label": candidate.get("fullLabel") or candidate.get("name"),
                    "context": candidate.get("context"),
                    "taxonomy": candidate.get("_taxonomy"),
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
                "taxonomy_parent_ids": (
                    (candidate.get("_taxonomy") or {}).get(
                        "direct_parent_ids", []
                    )
                ),
                "taxonomy_parent_labels": (
                    (candidate.get("_taxonomy") or {}).get(
                        "direct_parent_labels", []
                    )
                ),
                "taxonomy_ancestor_ids": (
                    (candidate.get("_taxonomy") or {}).get("ancestor_ids", [])
                ),
                "taxonomy_child_count": (
                    (candidate.get("_taxonomy") or {}).get(
                        "descendant_count", 0
                    )
                ),
                "taxonomy_child_labels": (
                    (candidate.get("_taxonomy") or {}).get(
                        "direct_child_labels", []
                    )
                ),
                "taxonomy_relation_sources": (
                    (candidate.get("_taxonomy") or {}).get(
                        "direct_parent_sources", {}
                    )
                ),
                "taxonomy_injected": bool(
                    candidate.get("_taxonomy_injected")
                ),
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
        "A broad parent interest is still recommended when the advertised "
        "product directly serves that whole domain or intentionally spans "
        "several child categories; do not demote the parent merely because "
        "more specific children exist. Specificity is useful only when it "
        "preserves the same meaning. The supplied taxonomy parent/child fields "
        "are catalog-structure evidence, not automatic relevance: use them to "
        "recognize the closest parent that covers a relevant child, but never "
        "infer that a sibling is relevant merely because another child is. "
        "Prefer the closest meaningful parent over a more distant ancestor. "
        "A taxonomy-injected parent must still be judged against the campaign "
        "context and may be adjacent or unrelated. "
        "Use adjacent when it is a defensible broad proxy or expansion signal "
        "but misses a decisive buyer, industry, or product signal. Use unrelated "
        "for incidental words, generic digital activity, conflicting consumer "
        "behavior, or a creative-only association. A high numeric score cannot "
        "turn an adjacent proxy into recommended. State short matched_signals, "
        "missing_signals, and a concrete limitation; do not invent catalog "
        "properties. "
        "Also classify match_basis. Use exact_product, exact_industry, "
        "exact_buyer, or exact_user_interest only for a literal semantic match "
        "to the intended campaign domain. Use broad_parent for a genuine parent "
        "of intended child interests. Use proxy whenever the candidate is merely "
        "the closest available catalog row, a possible overlap, or is missing "
        "the advertised product plus intended buyer/industry. A proxy cannot be "
        "recommended regardless of numeric score. Set has_conflict=true when "
        "the candidate represents a different real-world domain, a conflicting "
        "buyer class (for example institutional versus consumer), an explicit "
        "exclusion, or creative-only context. Conflicting rows must be unrelated, "
        "not adjacent. "
        "Respect taxonomy namespaces and the real-world meaning of the full "
        "label, category and subcategory. Shared words alone do not establish "
        "relevance across domains: a game genre must not promote the similarly "
        "named real-world sport, a software product must not promote generic "
        "business activity, and a venue/location must not become product "
        "intent. Conversely, a broad video-game interest is a direct user "
        "category for a controller explicitly sold across multiple game "
        "genres. Apply these principles to every taxonomy, not only the "
        "examples. "
        "A campaign city or store location is not travel/aviation intent unless "
        "the product itself is explicitly travel or transportation. When the "
        "product and target are explicitly gender- or life-stage-specific, "
        "score contradictory gender/life-stage segments near zero unless the "
        "brief says the offer is inclusive. "
        "Use only supplied zero-based candidate_index values and copy the "
        "corresponding segment_id exactly. The index and ID must refer to the "
        "same candidate. Return every candidate exactly once, and never infer "
        "sensitive personal traits. Assign relevance scores from 0 to 1."
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
        response = None
        parsed = None
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = await trace_responses_call(
                    name=(
                        "openai.audience_nano_rerank"
                        if attempt == 0
                        else "openai.audience_nano_rerank_retry"
                    ),
                    session_id=session_id,
                    model=config.AUDIENCE_NANO_RERANK_MODEL,
                    request=request,
                    metadata={
                        "schema": "audience_rerank",
                        "candidate_count": len(bounded),
                        "attempt": attempt + 1,
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
                            "effort": (
                                config.AUDIENCE_NANO_RERANK_REASONING_EFFORT
                            ),
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
                    raise ValueError(
                        "reranker introduced an unknown candidate index"
                    )
                if any(
                    item.segment_id != ids[item.candidate_index]
                    for item in parsed.items
                ):
                    raise ValueError(
                        "reranker candidate index and segment ID disagree"
                    )
                break
            except Exception as exc:
                last_error = exc
        if parsed is None:
            raise last_error or ValueError("missing structured output")
        raw_indexes = [item.candidate_index for item in parsed.items]

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
                        "match_basis": getattr(item, "match_basis", None),
                        "has_conflict": getattr(item, "has_conflict", False),
                        "matched_signals": getattr(item, "matched_signals", []),
                        "missing_signals": getattr(item, "missing_signals", []),
                        "limitation": getattr(item, "limitation", ""),
                    }
                continue
            score_by_id[segment_id] = item.relevance_score
            assessment_by_id[segment_id] = {
                "match_tier": getattr(item, "match_tier", None),
                "match_basis": getattr(item, "match_basis", None),
                "has_conflict": getattr(item, "has_conflict", False),
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
