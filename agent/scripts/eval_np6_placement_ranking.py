"""Evaluate deterministic NP-6 topic ranking against a running zone API."""
from __future__ import annotations

import asyncio
import argparse
import json
from pathlib import Path
import subprocess
import sys

import httpx

sys.path.insert(0, str(Path(__file__).parents[1]))

from config import config
from tools.placement_relevance import (
    build_placement_context,
    score_placement_relevance,
)
from tools.zone_ranker import rank_zones
from tools import zone_catalog


def repository_placements() -> list[dict]:
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


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-catalog",
        action="store_true",
        help="Evaluate the catalog built from the repository workbook without Mongo/API.",
    )
    parser.add_argument(
        "--cases",
        choices=("baseline", "hard", "all"),
        default="baseline",
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Enable hybrid placement retrieval for this evaluation process.",
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Enable the configured bounded placement reranker.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Evaluate only the named case ID; may be supplied more than once.",
    )
    args = parser.parse_args()
    eval_dir = Path(__file__).parents[1] / "evals"
    baseline = json.loads(
        (eval_dir / "np6_placement_relevance_cases.json").read_text(
            encoding="utf-8",
        )
    )
    hard = json.loads(
        (eval_dir / "np6_placement_relevance_hard_cases.json").read_text(
            encoding="utf-8",
        )
    )
    cases = (
        baseline
        if args.cases == "baseline"
        else hard
        if args.cases == "hard"
        else baseline + hard
    )
    if args.case_id:
        selected = set(args.case_id)
        cases = [case for case in cases if case["id"] in selected]
    if args.repo_catalog:
        placements = repository_placements()
        catalog_url = "repository://backend/seed"
    else:
        async with httpx.AsyncClient(base_url=config.BACKEND_URL, timeout=20) as client:
            response = await client.get("/api/zones/placements")
            response.raise_for_status()
            placements = response.json()
        catalog_url = config.BACKEND_URL

    topic_placements = [
        placement for placement in placements
        if placement.get("topicId") and placement.get("audienceContext")
    ]
    passed = 0
    rows = []
    original_get_all_zones = zone_catalog.get_all_zones
    original_rerank_enabled = config.PLACEMENT_RERANK_ENABLED
    original_rag_enabled = config.PLACEMENT_RAG_ENABLED

    async def fixed_catalog():
        return placements

    zone_catalog.get_all_zones = fixed_catalog
    config.PLACEMENT_RERANK_ENABLED = args.rerank
    config.PLACEMENT_RAG_ENABLED = args.rag
    try:
        for case in cases:
            context = build_placement_context(case["brief"], case["audience"])
            scored = sorted(
                (
                    (score_placement_relevance(zone, context)["score"], zone)
                    for zone in topic_placements
                ),
                key=lambda item: (-item[0], item[1]["id"]),
            )
            classifier_topic = scored[0][1]["topicId"] if scored else None
            ranked = await rank_zones(
                objective=case["brief"].get("objective", "awareness"),
                budget=case["brief"].get("budget", 0),
                kpi=case["brief"].get("kpi", ""),
                creative_files=[],
                placement_context=context,
                limit=1,
            )
            recommendation_topic = ranked[0].get("topicId") if ranked else None
            ok = (
                recommendation_topic == case["expected_topic"]
                and (
                    case.get("expect_semantic") is True
                    or classifier_topic == case["expected_topic"]
                )
            )
            passed += int(ok)
            rows.append({
                "id": case["id"],
                "expected": case["expected_topic"],
                "classifier_topic": classifier_topic,
                "recommendation_topic": recommendation_topic,
                "score": scored[0][0] if scored else 0,
                "ranking_mode": ranked[0].get("ranking_mode") if ranked else None,
                "retrieval": ranked[0].get("placement_retrieval") if ranked else None,
                "rerank": ranked[0].get("rerank_meta") if ranked else None,
                "passed": ok,
            })
    finally:
        zone_catalog.get_all_zones = original_get_all_zones
        config.PLACEMENT_RERANK_ENABLED = original_rerank_enabled
        config.PLACEMENT_RAG_ENABLED = original_rag_enabled

    report = {
        "catalog_url": catalog_url,
        "placement_count": len(placements),
        "topic_placement_count": len(topic_placements),
        "case_set": args.cases,
        "rag_enabled": args.rag,
        "rerank_enabled": args.rerank,
        "passed": passed,
        "total": len(cases),
        "accuracy": round(passed / max(len(cases), 1), 4),
        "cases": rows,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
