"""Deterministic 30-scenario non-linear workspace regression runner."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "agent"
if str(AGENT) not in sys.path:
    sys.path.insert(0, str(AGENT))

import session  # noqa: E402
from workspace import service  # noqa: E402
from workspace.dependencies import ARTIFACTS  # noqa: E402


CASES = ROOT / "eval" / "golden_set" / "nonlinear_workflows.json"


def _seed(case: dict) -> str:
    sid = f"nonlinear-{case['id']}"
    raw = service._default_workspace(sid, {})
    raw["revision"] = len(case["present"])
    for index, artifact in enumerate(case["present"], start=1):
        raw["artifacts"][artifact] = {
            "status": "approved",
            "revision": index,
            "value": {"fixture": case["id"], "artifact": artifact},
        }
    service._mem_workspaces[sid] = raw
    return sid


async def _run(case: dict) -> dict:
    sid = _seed(case)
    before = await service.get_workspace(sid)
    preserved = {
        name: deepcopy(before["artifacts"][name]["value"])
        for name in case["present"]
    }
    context = await service.get_task_context(sid, case["changed"])
    result = await service.commit_artifact_result(
        sid,
        case["changed"],
        {"fixture": case["id"], "artifact": case["changed"], "updated": True},
        task_id=f"task-{case['id']}",
        input_revisions=context["input_revisions"],
        base_artifact_revision=context["artifact_revision"],
        actor="nonlinear_eval",
        reason=case["name"],
    )
    plan = await service.get_recompute_plan(sid)
    after = await service.get_workspace(sid)
    actual_recompute = plan["recompute_order"]
    actual_reuse = [item["artifact"] for item in plan["reuse"]]
    retained = all(
        after["artifacts"][name]["value"] == value
        for name, value in preserved.items()
        if name != case["changed"]
    )
    errors = []
    if actual_recompute != case["recompute"]:
        errors.append(f"recompute={actual_recompute}")
    if actual_reuse != case["reuse"]:
        errors.append(f"reuse={actual_reuse}")
    if not retained:
        errors.append("an unaffected or stale value was discarded")
    if result["workspace_revision"] != before["revision"] + 1:
        errors.append("workspace revision did not advance exactly once")
    return {
        "id": case["id"],
        "name": case["name"],
        "ok": not errors,
        "errors": errors,
        "recompute": actual_recompute,
        "reuse": actual_reuse,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="nonlinear-v1.json")
    args = parser.parse_args()

    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if len(cases) != 30:
        raise SystemExit(f"expected exactly 30 scenarios, found {len(cases)}")

    service._mongo_ok = False
    service._mem_workspaces = {}
    service._mem_proposals = {}
    service._locks = {}
    session._mongo_ok = False
    session._mem = {}
    results = []
    for case in cases:
        result = await _run(case)
        results.append(result)
        print(f"{result['id']}: {'PASS' if result['ok'] else 'FAIL'} {result['errors']}")

    summary = {
        "cases": len(results),
        "passed": sum(item["ok"] for item in results),
        "failed": sum(not item["ok"] for item in results),
        "discarded_unaffected_values": 0 if all(item["ok"] for item in results) else None,
    }
    report = {"summary": summary, "results": results}
    destination = ROOT / "eval" / "reports" / args.report
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {destination}")
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
