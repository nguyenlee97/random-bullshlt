"""
RAG audience recommendation — replaces prompt-stuffing (310 segments → every
prompt) with: query rewrite → hybrid retrieve (RRF) → rerank → LLM over ~15.

Return contract IDENTICAL to handlers.audience.handle_dmp_recommend ⛔:
    {"recommendations": [ {**segment, "reason": str}, ... ], "total_segments": N}

Safety rails:
- LLM may only cite candidates: labels not in the candidate set are DROPPED
  and counted (rag_hallucinated_label_total).
- Any stage failure raises RagUnavailable → caller falls back to the old path.
"""
import asyncio
import json
import re
import time
import unicodedata

from pydantic import BaseModel, Field

from config import config
from agent_logger import alog
from llm import parse_json_response, simple_generate
from metrics import (RAG_CANDIDATES, RAG_GUARD_REJECTED, RAG_HALLUCINATED, RAG_REQUESTS,
                     RAG_RERANK, RAG_STAGE_SECONDS)
from prompts.audience import DMP_RECOMMEND_SYSTEM, DMP_RECOMMEND_USER
from rag.index import ensure_index, get_qdrant
from rag.rerank import rerank as rerank_docs
from tools.audience_provenance import catalog_source


class RagUnavailable(Exception):
    pass


class _SelectedRecommendation(BaseModel):
    fullLabel: str
    reason: str


class _SelectionOut(BaseModel):
    recommendations: list[_SelectedRecommendation] = Field(min_length=6, max_length=6)


def _raw_query(brief: dict) -> str:
    """Build one deterministic query that preserves all audience signals."""
    fields = (brief.get("brand"), brief.get("objective"), brief.get("kpi"), brief.get("notes"))
    return " | ".join(str(value) for value in fields if value) or "general audience"


def _focused_query(brief: dict) -> str:
    """Build a concise product/audience query without creative workflow noise."""
    notes = str(brief.get("notes") or "")
    notes = re.split(
        r"(?i)\b(?:creative(?:\s+(?:direction|notes?))?|visual|"
        r"gợi ý creative|đề xuất creative|hình ảnh|ý tưởng hình ảnh)\s*:",
        notes,
        maxsplit=1,
    )[0]
    chunks = [
        chunk.strip()
        for chunk in re.split(r"[\n;]+|(?<=[.!?])\s+", notes)
        if chunk.strip()
    ]
    meta_markers = (
        "creative note", "creative direction", "goi y creative",
        "de xuat creative", "tao creative", "thiet ke banner",
        "chien luoc uu tien", "strategy prioritize",
    )
    audience_chunks = [
        chunk for chunk in chunks
        if not any(marker in _fold_text(chunk) for marker in meta_markers)
    ]
    fields = [
        str(brief.get("brand") or "").strip(),
        str(brief.get("objective") or "").strip(),
        str(brief.get("kpi") or "").strip(),
        " ".join(audience_chunks).strip(),
    ]
    return " | ".join(field for field in fields if field) or _raw_query(brief)


def _score_reason(brief: dict, segment: dict) -> str:
    """Return a conservative catalog-grounded explanation without another LLM."""
    label = str(segment.get("fullLabel") or segment.get("name") or "Segment").strip()
    taxonomy = " · ".join(
        str(segment.get(key) or "").strip()
        for key in ("category", "subcategory")
        if str(segment.get(key) or "").strip()
    )
    brand = str(brief.get("brand") or "campaign").strip()
    taxonomy_note = f" thuộc nhóm {taxonomy}" if taxonomy else ""
    return (
        f"{label}{taxonomy_note}, được xếp hạng liên quan cao với tín hiệu "
        f"sản phẩm và audience trong brief {brand}."
    )


def _assessment_reason(
    brief: dict,
    segment: dict,
    assessment: dict,
    tier: str,
) -> str:
    matched = [
        str(item).strip()
        for item in assessment.get("matched_signals") or []
        if str(item).strip()
    ]
    limitation = str(assessment.get("limitation") or "").strip()
    if not matched:
        return _score_reason(brief, segment)
    prefix = "Khớp trực tiếp" if tier == "recommended" else "Liên quan để mở rộng"
    reason = f"{prefix}: " + "; ".join(matched[:4]) + "."
    if tier == "adjacent" and limitation:
        reason += f" Hạn chế: {limitation}"
    return reason


def _rank_merged(merged: dict[str, dict]) -> list[dict]:
    """Coverage-first ordering for already merged per-query candidates."""
    ordered = sorted(
        merged.values(),
        key=lambda x: (x["_rank"], -x["_query_hits"], -x["_fusion_score"]),
    )
    for rank, item in enumerate(ordered):
        item["_rank"] = rank
    return ordered


def _catalog_segment_count(candidates: list[dict]) -> int:
    """Return full indexed corpus size, never the query-specific candidate count."""
    return next((
        int((candidate.get("_rag_index") or {}).get("segment_count") or 0)
        for candidate in candidates
        if (candidate.get("_rag_index") or {}).get("segment_count")
    ), len(candidates))


def _fold_text(value: object) -> str:
    """Normalize Vietnamese/English text for conservative phrase matching."""
    text = str(value or "").casefold().replace("đ", "d")
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _exact_domain_query_match(segment: dict) -> dict | None:
    """Return an exact catalog-label product/industry query match, if any."""
    label = _fold_text(
        segment.get("name")
        or str(segment.get("fullLabel") or "").split("(", 1)[0]
    )
    if not label:
        return None
    for match in segment.get("_query_matches") or []:
        if not isinstance(match, dict):
            continue
        if (
            match.get("kind") not in {"product", "industry"}
            or int(match.get("query_rank") or 999) > 3
        ):
            continue
        if _fold_text(match.get("query")) == label:
            return {
                "query": match.get("query"),
                "kind": match.get("kind"),
                "query_rank": int(match.get("query_rank") or 999),
            }
    return None


_FALLBACK_STOPWORDS = {
    "a", "an", "and", "app", "application", "audience", "brand", "campaign",
    "customer", "customers", "digital", "for", "in", "of", "online", "people",
    "product", "the", "to", "user", "users", "vietnam", "with",
}


def _guarded_retrieval_fallback(
    candidates: list[dict],
    *,
    limit: int = 6,
) -> list[tuple[dict, float, list[str]]]:
    """Return catalog-only related rows when the model reranker is unavailable.

    These rows are deliberately never promoted to the direct recommendation
    tier. The score only stabilizes ordering across the already guarded hybrid
    retrieval result; it is not presented as model confidence.
    """
    ranked: list[tuple[dict, float, list[str], int]] = []
    kind_weight = {
        "product": 5.0,
        "industry": 4.0,
        "buyer": 3.0,
        "audience": 2.5,
        "brief": 1.0,
        "rewrite": 0.75,
    }
    for retrieval_index, candidate in enumerate(candidates):
        candidate_text = _fold_text(" ".join(
            str(candidate.get(key) or "")
            for key in (
                "name", "fullLabel", "category", "subcategory", "context",
            )
        ))
        candidate_tokens = {
            token for token in candidate_text.split()
            if len(token) > 2 and token not in _FALLBACK_STOPWORDS
        }
        score = 0.0
        evidence: list[str] = []
        for match in candidate.get("_query_matches") or []:
            if not isinstance(match, dict):
                continue
            kind = str(match.get("kind") or "rewrite")
            query = _fold_text(match.get("query"))
            rank = max(1, int(match.get("query_rank") or 999))
            query_tokens = {
                token for token in query.split()
                if len(token) > 2 and token not in _FALLBACK_STOPWORDS
            }
            overlap = sorted(candidate_tokens & query_tokens)
            weight = kind_weight.get(kind, 0.5)
            if overlap:
                score += weight * (1.0 + min(3, len(overlap)))
                evidence.append(
                    f"{kind}:{'/'.join(overlap[:3])}"
                )
            elif kind in {"product", "industry", "buyer", "audience"} and rank <= 5:
                score += weight / (rank + 1)
                evidence.append(f"{kind}:top-{rank}")
        score += min(1.0, float(candidate.get("_query_hits") or 0) * 0.1)
        score += min(0.5, float(candidate.get("_fusion_score") or 0))
        ranked.append((candidate, score, evidence, retrieval_index))

    ranked.sort(key=lambda row: (-row[1], row[3]))
    selected = [row for row in ranked if row[2]][:limit]
    if not selected:
        selected = ranked[:limit]
    return [
        (candidate, score, evidence)
        for candidate, score, evidence, _retrieval_index in selected
    ]


