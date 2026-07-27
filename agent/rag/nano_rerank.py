"""Bounded GPT-5.4-nano reranker for catalog-backed audience candidates.

This is a fixed relevance specialist, not a campaign conversation engine. It
may only reorder known DMP segment IDs and fails open to the retrieval order.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from config import config
from metrics import RAG_RERANK


class AudienceRerankItem(BaseModel):
    candidate_index: int = Field(ge=0, le=49)
    relevance_score: float = Field(ge=0, le=1)


class AudienceRerankResult(BaseModel):
    items: list[AudienceRerankItem] = Field(min_length=1, max_length=50)


_client: AsyncOpenAI | None = None


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


async def rerank_candidates(
    query: str,
    candidates: list[dict],
    *,
    client: Any | None = None,
    candidate_limit: int | None = None,
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
        response = await api.responses.parse(
            model=config.AUDIENCE_NANO_RERANK_MODEL,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
            text_format=AudienceRerankResult,
            reasoning={"effort": config.AUDIENCE_NANO_RERANK_REASONING_EFFORT},
            max_output_tokens=config.AUDIENCE_NANO_RERANK_MAX_OUTPUT_TOKENS,
            store=False,
            safety_identifier=_safety_identifier(query),
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ValueError("missing structured output")
        raw_indexes = [item.candidate_index for item in parsed.items]
        if any(index >= len(ids) for index in raw_indexes):
            raise ValueError("reranker introduced an unknown candidate index")

        score_by_id: dict[str, float] = {}
        returned: list[str] = []
        for item in parsed.items:
            segment_id = ids[item.candidate_index]
            if segment_id in score_by_id:
                score_by_id[segment_id] = max(
                    score_by_id[segment_id], item.relevance_score
                )
                continue
            score_by_id[segment_id] = item.relevance_score
            returned.append(segment_id)
        index_by_id = {value: index for index, value in enumerate(ids)}
        returned.sort(
            key=lambda value: (-score_by_id[value], index_by_id[value])
        )
        omitted = [value for value in ids if value not in score_by_id]
        complete = returned + omitted
        order = [index_by_id[value] for value in complete]
        RAG_RERANK.labels(outcome="nano_ok").inc()
        return order, {
            "applied": True,
            "mode": "openai_nano",
            "model": config.AUDIENCE_NANO_RERANK_MODEL,
            "candidate_count": len(bounded),
            "duplicate_count": len(raw_indexes) - len(set(raw_indexes)),
            "omitted_count": len(omitted),
            "scores": score_by_id,
            "response_id": getattr(response, "id", None),
        }
    except Exception as exc:
        RAG_RERANK.labels(outcome="nano_error").inc()
        return None, {
            "applied": False,
            "mode": "openai_nano",
            "reason": "provider_or_validation_failure",
            "error_type": type(exc).__name__,
            "error_detail": str(exc)[:160],
        }
