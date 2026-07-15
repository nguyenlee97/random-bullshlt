"""Offline retrieval/rerank evaluation against the 80 audience briefs.

Unlike run_eval.py, this bypasses final recommendation generation so retrieval
quality and reranker impact can be measured directly and cheaply.
"""
import argparse
import asyncio
import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
AGENT = ROOT / "agent"
GOLDEN = ROOT / "eval" / "golden_set"
REPORTS = ROOT / "eval" / "reports"

# Local evaluation always targets the Compose services. Environment variables
# still win, making this script usable against another isolated test stack.
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("BACKEND_URL", "http://localhost:3000")
load_dotenv(AGENT / ".env", override=False)
sys.path.insert(0, str(AGENT))

from config import config  # noqa: E402
from rag.index import inspect_index  # noqa: E402
from rag.query_rewrite import rewrite  # noqa: E402
from rag.recommend import _hybrid_search  # noqa: E402
from rag.rerank import rerank  # noqa: E402


def _catalog_maps():
    items = json.loads((GOLDEN / "catalog_full.json").read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("data") or items.get("attributes") or []
    return (
        {item["_id"]: item["segmentId"] for item in items},
        {item["segmentId"]: item["fullLabel"] for item in items},
    )


def _raw_query(brief, mode="all"):
    if mode == "notes":
        fields = (brief.get("notes"),)
    elif mode == "objective-notes":
        fields = (brief.get("objective"), brief.get("notes"))
    else:
        fields = (brief.get("brand"), brief.get("objective"),
                  brief.get("kpi"), brief.get("notes"))
    return [" | ".join(str(value) for value in fields if value)]


def _dcg(labels, grades, k):
    return sum(grades.get(label, 0) / math.log2(rank + 1)
               for rank, label in enumerate(labels[:k], start=1))


async def evaluate_case(path, golden_to_segment, segment_to_label, args):
    case = json.loads(path.read_text(encoding="utf-8"))
    audience = case["labels"]["audience"]
    t0 = time.perf_counter()
    if not args.rewrite:
        queries = _raw_query(case["brief"], args.raw_query_mode)
    else:
        queries = await rewrite(case["brief"])
        if args.include_raw_with_rewrite:
            raw = _raw_query(case["brief"], args.raw_query_mode)[0]
            queries = [raw, *(query for query in queries if query != raw)]
    rewrite_s = time.perf_counter() - t0

    stage = time.perf_counter()
    candidates = await _hybrid_search(queries, args.retrieve_k)
    retrieval_s = time.perf_counter() - stage
    candidate_ids = [c.get("segmentId") for c in candidates]

    order = None
    rerank_s = 0.0
    if args.rerank:
        stage = time.perf_counter()
        brief_text = " | ".join(str(case["brief"].get(key) or "")
                                for key in ("brand", "objective", "kpi", "notes"))
        order = await rerank(brief_text, [c["_text"] for c in candidates])
        rerank_s = time.perf_counter() - stage
    ranked = [candidates[i] for i in order] if order else candidates
    ranked_ids = [c.get("segmentId") for c in ranked]
    ranked_labels = [c.get("fullLabel") or c.get("name", "") for c in ranked]

    must_ids = {golden_to_segment.get(value, value)
                for value in audience.get("must_include", [])}
    acceptable_ids = {golden_to_segment.get(value, value)
                      for value in audience.get("acceptable", [])}
    excluded_ids = {golden_to_segment.get(value, value)
                    for value in audience.get("must_exclude", [])}
    relevant_ids = must_ids | acceptable_ids
    top_ids = ranked_ids[:args.final_k]
    top = ranked_labels[:args.final_k]
    retrieved_ids = set(candidate_ids[:args.retrieve_k])
    grades = {value: 1 for value in acceptable_ids}
    grades.update({value: 2 for value in must_ids})
    ideal = sorted(grades.values(), reverse=True)[:args.final_k]
    ideal_dcg = sum(grade / math.log2(rank + 1)
                    for rank, grade in enumerate(ideal, start=1))
    first_rank = next((rank for rank, value in enumerate(top_ids, start=1)
                       if value in relevant_ids), None)

    return {
        "id": case["id"],
        "tags": case.get("tags", []),
        "queries": queries,
        "retrieval_recall": (len(relevant_ids & retrieved_ids) / len(relevant_ids)
                             if relevant_ids else None),
        "must_recall_at_retrieve_k": (len(must_ids & retrieved_ids) / len(must_ids)
                                      if must_ids else None),
        "must_recall_at_k": (len(must_ids & set(top_ids)) / len(must_ids)
                             if must_ids else None),
        "mrr_at_k": round(1 / first_rank, 4) if first_rank else 0.0,
        "ndcg_at_k": round(_dcg(top_ids, grades, args.final_k) / ideal_dcg, 4)
        if ideal_dcg else None,
        "exclusion_violations": sorted(
            segment_to_label.get(value, value) for value in excluded_ids & set(top_ids)),
        "unknown_labels": sorted(
            label for value, label in zip(top_ids, top) if value not in segment_to_label),
        "reranked": bool(order),
        "top_labels": top,
        "latency_s": {
            "rewrite": round(rewrite_s, 3),
            "retrieve": round(retrieval_s, 3),
            "rerank": round(rerank_s, 3),
            "total": round(time.perf_counter() - t0, 3),
        },
    }


def _percentile(values, p):
    values = sorted(values)
    if not values:
        return None
    return round(values[int((len(values) - 1) * p)], 3)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--subset", default="", help="tag=<value>")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--retrieve-k", type=int, default=None)
    parser.add_argument("--final-k", type=int, default=None)
    rewrite_group = parser.add_mutually_exclusive_group()
    rewrite_group.add_argument("--rewrite", dest="rewrite", action="store_true")
    rewrite_group.add_argument("--no-rewrite", dest="rewrite", action="store_false")
    rerank_group = parser.add_mutually_exclusive_group()
    rerank_group.add_argument("--rerank", dest="rerank", action="store_true")
    rerank_group.add_argument("--no-rerank", dest="rerank", action="store_false")
    raw_group = parser.add_mutually_exclusive_group()
    raw_group.add_argument(
        "--include-raw-with-rewrite", dest="include_raw_with_rewrite", action="store_true")
    raw_group.add_argument(
        "--exclude-raw-with-rewrite", dest="include_raw_with_rewrite", action="store_false")
    parser.set_defaults(rewrite=None, rerank=None, include_raw_with_rewrite=None)
    parser.add_argument(
        "--raw-query-mode", choices=("all", "notes", "objective-notes"), default="all",
        help="Fields used by --no-rewrite experiments.")
    args = parser.parse_args()

    # No-flag runs must evaluate the deployed candidate, not an accidental
    # experimental pipeline. Every stage remains explicitly overrideable for
    # A/B reports.
    args.rewrite = config.RAG_QUERY_REWRITE if args.rewrite is None else args.rewrite
    args.rerank = config.RAG_USE_RERANK if args.rerank is None else args.rerank
    args.include_raw_with_rewrite = (
        args.rewrite
        if args.include_raw_with_rewrite is None
        else args.include_raw_with_rewrite
    )
    args.retrieve_k = args.retrieve_k or config.RAG_TOP_RETRIEVE
    args.final_k = args.final_k or config.RAG_TOP_FINAL

    index = await inspect_index()
    if not index.get("ready"):
        raise SystemExit(f"RAG index is not ready: {index}")

    # Initialize FastEmbed once before concurrent cases. Without this, the
    # first two workers can race while constructing duplicate ONNX sessions;
    # that measures evaluator startup rather than retrieval quality/latency.
    from rag.embeddings import embed_dense, embed_sparse
    await asyncio.gather(
        asyncio.to_thread(embed_dense, ["evaluation warmup"]),
        asyncio.to_thread(embed_sparse, ["evaluation warmup"]),
    )

    paths = sorted(GOLDEN.glob("brief_*.json"))
    if args.subset.startswith("tag="):
        tag = args.subset[4:]
        paths = [path for path in paths
                 if tag in json.loads(path.read_text(encoding="utf-8")).get("tags", [])]
    if args.limit:
        paths = paths[:args.limit]

    golden_to_segment, segment_to_label = _catalog_maps()
    semaphore = asyncio.Semaphore(args.concurrency)

    async def guarded(path):
        async with semaphore:
            try:
                result = await evaluate_case(
                    path, golden_to_segment, segment_to_label, args)
                print(f"  {result['id']}: r50={result['retrieval_recall']:.3f} "
                      f"must{args.final_k}={result['must_recall_at_k']:.3f} "
                      f"ndcg{args.final_k}={result['ndcg_at_k']:.3f}")
                return result
            except Exception as exc:
                print(f"  {path.stem}: ERROR {type(exc).__name__}: {str(exc)[:120]}")
                return {"id": path.stem, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    results = await asyncio.gather(*(guarded(path) for path in paths))
    ok = [result for result in results if "error" not in result]
    totals = [result["latency_s"]["total"] for result in ok]
    summary = {
        "n": len(results),
        "errors": len(results) - len(ok),
        f"mean_retrieval_recall@{args.retrieve_k}": round(statistics.mean(
            r["retrieval_recall"] for r in ok if r["retrieval_recall"] is not None), 3) if ok else None,
        f"mean_must_recall@{args.final_k}": round(statistics.mean(
            r["must_recall_at_k"] for r in ok), 3) if ok else None,
        f"mean_mrr@{args.final_k}": round(statistics.mean(
            r["mrr_at_k"] for r in ok), 3) if ok else None,
        f"mean_ndcg@{args.final_k}": round(statistics.mean(
            r["ndcg_at_k"] for r in ok if r["ndcg_at_k"] is not None), 3) if ok else None,
        "exclusion_violations_total": sum(len(r["exclusion_violations"]) for r in ok),
        "unknown_labels_total": sum(len(r["unknown_labels"]) for r in ok),
        "rerank_successes": sum(1 for r in ok if r["reranked"]),
        "p50_latency_s": _percentile(totals, 0.50),
        "p95_latency_s": _percentile(totals, 0.95),
    }
    report = {
        "label": args.label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "dense_model": config.RAG_DENSE_MODEL,
            "sparse_model": config.RAG_SPARSE_MODEL,
            "rerank_model": config.RERANK_MODEL if args.rerank else None,
            "rewrite": args.rewrite,
            "rerank": args.rerank,
            "include_raw_with_rewrite": args.include_raw_with_rewrite,
            "raw_query_mode": args.raw_query_mode if not args.rewrite else None,
            "retrieve_k": args.retrieve_k,
            "final_k": args.final_k,
            "mirrors_production_defaults": {
                "rewrite": args.rewrite == config.RAG_QUERY_REWRITE,
                "rerank": args.rerank == config.RAG_USE_RERANK,
                "retrieve_k": args.retrieve_k == config.RAG_TOP_RETRIEVE,
                "final_k": args.final_k == config.RAG_TOP_FINAL,
            },
            "index": index,
        },
        "summary": summary,
        "results": results,
    }
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / f"{args.label}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report -> {path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