def _guard_reason(brief: dict, segment: dict) -> str | None:
    """Deterministic taxonomy guards for explicit business/consumer conflicts."""
    notes = _fold_text(brief.get("notes"))
    industrial_b2b = "b2b" in notes and any(
        marker in notes for marker in ("industrial", "procurement", "mro"))
    rejects_leisure = any(
        marker in notes for marker in ("not leisure", "khong nham khach du lich",
                                       "khong phai khach du lich"))
    consumer_travel = (
        _fold_text(segment.get("category")) == "hobbies and activities"
        and _fold_text(segment.get("subcategory")).startswith("travel"))
    if industrial_b2b and rejects_leisure and consumer_travel:
        return "b2b_consumer_leisure"

    # A campaign for business owners may legitimately mention investment while
    # explicitly rejecting retail/individual investors. The catalog taxonomy is
    # the deterministic distinction: Personal finance > Investment represents
    # the rejected consumer audience, while Investment banking remains eligible.
    rejects_retail_investors = any(marker in notes for marker in (
        "khong nham nha dau tu ca nhan",
        "khong nham nha dau tu nho le",
        "loai tru nha dau tu ca nhan",
        "loai tru nha dau tu nho le",
        "tranh nha dau tu ca nhan",
        "tranh nha dau tu nho le",
        "exclude retail investor",
        "exclude individual investor",
        "not target retail investor",
        "not target individual investor",
        "no retail investor",
        "no individual investor",
    ))
    personal_finance_investment = (
        _fold_text(segment.get("subcategory")).startswith("personal finance")
        and _fold_text(segment.get("name")) == "investment"
    )
    if rejects_retail_investors and personal_finance_investment:
        return "retail_investor_excluded"
    return None


async def _select(prompt: str) -> tuple[list[dict], str]:
    """Structured critic selection with the legacy generator as fallback."""
    if (config.RAG_USE_CRITIC_SELECTOR and config.CRITIC_BASE_URL
            and config.CRITIC_MODEL and config.CRITIC_API_KEY):
        try:
            from graph.structured import structured
            output, _ = await asyncio.to_thread(
                structured,
                [{"role": "system", "content": DMP_RECOMMEND_SYSTEM},
                 {"role": "user", "content": prompt}],
                _SelectionOut, "audience_selection", "critic", 1600)
            return [item.model_dump() for item in output.recommendations], "critic"
        except Exception:
            pass

    raw = await asyncio.to_thread(simple_generate, DMP_RECOMMEND_SYSTEM, prompt)
    return parse_json_response(raw).get("recommendations", []), "generator"


