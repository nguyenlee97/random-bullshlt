"""Optional OpenAI reranker for the bounded NP-6 placement shortlist.

The deterministic scorer remains authoritative and is always available.
This component may only reorder known candidate IDs. Any provider, schema, or
validation failure returns the deterministic order unchanged.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from config import config


class PlacementRerankItem(BaseModel):
    placement_id: str
    relevance_score: float = Field(ge=0, le=1)
    rationale: str = Field(max_length=240)


class PlacementRerankResult(BaseModel):
    items: list[PlacementRerankItem] = Field(min_length=1, max_length=30)


class PlacementTopicRerankItem(BaseModel):
    topic_id: str
    relevance_score: float = Field(ge=0, le=1)
    rationale: str = Field(max_length=240)


class PlacementTopicRerankResult(BaseModel):
    items: list[PlacementTopicRerankItem] = Field(min_length=1, max_length=30)


_client: AsyncOpenAI | None = None


def configured() -> bool:
    return bool(
        config.PLACEMENT_RERANK_ENABLED
        and config.OPENAI_API_KEY
        and config.PLACEMENT_RERANK_MODEL
    )


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=config.PLACEMENT_RERANK_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _client


def _safety_identifier(context: dict) -> str:
    source = str(context.get("request_id") or context.get("text") or "np6")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:32]
    return f"placement_{digest}"


def _candidate_payload(zone: dict) -> dict:
    relevance = zone.get("topic_relevance") or {}
    retrieval = zone.get("placement_retrieval") or {}
    audience = zone.get("audienceContext") or {}
    return {
        "placement_id": zone.get("id"),
        "publisher": zone.get("publisher"),
        "topic_id": zone.get("topicId"),
        "primary_topics": audience.get("primaryTopics") or [],
        "secondary_topics": audience.get("secondaryTopics") or [],
        "keywords_vi": (audience.get("keywordsVi") or [])[:8],
        "keywords_en": (audience.get("keywordsEn") or [])[:8],
        "dmp_categories": audience.get("dmpCategoryAffinities") or [],
        "dmp_subcategories": audience.get("dmpSubcategoryAffinities") or [],
        "dmp_segments": audience.get("dmpSegmentAffinities") or [],
        "placement_family": zone.get("placementFamily"),
        "objective": zone.get("obj"),
        "reach": zone.get("reach"),
        "viewability": zone.get("vi"),
        "ctr": zone.get("ctr"),
        "cpm": zone.get("cpm"),
        "deterministic_score": zone.get("score"),
        "matched_keywords": relevance.get("matched_keywords") or [],
        "matched_categories": relevance.get("matched_categories") or [],
        "matched_subcategories": relevance.get("matched_subcategories") or [],
        "matched_segments": relevance.get("matched_segments") or [],
        "semantic_retrieval": {
            "rank": retrieval.get("rank"),
            "dense_score": retrieval.get("dense_score"),
            "sparse_score": retrieval.get("sparse_score"),
            "semantic_match": retrieval.get("semantic_match") is True,
        },
    }


async def rerank_placements(
    candidates: list[dict],
    context: dict | None,
    *,
    client: Any | None = None,
) -> tuple[list[dict], dict]:
    if not configured() or not candidates or not (context or {}).get("text"):
        return candidates, {"applied": False, "reason": "disabled_or_no_context"}

    bounded = candidates[:config.PLACEMENT_RERANK_CANDIDATE_LIMIT]
    allowed_ids = [str(zone["id"]) for zone in bounded]
    payload = {
        "campaign_context": {
            "text": context.get("text"),
            "audience_categories": context.get("audience_categories") or [],
            "audience_subcategories": context.get("audience_subcategories") or [],
            "audience_segments": context.get("audience_segments") or [],
        },
        "candidates": [_candidate_payload(zone) for zone in bounded],
    }
    instructions = (
        "Rank advertising placements by how well their documented page topic "
        "and audience context fit the supplied campaign. Reconcile semantic "
        "retrieval evidence with the documented topic, keywords, and DMP "
        "affinities; use performance only as a secondary tie-breaker. Return "
        "every candidate exactly once, use only the provided placement_id "
        "values, and never infer sensitive personal traits."
    )
    try:
        api = client or _get_client()
        response = await api.responses.parse(
            model=config.PLACEMENT_RERANK_MODEL,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
            text_format=PlacementRerankResult,
            reasoning={"effort": config.PLACEMENT_RERANK_REASONING_EFFORT},
            max_output_tokens=config.PLACEMENT_RERANK_MAX_OUTPUT_TOKENS,
            store=False,
            safety_identifier=_safety_identifier(context),
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ValueError("missing structured output")
        returned_ids = [item.placement_id for item in parsed.items]
        if len(returned_ids) != len(set(returned_ids)):
            raise ValueError("duplicate placement IDs")
        if set(returned_ids) != set(allowed_ids):
            raise ValueError("reranker changed the candidate set")

        by_id = {zone["id"]: zone for zone in bounded}
        item_by_id = {item.placement_id: item for item in parsed.items}
        reordered = []
        for placement_id in returned_ids:
            item = item_by_id[placement_id]
            reordered.append({
                **by_id[placement_id],
                "llm_rerank": {
                    "model": config.PLACEMENT_RERANK_MODEL,
                    "score": item.relevance_score,
                    "rationale": item.rationale,
                },
            })
        return reordered + candidates[len(bounded):], {
            "applied": True,
            "model": config.PLACEMENT_RERANK_MODEL,
            "candidate_count": len(bounded),
            "response_id": getattr(response, "id", None),
        }
    except Exception as exc:
        return candidates, {
            "applied": False,
            "reason": "provider_or_validation_failure",
            "error_type": type(exc).__name__,
        }


async def rerank_topics(
    candidates: list[dict],
    context: dict | None,
    *,
    client: Any | None = None,
) -> tuple[list[dict], dict]:
    """Rerank unique retrieved topics before expanding to placement formats."""
    if not configured() or not candidates or not (context or {}).get("text"):
        return candidates, {"applied": False, "reason": "disabled_or_no_context"}

    bounded = candidates[:30]
    allowed_ids = [str(item["topic_id"]) for item in bounded]
    payload = {
        "campaign_context": {
            "text": context.get("text"),
            "semantic_text": context.get("semantic_text"),
            "audience_categories": context.get("audience_categories") or [],
            "audience_subcategories": context.get("audience_subcategories") or [],
            "audience_segments": context.get("audience_segments") or [],
        },
        "retrieved_topics": [{
            "topic_id": item.get("topic_id"),
            "document": item.get("document"),
            "dense_score": item.get("dense_score"),
            "sparse_score": item.get("sparse_score"),
            "fusion_score": item.get("fusion_score"),
            "retrieval_rank": item.get("rank"),
        } for item in bounded],
    }
    instructions = (
        "Rerank the retrieved advertising page topics by contextual suitability "
        "for the supplied campaign. Interpret Vietnamese and English synonyms, "
        "mixed intent, product use cases, and the documented topic vocabulary. "
        "Retrieval scores are evidence, not ground truth. Return every topic "
        "exactly once, use only the supplied topic_id values, score relevance "
        "from 0 to 1, and never infer sensitive personal traits."
    )
    try:
        api = client or _get_client()
        response = await api.responses.parse(
            model=config.PLACEMENT_RERANK_MODEL,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
            text_format=PlacementTopicRerankResult,
            reasoning={"effort": config.PLACEMENT_RERANK_REASONING_EFFORT},
            max_output_tokens=config.PLACEMENT_RERANK_MAX_OUTPUT_TOKENS,
            store=False,
            safety_identifier=_safety_identifier(context),
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ValueError("missing structured output")
        raw_returned_ids = [item.topic_id for item in parsed.items]
        if not set(raw_returned_ids).issubset(set(allowed_ids)):
            raise ValueError("reranker introduced an unknown topic")
        returned_ids = list(dict.fromkeys(raw_returned_ids))
        duplicate_count = len(raw_returned_ids) - len(returned_ids)

        by_id = {item["topic_id"]: item for item in bounded}
        item_by_id = {item.topic_id: item for item in parsed.items}
        reordered = []
        for rank, topic_id in enumerate(returned_ids, start=1):
            verdict = item_by_id[topic_id]
            reordered.append({
                **by_id[topic_id],
                "topic_rerank": {
                    "rank": rank,
                    "model": config.PLACEMENT_RERANK_MODEL,
                    "score": verdict.relevance_score,
                    "rationale": verdict.rationale,
                },
            })
        # Structured providers sometimes omit clearly irrelevant tail topics.
        # Omission is safe to repair because the omitted IDs were already in
        # the retrieved candidate set; append them in retrieval order with zero
        # model relevance. Unknown or duplicate IDs still fail closed above.
        omitted_ids = [
            topic_id for topic_id in allowed_ids if topic_id not in item_by_id
        ]
        for topic_id in omitted_ids:
            reordered.append({
                **by_id[topic_id],
                "topic_rerank": {
                    "rank": len(reordered) + 1,
                    "model": config.PLACEMENT_RERANK_MODEL,
                    "score": 0.0,
                    "rationale": "Không được model chọn; giữ lại theo retrieval để audit.",
                },
            })
        return reordered, {
            "applied": True,
            "stage": "topic",
            "model": config.PLACEMENT_RERANK_MODEL,
            "candidate_count": len(bounded),
            "omitted_count": len(omitted_ids),
            "duplicate_count": duplicate_count,
            "response_id": getattr(response, "id", None),
        }
    except Exception as exc:
        return candidates, {
            "applied": False,
            "stage": "topic",
            "reason": "provider_or_validation_failure",
            "error_type": type(exc).__name__,
        }


def reset_for_test() -> None:
    global _client
    _client = None
