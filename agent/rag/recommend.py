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
import time

from config import config
from agent_logger import alog
from llm import parse_json_response, simple_generate
from metrics import RAG_HALLUCINATED, RAG_REQUESTS
from prompts.audience import DMP_RECOMMEND_SYSTEM, DMP_RECOMMEND_USER
from rag.index import ensure_index, get_qdrant
from rag.rerank import rerank as rerank_docs


class RagUnavailable(Exception):
    pass


async def _hybrid_search(queries: list[str], limit: int) -> list[dict]:
    """Multi-query hybrid (dense+sparse, RRF) → merged, deduped payload list."""
    from qdrant_client import models as qm
    from rag.embeddings import embed_dense, embed_sparse

    dense, sparse = await asyncio.gather(
        asyncio.to_thread(embed_dense, queries),
        asyncio.to_thread(embed_sparse, queries),
    )
    client = get_qdrant()
    merged: dict[str, dict] = {}
    for i in range(len(queries)):
        res = client.query_points(
            config.RAG_COLLECTION,
            prefetch=[
                qm.Prefetch(query=dense[i], using="dense", limit=limit),
                qm.Prefetch(query=qm.SparseVector(
                    indices=sparse[i].indices.tolist(),
                    values=sparse[i].values.tolist()), using="sparse", limit=limit),
            ],
            query=qm.FusionQuery(fusion=qm.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        for rank, p in enumerate(res.points):
            key = p.payload.get("_id") or p.payload.get("fullLabel")
            if key not in merged or rank < merged[key]["_rank"]:
                merged[key] = {**p.payload, "_rank": rank}
    return sorted(merged.values(), key=lambda x: x["_rank"])


async def recommend_rag(session_id: str, brief: dict) -> dict:
    t0 = time.time()
    if not await ensure_index(session_id):
        raise RagUnavailable("qdrant index unavailable")

    # 1. query rewrite (never fatal — has internal fallback)
    from rag.query_rewrite import rewrite
    queries = await rewrite(brief)

    # 2. hybrid retrieve
    try:
        candidates = await _hybrid_search(queries, config.RAG_TOP_RETRIEVE)
    except Exception as e:
        raise RagUnavailable(f"retrieval failed: {str(e)[:120]}") from e
    if not candidates:
        raise RagUnavailable("retrieval returned 0 candidates")

    # 3. rerank (graceful skip → keep RRF order)
    brief_text = " | ".join(str(brief.get(k) or "") for k in ("brand", "objective", "kpi", "notes"))
    order = await rerank_docs(brief_text, [c["_text"] for c in candidates])
    reranked = [candidates[i] for i in order] if order else candidates
    top = reranked[: config.RAG_TOP_FINAL]

    # 4. LLM reasons over candidates only (same prompt family as old path)
    labels = [c.get("fullLabel") or c.get("name", "") for c in top]
    prompt = DMP_RECOMMEND_USER.format(
        brand=brief.get("brand", "?"), objective=brief.get("objective", "?"),
        kpi=brief.get("kpi", "?"), notes=brief.get("notes", "(trống)"),
        segments_json=json.dumps(labels, ensure_ascii=False),
    )
    raw = await asyncio.to_thread(simple_generate, DMP_RECOMMEND_SYSTEM, prompt)
    recs = parse_json_response(raw).get("recommendations", [])

    # 5. candidate-ID validation ⛔ — LLM may not invent segments
    label_map = {(c.get("fullLabel") or c.get("name", "")): c for c in top}
    enriched, dropped = [], 0
    for rec in recs:
        seg = label_map.get(rec.get("fullLabel", ""))
        if seg:
            seg = {k: v for k, v in seg.items() if k not in ("_rank", "_text")}
            enriched.append({**seg, "reason": rec.get("reason", "")})
        else:
            dropped += 1
    if dropped:
        RAG_HALLUCINATED.inc(dropped)

    RAG_REQUESTS.labels(outcome="ok").inc()
    await alog(session_id, "info", {
        "rag": "recommend_done", "queries": queries, "candidates": len(candidates),
        "reranked": bool(order), "returned": len(enriched), "dropped_hallucinated": dropped,
        "duration_ms": int((time.time() - t0) * 1000)})
    return {"recommendations": enriched, "total_segments": len(candidates),
            "rag": {"queries": queries, "candidates": len(candidates), "reranked": bool(order)}}