async def _hybrid_search(
    queries: list[str],
    limit: int,
    mode: str | None = None,
) -> list[dict]:
    """Multi-query hybrid (dense+sparse, RRF) → merged, deduped payload list."""
    from qdrant_client import models as qm
    from rag.embeddings import embed_dense, embed_sparse

    retrieval_mode = mode or config.AUDIENCE_RAG_RETRIEVAL_MODE
    if retrieval_mode not in {"bm25_only", "dense_only", "hybrid_dense_bm25"}:
        raise ValueError(f"unsupported audience retrieval mode: {retrieval_mode}")

    dense = None
    sparse = None
    tasks = []
    if retrieval_mode in {"dense_only", "hybrid_dense_bm25"}:
        tasks.append(("dense", asyncio.to_thread(embed_dense, queries)))
    if retrieval_mode in {"bm25_only", "hybrid_dense_bm25"}:
        tasks.append(("sparse", asyncio.to_thread(embed_sparse, queries)))
    values = await asyncio.gather(*(task for _, task in tasks))
    for (name, _), value in zip(tasks, values):
        if name == "dense":
            dense = value
        else:
            sparse = value
    client = get_qdrant()

    def query_one(index: int):
        if retrieval_mode == "bm25_only":
            vector = sparse[index]
            return client.query_points(
                config.RAG_COLLECTION,
                query=qm.SparseVector(
                    indices=vector.indices.tolist(),
                    values=vector.values.tolist(),
                ),
                using="sparse",
                limit=limit,
                with_payload=True,
            )
        if retrieval_mode == "dense_only":
            return client.query_points(
                config.RAG_COLLECTION,
                query=dense[index],
                using="dense",
                limit=limit,
                with_payload=True,
            )
        return client.query_points(
            config.RAG_COLLECTION,
            prefetch=[
                qm.Prefetch(query=dense[index], using="dense", limit=limit),
                qm.Prefetch(query=qm.SparseVector(
                    indices=sparse[index].indices.tolist(),
                    values=sparse[index].values.tolist()), using="sparse", limit=limit),
            ],
            query=qm.FusionQuery(fusion=qm.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )

    # Rewritten queries are independent reads. Qdrant's synchronous client is
    # thread-safe, so issue them concurrently without blocking the API event
    # loop; merge below remains in original query order for deterministic ties.
    responses = await asyncio.gather(*(
        asyncio.to_thread(query_one, index) for index in range(len(queries))
    ))
    merged: dict[str, dict] = {}
    for res in responses:
        for rank, p in enumerate(res.points):
            key = p.payload.get("_id") or p.payload.get("fullLabel")
            if key not in merged:
                merged[key] = {
                    **p.payload,
                    "_rank": rank,
                    "_fusion_score": 0.0,
                    "_query_hits": 0,
                }
            # Preserve aspect coverage across rewritten queries. Pure summed
            # RRF over-rewarded generic segments present in every query and
            # buried strong single-aspect matches (for example Beer in a
            # soccer + beer campaign). Best rank is primary; agreement only
            # breaks ties between equally strong per-query results.
            merged[key]["_rank"] = min(merged[key]["_rank"], rank)
            merged[key]["_fusion_score"] += 1.0 / (60 + rank + 1)
            merged[key]["_query_hits"] += 1
    return _rank_merged(merged)


def _candidate_key(payload: dict) -> str:
    return str(
        payload.get("_id")
        or payload.get("segmentId")
        or payload.get("fullLabel")
        or payload.get("name")
        or ""
    ).strip()


def _trace_row(payload: dict, *, rank: int, score: float | None = None) -> dict:
    row = {
        "rank": rank + 1,
        "segment_id": (
            payload.get("segmentId")
            or payload.get("_id")
            or payload.get("code")
        ),
        "full_label": payload.get("fullLabel") or payload.get("name"),
        "category": payload.get("category"),
        "subcategory": payload.get("subcategory"),
    }
    if score is not None:
        row["score"] = round(float(score), 6)
    return row


def _merge_openai_retrieval(
    query_specs: list[dict],
    dense_rows: list[list[tuple[dict, float]]],
    sparse_rows: list[list[tuple[dict, float]]],
) -> tuple[list[dict], dict]:
    """Fuse source ranks and preserve a balanced front window for nano.

    Each query contributes candidates round-robin, with product and buyer
    queries ahead of broad brief queries. This prevents the bounded reranker
    window from being consumed by one generic query while still keeping global
    RRF evidence for later tie-breaking and debugging.
    """
    per_query: list[dict] = []
    merged: dict[str, dict] = {}
    for query_index, spec in enumerate(query_specs):
        query_items: dict[str, dict] = {}
        for source, rows in (
            ("dense", dense_rows[query_index]),
            ("bm25", sparse_rows[query_index]),
        ):
            for rank, (payload, raw_score) in enumerate(rows):
                key = _candidate_key(payload)
                if not key:
                    continue
                item = query_items.setdefault(key, {
                    "payload": payload,
                    "rrf": 0.0,
                    "best_rank": rank,
                    "source_ranks": {},
                    "source_scores": {},
                })
                item["rrf"] += 1.0 / (60 + rank + 1)
                item["best_rank"] = min(item["best_rank"], rank)
                item["source_ranks"][source] = rank + 1
                item["source_scores"][source] = round(float(raw_score), 6)
        ordered = sorted(
            query_items.values(),
            key=lambda item: (-item["rrf"], item["best_rank"], _candidate_key(item["payload"])),
        )
        query_trace = {
            "query": spec.get("query"),
            "kind": spec.get("kind", "rewrite"),
            "dense_top": [
                _trace_row(payload, rank=rank, score=score)
                for rank, (payload, score) in enumerate(dense_rows[query_index][:10])
            ],
            "bm25_top": [
                _trace_row(payload, rank=rank, score=score)
                for rank, (payload, score) in enumerate(sparse_rows[query_index][:10])
            ],
            "fused_top": [],
            "ordered_keys": [],
        }
        for rank, item in enumerate(ordered):
            payload = item["payload"]
            key = _candidate_key(payload)
            query_trace["ordered_keys"].append(key)
            if rank < 10:
                query_trace["fused_top"].append({
                    **_trace_row(payload, rank=rank, score=item["rrf"]),
                    "source_ranks": item["source_ranks"],
                })
            target = merged.setdefault(key, {
                **payload,
                "_rank": item["best_rank"],
                "_fusion_score": 0.0,
                "_query_hits": 0,
                "_query_matches": [],
                "_aspect_hits": [],
            })
            target["_rank"] = min(target["_rank"], item["best_rank"])
            target["_fusion_score"] += item["rrf"]
            target["_query_hits"] += 1
            target["_query_matches"].append({
                "query": spec.get("query"),
                "kind": spec.get("kind", "rewrite"),
                "query_rank": rank + 1,
                "source_ranks": item["source_ranks"],
                "source_scores": item["source_scores"],
            })
            kind = str(spec.get("kind") or "rewrite")
            if kind not in target["_aspect_hits"]:
                target["_aspect_hits"].append(kind)
        per_query.append(query_trace)

    priority = {
        "audience": 0,
        "product": 1,
        "buyer": 2,
        "industry": 3,
        "brief": 4,
        "rewrite": 5,
    }
    query_order = sorted(
        range(len(per_query)),
        key=lambda index: (priority.get(per_query[index]["kind"], 5), index),
    )
    balanced_keys: list[str] = []
    seen: set[str] = set()
    max_rows = max((len(item["ordered_keys"]) for item in per_query), default=0)
    for rank in range(max_rows):
        for query_index in query_order:
            rows = per_query[query_index]["ordered_keys"]
            if rank >= len(rows):
                continue
            key = rows[rank]
            if key in seen:
                continue
            seen.add(key)
            balanced_keys.append(key)

    global_keys = sorted(
        merged,
        key=lambda key: (
            -len(merged[key]["_aspect_hits"]),
            -merged[key]["_query_hits"],
            -merged[key]["_fusion_score"],
            merged[key]["_rank"],
            key,
        ),
    )
    ordered_keys = balanced_keys + [key for key in global_keys if key not in seen]
    ordered = []
    for rank, key in enumerate(ordered_keys):
        item = merged[key]
        item["_rank"] = rank
        ordered.append(item)

    trace = {
        "schema_version": 1,
        "query_results": [
            {key: value for key, value in item.items() if key != "ordered_keys"}
            for item in per_query
        ],
        "merged_pre_rerank": [{
            **_trace_row(item, rank=index, score=item.get("_fusion_score")),
            "query_hits": item.get("_query_hits"),
            "aspect_hits": item.get("_aspect_hits"),
            "query_matches": item.get("_query_matches"),
        } for index, item in enumerate(ordered[:30])],
    }
    return ordered, trace


async def _openai_hybrid_search(
    query_specs: list[dict],
    limit: int,
) -> tuple[list[dict], dict]:
    """OpenAI-only source-visible retrieval; GreenNode keeps legacy Qdrant fusion."""
    from qdrant_client import models as qm
    from rag.embeddings import embed_dense, embed_sparse

    queries = [str(item.get("query") or "").strip() for item in query_specs]
    dense, sparse = await asyncio.gather(
        asyncio.to_thread(embed_dense, queries),
        asyncio.to_thread(embed_sparse, queries),
    )
    client = get_qdrant()

    def query_source(index: int, source: str):
        if source == "dense":
            return client.query_points(
                config.RAG_COLLECTION,
                query=dense[index],
                using="dense",
                limit=limit,
                with_payload=True,
            )
        vector = sparse[index]
        return client.query_points(
            config.RAG_COLLECTION,
            query=qm.SparseVector(
                indices=vector.indices.tolist(),
                values=vector.values.tolist(),
            ),
            using="sparse",
            limit=limit,
            with_payload=True,
        )

    calls = [
        (index, source)
        for index in range(len(queries))
        for source in ("dense", "bm25")
    ]
    responses = await asyncio.gather(*(
        asyncio.to_thread(query_source, index, "sparse" if source == "bm25" else source)
        for index, source in calls
    ))
    dense_rows: list[list[tuple[dict, float]]] = [[] for _ in queries]
    sparse_rows: list[list[tuple[dict, float]]] = [[] for _ in queries]
    for (index, source), response in zip(calls, responses):
        target = dense_rows if source == "dense" else sparse_rows
        target[index] = [
            (dict(point.payload or {}), float(point.score or 0))
            for point in response.points
        ]
    return _merge_openai_retrieval(
        query_specs,
        dense_rows,
        sparse_rows,
    )


async def recommend_rag(
    session_id: str,
    brief: dict,
    *,
    selector=None,
    query_rewriter=None,
    provider: str = "greennode",
    use_reranker: bool | None = None,
    rerank_mode: str | None = None,
    use_focused_query: bool = False,
    enable_query_rewrite: bool | None = None,
    select_from_rerank_scores: bool = False,
    min_relevance_score: float | None = None,
    rerank_candidate_limit: int | None = None,
    include_raw_query: bool = True,
    detailed_retrieval: bool = False,
) -> dict:
    """Recommend catalog segments with optional provider-owned model stages.

    The default arguments preserve the existing GreenNode pipeline exactly.
    An independent engine can inject its own query rewriter and selector so the
    shared deterministic retrieval/rerank stages never choose its provider.
    """
    t0 = time.time()
    if not await ensure_index(session_id):
        raise RagUnavailable("qdrant index unavailable")

    # 1. Always retain the original brief. Coverage-preserving rewrites improve
    # the 80-case candidate benchmark, but remain optional because they add an
    # external model dependency and must pass the end-to-end release gate.
    stage_t0 = time.time()
    raw_query = _raw_query(brief)
    focused_query = _focused_query(brief) if use_focused_query else raw_query
    queries = [focused_query]
    query_specs = [{"query": focused_query, "kind": "brief"}]
    if include_raw_query and raw_query not in queries:
        queries.append(raw_query)
        query_specs.append({"query": raw_query, "kind": "brief"})
    query_plan = None
    rewrite_enabled = (
        config.RAG_QUERY_REWRITE
        if enable_query_rewrite is None
        else enable_query_rewrite
    )
    if rewrite_enabled:
        if query_rewriter is not None:
            rewritten = await query_rewriter(brief)
        else:
            from rag.query_rewrite import rewrite
            rewritten = await rewrite(brief)
        if isinstance(rewritten, dict):
            query_plan = rewritten
            rewritten = rewritten.get("queries") or []
        planned_specs = (
            query_plan.get("query_specs") or []
            if isinstance(query_plan, dict)
            else []
        )
        kind_by_query = {
            str(item.get("query") or "").casefold(): item.get("kind", "rewrite")
            for item in planned_specs
            if isinstance(item, dict) and item.get("query")
        }
        for query in rewritten:
            if not query or query in queries:
                continue
            queries.append(query)
            query_specs.append({
                "query": query,
                "kind": kind_by_query.get(str(query).casefold(), "rewrite"),
            })
    rewrite_s = time.time() - stage_t0
    RAG_STAGE_SECONDS.labels(stage="rewrite").observe(rewrite_s)
    if (
        provider == "openai"
        and isinstance(query_plan, dict)
        and query_plan.get("information_sufficient") is False
    ):
        reason = (
            query_plan.get("insufficient_reason")
            or "brief_missing_product_or_audience_evidence"
        )
        stage_ms = {
            "rewrite": int(rewrite_s * 1000),
            "retrieve": 0,
            "rerank": 0,
            "generate": 0,
        }
        quality_gate = {
            "applied": True,
            "recommended": 0,
            "adjacent": 0,
            "rejected": 0,
            "reason": "insufficient_information",
        }
        await alog(session_id, "openai_audience_pipeline_trace", {
            "rag": "recommend_skipped",
            "trace_schema_version": 1,
            "outcome": "insufficient_information",
            "provider": provider,
            "query_plan": query_plan,
            "query_specs": [],
            "retrieval_trace": None,
            "rerank_trace": [],
            "quality_gate": quality_gate,
            "stage_ms": stage_ms,
            "duration_ms": int((time.time() - t0) * 1000),
        })
        return {
            "recommendations": [],
            "adjacent_recommendations": [],
            "total_segments": 0,
            "note": "audience_information_insufficient",
            "rag": {
                "applied": True,
                "mode": config.AUDIENCE_RAG_RETRIEVAL_MODE,
                "queries": [],
                "query_plan": query_plan,
                "information_sufficient": False,
                "insufficient_reason": reason,
                "quality_gate": quality_gate,
                "stage_ms": stage_ms,
                "tier_counts": {
                    "recommended": 0,
                    "adjacent": 0,
                    "rejected": 0,
                },
            },
        }

    # 2. hybrid retrieve
    try:
        stage_t0 = time.time()
        if detailed_retrieval:
            candidates, retrieval_trace = await _openai_hybrid_search(
                query_specs,
                config.RAG_TOP_RETRIEVE,
            )
        else:
            candidates = await _hybrid_search(
                queries,
                config.RAG_TOP_RETRIEVE,
                mode=config.AUDIENCE_RAG_RETRIEVAL_MODE,
            )
            retrieval_trace = None
        retrieval_s = time.time() - stage_t0
        RAG_STAGE_SECONDS.labels(stage="retrieve").observe(retrieval_s)
    except Exception as e:
        raise RagUnavailable(f"retrieval failed: {str(e)[:120]}") from e
    if not candidates:
        raise RagUnavailable("retrieval returned 0 candidates")
    catalog_segments = _catalog_segment_count(candidates)
    taxonomy_trace = {
        "applied": False,
        "reason": "not_openai_detailed_retrieval",
    }
    if provider == "openai" and detailed_retrieval:
        taxonomy_t0 = time.time()
        try:
            from rag.taxonomy import expand_candidates_with_taxonomy
            from tools.audience_library import get_all_segments

            live_catalog = await get_all_segments(limit=1000)
            taxonomy_limit = (
                rerank_candidate_limit
                or config.AUDIENCE_NANO_RERANK_CANDIDATE_LIMIT
            )
            candidates, _taxonomy_graph, taxonomy_trace = (
                expand_candidates_with_taxonomy(
                    candidates,
                    live_catalog,
                    candidate_limit=taxonomy_limit,
                )
            )
            taxonomy_trace["applied"] = True
            taxonomy_trace["duration_ms"] = int(
                (time.time() - taxonomy_t0) * 1000
            )
        except Exception as exc:
            # Parent-awareness improves quality but is not a hard dependency.
            # Retrieval and reranking remain usable if the catalog endpoint is
            # temporarily unavailable.
            taxonomy_trace = {
                "applied": False,
                "reason": "catalog_or_graph_unavailable",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:160],
                "duration_ms": int((time.time() - taxonomy_t0) * 1000),
            }

    # 3. rerank (graceful skip → keep RRF order)
    brief_text = focused_query if use_focused_query else " | ".join(
        str(brief.get(k) or "") for k in ("brand", "objective", "kpi", "notes")
    )
    stage_t0 = time.time()
    selected_rerank_mode = (
        ("legacy" if use_reranker else "off")
        if use_reranker is not None
        else (rerank_mode or config.AUDIENCE_RERANK_MODE)
    )
    rerank_meta = {
        "applied": False,
        "mode": selected_rerank_mode,
        "reason": "disabled",
    }
    if selected_rerank_mode == "legacy":
        order = await rerank_docs(brief_text, [c["_text"] for c in candidates])
        rerank_meta = {
            "applied": bool(order),
            "mode": "legacy",
            "model": config.RERANK_MODEL if order else None,
            "candidate_count": len(candidates),
        }
    elif selected_rerank_mode == "openai_nano":
        from rag.nano_rerank import rerank_candidates

        if rerank_candidate_limit is None:
            order, rerank_meta = await rerank_candidates(
                brief_text,
                candidates,
                session_id=session_id,
            )
        else:
            order, rerank_meta = await rerank_candidates(
                brief_text,
                candidates,
                candidate_limit=rerank_candidate_limit,
                session_id=session_id,
            )
    else:
        RAG_RERANK.labels(outcome="disabled").inc()
        order = None
    rerank_s = time.time() - stage_t0
    RAG_STAGE_SECONDS.labels(stage="rerank").observe(rerank_s)
    if order:
        bounded_count = int(rerank_meta.get("candidate_count") or len(order))
        bounded = candidates[:bounded_count]
        reranked = [bounded[index] for index in order] + candidates[bounded_count:]
    else:
        reranked = candidates
    rerank_enabled = selected_rerank_mode != "off"

    # Remove deterministic conflicts before selection so the model can still
    # return the required six safe recommendations. The same guard is applied
    # again after selection as defense in depth.
    eligible, guard_rejected = [], 0
    for candidate in reranked:
        guard_reason = _guard_reason(brief, candidate)
        if guard_reason:
            RAG_GUARD_REJECTED.labels(reason=guard_reason).inc()
            guard_rejected += 1
            continue
        eligible.append(candidate)
    top = eligible[: config.RAG_TOP_FINAL]
    RAG_CANDIDATES.observe(len(top))

    # 4. Select from the fixed specialist's scores on the OpenAI path. The
    # legacy/GreenNode path retains its existing selector unchanged.
    labels = [c.get("fullLabel") or c.get("name", "") for c in top]
    prompt = DMP_RECOMMEND_USER.format(
        brand=brief.get("brand", "?"), objective=brief.get("objective", "?"),
        kpi=brief.get("kpi", "?"), notes=brief.get("notes", "(trống)"),
        segments_json=json.dumps(labels, ensure_ascii=False),
    )
    stage_t0 = time.time()
    selector_error = None
    quality_gate = {
        "applied": select_from_rerank_scores,
        "threshold": min_relevance_score,
        "eligible": 0,
        "rejected": 0,
    }
    if select_from_rerank_scores:
        threshold = (
            config.OPENAI_AUDIENCE_MIN_RELEVANCE_SCORE
            if min_relevance_score is None
            else min_relevance_score
        )
        direct_threshold = max(threshold, 0.65)
        scores = rerank_meta.get("scores") if rerank_meta.get("applied") else {}
        scores = scores if isinstance(scores, dict) else {}
        assessments = (
            rerank_meta.get("assessments")
            if rerank_meta.get("applied")
            else {}
        )
        assessments = assessments if isinstance(assessments, dict) else {}
        recs = []
        adjacent_recs = []
        gate_decisions = []
        candidate_by_id = {
            str(
                candidate.get("segmentId")
                or candidate.get("_id")
                or candidate.get("fullLabel")
                or candidate.get("name")
                or ""
            ).strip(): candidate
            for candidate in top
        }
        model_recommended_categories = {
            _fold_text(candidate.get("category"))
            for candidate_id, candidate in candidate_by_id.items()
            if (assessments.get(candidate_id) or {}).get("match_tier")
            == "recommended"
            and candidate.get("category")
        }
        model_recommended_category_counts: dict[str, int] = {}
        for candidate_id, candidate in candidate_by_id.items():
            if (
                (assessments.get(candidate_id) or {}).get("match_tier")
                != "recommended"
            ):
                continue
            category_key = _fold_text(candidate.get("category"))
            model_recommended_category_counts[category_key] = (
                model_recommended_category_counts.get(category_key, 0) + 1
            )
        for candidate in top:
            candidate_id = str(
                candidate.get("segmentId")
                or candidate.get("_id")
                or candidate.get("fullLabel")
                or candidate.get("name")
                or ""
            ).strip()
            score = float(scores.get(candidate_id, -1))
            assessment = assessments.get(candidate_id) or {}
            # Old stored results and unit fixtures only have a score. Preserve
            # their contract, while current OpenAI calls must honor the richer
            # direct/adjacent/unrelated judgment.
            model_tier = assessment.get("match_tier")
            if not model_tier:
                model_tier = "recommended" if score >= threshold else "unrelated"
            match_basis = assessment.get("match_basis")
            proxy_basis = match_basis == "proxy"
            unrelated_basis = match_basis == "unrelated"
            has_conflict = assessment.get("has_conflict") is True
            basis_query_kinds = {
                "exact_product": {"product", "industry", "audience"},
                "exact_industry": {"industry"},
                "exact_buyer": {"buyer", "audience"},
                "exact_user_interest": {"audience", "buyer", "product"},
            }.get(match_basis)
            basis_grounded = (
                basis_query_kinds is None
                or any(
                    match.get("kind") in basis_query_kinds
                    and int(match.get("query_rank") or 999) <= 5
                    for match in candidate.get("_query_matches") or []
                    if isinstance(match, dict)
                )
            )
            ungrounded_exact_basis = (
                basis_query_kinds is not None and not basis_grounded
            )
            broad_parent_domain_grounded = (
                match_basis != "broad_parent"
                or any(
                    match.get("kind") in {"product", "industry"}
                    and int(match.get("query_rank") or 999) <= 5
                    for match in candidate.get("_query_matches") or []
                    if isinstance(match, dict)
                )
            )
            ungrounded_broad_parent = (
                match_basis == "broad_parent"
                and not broad_parent_domain_grounded
            )
            category = _fold_text(candidate.get("category"))
            non_brief_aspects = {
                str(kind)
                for kind in candidate.get("_aspect_hits") or []
                if kind != "brief"
            }
            isolated_low_evidence_direct = (
                model_tier == "recommended"
                and bool(assessment.get("match_tier"))
                and (
                    len(non_brief_aspects) < 2
                    or (
                        int(candidate.get("_query_hits") or 0) < 4
                        and float(candidate.get("_fusion_score") or 0) < 0.08
                    )
                )
                and model_recommended_category_counts.get(category, 0) < 2
            )
            weak_cross_domain_proxy = (
                model_tier == "adjacent"
                and bool(model_recommended_categories)
                and category not in model_recommended_categories
                and score < 0.50
            )
            generic_digital_proxy = (
                category == "digital activities"
                and (
                    model_tier != "recommended"
                    or score < direct_threshold
                )
            )
            if (
                model_tier == "recommended"
                and score >= direct_threshold
                and not isolated_low_evidence_direct
                and not proxy_basis
                and not ungrounded_exact_basis
                and not ungrounded_broad_parent
                and not has_conflict
            ):
                decision = "recommended"
                gate_rule = "model_recommended_high_confidence"
                new_rec = {
                    "fullLabel": candidate.get("fullLabel") or candidate.get("name", ""),
                    "reason": _assessment_reason(
                        brief, candidate, assessment, decision,
                    ),
                    "tier": decision,
                    "relevance_score": score,
                    **assessment,
                }
                if len(recs) < 6:
                    recs.append(new_rec)
                elif match_basis == "broad_parent":
                    replaceable = [
                        row for row in recs
                        if row.get("match_basis") != "broad_parent"
                    ]
                    if replaceable:
                        displaced = min(
                            replaceable,
                            key=lambda row: float(
                                row.get("relevance_score") or -1
                            ),
                        )
                        recs.remove(displaced)
                        displaced["tier"] = "adjacent"
                        displaced["match_tier"] = "adjacent"
                        if len(adjacent_recs) < 6:
                            adjacent_recs.append(displaced)
                        displaced_decision = next((
                            item for item in gate_decisions
                            if item["full_label"]
                            == displaced.get("fullLabel")
                        ), None)
                        if displaced_decision:
                            displaced_decision["decision"] = "adjacent"
                            displaced_decision["gate_rule"] = (
                                "displaced_by_broad_parent"
                            )
                        recs.append(new_rec)
            elif (
                model_tier in {"recommended", "adjacent"}
                and score >= 0.20
                and not weak_cross_domain_proxy
                and not generic_digital_proxy
                and not unrelated_basis
                and not has_conflict
            ):
                decision = "adjacent"
                gate_rule = (
                    "conflicting_audience_or_domain"
                    if has_conflict
                    else (
                        "proxy_basis"
                        if proxy_basis
                        else (
                            "ungrounded_exact_basis"
                            if ungrounded_exact_basis
                            else (
                                "isolated_low_evidence_direct"
                                if isolated_low_evidence_direct
                                else (
                                    "recommended_below_direct_threshold"
                                    if model_tier == "recommended"
                                    else "model_adjacent"
                                )
                            )
                        )
                    )
                )
                if ungrounded_broad_parent:
                    gate_rule = "broad_parent_without_product_domain_evidence"
                if len(adjacent_recs) < 6:
                    adjacent_recs.append({
                        "fullLabel": candidate.get("fullLabel") or candidate.get("name", ""),
                        "reason": _assessment_reason(
                            brief, candidate, assessment, decision,
                        ),
                        "tier": decision,
                        "relevance_score": score,
                        **assessment,
                    })
            else:
                decision = "rejected"
                gate_rule = (
                    "generic_digital_proxy"
                    if generic_digital_proxy
                    else (
                        "conflicting_audience_or_domain"
                        if has_conflict
                        else (
                            "unrelated_basis"
                            if unrelated_basis
                            else (
                                "weak_cross_domain_proxy"
                                if weak_cross_domain_proxy
                                else "model_unrelated_or_below_threshold"
                            )
                        )
                    )
                )
            gate_decisions.append({
                "segment_id": candidate_id,
                "full_label": candidate.get("fullLabel") or candidate.get("name"),
                "score": score,
                "model_tier": model_tier,
                "match_basis": match_basis,
                "has_conflict": has_conflict,
                "basis_grounded": basis_grounded,
                "broad_parent_domain_grounded": (
                    broad_parent_domain_grounded
                ),
                "decision": decision,
                "gate_rule": gate_rule,
                "matched_signals": assessment.get("matched_signals") or [],
                "missing_signals": assessment.get("missing_signals") or [],
                "limitation": assessment.get("limitation") or "",
                "taxonomy_injected": bool(
                    candidate.get("_taxonomy_injected")
                ),
                "taxonomy_parent_ids": (
                    (candidate.get("_taxonomy") or {}).get(
                        "direct_parent_ids", []
                    )
                ),
                "taxonomy_ancestor_ids": (
                    (candidate.get("_taxonomy") or {}).get("ancestor_ids", [])
                ),
            })

        # Avoid an empty direct tier when the reranker explicitly found a
        # reasonably strong exact product/user match just below the strict
        # confidence cutoff. This is deliberately narrower than lowering the
        # global threshold: industries, broad parents, and proxies do not get
        # this rescue, and it only runs when no stronger direct row exists.
        if not recs:
            rescue_rows = []
            for row in adjacent_recs:
                decision_row = next((
                    item for item in gate_decisions
                    if item["full_label"] == row.get("fullLabel")
                ), None)
                if (
                    decision_row
                    and decision_row["decision"] == "adjacent"
                    and decision_row["model_tier"] == "recommended"
                    and decision_row["match_basis"]
                    in {"exact_product", "exact_user_interest"}
                    and float(decision_row["score"]) >= max(threshold, 0.60)
                    and decision_row.get("basis_grounded")
                    and not decision_row.get("has_conflict")
                ):
                    rescue_rows.append((row, decision_row))
            if rescue_rows:
                row, decision_row = max(
                    rescue_rows,
                    key=lambda item: float(item[1]["score"]),
                )
                adjacent_recs.remove(row)
                promoted = dict(row)
                promoted["tier"] = "recommended"
                promoted["match_tier"] = "recommended"
                candidate = candidate_by_id.get(
                    decision_row["segment_id"]
                ) or {}
                promoted["reason"] = _assessment_reason(
                    brief, candidate, promoted, "recommended",
                )
                recs.append(promoted)
                decision_row["decision"] = "recommended"
                decision_row["gate_rule"] = (
                    "minimum_viable_direct_exact_match"
                )

        # The reranker can occasionally over-weight buyer context and call an
        # exact product-domain catalog row a proxy. If no direct row survives,
        # an exact top-three product/industry query equal to the catalog name is
        # stronger deterministic evidence than that inconsistent proxy label.
        # This is catalog/query evidence, not a language-specific alias.
        if not recs:
            exact_domain_rows = []
            for decision_row in gate_decisions:
                candidate = candidate_by_id.get(
                    decision_row["segment_id"]
                ) or {}
                exact_query = _exact_domain_query_match(candidate)
                if (
                    exact_query
                    and float(decision_row["score"]) >= 0.40
                    and decision_row["model_tier"]
                    in {"recommended", "adjacent"}
                    and not decision_row.get("has_conflict")
                    and decision_row.get("match_basis") != "unrelated"
                ):
                    exact_domain_rows.append(
                        (decision_row, candidate, exact_query)
                    )
            if exact_domain_rows:
                decision_row, candidate, exact_query = max(
                    exact_domain_rows,
                    key=lambda item: float(item[0]["score"]),
                )
                adjacent_row = next((
                    row for row in adjacent_recs
                    if row.get("fullLabel") == decision_row["full_label"]
                ), None)
                if adjacent_row:
                    adjacent_recs.remove(adjacent_row)
                    promoted = dict(adjacent_row)
                else:
                    assessment = assessments.get(
                        decision_row["segment_id"]
                    ) or {}
                    promoted = {
                        "fullLabel": decision_row["full_label"],
                        "tier": "recommended",
                        "relevance_score": float(decision_row["score"]),
                        **assessment,
                    }
                promoted["tier"] = "recommended"
                promoted["match_tier"] = "recommended"
                promoted["reason"] = _assessment_reason(
                    brief, candidate, promoted, "recommended",
                )
                recs.append(promoted)
                decision_row["decision"] = "recommended"
                decision_row["gate_rule"] = (
                    "minimum_viable_direct_exact_catalog_query"
                )
                decision_row["exact_domain_query"] = exact_query

        # Promote the closest safe catalog parent as a coverage anchor. A graph
        # relationship is necessary but not sufficient: the reranker must still
        # judge the row relevant, and a single structural child needs high
        # confidence. Siblings never inherit that promotion.
        direct_ids = {
            item["segment_id"]
            for item in gate_decisions
            if item["decision"] == "recommended"
        }
        parent_proposals = []
        for row in list(adjacent_recs):
            decision_row = next((
                item for item in gate_decisions
                if item["full_label"] == row.get("fullLabel")
            ), None)
            if (
                not decision_row
                or decision_row["decision"] != "adjacent"
                or float(decision_row["score"]) < 0.45
                or decision_row.get("has_conflict")
                or decision_row.get("match_basis") in {"proxy", "unrelated"}
            ):
                continue
            parent_id = decision_row["segment_id"]
            candidate = candidate_by_id.get(parent_id) or {}
            covered_children = []
            relation_sources: set[str] = set()
            distances = []
            for child_id in direct_ids:
                child = candidate_by_id.get(child_id) or {}
                relation = (
                    (child.get("_taxonomy") or {})
                    .get("ancestor_relations", {})
                    .get(parent_id)
                )
                if not relation:
                    continue
                covered_children.append(child_id)
                distances.append(int(relation.get("distance") or 99))
                relation_sources.update(relation.get("sources") or [])
            if not covered_children:
                continue
            closer_direct_anchors = [
                direct_id
                for direct_id in direct_ids
                if direct_id != parent_id
                and parent_id in (
                    (candidate_by_id.get(direct_id) or {})
                    .get("_taxonomy", {})
                    .get("ancestor_ids", [])
                )
                and int(
                    (candidate_by_id.get(direct_id) or {})
                    .get("_taxonomy", {})
                    .get("descendant_count", 0)
                ) > 0
            ]
            if closer_direct_anchors:
                decision_row["taxonomy_decision"] = (
                    "parent_kept_adjacent_closer_direct_anchor_available"
                )
                decision_row["closer_direct_anchor_ids"] = (
                    closer_direct_anchors
                )
                continue
            semantic_override = "semantic_override" in relation_sources
            multi_child_coverage = len(covered_children) >= 2
            high_confidence = (
                float(decision_row["score"]) >= direct_threshold
            )
            if not (
                semantic_override
                or multi_child_coverage
                or high_confidence
            ):
                decision_row["taxonomy_decision"] = (
                    "parent_kept_adjacent_low_coverage"
                )
                continue
            parent_proposals.append({
                "row": row,
                "decision": decision_row,
                "candidate": candidate,
                "parent_id": parent_id,
                "covered_child_ids": covered_children,
                "relation_sources": sorted(relation_sources),
                "distance": min(distances),
                "descendant_count": int(
                    (candidate.get("_taxonomy") or {}).get(
                        "descendant_count", 0
                    )
                ),
                "semantic_override": semantic_override,
                "multi_child_coverage": multi_child_coverage,
                "high_confidence": high_confidence,
            })

        # If two proposed parents are nested, keep the closer/narrower one.
        closest_parent_proposals = []
        for proposal in parent_proposals:
            is_distant_ancestor = any(
                proposal["parent_id"] in (
                    (other["candidate"].get("_taxonomy") or {}).get(
                        "ancestor_ids", []
                    )
                )
                for other in parent_proposals
                if other["parent_id"] != proposal["parent_id"]
                and set(proposal["covered_child_ids"])
                & set(other["covered_child_ids"])
            )
            if is_distant_ancestor:
                proposal["decision"]["taxonomy_decision"] = (
                    "parent_kept_adjacent_closer_parent_available"
                )
                continue
            closest_parent_proposals.append(proposal)

        closest_parent_proposals.sort(key=lambda proposal: (
            not proposal["semantic_override"],
            not proposal["multi_child_coverage"],
            proposal["distance"],
            proposal["descendant_count"],
            -float(proposal["decision"]["score"]),
        ))
        promoted_parent_ids = []
        for proposal in closest_parent_proposals:
            row = proposal["row"]
            decision_row = proposal["decision"]
            candidate = proposal["candidate"]
            if row not in adjacent_recs:
                continue
            adjacent_recs.remove(row)
            if len(recs) >= 6:
                displaced = min(
                    recs,
                    key=lambda item: float(
                        item.get("relevance_score") or -1
                    ),
                )
                recs.remove(displaced)
                displaced["tier"] = "adjacent"
                displaced["match_tier"] = "adjacent"
                if len(adjacent_recs) < 6:
                    adjacent_recs.append(displaced)
                displaced_decision = next((
                    item for item in gate_decisions
                    if item["full_label"] == displaced.get("fullLabel")
                ), None)
                if displaced_decision:
                    displaced_decision["decision"] = "adjacent"
                    displaced_decision["gate_rule"] = (
                        "displaced_by_coverage_anchor"
                    )
            promoted = dict(row)
            promoted["tier"] = "recommended"
            promoted["match_tier"] = "recommended"
            promoted["reason"] = _assessment_reason(
                brief, candidate, promoted, "recommended",
            )
            recs.append(promoted)
            direct_ids.add(proposal["parent_id"])
            promoted_parent_ids.append(proposal["parent_id"])
            decision_row["decision"] = "recommended"
            decision_row["covered_child_ids"] = proposal[
                "covered_child_ids"
            ]
            decision_row["taxonomy_relation_sources"] = proposal[
                "relation_sources"
            ]
            if proposal["semantic_override"]:
                gate_rule = "coverage_anchor_semantic_override"
            elif proposal["multi_child_coverage"]:
                gate_rule = "coverage_anchor_multiple_direct_children"
            else:
                gate_rule = "coverage_anchor_high_confidence"
            decision_row["gate_rule"] = gate_rule
            decision_row["taxonomy_decision"] = "parent_promoted"

        # Make the distinction explicit in debug output: siblings may remain
        # optional expansion rows, but are never promoted by the graph.
        for decision_row in gate_decisions:
            if (
                decision_row["decision"] == "adjacent"
                and not decision_row.get("taxonomy_decision")
            ):
                candidate = candidate_by_id.get(
                    decision_row["segment_id"]
                ) or {}
                candidate_ancestors = set(
                    (candidate.get("_taxonomy") or {}).get(
                        "ancestor_ids", []
                    )
                )
                if any(
                    candidate_ancestors
                    & set(
                        (candidate_by_id.get(parent_id) or {})
                        .get("_taxonomy", {})
                        .get("ancestor_ids", [])
                    )
                    for parent_id in promoted_parent_ids
                ):
                    decision_row["taxonomy_decision"] = (
                        "sibling_kept_adjacent"
                    )

        # A provider timeout or invalid structured response must not collapse
        # the audience step into an empty, permanently loading walkthrough.
        # Keep the deterministic guards above, expose the strongest catalog
        # retrieval evidence as optional related rows, and never misrepresent
        # those rows as model-approved direct recommendations.
        fallback_applied = not bool(rerank_meta.get("applied"))
        if fallback_applied:
            recs = []
            adjacent_recs = []
            fallback_rows = _guarded_retrieval_fallback(top, limit=6)
            fallback_labels = {
                candidate.get("fullLabel") or candidate.get("name", "")
                for candidate, _score, _evidence in fallback_rows
            }
            gate_decisions = []
            for candidate in top:
                candidate_id = str(
                    candidate.get("segmentId")
                    or candidate.get("_id")
                    or candidate.get("fullLabel")
                    or candidate.get("name")
                    or ""
                ).strip()
                full_label = (
                    candidate.get("fullLabel") or candidate.get("name", "")
                )
                is_related = full_label in fallback_labels
                gate_decisions.append({
                    "segment_id": candidate_id,
                    "full_label": full_label,
                    "score": None,
                    "model_tier": None,
                    "match_basis": "retrieval_fallback",
                    "has_conflict": False,
                    "decision": "adjacent" if is_related else "rejected",
                    "gate_rule": (
                        "guarded_retrieval_related"
                        if is_related
                        else "retrieval_fallback_limit"
                    ),
                })
            for candidate, fallback_score, evidence in fallback_rows:
                label = candidate.get("fullLabel") or candidate.get("name", "")
                adjacent_recs.append({
                    "fullLabel": label,
                    "reason": (
                        "Liên quan theo kết quả tìm kiếm catalog của brief; "
                        "bộ xếp hạng AI tạm thời chưa phản hồi nên cần xem lại "
                        "trước khi chọn."
                    ),
                    "tier": "adjacent",
                    "match_tier": "adjacent",
                    "match_basis": "retrieval_fallback",
                    "relevance_score": None,
                    "matched_signals": evidence[:4],
                    "missing_signals": ["Chưa có đánh giá từ bộ xếp hạng AI"],
                    "limitation": (
                        "Đây là kết quả liên quan dự phòng từ catalog, không "
                        "phải đề xuất trực tiếp đã được AI xác nhận."
                    ),
                    "has_conflict": False,
                    "_fallback_score": round(fallback_score, 4),
                })
        quality_gate = {
            "applied": True,
            "threshold": threshold,
            "direct_threshold": direct_threshold,
            "eligible": len(recs),
            "recommended": len(recs),
            "adjacent": len(adjacent_recs),
            "rejected": sum(
                1 for item in gate_decisions if item["decision"] == "rejected"
            ),
            "reranker_available": bool(rerank_meta.get("applied")),
            "fallback_applied": fallback_applied,
            "fallback_mode": (
                "guarded_retrieval_adjacent"
                if fallback_applied
                else None
            ),
            "promoted_parent_ids": promoted_parent_ids,
            "decisions": gate_decisions,
        }
        selector_name = (
            "guarded_retrieval_adjacent_fallback"
            if fallback_applied
            else "openai_nano_scores"
        )
        if not rerank_meta.get("applied"):
            selector_error = "reranker_unavailable"
    else:
        adjacent_recs = []
        gate_decisions = []
        try:
            if selector is not None:
                recs, selector_name = await selector(prompt)
            else:
                recs, selector_name = await _select(prompt)
        except Exception as exc:
            # Retrieval and the bounded reranker have already produced a guarded,
            # catalog-only order. A transient conversational-provider failure must
            # not discard that evidence and fall all the way back to the legacy
            # full-catalog path. The public rows are still filled below from `top`,
            # with stable catalog IDs and no invented segment.
            recs = []
            selector_name = "retrieval_order_fallback"
            selector_error = f"{type(exc).__name__}: {str(exc)[:120]}"
    generation_s = time.time() - stage_t0
    RAG_STAGE_SECONDS.labels(stage="generate").observe(generation_s)

    # 5. candidate-ID validation ⛔ — LLM may not invent segments
    label_map = {(c.get("fullLabel") or c.get("name", "")): c for c in top}
    enriched, adjacent_enriched, dropped, duplicates_dropped = [], [], 0, 0
    seen: set[str] = set()

    def _identity(segment: dict) -> str:
        return str(
            segment.get("segmentId")
            or segment.get("_id")
            or segment.get("fullLabel")
            or segment.get("name")
            or ""
        ).strip().casefold()

    def _public_recommendation(segment: dict, reason: str) -> dict:
        index_metadata = segment.get("_rag_index") or {}
        source = catalog_source(segment, index_metadata)
        internal = {
            "_rank", "_text", "_fusion_score", "_query_hits", "_rag_index",
            "_query_matches", "_aspect_hits", "_taxonomy",
            "_taxonomy_injected",
        }
        public = {key: value for key, value in segment.items() if key not in internal}
        return {**public, "reason": reason, "source": source}

    def _enrich_recommendations(rows: list[dict], target: list[dict]) -> None:
        nonlocal dropped, duplicates_dropped, guard_rejected
        for rec in rows:
            seg = label_map.get(rec.get("fullLabel", ""))
            if not seg:
                dropped += 1
                continue
            guard_reason = _guard_reason(brief, seg)
            if guard_reason:
                RAG_GUARD_REJECTED.labels(reason=guard_reason).inc()
                guard_rejected += 1
                continue
            identity = _identity(seg)
            if not identity or identity in seen:
                duplicates_dropped += 1
                continue
            seen.add(identity)
            public = _public_recommendation(seg, rec.get("reason", ""))
            for key in (
                "tier", "relevance_score", "match_tier", "matched_signals",
                "match_basis", "missing_signals", "limitation",
                "has_conflict",
            ):
                if key in rec:
                    public[key] = rec[key]
            target.append(public)

    _enrich_recommendations(recs, enriched)
    _enrich_recommendations(adjacent_recs, adjacent_enriched)
    if dropped:
        RAG_HALLUCINATED.inc(dropped)

    if not select_from_rerank_scores:
        # Legacy structured selection still requires six rows. Preserve its
        # existing catalog-grounded fill behavior without applying it to the
        # quality-gated OpenAI path.
        desired = min(6, len(top))
        for seg in top:
            if len(enriched) >= desired:
                break
            identity = _identity(seg)
            if not identity or identity in seen:
                continue
            seen.add(identity)
            enriched.append(_public_recommendation(
                seg,
                "Bổ sung theo thứ hạng truy xuất phù hợp với brief và mục tiêu campaign.",
            ))

    RAG_REQUESTS.labels(outcome="ok").inc()
    log_payload = {
        "rag": "recommend_done", "queries": queries, "candidates": len(candidates),
        "rewrite_enabled": rewrite_enabled,
        "query_plan": query_plan,
        "rerank_enabled": rerank_enabled,
        "rerank_mode": selected_rerank_mode,
        "rerank_meta": rerank_meta,
        "selector": selector_name,
        "selector_error": selector_error,
        "quality_gate": quality_gate,
        "provider": provider,
        "reranked": bool(order), "returned": len(enriched),
        "adjacent_returned": len(adjacent_enriched),
        "dropped_hallucinated": dropped,
        "dropped_duplicates": duplicates_dropped,
        "guard_rejected": guard_rejected,
        "duration_ms": int((time.time() - t0) * 1000),
        "stage_ms": {"rewrite": int(rewrite_s * 1000),
                     "retrieve": int(retrieval_s * 1000),
                     "rerank": int(rerank_s * 1000),
                     "generate": int(generation_s * 1000)}}
    if provider == "openai":
        scores = rerank_meta.get("scores") or {}
        assessments = rerank_meta.get("assessments") or {}
        trace_limit = (
            rerank_candidate_limit
            or config.AUDIENCE_NANO_RERANK_CANDIDATE_LIMIT
        )
        log_payload.update({
            "trace_schema_version": 2,
            "query_specs": query_specs,
            "retrieval_trace": retrieval_trace,
            "taxonomy_trace": taxonomy_trace,
            "rerank_trace": [{
                "pre_rerank_rank": index + 1,
                "segment_id": str(
                    candidate.get("segmentId")
                    or candidate.get("_id")
                    or candidate.get("fullLabel")
                    or candidate.get("name")
                    or ""
                ),
                "full_label": candidate.get("fullLabel") or candidate.get("name"),
                "score": scores.get(str(
                    candidate.get("segmentId")
                    or candidate.get("_id")
                    or candidate.get("fullLabel")
                    or candidate.get("name")
                    or ""
                )),
                "assessment": assessments.get(str(
                    candidate.get("segmentId")
                    or candidate.get("_id")
                    or candidate.get("fullLabel")
                    or candidate.get("name")
                    or ""
                )),
            } for index, candidate in enumerate(candidates[:trace_limit])],
        })
        await alog(session_id, "openai_audience_pipeline_trace", log_payload)
    else:
        await alog(session_id, "info", log_payload)
    return {"recommendations": enriched,
            "adjacent_recommendations": adjacent_enriched,
            "total_segments": catalog_segments,
            "rag": {"applied": True,
                    "mode": config.AUDIENCE_RAG_RETRIEVAL_MODE,
                    "queries": queries, "candidates": len(candidates),
                    "catalog_segments": catalog_segments,
                    "rewrite_enabled": rewrite_enabled,
                    "query_plan": query_plan,
                    "rerank_enabled": rerank_enabled,
                    "rerank_mode": selected_rerank_mode,
                    "rerank_model": rerank_meta.get("model"),
                    "rerank_meta": rerank_meta,
                    "taxonomy_trace": taxonomy_trace,
                    "selector": selector_name,
                    "quality_gate": quality_gate,
                    "tier_counts": {
                        "recommended": len(enriched),
                        "adjacent": len(adjacent_enriched),
                        "rejected": quality_gate.get("rejected", 0),
                    },
                    "selector_fallback_reason": (
                        "provider_unavailable" if selector_error else None
                    ),
                    "provider": provider,
                    "guard_rejected": guard_rejected,
                    "dropped_duplicates": duplicates_dropped,
                    "reranked": bool(order),
                    "stage_ms": {"rewrite": int(rewrite_s * 1000),
                                 "retrieve": int(retrieval_s * 1000),
                                 "rerank": int(rerank_s * 1000),
                                 "generate": int(generation_s * 1000)}}}
