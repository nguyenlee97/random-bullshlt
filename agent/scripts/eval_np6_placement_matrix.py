"""Compare NP-6 placement ranking configurations on the full labeled suite.

The report is deliberately case-level: aggregate accuracy alone can hide a
configuration that improves common topics while regressing difficult synonyms.
Run from the repository root:

    agent/venv/Scripts/python.exe agent/scripts/eval_np6_placement_matrix.py \
        --repo-catalog --output eval/reports/np6-placement-matrix.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[1]))

from config import config
from tools.placement_relevance import build_placement_context
from tools.zone_ranker import rank_zones
from tools import zone_catalog


VARIANTS = (
    {
        "id": "deterministic_baseline",
        "label": "Deterministic contextual baseline",
        "rag": False,
        "rerank": False,
    },
    {
        "id": "dense_bm25",
        "label": "Dense semantic + BM25 retrieval",
        "rag": True,
        "rerank": False,
    },
    {
        "id": "dense_bm25_nano",
        "label": "Dense semantic + BM25 + GPT-5.4-nano reranking",
        "rag": True,
        "rerank": True,
    },
)


def _repository_placements() -> list[dict]:
    repo = Path(__file__).parents[2]
    source = r"""
const path = require('node:path');
const { readWorksheetRows } = require('./backend/seed/workbook-rows');
const { buildZonesCatalog } = require('./backend/seed');
(async () => {
  const raw = await readWorksheetRows(
    path.join(process.cwd(), 'backend', 'seed', 'data', 'Ads Zone.xlsx'),
    'Ad Zones'
  );
  const rows = raw.map((row) => ({
    mockId: row['Zone ID'],
    reach: row.Reach || 0,
    vi: row['VI %'] || 0,
    ctr: row['CTR %'] || 0,
    cpm: row['CPM VND'] || 0,
    obj: row['Best For'] || 'awareness',
    note: row.Notes || '',
  }));
  process.stdout.write(JSON.stringify(buildZonesCatalog(rows).placements));
})().catch((error) => { console.error(error); process.exit(1); });
"""
    result = subprocess.run(
        ["node", "-e", source],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def _unique_topics(ranked: list[dict], limit: int = 5) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for zone in ranked:
        topic = str(zone.get("topicId") or "legacy_other")
        if topic in seen:
            continue
        seen.add(topic)
        basis = zone.get("recommendation_basis") or {}
        retrieval = zone.get("placement_retrieval") or {}
        rows.append({
            "topic_id": topic,
            "placement_id": zone.get("id"),
            "placement_name": zone.get("name"),
            "publisher": zone.get("publisher") or zone.get("platform"),
            "ranking_mode": zone.get("ranking_mode"),
            "context_score": round(float(
                (zone.get("topic_relevance") or {}).get("score") or 0
            ), 4),
            "performance_score": round(float(zone.get("score") or 0), 4),
            "semantic_match": bool(basis.get("semantic_match")),
            "dense_score": retrieval.get("dense_score"),
            "sparse_score": retrieval.get("sparse_score"),
            "retrieval_rank": retrieval.get("rank"),
            "topic_rerank_rank": retrieval.get("topic_rerank_rank"),
            "topic_rerank_score": retrieval.get("topic_rerank_score"),
        })
        if len(rows) >= limit:
            break
    return rows


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int((len(ordered) - 1) * percentile)
    return round(ordered[index], 3)


async def _evaluate_variant(
    variant: dict[str, Any],
    cases: list[dict],
    placements: list[dict],
) -> dict:
    config.PLACEMENT_RAG_ENABLED = bool(variant["rag"])
    config.PLACEMENT_RERANK_ENABLED = bool(variant["rerank"])
    results: list[dict] = []

    for case in cases:
        started = time.perf_counter()
        context = build_placement_context(case["brief"], case.get("audience") or [])
        ranked = await rank_zones(
            objective=case["brief"].get("objective", "awareness"),
            budget=case["brief"].get("budget", 0),
            kpi=case["brief"].get("kpi", ""),
            creative_files=[],
            placement_context=context,
            limit=len(placements),
        )
        elapsed = time.perf_counter() - started
        topics = _unique_topics(ranked)
        expected = case["expected_topic"]
        expected_rank = next(
            (index for index, item in enumerate(topics, start=1)
             if item["topic_id"] == expected),
            None,
        )
        first = ranked[0] if ranked else {}
        rerank_meta = first.get("rerank_meta") or {}
        results.append({
            "id": case["id"],
            "case_group": case.get("case_group") or (
                "semantic_synonym" if case.get("expect_semantic") else "baseline"
            ),
            "brief": case["brief"],
            "audience": case.get("audience") or [],
            "expected_topic": expected,
            "expected_topic_rank": expected_rank,
            "top1_correct": expected_rank == 1,
            "top3_correct": expected_rank is not None and expected_rank <= 3,
            "reciprocal_rank": round(1 / expected_rank, 4) if expected_rank else 0,
            "latency_s": round(elapsed, 3),
            "ranking_mode": first.get("ranking_mode"),
            "retrieval_applied": bool(
                (first.get("recommendation_basis") or {}).get("retrieval_applied")
            ),
            "retrieval_mode": (
                (first.get("recommendation_basis") or {}).get("retrieval_mode")
            ),
            "rerank_applied": bool(rerank_meta.get("applied")),
            "rerank_model": rerank_meta.get("model"),
            "rerank_reason": rerank_meta.get("reason"),
            "top_topics": topics,
            "top_placements": [
                {
                    "id": zone.get("id"),
                    "name": zone.get("name"),
                    "publisher": zone.get("publisher") or zone.get("platform"),
                    "topic_id": zone.get("topicId"),
                    "recommended_basis": zone.get("recommendation_basis"),
                    "rerank_meta": zone.get("rerank_meta"),
                }
                for zone in ranked[:6]
            ],
        })

    latencies = [row["latency_s"] for row in results]
    return {
        **variant,
        "summary": {
            "cases": len(results),
            "top1_correct": sum(row["top1_correct"] for row in results),
            "top1_accuracy": round(
                sum(row["top1_correct"] for row in results) / max(len(results), 1),
                4,
            ),
            "top3_correct": sum(row["top3_correct"] for row in results),
            "top3_accuracy": round(
                sum(row["top3_correct"] for row in results) / max(len(results), 1),
                4,
            ),
            "mean_reciprocal_rank": round(statistics.mean(
                row["reciprocal_rank"] for row in results
            ), 4),
            "semantic_cases": sum(
                row["case_group"] == "semantic_synonym" for row in results
            ),
            "semantic_top1_accuracy": round(
                sum(
                    row["top1_correct"]
                    for row in results
                    if row["case_group"] == "semantic_synonym"
                ) / max(sum(
                    row["case_group"] == "semantic_synonym" for row in results
                ), 1),
                4,
            ),
            "rerank_applied_cases": sum(row["rerank_applied"] for row in results),
            "p50_latency_s": _percentile(latencies, 0.5),
            "p95_latency_s": _percentile(latencies, 0.95),
            "mean_latency_s": round(statistics.mean(latencies), 3),
        },
        "results": results,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-catalog", action="store_true")
    parser.add_argument(
        "--output",
        default="eval/reports/np6-placement-matrix.json",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Evaluate only selected case IDs; may be repeated.",
    )
    args = parser.parse_args()

    eval_dir = Path(__file__).parents[1] / "evals"
    cases = []
    for name in (
        "np6_placement_relevance_cases.json",
        "np6_placement_relevance_hard_cases.json",
        "np6_placement_relevance_audience_cases.json",
    ):
        cases.extend(json.loads((eval_dir / name).read_text(encoding="utf-8")))
    if args.case_id:
        selected = set(args.case_id)
        cases = [case for case in cases if case["id"] in selected]

    if args.repo_catalog:
        placements = _repository_placements()
        catalog_source = "repository://backend/seed"
    else:
        import httpx

        async with httpx.AsyncClient(
            base_url=config.BACKEND_URL, timeout=30
        ) as client:
            response = await client.get("/api/zones/placements")
            response.raise_for_status()
            placements = response.json()
        catalog_source = config.BACKEND_URL

    original_get_all_zones = zone_catalog.get_all_zones
    original_rag = config.PLACEMENT_RAG_ENABLED
    original_rerank = config.PLACEMENT_RERANK_ENABLED

    async def fixed_catalog():
        return placements

    zone_catalog.get_all_zones = fixed_catalog
    try:
        variants = []
        for variant in VARIANTS:
            print(f"Evaluating {variant['label']} ({len(cases)} cases)...", flush=True)
            variants.append(await _evaluate_variant(variant, cases, placements))
    finally:
        zone_catalog.get_all_zones = original_get_all_zones
        config.PLACEMENT_RAG_ENABLED = original_rag
        config.PLACEMENT_RERANK_ENABLED = original_rerank

    report = {
        "schema": "np6-placement-ranking-matrix-v1",
        "catalog_source": catalog_source,
        "placement_count": len(placements),
        "topic_count": len({
            placement.get("topicId") for placement in placements
            if placement.get("topicId")
        }),
        "case_count": len(cases),
        "case_ids": [case["id"] for case in cases],
        "variants": variants,
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = Path(__file__).parents[2] / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(
        {item["id"]: item["summary"] for item in variants},
        ensure_ascii=False,
        indent=2,
    ))
    print(f"report -> {output}")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(main()))
