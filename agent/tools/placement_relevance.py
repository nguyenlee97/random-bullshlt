"""Deterministic NP-6 placement-context retrieval and scoring.

This stays separate from audience RAG. It consumes only approved brief fields
and selected/recommended DMP labels, then scores catalog-authored placement
topic metadata. No personal trait is inferred from a placement.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def build_placement_context(
    brief: dict | None,
    audience: dict | list | None = None,
) -> dict:
    """Build a bounded, explainable query from current campaign artifacts."""
    brief = brief or {}
    audience = audience or {}
    brief_fields = {
        field: brief.get(field, "")
        for field in ("brand", "advertiser", "objective", "kpi", "notes")
    }
    if isinstance(audience, dict):
        audience_items = (
            audience.get("attrs")
            or audience.get("recommendations")
            or audience.get("segments")
            or []
        )
    elif isinstance(audience, list):
        audience_items = audience
    else:
        audience_items = []

    labels = []
    categories = []
    subcategories = []
    segment_labels = []
    for item in audience_items:
        if not isinstance(item, dict):
            if item not in (None, ""):
                labels.append(str(item))
                segment_labels.append(str(item))
            continue
        labels.extend(
            str(item.get(field))
            for field in ("fullLabel", "name", "subcategory", "context")
            if item.get(field)
        )
        segment_labels.extend(
            str(item.get(field))
            for field in ("fullLabel", "name")
            if item.get(field)
        )
        if item.get("category"):
            categories.append(str(item["category"]))
        if item.get("subcategory"):
            subcategories.append(str(item["subcategory"]))

    content_parts = [*brief_fields.values(), *labels]
    text_parts = [*content_parts, *categories]
    semantic_parts = [
        brief.get("notes", ""),
        brief.get("kpi", ""),
        *labels,
        *categories,
        *subcategories,
        *segment_labels,
    ]
    return {
        "text": " | ".join(str(part) for part in text_parts if part),
        "content_text": " | ".join(str(part) for part in content_parts if part),
        # Brand names and generic objectives are useful audit context but often
        # add noise to multilingual embedding retrieval. This narrower query
        # retains the campaign's authored topic/audience language.
        "semantic_text": " | ".join(
            str(part) for part in semantic_parts if part
        ),
        "audience_labels": labels,
        "audience_categories": categories,
        "audience_subcategories": subcategories,
        "audience_segments": segment_labels,
        "source_fields": [
            field for field, value in brief_fields.items() if value
        ],
    }


def score_placement_relevance(zone: dict, context: dict | None) -> dict:
    """Return a 0..1 relevance score with matched catalog evidence."""
    audience_context = zone.get("audienceContext") or {}
    primary_topics = audience_context.get("primaryTopics") or []
    if not context or not context.get("text") or not primary_topics:
        return {
            "score": 0.0,
            "matched_keywords": [],
            "matched_categories": [],
            "matched_subcategories": [],
            "matched_segments": [],
            "matched_topics": [],
            "signal": "no_topic_signal",
        }

    if audience_context.get("universalRelevance") is True:
        confidence = float(audience_context.get("confidence") or 1)
        return {
            "score": round(0.18 * confidence, 4),
            "matched_keywords": [],
            "matched_categories": [],
            "matched_subcategories": [],
            "matched_segments": [],
            "matched_topics": ["general"],
            "signal": "universal_homepage",
        }

    # DMP category names are scored only against explicit category affinities.
    # Keeping them out of keyword/topic matching prevents broad labels such as
    # "Business and industry" from overpowering a specific education brief.
    query = _fold(context.get("content_text") or context.get("text"))
    query_tokens = set(query.split())
    keywords = [
        *(audience_context.get("keywordsVi") or []),
        *(audience_context.get("keywordsEn") or []),
    ]
    matched_keywords = []
    for keyword in keywords:
        folded = _fold(keyword)
        tokens = set(folded.split())
        if tokens and tokens.issubset(query_tokens) and keyword not in matched_keywords:
            matched_keywords.append(keyword)

    affinities = audience_context.get("dmpCategoryAffinities") or []
    category_query = _fold(" | ".join(context.get("audience_categories") or []))
    matched_categories = [
        affinity for affinity in affinities
        if _fold(affinity) and (
            _fold(affinity) in query
            or _fold(affinity) in category_query
            or any(
                token in query_tokens
                for token in _fold(affinity).split()
                if len(token) >= 5
            )
        )
    ]

    subcategory_query = _fold(
        " | ".join(context.get("audience_subcategories") or [])
    )
    subcategory_affinities = (
        audience_context.get("dmpSubcategoryAffinities") or []
    )
    matched_subcategories = [
        affinity for affinity in subcategory_affinities
        if _fold(affinity) and (
            _fold(affinity) in subcategory_query
            or _fold(affinity) in query
        )
    ]

    segment_query = _fold(" | ".join(context.get("audience_segments") or []))
    segment_affinities = audience_context.get("dmpSegmentAffinities") or []
    matched_segments = [
        affinity for affinity in segment_affinities
        if _fold(affinity) and (
            _fold(affinity) in segment_query
            or _fold(affinity) in query
        )
    ]

    matched_topics = []
    for topic in primary_topics:
        tokens = {
            token for token in _fold(topic).split()
            if len(token) >= 4
        }
        if tokens & query_tokens:
            matched_topics.append(topic)

    keyword_score = min(0.55, len(matched_keywords) * 0.18)
    category_score = min(0.22, len(matched_categories) * 0.14)
    subcategory_score = min(0.42, len(matched_subcategories) * 0.32)
    segment_score = min(0.52, len(matched_segments) * 0.40)
    topic_score = min(0.25, len(matched_topics) * 0.25)
    confidence = float(audience_context.get("confidence") or 1)
    score = min(
        1.0,
        (
            keyword_score
            + category_score
            + subcategory_score
            + segment_score
            + topic_score
        ) * confidence,
    )
    return {
        "score": round(score, 4),
        "matched_keywords": matched_keywords[:6],
        "matched_categories": matched_categories[:4],
        "matched_subcategories": matched_subcategories[:4],
        "matched_segments": matched_segments[:4],
        "matched_topics": matched_topics,
        "signal": "topic_match" if score > 0 else "no_topic_match",
    }
