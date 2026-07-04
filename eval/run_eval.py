"""
Golden-set eval runner (07-eval-framework.md §5).

Per brief: fresh session → set brief via the real formData path →
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
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
GOLDEN = ROOT / "golden_set"
REPORTS = ROOT / "reports"

# Map recommendation fullLabels back to _ids using the FULL live catalog (310+ segments;
# AUTHORING-GUIDE.md v2 — the old 71-item audience_library.json dump is a subset and would
# silently under-map any full_catalog_only-tagged brief's recommendations to no _id at all).
CATALOG = GOLDEN / "catalog_full.json"


def load_id_to_label() -> dict[str, str]:
    """Golden labels store VPS _ids; environments (docker/local) regenerate _ids
    on seed. fullLabel is the stable cross-environment key — ALL metric joins
    happen in label space. (Bug found 2026-07-04: recall=0.0 vs docker stack.)"""
    items = json.loads(CATALOG.read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("data") or items.get("attributes") or []
    return {it["_id"]: it["fullLabel"] for it in items if it.get("fullLabel") and it.get("_id")}


def resolve_labels(ids: list[str], id_to_label: dict[str, str]) -> set[str]:
    """label-space: unknown ids kept as-is (still comparable, just never match)."""
    return {id_to_label.get(i, i) for i in ids}


def rec_labels(recommendations: list[dict]) -> list[str]:
    return [r.get("fullLabel") or r.get("name", "") for r in recommendations
            if r.get("fullLabel") or r.get("name")]


async def eval_one(client: httpx.AsyncClient, brief_file: Path, agent_url: str,
                   headers: dict, id_to_label: dict, use_judge: bool, k: int) -> dict:
    case = json.loads(brief_file.read_text(encoding="utf-8"))
    sid = f"eval_{uuid.uuid4().hex[:10]}"
    t0 = time.time()

    # 1. set brief through the real deterministic path
    r = await client.post(f"{agent_url}/api/agent/chat", headers=headers, timeout=120, json={
        "session_id": sid, "step": 0, "message": "",
        "formData": {"brief": case["brief"]},
    })
    r.raise_for_status()

    # 2. audience recommendation
    r = await client.get(f"{agent_url}/api/agent/dmp-recommend",
                         headers=headers, params={"session_id": sid}, timeout=180)
    r.raise_for_status()
    recs = r.json().get("recommendations", [])
    latency = time.time() - t0

    # 3. deterministic metrics — ALL joins in fullLabel space (env-independent)
    got = set(rec_labels(recs)[:k])
    labels = case["labels"]["audience"]
    must = resolve_labels(labels["must_include"], id_to_label)
    excl = resolve_labels(labels["must_exclude"], id_to_label)
    recall = len(must & got) / len(must) if must else None
    violations = sorted(excl & got)

    out = {
        "id": case["id"], "tags": case.get("tags", []),
        "n_recs": len(recs), "recall_at_k": recall,
        "exclusion_violations": violations, "latency_s": round(latency, 1),
    }

    # 4. judge — labels resolved to human-readable fullLabels (raw _ids were
    # uninterpretable for the judge's label_recall criterion — same bugfix)
    if use_judge:
        from judge import judge_audience
        judge_labels = {"audience": {
            "must_include": sorted(must), "acceptable": sorted(
                resolve_labels(labels.get("acceptable", []), id_to_label)),
            "must_exclude": sorted(excl)}}
        j = await judge_audience(case["brief"], judge_labels, recs)
        out["judge"] = j["scores"]
        out["judge_mean"] = round(j["mean"], 2)
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-url", default="http://localhost:8000")
    ap.add_argument("--api-key", default="", help="X-API-Key if auth enabled")
    ap.add_argument("--subset", default="", help="tag=<value> filter")
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--label", default="", help="report filename label")
    args = ap.parse_args()

    briefs = sorted(GOLDEN.glob("brief_*.json"))
    if args.subset.startswith("tag="):
        tag = args.subset[4:]
        briefs = [b for b in briefs
                  if tag in json.loads(b.read_text(encoding="utf-8")).get("tags", [])]
    if not briefs:
        sys.exit("no briefs matched")

    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    id_to_label = load_id_to_label()
    sem = asyncio.Semaphore(args.concurrency)
    results = []

    async with httpx.AsyncClient() as client:
        async def guarded(bf):
            async with sem:
                try:
                    res = await eval_one(client, bf, args.agent_url, headers,
                                         id_to_label, not args.no_judge, args.k)
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

    summary = {
        "n": len(results), "errors": len(results) - len(ok),
        f"mean_recall@{args.k}": round(statistics.mean(recalls), 3) if recalls else None,
        "exclusion_violations_total": total_viol,   # ⛔ CI gate: must be 0
        "judge_score": round(statistics.mean(judge_means), 3) if judge_means else None,
        "p95_latency_s": round(sorted(r["latency_s"] for r in ok)[int(len(ok) * 0.95) - 1], 1) if ok else None,
    }
    print("\n== SUMMARY ==\n" + json.dumps(summary, indent=2, ensure_ascii=False))

    REPORTS.mkdir(exist_ok=True)
    label = args.label or time.strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS / f"{label}.json"
    report_path.write_text(json.dumps({"summary": summary, "results": results},
                                      indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ report → {report_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
