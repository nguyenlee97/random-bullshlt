"""Hybrid semantic retrieval over the bounded placement catalog.

The NP-6 catalog is currently small (hundreds, not millions, of documents), so
an in-process index is both faster and operationally safer than adding another
network service. Dense multilingual embeddings provide semantic recall; a
BM25-style sparse score preserves exact Vietnamese/English catalog vocabulary.

This module only retrieves known placement IDs. It never changes eligibility,
availability, reach arithmetic, or campaign-engine/model selection. Any
embedding/index failure is handled by the caller as a deterministic fallback.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import hashlib
import json
import math
import re
import unicodedata
from typing import Any

import numpy as np

from config import config


_index: dict[str, Any] = {}
_index_lock = asyncio.Lock()
_embedding_client = None


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _tokens(value: Any) -> list[str]:
    return [token for token in _fold(value).split() if len(token) >= 2]


def placement_document(zone: dict) -> str:
    """Create the retrievable document from catalog-authored metadata only."""
    audience = zone.get("audienceContext") or {}
    topic = zone.get("topicId") or ""
    parts = [
        zone.get("id"),
        zone.get("name"),
        zone.get("publisher") or zone.get("platform"),
        topic,
        str(topic).replace("_", " "),
        zone.get("placementFamily"),
        zone.get("inventoryTier"),
        *(audience.get("primaryTopics") or []),
        *(audience.get("secondaryTopics") or []),
        *(audience.get("keywordsVi") or []),
        *(audience.get("keywordsEn") or []),
        *(audience.get("dmpCategoryAffinities") or []),
        *(audience.get("dmpSubcategoryAffinities") or []),
        *(audience.get("dmpSegmentAffinities") or []),
        *(audience.get("intentSignals") or []),
    ]
    return " | ".join(str(part) for part in parts if part)


def _topic_documents(zones: list[dict]) -> list[dict]:
    """Collapse repeated placement formats into coherent topic documents."""
    grouped: dict[str, dict[str, Any]] = {}
    for zone in zones:
        topic = str(zone.get("topicId") or "legacy_other")
        group = grouped.setdefault(topic, {
            "topic": topic,
            "values": [],
            "seen": set(),
        })
        audience = zone.get("audienceContext") or {}
        values = [
            topic,
            topic.replace("_", " "),
            *(audience.get("primaryTopics") or []),
            *(audience.get("secondaryTopics") or []),
            *(audience.get("keywordsVi") or []),
            *(audience.get("keywordsEn") or []),
            *(audience.get("dmpCategoryAffinities") or []),
            *(audience.get("dmpSubcategoryAffinities") or []),
            *(audience.get("dmpSegmentAffinities") or []),
            *(audience.get("intentSignals") or []),
        ]
        for value in values:
            folded = _fold(value)
            if not folded or folded in group["seen"]:
                continue
            group["seen"].add(folded)
            group["values"].append(str(value))
    return [
        {
            "topic": topic,
            "document": " | ".join(grouped[topic]["values"]),
        }
        for topic in sorted(grouped)
    ]


def _fingerprint(topic_documents: list[dict], zones: list[dict]) -> str:
    stable = {
        "topics": topic_documents,
        "placements": [
            {
                "id": zone.get("id"),
                "topicId": zone.get("topicId"),
                "catalogVersion": zone.get("catalogVersion"),
            }
            for zone in sorted(zones, key=lambda item: str(item.get("id") or ""))
        ],
    }
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return matrix / norms


def _get_embedding_client():
    global _embedding_client
    if _embedding_client is None:
        from openai import AsyncOpenAI

        _embedding_client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=config.PLACEMENT_RAG_EMBEDDING_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _embedding_client


async def _embed_dense(texts: list[str]) -> list[list[float]]:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OpenAI embedding credentials unavailable")
    response = await _get_embedding_client().embeddings.create(
        model=config.PLACEMENT_RAG_EMBEDDING_MODEL,
        input=texts,
        encoding_format="float",
    )
    ordered = sorted(response.data, key=lambda item: item.index)
    if len(ordered) != len(texts):
        raise RuntimeError("embedding response count mismatch")
    return [item.embedding for item in ordered]


async def _ensure_index(zones: list[dict]) -> dict[str, Any]:
    topic_documents = _topic_documents(zones)
    fingerprint = _fingerprint(topic_documents, zones)
    if _index.get("fingerprint") == fingerprint:
        return _index

    async with _index_lock:
        if _index.get("fingerprint") == fingerprint:
            return _index

        documents = [item["document"] for item in topic_documents]
        vectors = await _embed_dense(documents)
        dense = _normalize(np.asarray(vectors, dtype=np.float32))
        token_counts = [Counter(_tokens(document)) for document in documents]
        document_frequency = Counter()
        for counts in token_counts:
            document_frequency.update(counts.keys())
        count = max(len(documents), 1)
        idf = {
            token: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }
        average_length = (
            sum(sum(counts.values()) for counts in token_counts) / count
        )
        _index.clear()
        _index.update({
            "fingerprint": fingerprint,
            "ids": [item["topic"] for item in topic_documents],
            "documents": documents,
            "dense": dense,
            "token_counts": token_counts,
            "idf": idf,
            "average_length": average_length or 1,
        })
        return _index


def _queries(context: dict) -> list[str]:
    candidates = [
        context.get("semantic_text"),
        context.get("content_text"),
        " | ".join(context.get("audience_segments") or []),
        " | ".join(context.get("audience_subcategories") or []),
        " | ".join(context.get("audience_categories") or []),
        context.get("text"),
    ]
    queries = []
    seen = set()
    for candidate in candidates:
        folded = _fold(candidate)
        if not folded or folded in seen:
            continue
        seen.add(folded)
        queries.append(str(candidate))
        if len(queries) >= config.PLACEMENT_RAG_MAX_QUERIES:
            break
    return queries


def _bm25(query: str, index: dict[str, Any]) -> np.ndarray:
    query_tokens = set(_tokens(query))
    scores = np.zeros(len(index["ids"]), dtype=np.float32)
    if not query_tokens:
        return scores
    k1, b = 1.5, 0.75
    average_length = index["average_length"]
    for row, counts in enumerate(index["token_counts"]):
        length = max(sum(counts.values()), 1)
        score = 0.0
        for token in query_tokens:
            frequency = counts.get(token, 0)
            if not frequency:
                continue
            denominator = frequency + k1 * (1 - b + b * length / average_length)
            score += index["idf"].get(token, 0) * (
                frequency * (k1 + 1) / denominator
            )
        scores[row] = score
    return scores


async def retrieve_placements(
    zones: list[dict],
    context: dict | None,
    *,
    limit: int | None = None,
) -> tuple[dict[str, dict], dict]:
    """Return known placement IDs with dense+BM25 retrieval evidence."""
    if not context or not context.get("text") or not zones:
        return {}, {"applied": False, "reason": "no_context_or_catalog"}

    queries = _queries(context)
    if not queries:
        return {}, {"applied": False, "reason": "no_queries"}

    index = await _ensure_index(zones)
    query_vectors = await _embed_dense(queries)
    query_matrix = _normalize(np.asarray(query_vectors, dtype=np.float32))
    dense_scores = query_matrix @ index["dense"].T
    topic_retrieve_limit = min(
        limit or config.PLACEMENT_RAG_RETRIEVE_LIMIT,
        len(index["ids"]),
    )
    prefetch_limit = min(
        max(topic_retrieve_limit * 2, 12),
        len(index["ids"]),
    )
    merged: dict[int, dict] = {}

    for query_index, query in enumerate(queries):
        dense = dense_scores[query_index]
        sparse = _bm25(query, index)
        dense_order = np.argsort(-dense)[:prefetch_limit]
        sparse_order = np.asarray([
            row
            for row in np.argsort(-sparse)[:prefetch_limit]
            if sparse[row] > 0
        ], dtype=int)
        query_rows: dict[int, float] = {}
        for rank, row in enumerate(dense_order):
            query_rows[int(row)] = query_rows.get(int(row), 0) + 1 / (60 + rank + 1)
        for rank, row in enumerate(sparse_order):
            query_rows[int(row)] = query_rows.get(int(row), 0) + 1 / (60 + rank + 1)

        sparse_max = float(sparse.max(initial=0))
        for row, fusion in query_rows.items():
            item = merged.setdefault(row, {
                "fusion": 0.0,
                "query_hits": 0,
                "dense_score": -1.0,
                "sparse_score": 0.0,
            })
            item["fusion"] += fusion
            item["query_hits"] += 1
            item["dense_score"] = max(item["dense_score"], float(dense[row]))
            if sparse_max > 0:
                item["sparse_score"] = max(
                    item["sparse_score"],
                    float(sparse[row]) / sparse_max,
                )

    ordered = sorted(
        merged.items(),
        key=lambda pair: (
            -pair[1]["fusion"],
            -pair[1]["query_hits"],
            -pair[1]["dense_score"],
            index["ids"][pair[0]],
        ),
    )[:topic_retrieve_limit]
    max_fusion = max((item["fusion"] for _, item in ordered), default=1)
    topic_evidence = {}
    for rank, (row, item) in enumerate(ordered, start=1):
        semantic_match = (
            rank <= config.PLACEMENT_RAG_CONTEXT_LIMIT
            and item["dense_score"] >= config.PLACEMENT_RAG_SEMANTIC_THRESHOLD
        )
        topic_evidence[index["ids"][row]] = {
            "applied": True,
            "mode": "hybrid_dense_bm25",
            "rank": rank,
            "dense_score": round(item["dense_score"], 4),
            "sparse_score": round(item["sparse_score"], 4),
            "fusion_score": round(item["fusion"] / max_fusion, 4),
            "query_hits": item["query_hits"],
            "semantic_match": semantic_match,
        }
    evidence = {
        str(zone.get("id") or ""): {
            **topic_evidence[str(zone.get("topicId") or "legacy_other")],
            "topic_id": str(zone.get("topicId") or "legacy_other"),
        }
        for zone in zones
        if str(zone.get("topicId") or "legacy_other") in topic_evidence
    }
    return evidence, {
        "applied": True,
        "mode": "hybrid_dense_bm25",
        "queries": queries,
        "catalog_count": len(zones),
        "topic_count": len(index["ids"]),
        "candidate_count": len(evidence),
        "topic_candidate_count": len(topic_evidence),
        "topics": [
            {
                "topic_id": topic,
                "document": index["documents"][index["ids"].index(topic)],
                **item,
            }
            for topic, item in sorted(
                topic_evidence.items(),
                key=lambda pair: pair[1]["rank"],
            )
        ],
        "fingerprint": index["fingerprint"],
        "embedding_model": config.PLACEMENT_RAG_EMBEDDING_MODEL,
        "semantic_threshold": config.PLACEMENT_RAG_SEMANTIC_THRESHOLD,
        "context_limit": config.PLACEMENT_RAG_CONTEXT_LIMIT,
    }


def reset_for_test() -> None:
    global _embedding_client
    _index.clear()
    _embedding_client = None
