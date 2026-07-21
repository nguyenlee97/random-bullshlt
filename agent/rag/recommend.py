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


async def _hybrid_search(queries: list[str], limit: int) -> list[dict]:
    """Multi-query hybrid (dense+sparse, RRF) → merged, deduped payload list."""
    from qdrant_client import models as qm
    from rag.embeddings import embed_dense, embed_sparse

    dense, sparse = await asyncio.gather(
        asyncio.to_thread(embed_dense, queries),
        asyncio.to_thread(embed_sparse, queries),
    )
    client = get_qdrant()

    def query_one(index: int):
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


async def recommend_rag(
    session_id: str,
    brief: dict,
    *,
    selector=None,
    query_rewriter=None,
    provider: str = "greennode",
    use_reranker: bool | None = None,
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
    queries = [_raw_query(brief)]
    if config.RAG_QUERY_REWRITE:
        if query_rewriter is not None:
            rewritten = await query_rewriter(brief)
        else:
            from rag.query_rewrite import rewrite
            rewritten = await rewrite(brief)
        queries.extend(q for q in rewritten if q and q not in queries)
    rewrite_s = time.time() - stage_t0
    RAG_STAGE_SECONDS.labels(stage="rewrite").observe(rewrite_s)

    # 2. hybrid retrieve
    try:
        stage_t0 = time.time()
        candidates = await _hybrid_search(queries, config.RAG_TOP_RETRIEVE)
        retrieval_s = time.time() - stage_t0
        RAG_STAGE_SECONDS.labels(stage="retrieve").observe(retrieval_s)
    except Exception as e:
        raise RagUnavailable(f"retrieval failed: {str(e)[:120]}") from e
    if not candidates:
        raise RagUnavailable("retrieval returned 0 candidates")
    catalog_segments = _catalog_segment_count(candidates)

    # 3. rerank (graceful skip → keep RRF order)
    brief_text = " | ".join(str(brief.get(k) or "") for k in ("brand", "objective", "kpi", "notes"))
    stage_t0 = time.time()
    rerank_enabled = config.RAG_USE_RERANK if use_reranker is None else use_reranker
    if rerank_enabled:
        order = await rerank_docs(brief_text, [c["_text"] for c in candidates])
    else:
        RAG_RERANK.labels(outcome="disabled").inc()
        order = None
    rerank_s = time.time() - stage_t0
    RAG_STAGE_SECONDS.labels(stage="rerank").observe(rerank_s)
    reranked = [candidates[i] for i in order] if order else candidates

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

    # 4. LLM reasons over candidates only (same prompt family as old path)
    labels = [c.get("fullLabel") or c.get("name", "") for c in top]
    prompt = DMP_RECOMMEND_USER.format(
        brand=brief.get("brand", "?"), objective=brief.get("objective", "?"),
        kpi=brief.get("kpi", "?"), notes=brief.get("notes", "(trống)"),
        segments_json=json.dumps(labels, ensure_ascii=False),
    )
    stage_t0 = time.time()
    if selector is not None:
        recs, selector_name = await selector(prompt)
    else:
        recs, selector_name = await _select(prompt)
    generation_s = time.time() - stage_t0
    RAG_STAGE_SECONDS.labels(stage="generate").observe(generation_s)

    # 5. candidate-ID validation ⛔ — LLM may not invent segments
    label_map = {(c.get("fullLabel") or c.get("name", "")): c for c in top}
    enriched, dropped, duplicates_dropped = [], 0, 0
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
        internal = {"_rank", "_text", "_fusion_score", "_query_hits", "_rag_index"}
        public = {key: value for key, value in segment.items() if key not in internal}
        return {**public, "reason": reason, "source": source}

    for rec in recs:
        seg = label_map.get(rec.get("fullLabel", ""))
        if seg:
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
            enriched.append(_public_recommendation(seg, rec.get("reason", "")))
        else:
            dropped += 1
    if dropped:
        RAG_HALLUCINATED.inc(dropped)

    # Structured selection requires six rows, but a provider can repeat one
    # valid label. Fill any resulting gap from the already-ranked, guarded
    # candidate set so every output remains unique and catalog-grounded.
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
    await alog(session_id, "info", {
        "rag": "recommend_done", "queries": queries, "candidates": len(candidates),
        "rewrite_enabled": config.RAG_QUERY_REWRITE,
        "rerank_enabled": rerank_enabled,
        "selector": selector_name,
        "provider": provider,
        "reranked": bool(order), "returned": len(enriched),
        "dropped_hallucinated": dropped,
        "dropped_duplicates": duplicates_dropped,
        "guard_rejected": guard_rejected,
        "duration_ms": int((time.time() - t0) * 1000),
        "stage_ms": {"rewrite": int(rewrite_s * 1000),
                     "retrieve": int(retrieval_s * 1000),
                     "rerank": int(rerank_s * 1000),
                     "generate": int(generation_s * 1000)}})
    return {"recommendations": enriched, "total_segments": catalog_segments,
            "rag": {"queries": queries, "candidates": len(candidates),
                    "catalog_segments": catalog_segments,
                    "rewrite_enabled": config.RAG_QUERY_REWRITE,
                    "rerank_enabled": rerank_enabled,
                    "selector": selector_name,
                    "provider": provider,
                    "guard_rejected": guard_rejected,
                    "dropped_duplicates": duplicates_dropped,
                    "reranked": bool(order),
                    "stage_ms": {"rewrite": int(rewrite_s * 1000),
                                 "retrieve": int(retrieval_s * 1000),
                                 "rerank": int(rerank_s * 1000),
                                 "generate": int(generation_s * 1000)}}}
