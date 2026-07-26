"""Compare audience retrieval/reranking configurations on the 80-brief set.

The benchmark evaluates the candidate ordering before the final conversational
selector. This isolates whether BM25, dense retrieval, and nano reranking
actually improve catalog relevance rather than merely changing prose.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
AGENT = ROOT / "agent"
GOLDEN = ROOT / "eval" / "golden_set"
sys.path.insert(0, str(AGENT))

from config import config  # noqa: E402
from rag.index import build_index, inspect_index  # noqa: E402
from rag.nano_rerank import rerank_candidates  # noqa: E402
from rag.recommend import _guard_reason, _hybrid_search, _raw_query  # noqa: E402


VARIANTS = (
    {
        "id": "bm25_baseline",
        "label": "Deterministic BM25 sparse retrieval",
        "retrieval_mode": "bm25_only",
        "reranker": "off",
    },
    {
        "id": "dense_bm25",
        "label": "Dense semantic + BM25 retrieval",
        "retrieval_mode": "hybrid_dense_bm25",
        "reranker": "off",
    },
    {
        "id": "dense_bm25_nano",
        "label": "Dense semantic + BM25 + GPT-5.4-nano reranking",
        "retrieval_mode": "hybrid_dense_bm25",
        "reranker": "openai_nano",
    },
)


def _catalog_maps() -> tuple[dict[str, str], dict[str, str]]:
    items = json.loads((GOLDEN / "catalog_full.json").read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("data") or items.get("attributes") or []
    return (
        {item["_id"]: item["segmentId"] for item in items},
        {item["segmentId"]: item["fullLabel"] for item in items},
    )


def _identity(candidate: dict) -> str:
    return str(
        candidate.get("segmentId")
        or candidate.get("_id")
        or candidate.get("fullLabel")
        or candidate.get("name")
        or ""
    )


def _dcg(ids: list[str], grades: dict[str, int], limit: int) -> float:
    return sum(
        grades.get(value, 0) / math.log2(rank + 1)
        for rank, value in enumerate(ids[:limit], start=1)
    )


def _metric_at_k(
    ranked_ids: list[str],
    must_ids: set[str],
    acceptable_ids: set[str],
    excluded_ids: set[str],
    limit: int,
) -> dict:
    top = ranked_ids[:limit]
    relevant = must_ids | acceptable_ids
    first_rank = next(
        (rank for rank, value in enumerate(top, start=1) if value in relevant),
        None,
    )
    grades = {value: 1 for value in acceptable_ids}
    grades.update({value: 2 for value in must_ids})
    ideal_grades = sorted(grades.values(), reverse=True)[:limit]
    ideal_dcg = sum(
        grade / math.log2(rank + 1)
        for rank, grade in enumerate(ideal_grades, start=1)
    )
    return {
        "must_recall": (
            len(must_ids & set(top)) / len(must_ids) if must_ids else None
        ),
        "relevant_recall": (
            len(relevant & set(top)) / len(relevant) if relevant else None
        ),
        "mrr": round(1 / first_rank, 4) if first_rank else 0,
        "ndcg": round(_dcg(top, grades, limit) / ideal_dcg, 4)
        if ideal_dcg else None,
        "exclusion_violations": sorted(excluded_ids & set(top)),
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[int((len(ordered) - 1) * percentile)], 3)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="eval/reports/np6-audience-matrix.json",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Evaluate only selected variant IDs; may be repeated.",
    )
    parser.add_argument("--retrieve-k", type=int, default=50)
    parser.add_argument("--rerank-k", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument(
        "--embedded-qdrant-path",
        default="",
        help="Use an isolated local Qdrant path instead of the configured server.",
    )
    parser.add_argument("--force-index", action="store_true")
    parser.add_argument(
        "--candidate-export",
        default="",
        help="Optional JSON export of retrieved candidates for isolated rerank runs.",
    )
    args = parser.parse_args()

    if args.embedded_qdrant_path:
        from qdrant_client import QdrantClient
        import rag.index as rag_index

        rag_index._qdrant = QdrantClient(path=args.embedded_qdrant_path)
        rag_index._index_checked = False

    if args.force_index:
        await build_index(force=True)
    index = await inspect_index()
    if not index.get("ready"):
        raise SystemExit(f"Audience index is not ready: {index}")

    paths = sorted(GOLDEN.glob("brief_*.json"))
    if args.case_id:
        selected = set(args.case_id)
        paths = [
            path for path in paths
            if json.loads(path.read_text(encoding="utf-8"))["id"] in selected
        ]
    if args.limit:
        paths = paths[:args.limit]
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    golden_to_segment, segment_to_label = _catalog_maps()

    # Initialize CPU models outside timed case execution.
    from rag.embeddings import embed_dense, embed_sparse
    await asyncio.gather(
        asyncio.to_thread(embed_dense, ["audience evaluation warmup"]),
        asyncio.to_thread(embed_sparse, ["audience evaluation warmup"]),
    )

    retrieval_cache: dict[tuple[str, str], tuple[list[dict], float]] = {}
    cache_lock = asyncio.Lock()

    async def retrieve(case: dict, mode: str) -> tuple[list[dict], float]:
        key = (case["id"], mode)
        async with cache_lock:
            cached = retrieval_cache.get(key)
        if cached is not None:
            return cached
        started = time.perf_counter()
        candidates = await _hybrid_search(
            [_raw_query(case["brief"])],
            args.retrieve_k,
            mode=mode,
        )
        value = (candidates, time.perf_counter() - started)
        async with cache_lock:
            retrieval_cache[key] = value
        return value

    async def evaluate_case(case: dict, variant: dict) -> dict:
        candidates, retrieval_s = await retrieve(
            case, variant["retrieval_mode"]
        )
        ranked = list(candidates)
        rerank_meta = {
            "applied": False,
            "mode": variant["reranker"],
            "reason": "disabled",
        }
        rerank_s = 0.0
        if variant["reranker"] == "openai_nano":
            started = time.perf_counter()
            order, rerank_meta = await rerank_candidates(
                _raw_query(case["brief"]),
                ranked,
                candidate_limit=args.rerank_k,
            )
            rerank_s = time.perf_counter() - started
            if order:
                bounded = ranked[:args.rerank_k]
                ranked = [bounded[index] for index in order] + ranked[args.rerank_k:]

        guarded: list[dict] = []
        guard_rejected: list[dict] = []
        for candidate in ranked:
            reason = _guard_reason(case["brief"], candidate)
            if reason:
                guard_rejected.append({
                    "segment_id": _identity(candidate),
                    "label": candidate.get("fullLabel") or candidate.get("name"),
                    "reason": reason,
                })
                continue
            guarded.append(candidate)
        ranked = guarded

        audience = case["labels"]["audience"]
        must_ids = {
            golden_to_segment.get(value, value)
            for value in audience.get("must_include", [])
        }
        acceptable_ids = {
            golden_to_segment.get(value, value)
            for value in audience.get("acceptable", [])
        }
        excluded_ids = {
            golden_to_segment.get(value, value)
            for value in audience.get("must_exclude", [])
        }
        retrieved_ids = [_identity(candidate) for candidate in candidates]
        ranked_ids = [_identity(candidate) for candidate in ranked]
        at6 = _metric_at_k(
            ranked_ids, must_ids, acceptable_ids, excluded_ids, 6
        )
        at25 = _metric_at_k(
            ranked_ids, must_ids, acceptable_ids, excluded_ids, 25
        )
        relevant = must_ids | acceptable_ids
        return {
            "id": case["id"],
            "tags": case.get("tags", []),
            "brief": case["brief"],
            "expected": {
                "must_include": [
                    segment_to_label.get(value, value) for value in sorted(must_ids)
                ],
                "acceptable": [
                    segment_to_label.get(value, value)
                    for value in sorted(acceptable_ids)
                ],
                "must_exclude": [
                    segment_to_label.get(value, value)
                    for value in sorted(excluded_ids)
                ],
            },
            "retrieval_recall_at_50": (
                len(relevant & set(retrieved_ids)) / len(relevant)
                if relevant else None
            ),
            "at_6": {
                **at6,
                "exclusion_violations": [
                    segment_to_label.get(value, value)
                    for value in at6["exclusion_violations"]
                ],
            },
            "at_25": {
                **at25,
                "exclusion_violations": [
                    segment_to_label.get(value, value)
                    for value in at25["exclusion_violations"]
                ],
            },
            "guard_rejected": guard_rejected,
            "rerank": rerank_meta,
            "latency_s": {
                "retrieve": round(retrieval_s, 3),
                "rerank": round(rerank_s, 3),
                "total": round(retrieval_s + rerank_s, 3),
            },
            "top_segments": [
                {
                    "rank": rank,
                    "segment_id": _identity(candidate),
                    "label": candidate.get("fullLabel") or candidate.get("name"),
                    "type": candidate.get("type"),
                    "category": candidate.get("category"),
                    "subcategory": candidate.get("subcategory"),
                    "judgment": (
                        "must_include"
                        if _identity(candidate) in must_ids
                        else "acceptable"
                        if _identity(candidate) in acceptable_ids
                        else "must_exclude"
                        if _identity(candidate) in excluded_ids
                        else "unlabeled"
                    ),
                }
                for rank, candidate in enumerate(ranked[:10], start=1)
            ],
        }

    selected_variants = [
        variant for variant in VARIANTS
        if not args.variant or variant["id"] in set(args.variant)
    ]
    reports = []
    for variant in selected_variants:
        print(f"Evaluating {variant['label']} ({len(cases)} cases)...", flush=True)
        semaphore = asyncio.Semaphore(max(args.concurrency, 1))

        async def guarded(case: dict):
            async with semaphore:
                try:
                    return await evaluate_case(case, variant)
                except Exception as exc:
                    return {
                        "id": case["id"],
                        "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    }

        results = await asyncio.gather(*(guarded(case) for case in cases))
        valid = [result for result in results if "error" not in result]
        latencies = [result["latency_s"]["total"] for result in valid]

        def mean(path: tuple[str, str]) -> float | None:
            values = [
                result[path[0]][path[1]]
                for result in valid
                if result[path[0]][path[1]] is not None
            ]
            return round(statistics.mean(values), 4) if values else None

        summary = {
            "cases": len(results),
            "errors": len(results) - len(valid),
            "mean_retrieval_recall_at_50": round(statistics.mean(
                result["retrieval_recall_at_50"]
                for result in valid
                if result["retrieval_recall_at_50"] is not None
            ), 4) if valid else None,
            "mean_must_recall_at_6": mean(("at_6", "must_recall")),
            "mean_relevant_recall_at_6": mean(("at_6", "relevant_recall")),
            "mean_mrr_at_6": mean(("at_6", "mrr")),
            "mean_ndcg_at_6": mean(("at_6", "ndcg")),
            "exclusion_violations_at_6": sum(
                len(result["at_6"]["exclusion_violations"]) for result in valid
            ),
            "mean_must_recall_at_25": mean(("at_25", "must_recall")),
            "mean_ndcg_at_25": mean(("at_25", "ndcg")),
            "exclusion_violations_at_25": sum(
                len(result["at_25"]["exclusion_violations"]) for result in valid
            ),
            "guard_rejections": sum(
                len(result["guard_rejected"]) for result in valid
            ),
            "rerank_applied_cases": sum(
                bool(result["rerank"].get("applied")) for result in valid
            ),
            "mean_latency_s": round(statistics.mean(latencies), 3)
            if latencies else None,
            "p50_latency_s": _percentile(latencies, 0.5),
            "p95_latency_s": _percentile(latencies, 0.95),
        }
        reports.append({**variant, "summary": summary, "results": results})
        print(json.dumps({variant["id"]: summary}, ensure_ascii=False, indent=2))

    report = {
        "schema": "np6-audience-recommendation-matrix-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "catalog": index,
        "retrieve_k": args.retrieve_k,
        "rerank_k": args.rerank_k,
        "variants": reports,
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if args.candidate_export:
        candidate_output = Path(args.candidate_export)
        if not candidate_output.is_absolute():
            candidate_output = ROOT / candidate_output
        candidate_output.parent.mkdir(parents=True, exist_ok=True)
        candidate_output.write_text(
            json.dumps({
                "schema": "np6-audience-candidate-cache-v1",
                "catalog": index,
                "retrieve_k": args.retrieve_k,
                "cases": [
                    {
                        "id": case["id"],
                        "brief": case["brief"],
                        "labels": case["labels"],
                        "tags": case.get("tags", []),
                        "retrieval": {
                            mode: {
                                "latency_s": round(latency, 3),
                                "candidates": candidates,
                            }
                            for (case_id, mode), (candidates, latency)
                            in retrieval_cache.items()
                            if case_id == case["id"]
                        },
                    }
                    for case in cases
                ],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"candidate cache -> {candidate_output}")
    print(f"report -> {output}")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(main()))
