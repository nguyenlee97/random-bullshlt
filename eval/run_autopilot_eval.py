"""Deterministic 20-brief Campaign Autopilot orchestration evaluation.

Model quality is measured by the dedicated RAG, targeting, and creative suites.
This runner exercises the real durable run/task/review/workspace state machine
with deterministic capability outputs, stopping at mandatory launch approval.
It never creates an order.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import statistics
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "agent"
if str(AGENT) not in sys.path:
    sys.path.insert(0, str(AGENT))
os.environ["MONGODB_URI"] = "mongodb://127.0.0.1:1"

import session  # noqa: E402
from autopilot import service as autopilot  # noqa: E402
from autopilot import worker  # noqa: E402
from autopilot.capabilities import CapabilityResult  # noqa: E402
from workspace import service as workspace_service  # noqa: E402


POLICIES = ("auto_build_draft", "critical_only", "review_every_stage")


async def _no_store() -> bool:
    return False


def _reset_memory() -> None:
    session._mongo_ok = False
    session._mem = {}
    session._mem_logs = []
    session._ensure_mongo = _no_store
    workspace_service._mongo_ok = False
    workspace_service._mem_workspaces = {}
    workspace_service._mem_proposals = {}
    workspace_service._locks = {}
    workspace_service._ensure_store = _no_store
    autopilot._mem_runs = {}
    autopilot._mem_tasks = {}
    autopilot._mem_events = []
    autopilot._lock = asyncio.Lock()


def _brief_cases() -> list[dict]:
    paths = sorted((ROOT / "eval" / "golden_set").glob("brief_*.json"))[:20]
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if len(cases) != 20:
        raise RuntimeError(f"expected 20 golden briefs, found {len(cases)}")
    return cases


async def _fake_execute(task: dict, run: dict) -> CapabilityResult:
    key = task["key"]
    values = {
        "normalize_brief": {"normalized": True},
        "validate_brief": {"valid": True},
        "generate_strategy": {"selected": "balanced"},
        "retrieve_audience": {"attrs": [{"_id": "catalog-segment"}], "size": 1},
        "derive_targeting": {"geo": ["TP.HCM"], "age": ["25-34"]},
        "plan_placement_intent": {
            "kind": "placement_intent",
            "candidate_zone_ids": ["ZingMP3_Masthead"],
            "candidates": [{
                "id": "ZingMP3_Masthead", "format": "banner",
                "width": 1160, "height": 250, "cpm": 60000,
                "reach": 14000000,
            }],
            "strategy_id": "balanced",
            "selection_method": "autopilot_eval_fixture",
        },
        "plan_creative_formats": {
            "source": "upload",
            "formats": [{
                "format_id": "znews-masthead-1160x250",
                "width": 1160, "height": 250,
                "zone_ids": ["ZingMP3_Masthead"],
            }],
            "covered_zone_ids": ["ZingMP3_Masthead"],
            "estimated_provider_calls": 0,
            "max_assets": 3,
        },
        "prepare_creatives": {
            "files": [{
                "name": "autopilot-eval.png", "type": "image/png",
                "width": 1160, "height": 250,
                "url": "http://localhost:3000/uploads/autopilot-eval.png",
            }],
            "uploaded": True,
            "source": "upload",
        },
        "analyze_creatives": {"files": [{"status": "auto_approved"}]},
        "rank_placements": {
            "selectedZoneIds": ["ZingMP3_Masthead"],
            "zones": [{"id": "ZingMP3_Masthead", "cpm": 60000, "reach": 14000000}],
        },
        "assign_creatives": {"assignments": {"ZingMP3_Masthead": 0}},
        "forecast": {"risk": "low", "estimated_reach": 1000000},
        "build_order_draft": {
            "status": "draft",
            "payload": {"idempotencyKey": f"autopilot:{run['run_id']}:launch"},
        },
        "run_order_guard": {"passed": True},
        "launch_approval": {
            "ready": True, "requires_explicit_approval": True,
            "order_draft_revision": 1,
        },
    }
    return CapabilityResult(
        value=values[key],
        evidence=[{"type": "autopilot_eval_fixture", "task": key}],
        force_review=key == "launch_approval",
    )


async def _seed_brief(session_id: str, brief: dict) -> None:
    current = await workspace_service.get_workspace(session_id)
    await workspace_service.apply_mutation(
        session_id, "brief", brief, base_revision=current["revision"],
        actor="autopilot_eval", idempotency_key=f"{session_id}:brief",
    )


async def _run_case(case: dict, index: int) -> dict:
    started = time.perf_counter()
    session_id = f"autopilot-eval-{case['id']}"
    policy = POLICIES[index % len(POLICIES)]
    await _seed_brief(session_id, case["brief"])
    run = await autopilot.create_run(
        session_id, approval_policy=policy,
        idempotency_key=f"{session_id}:run",
    )
    reviews = 0
    error = None
    for _ in range(100):
        run = await autopilot.get_run(run["run_id"])
        waiting = next(
            (task for task in run["tasks"] if task["status"] == "waiting_review"),
            None,
        )
        if waiting:
            if waiting["key"] == "launch_approval":
                break
            run = await autopilot.review_task(
                run["run_id"], waiting["task_id"], approved=True,
                actor="autopilot_eval_reviewer", reason="fixture evidence accepted",
            )
            reviews += 1
            continue
        if run["status"] in {"failed", "cancelled", "completed"}:
            error = f"unexpected terminal status: {run['status']}"
            break
        task = await autopilot.claim_next_task("autopilot-eval-worker")
        if task is None:
            error = "no claimable task before launch review"
            break
        await worker._process(task)
    else:
        error = "step limit exceeded"

    run = await autopilot.get_run(run["run_id"])
    current = await workspace_service.get_workspace(session_id)
    by_key = {task["key"]: task for task in run["tasks"]}
    checks = {
        "waiting_for_launch": by_key["launch_approval"]["status"] == "waiting_review",
        "order_ready_draft": current["artifacts"]["order_draft"]["status"] == "approved",
        "no_order_created": current["artifacts"]["order"]["status"] == "missing",
        "create_not_released": by_key["create_order"]["status"] == "pending",
        "no_failed_tasks": not any(task["status"] == "failed" for task in run["tasks"]),
        "explicit_launch_required": bool(
            (by_key["launch_approval"].get("result") or {}).get(
                "requires_explicit_approval"
            )
        ),
    }
    if error:
        checks["runner"] = False
    return {
        "id": case["id"], "lang": case.get("lang"), "policy": policy,
        "objective": case["brief"].get("objective"),
        "budget": case["brief"].get("budget"),
        "ok": all(checks.values()), "checks": checks, "error": error,
        "reviews_before_launch": reviews,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }


async def _failure_drills() -> list[dict]:
    drills: list[dict] = []

    try:
        await autopilot.create_run("drill-missing-brief", idempotency_key="missing")
        missing_ok = False
    except ValueError:
        missing_ok = True
    drills.append({"name": "missing_brief", "ok": missing_ok})

    brief = {
        "brand": "Drill", "objective": "awareness", "budget": 10,
        "startDate": "2030-01-01", "endDate": "2030-01-10",
    }
    await _seed_brief("drill-idempotent", brief)
    first = await autopilot.create_run(
        "drill-idempotent", idempotency_key="same-start"
    )
    second = await autopilot.create_run(
        "drill-idempotent", idempotency_key="same-start"
    )
    drills.append({
        "name": "duplicate_start", "ok": first["run_id"] == second["run_id"]
    })
    await autopilot.cancel_run(first["run_id"])

    await _seed_brief("drill-lease", brief)
    lease_run = await autopilot.create_run("drill-lease", idempotency_key="lease")
    leased = await autopilot.claim_next_task("dead-worker", lease_seconds=10)
    autopilot._mem_tasks[leased["task_id"]]["lease_expires_at"] = (
        autopilot._now() - timedelta(seconds=1)
    )
    recovered = await autopilot.recover_expired_leases()
    lease_latest = await autopilot.get_run(lease_run["run_id"])
    drills.append({
        "name": "expired_worker_lease", "ok": recovered == 1
        and lease_latest["tasks"][0]["status"] == "queued",
    })
    await autopilot.cancel_run(lease_run["run_id"])

    await _seed_brief("drill-edit", brief)
    edit_run = await autopilot.create_run("drill-edit", idempotency_key="edit")
    for key in ("normalize_brief", "validate_brief", "generate_strategy"):
        task = next(item for item in edit_run["tasks"] if item["key"] == key)
        autopilot._mem_tasks[task["task_id"]]["status"] = "succeeded"
    current = await workspace_service.get_workspace("drill-edit")
    await workspace_service.apply_mutation(
        "drill-edit", "brief", {**brief, "budget": 12},
        base_revision=current["revision"], actor="autopilot_eval",
        idempotency_key="edit-in-flight",
    )
    replanned = await autopilot.reconcile_workspace_changes(edit_run["run_id"])
    drills.append({
        "name": "mid_run_edit", "ok": replanned["changed"]
        and replanned["run"]["plan_revision"] == 2,
    })
    await autopilot.cancel_run(edit_run["run_id"])

    await _seed_brief("drill-review", brief)
    review_run = await autopilot.create_run("drill-review", idempotency_key="review")
    launch_id = f"{review_run['run_id']}:launch_approval"
    for task in review_run["tasks"]:
        autopilot._mem_tasks[task["task_id"]]["status"] = (
            "waiting_review" if task["key"] == "launch_approval"
            else "pending" if task["key"] in {"create_order", "verify_order", "create_setup_report"}
            else "succeeded"
        )
    autopilot._mem_runs[review_run["run_id"]]["status"] = "waiting_review"
    await autopilot.review_task(review_run["run_id"], launch_id, approved=True)
    try:
        await autopilot.review_task(review_run["run_id"], launch_id, approved=True)
        replay_ok = False
    except autopilot.RunConflict:
        replay_ok = True
    latest = await autopilot.get_run(review_run["run_id"])
    create = next(task for task in latest["tasks"] if task["key"] == "create_order")
    drills.append({
        "name": "duplicate_launch_approval", "ok": replay_ok
        and create["status"] == "queued",
    })
    await autopilot.cancel_run(review_run["run_id"])
    return drills


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="autopilot-20-v1")
    args = parser.parse_args()
    _reset_memory()
    worker.execute = _fake_execute
    results = []
    for index, case in enumerate(_brief_cases()):
        result = await _run_case(case, index)
        results.append(result)
        print(f"{result['id']}: {'PASS' if result['ok'] else 'FAIL'} {result['policy']}")
    drills = await _failure_drills()
    for drill in drills:
        print(f"drill/{drill['name']}: {'PASS' if drill['ok'] else 'FAIL'}")

    valid = len(results)
    ready = sum(result["checks"]["order_ready_draft"] for result in results)
    latencies = [result["latency_ms"] for result in results]
    summary = {
        "briefs": valid,
        "passed": sum(result["ok"] for result in results),
        "failed": sum(not result["ok"] for result in results),
        "order_ready_draft_rate": round(ready / valid, 3),
        "required_review_pause_rate": round(sum(
            result["checks"]["waiting_for_launch"] for result in results
        ) / valid, 3),
        "launch_without_approval": sum(
            not result["checks"]["no_order_created"] for result in results
        ),
        "failure_drills": len(drills),
        "failure_drills_passed": sum(drill["ok"] for drill in drills),
        "mean_latency_ms": round(statistics.mean(latencies), 2),
        "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95) - 1],
    }
    report = {
        "label": args.label,
        "scope": "durable orchestration with deterministic capability fixtures",
        "summary": summary,
        "results": results,
        "failure_drills": drills,
        "linked_integration_evidence": [
            "docs/next-hackathon/10-m4-autopilot-replan-evidence.md",
            "docs/next-hackathon/11-m4-autopilot-e2e-evidence.md",
            "eval/reports/rag-qdrant-fallback-v2.json",
            "eval/reports/creative-safety-gemma-v3.json",
        ],
    }
    destination = ROOT / "eval" / "reports" / f"{args.label}.json"
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {destination}")
    if summary["failed"] or summary["failure_drills_passed"] != len(drills):
        raise SystemExit(1)
    if summary["order_ready_draft_rate"] < 0.9:
        raise SystemExit("order-ready draft rate below 90%")
    if summary["required_review_pause_rate"] != 1.0:
        raise SystemExit("required-review pause rate below 100%")
    if summary["launch_without_approval"]:
        raise SystemExit("unauthorized launch detected")


if __name__ == "__main__":
    asyncio.run(main())
