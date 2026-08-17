"""Evaluate GPT-5.4-nano audience reranking from an exported candidate cache.

This runner is intentionally independent of Qdrant. It allows the expensive
reranker experiment to execute in an environment that owns OpenAI credentials
without copying credentials or changing the live audience feature flags.
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


def _identity(candidate: dict) -> str:
    return str(
        candidate.get("segmentId")
        or candidate.get("_id")
        or candidate.get("fullLabel")
        or candidate.get("name")
        or ""
    )


def _fold_catalog(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    items = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("data") or items.get("attributes") or []
    return (
        {item["_id"]: item["segmentId"] for item in items},
        {item["segmentId"]: item["fullLabel"] for item in items},
    )


def _dcg(ids: list[str], grades: dict[str, int], limit: int) -> float:
    return sum(
        grades.get(value, 0) / math.log2(rank + 1)
        for rank, value in enumerate(ids[:limit], start=1)
    )


def _metrics(
    ids: list[str],
    must: set[str],
    acceptable: set[str],
    excluded: set[str],
    limit: int,
) -> dict:
    top = ids[:limit]
    relevant = must | acceptable
    first = next(
        (rank for rank, value in enumerate(top, start=1) if value in relevant),
        None,
    )
    grades = {value: 1 for value in acceptable}
    grades.update({value: 2 for value in must})
    ideal = sorted(grades.values(), reverse=True)[:limit]
    ideal_dcg = sum(
        grade / math.log2(rank + 1)
        for rank, grade in enumerate(ideal, start=1)
    )
    return {
        "must_recall": len(must & set(top)) / len(must) if must else None,
        "relevant_recall": (
            len(relevant & set(top)) / len(relevant) if relevant else None
        ),
        "mrr": round(1 / first, 4) if first else 0,
        "ndcg": round(_dcg(top, grades, limit) / ideal_dcg, 4)
        if ideal_dcg else None,
        "exclusion_violations": sorted(excluded & set(top)),
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[int((len(ordered) - 1) * percentile)], 3)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--agent-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--rerank-k", type=int, default=30)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()

    sys.path.insert(0, args.agent_root)
    from config import config

    # Candidate-only experiments can run against an older deployed Config
    # object. These attributes do not modify the live service or its flags.
    defaults = {
        "AUDIENCE_NANO_RERANK_MODEL": "gpt-5.4-nano",
        "AUDIENCE_NANO_RERANK_REASONING_EFFORT": "low",
        "AUDIENCE_NANO_RERANK_CANDIDATE_LIMIT": args.rerank_k,
        "AUDIENCE_NANO_RERANK_MAX_OUTPUT_TOKENS": 3500,
        "AUDIENCE_NANO_RERANK_TIMEOUT_SECONDS": 30.0,
    }
    for name, value in defaults.items():
        if not hasattr(config, name):
            setattr(config, name, value)

    from rag.nano_rerank import rerank_candidates
    from rag.recommend import _guard_reason, _raw_query

    cache = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    mongo_to_segment, segment_to_label = _fold_catalog(Path(args.catalog))
    semaphore = asyncio.Semaphore(max(args.concurrency, 1))

    async def evaluate(case: dict) -> dict:
        async with semaphore:
            entry = case["retrieval"]["hybrid_dense_bm25"]
            candidates = entry["candidates"]
            started = time.perf_counter()
            order, meta = await rerank_candidates(
                _raw_query(case["brief"]),
                candidates,
                candidate_limit=args.rerank_k,
            )
            rerank_s = time.perf_counter() - started
            ranked = list(candidates)
            if order:
                bounded = ranked[:args.rerank_k]
                ranked = [bounded[index] for index in order] + ranked[args.rerank_k:]

            guarded, rejected = [], []
            for candidate in ranked:
                reason = _guard_reason(case["brief"], candidate)
                if reason:
                    rejected.append({
                        "segment_id": _identity(candidate),
                        "label": candidate.get("fullLabel") or candidate.get("name"),
                        "reason": reason,
                    })
                    continue
                guarded.append(candidate)
            ranked = guarded

            audience = case["labels"]["audience"]
            must = {
                mongo_to_segment.get(value, value)
                for value in audience.get("must_include", [])
            }
            acceptable = {
                mongo_to_segment.get(value, value)
                for value in audience.get("acceptable", [])
            }
            excluded = {
                mongo_to_segment.get(value, value)
                for value in audience.get("must_exclude", [])
            }
            ids = [_identity(candidate) for candidate in ranked]
            at6 = _metrics(ids, must, acceptable, excluded, 6)
            at25 = _metrics(ids, must, acceptable, excluded, 25)
            return {
                "id": case["id"],
                "tags": case.get("tags", []),
                "brief": case["brief"],
                "expected": {
                    "must_include": [
                        segment_to_label.get(value, value)
                        for value in sorted(must)
                    ],
                    "acceptable": [
                        segment_to_label.get(value, value)
                        for value in sorted(acceptable)
                    ],
                    "must_exclude": [
                        segment_to_label.get(value, value)
                        for value in sorted(excluded)
                    ],
                },
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
                "guard_rejected": rejected,
                "rerank": meta,
                "latency_s": {
                    "retrieve": entry.get("latency_s"),
                    "rerank": round(rerank_s, 3),
                    "total": round(
                        float(entry.get("latency_s") or 0) + rerank_s, 3
                    ),
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
                            if _identity(candidate) in must
                            else "acceptable"
                            if _identity(candidate) in acceptable
                            else "must_exclude"
                            if _identity(candidate) in excluded
                            else "unlabeled"
                        ),
                    }
                    for rank, candidate in enumerate(ranked[:10], start=1)
                ],
            }

    async def safe(case: dict):
        try:
            return await evaluate(case)
        except Exception as exc:
            return {
                "id": case["id"],
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            }

    cases = cache["cases"]
    if args.case_id:
        selected = set(args.case_id)
        cases = [case for case in cases if case["id"] in selected]
    if args.limit:
        cases = cases[:args.limit]
    results = await asyncio.gather(*(safe(case) for case in cases))
    valid = [row for row in results if "error" not in row]
    latencies = [row["latency_s"]["total"] for row in valid]

    def mean(section: str, metric: str) -> float | None:
        values = [
            row[section][metric]
            for row in valid
            if row[section][metric] is not None
        ]
        return round(statistics.mean(values), 4) if values else None

    summary = {
        "cases": len(results),
        "errors": len(results) - len(valid),
        "mean_must_recall_at_6": mean("at_6", "must_recall"),
        "mean_relevant_recall_at_6": mean("at_6", "relevant_recall"),
        "mean_mrr_at_6": mean("at_6", "mrr"),
        "mean_ndcg_at_6": mean("at_6", "ndcg"),
        "exclusion_violations_at_6": sum(
            len(row["at_6"]["exclusion_violations"]) for row in valid
        ),
        "mean_must_recall_at_25": mean("at_25", "must_recall"),
        "mean_ndcg_at_25": mean("at_25", "ndcg"),
        "exclusion_violations_at_25": sum(
            len(row["at_25"]["exclusion_violations"]) for row in valid
        ),
        "guard_rejections": sum(len(row["guard_rejected"]) for row in valid),
        "rerank_applied_cases": sum(
            bool(row["rerank"].get("applied")) for row in valid
        ),
        "mean_latency_s": round(statistics.mean(latencies), 3)
        if latencies else None,
        "p50_latency_s": _percentile(latencies, 0.5),
        "p95_latency_s": _percentile(latencies, 0.95),
    }
    report = {
        "schema": "np6-audience-nano-candidate-rerank-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_schema": cache.get("schema"),
        "variant": {
            "id": "dense_bm25_nano",
            "label": "Dense semantic + BM25 + GPT-5.4-nano reranking",
            "retrieval_mode": "hybrid_dense_bm25",
            "reranker": "openai_nano",
            "summary": summary,
            "results": results,
        },
    }
    Path(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
