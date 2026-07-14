"""
Golden-set eval runner (07-eval-framework.md §5).

Per brief: fresh session → commit brief via the real workspace endpoint →
GET /dmp-recommend → deterministic metrics + LLM judge → report.

Usage (agent must be running):
    python eval/run_eval.py                       # full set, judge on
    python eval/run_eval.py --no-judge            # deterministic metrics only (free)
    python eval/run_eval.py --subset tag=adversarial --concurrency 2
    python eval/run_eval.py --agent-url http://localhost:8000

Metrics (canonical names from 07-eval-framework.md §2):
    audience_recall@k, exclusion_violations (target 0 ⛔), judge_score, latency.
Report → eval/reports/<label>.json + console table. Compare runs manually or
via the CI gate thresholds in eval/gate.yml (Phase 4).
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
GOLDEN = ROOT / "golden_set"
REPORTS = ROOT / "reports"
AGENT_DIR = ROOT.parent / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from eval_utils import rec_segment_ids, resolve_segments

# Map recommendation fullLabels back to _ids using the FULL live catalog (310+ segments;
# AUTHORING-GUIDE.md v2 — the old 71-item audience_library.json dump is a subset and would
# silently under-map any full_catalog_only-tagged brief's recommendations to no _id at all).
CATALOG = GOLDEN / "catalog_full.json"


def load_catalog_maps() -> tuple[dict[str, str], dict[str, str]]:
    """Map golden Mongo ids to stable segmentIds, then ids to display labels."""
    items = json.loads(CATALOG.read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("data") or items.get("attributes") or []
    return (
        {it["_id"]: it["segmentId"] for it in items
         if it.get("_id") and it.get("segmentId")},
        {it["segmentId"]: it["fullLabel"] for it in items
         if it.get("segmentId") and it.get("fullLabel")},
    )


async def get_recommendation(client: httpx.AsyncClient, url: str, headers: dict,
                             session_id: str) -> httpx.Response:
    """Retry idempotent recommendation reads on throttling/transient timeout."""
    for attempt in range(3):
        try:
            response = await client.get(
                url, headers=headers, params={"session_id": session_id}, timeout=180)
            if response.status_code != 429:
                return response
            retry_after = float(response.headers.get("Retry-After", "6"))
        except httpx.ReadTimeout:
            if attempt == 2:
                raise
            retry_after = 2 ** attempt
        await asyncio.sleep(min(max(retry_after, 1), 60))
    return response


async def eval_one(client: httpx.AsyncClient, brief_file: Path, agent_url: str,
                   headers: dict, golden_to_segment: dict, segment_to_label: dict,
                   use_judge: bool, k: int,
                   expect_rag: bool) -> dict:
    case = json.loads(brief_file.read_text(encoding="utf-8"))
    sid = f"eval_{uuid.uuid4().hex[:10]}"
    # 1. Commit the confirmed brief through the same endpoint used by the UI's
    # confirmation button. This persists real session state without paying for
    # unrelated brief-analysis generation in an audience-only benchmark.
    r = await client.post(
        f"{agent_url}/api/agent/commit-workspace", headers=headers, timeout=30,
        json={"session_id": sid, "field": "brief", "value": case["brief"]})
    r.raise_for_status()

    # 2. audience recommendation
    t0 = time.time()  # recommendation latency only; brief analysis is a separate operation
    r = await get_recommendation(
        client, f"{agent_url}/api/agent/dmp-recommend", headers, sid)
    r.raise_for_status()
    response_data = r.json()
    recs = response_data.get("recommendations", [])
    latency = time.time() - t0

    # 3. Use segmentId for joins: unlike Mongo _id it survives reseeding, and
    # unlike fullLabel it is unaffected by display-name drift.
    label_to_segment = {label: value for value, label in segment_to_label.items()}
    ordered_got = rec_segment_ids(recs, label_to_segment)[:k]
    got = set(ordered_got)
    labels = case["labels"]["audience"]
    must = resolve_segments(labels["must_include"], golden_to_segment)
    excl = resolve_segments(labels["must_exclude"], golden_to_segment)
    recall = len(must & got) / len(must) if must else None
    violations = sorted(segment_to_label.get(value, value) for value in excl & got)
    first_relevant_rank = next(
        (rank for rank, label in enumerate(ordered_got, start=1) if label in must), None)
    mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
    unknown = sorted(value for value in got if value not in segment_to_label)
    rag_meta = response_data.get("rag")

    out = {
        "id": case["id"], "tags": case.get("tags", []),
        "n_recs": len(recs), "recall_at_k": recall,
        "mrr_at_k": round(mrr, 4),
        "exclusion_violations": violations,
        "unknown_recommendations": unknown,
        "latency_s": round(latency, 2),
        "rag": rag_meta,
        "rag_fallback": bool(expect_rag and not rag_meta),
        "recommendations": [
            {"segmentId": rec.get("segmentId"),
             "fullLabel": rec.get("fullLabel") or rec.get("name", ""),
             "reason": rec.get("reason", "")}
            for rec in recs
        ],
    }

    # 4. judge — labels resolved to human-readable fullLabels (raw _ids were
    # uninterpretable for the judge's label_recall criterion — same bugfix)
    if use_judge:
        from judge import judge_audience
        judge_labels = {"audience": {
            "must_include": sorted(segment_to_label.get(value, value) for value in must),
            "acceptable": sorted(segment_to_label.get(value, value) for value in
                                 resolve_segments(labels.get("acceptable", []),
                                                  golden_to_segment)),
            "must_exclude": sorted(segment_to_label.get(value, value) for value in excl)}}
        j = await judge_audience(case["brief"], judge_labels, recs)
        out["judge"] = j["scores"]
        out["judge_mean"] = round(j["mean"], 2)
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-url", default="http://localhost:8000")
    ap.add_argument("--api-key", default="", help="X-API-Key if auth enabled")
    ap.add_argument("--subset", default="", help="tag=<value> filter")
    ap.add_argument("--case", default="", help="single case id, e.g. brief_073")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--repeat", type=int, default=1,
                    help="repeat selected cases to measure stochastic stability")
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--label", default="", help="report filename label")
    ap.add_argument("--expect-rag", action="store_true",
                    help="count responses without RAG metadata as fallbacks")
    args = ap.parse_args()

    briefs = sorted(GOLDEN.glob("brief_*.json"))
    if args.case:
        briefs = [brief for brief in briefs if brief.stem == args.case]
    if args.subset.startswith("tag="):
        tag = args.subset[4:]
        briefs = [b for b in briefs
                  if tag in json.loads(b.read_text(encoding="utf-8")).get("tags", [])]
    if args.limit:
        briefs = briefs[:args.limit]
    briefs = briefs * max(args.repeat, 1)
    if not briefs:
        sys.exit("no briefs matched")

    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    golden_to_segment, segment_to_label = load_catalog_maps()
    sem = asyncio.Semaphore(args.concurrency)
    results = []

    async with httpx.AsyncClient() as client:
        async def guarded(bf):
            async with sem:
                try:
                    res = await eval_one(client, bf, args.agent_url, headers,
                                         golden_to_segment, segment_to_label,
                                         not args.no_judge, args.k,
                                         args.expect_rag)
                except Exception as e:
                    res = {"id": bf.stem, "error": f"{type(e).__name__}: {str(e)[:120]}"}
                print(f"  {res.get('id')}: recall={res.get('recall_at_k')} "
                      f"viol={res.get('exclusion_violations')} judge={res.get('judge_mean', '-')} "
                      f"{res.get('error', '')}")
                return res
        results = await asyncio.gather(*[guarded(b) for b in briefs])

    ok = [r for r in results if "error" not in r]
    recalls = [r["recall_at_k"] for r in ok if r["recall_at_k"] is not None]
    total_viol = sum(len(r["exclusion_violations"]) for r in ok)
    judge_means = [r["judge_mean"] for r in ok if "judge_mean" in r]
    latencies = sorted(r["latency_s"] for r in ok)
    mrrs = [r["mrr_at_k"] for r in ok]

    def percentile(values, p):
        if not values:
            return None
        idx = max(0, min(len(values) - 1, int((len(values) - 1) * p)))
        return round(values[idx], 2)

    summary = {
        "n": len(results), "errors": len(results) - len(ok),
        f"mean_recall@{args.k}": round(statistics.mean(recalls), 3) if recalls else None,
        f"mean_mrr@{args.k}": round(statistics.mean(mrrs), 3) if mrrs else None,
        "exclusion_violations_total": total_viol,   # ⛔ CI gate: must be 0
        "judge_score": round(statistics.mean(judge_means), 3) if judge_means else None,
        "unknown_recommendations_total": sum(len(r["unknown_recommendations"]) for r in ok),
        "rag_fallbacks": sum(1 for r in ok if r.get("rag_fallback")),
        "mean_recommendations": round(statistics.mean(r["n_recs"] for r in ok), 2) if ok else None,
        "p50_latency_s": percentile(latencies, 0.50),
        "p95_latency_s": percentile(latencies, 0.95),
    }
    print("\n== SUMMARY ==\n" + json.dumps(summary, indent=2, ensure_ascii=False))

    REPORTS.mkdir(exist_ok=True)
    label = args.label or time.strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS / f"{label}.json"
    report_path.write_text(json.dumps({
                                      "label": label,
                                      "created_at": datetime.now(timezone.utc).isoformat(),
                                      "agent_url": args.agent_url,
                                      "k": args.k,
                                      "expect_rag": args.expect_rag,
                                      "summary": summary, "results": results},
                                      indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport -> {report_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
