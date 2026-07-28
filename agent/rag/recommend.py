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

    priority = {"product": 0, "buyer": 1, "industry": 2, "brief": 3, "rewrite": 4}
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
            if model_tier == "recommended" and score >= threshold:
                decision = "recommended"
                if len(recs) < 6:
                    recs.append({
                        "fullLabel": candidate.get("fullLabel") or candidate.get("name", ""),
                        "reason": _assessment_reason(
                            brief, candidate, assessment, decision,
                        ),
                        "tier": decision,
                        "relevance_score": score,
                        **assessment,
                    })
            elif model_tier == "adjacent" and score >= 0.20:
                decision = "adjacent"
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
            gate_decisions.append({
                "segment_id": candidate_id,
                "full_label": candidate.get("fullLabel") or candidate.get("name"),
                "score": score,
                "model_tier": model_tier,
                "decision": decision,
                "matched_signals": assessment.get("matched_signals") or [],
                "missing_signals": assessment.get("missing_signals") or [],
                "limitation": assessment.get("limitation") or "",
            })
        quality_gate = {
            "applied": True,
            "threshold": threshold,
            "eligible": len(recs),
            "recommended": len(recs),
            "adjacent": len(adjacent_recs),
            "rejected": sum(
                1 for item in gate_decisions if item["decision"] == "rejected"
            ),
            "reranker_available": bool(rerank_meta.get("applied")),
            "decisions": gate_decisions,
        }
        selector_name = "openai_nano_scores"
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
            "_query_matches", "_aspect_hits",
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
                "missing_signals", "limitation",
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
            "trace_schema_version": 1,
            "query_specs": query_specs,
            "retrieval_trace": retrieval_trace,
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
