"""Run the Vietnamese Campaign Copilot state/mutation regression corpus locally."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import time
import uuid

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "agent" / ".env")
DEFAULT_CASES = ROOT / "eval" / "golden_set" / "copilot_multiturn_vi.json"
CATALOG = ROOT / "eval" / "golden_set" / "catalog_full.json"

DEFAULT_BRIEF = {
    "brand": "Demo Brand",
    "objective": "awareness",
    "budget": 50,
    "kpi": "Reach 2M",
    "startDate": "2030-01-01",
    "endDate": "2030-01-10",
    "notes": "",
}
DEFAULT_CREATIVE = {"files": [
    {
        "id": "f1", "name": "hero.png", "type": "image/png",
        "analysisId": "ana-1", "analysisStatus": "approved",
    },
    {
        "id": "f2", "name": "square.png", "type": "image/png",
        "analysisId": "ana-2", "analysisStatus": "approved",
    },
]}


def _segment_map() -> dict[str, dict]:
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    result = {}
    for row in rows:
        for key in ("_id", "segmentId", "fullLabel", "name"):
            if row.get(key):
                result[str(row[key]).casefold()] = row
    return result


SEGMENTS = _segment_map()


class EvalFailure(AssertionError):
    pass


class Runner:
    def __init__(self, client: httpx.AsyncClient, base: str):
        self.client = client
        self.base = base.rstrip("/")

    async def workspace(self, session_id: str) -> dict:
        response = await self.client.get(
            f"{self.base}/workspace", params={"session_id": session_id}
        )
        response.raise_for_status()
        return response.json()

    async def commit(self, session_id: str, field: str, value, revision: int) -> int:
        response = await self.client.post(
            f"{self.base}/commit-workspace",
            json={
                "session_id": session_id,
                "field": field,
                "value": value,
                "base_revision": revision,
                "actor": "copilot_eval",
                "reason": "eval seed/action",
                "idempotency_key": f"eval:{uuid.uuid4().hex}",
            },
        )
        response.raise_for_status()
        return response.json()["workspace_revision"]

    async def seed(self, session_id: str, seed: dict) -> int:
        revision = 0
        if seed.get("brief"):
            value = dict(DEFAULT_BRIEF)
            if isinstance(seed["brief"], dict):
                value.update(seed["brief"])
            revision = await self.commit(session_id, "brief", value, revision)
        if seed.get("audience"):
            attrs = []
            for ref in seed["audience"]:
                item = SEGMENTS.get(str(ref).casefold())
                if not item:
                    raise EvalFailure(f"seed segment not found: {ref}")
                attrs.append(item)
            revision = await self.commit(
                session_id, "segment", {"attrs": attrs, "size": 0}, revision
            )
        if seed.get("targeting"):
            revision = await self.commit(
                session_id, "targeting", seed["targeting"], revision
            )
        if seed.get("creative"):
            revision = await self.commit(
                session_id, "creative", DEFAULT_CREATIVE, revision
            )
        if seed.get("placements"):
            revision = await self.commit(
                session_id,
                "setup",
                {"selectedZoneIds": seed["placements"], "phase": "assign"},
                revision,
            )
        if seed.get("assignments"):
            revision = await self.commit(
                session_id, "assignments", seed["assignments"], revision
            )
        return revision

    async def chat(self, session_id: str, message: str, revision: int) -> tuple[dict, float]:
        started = time.perf_counter()
        response = await self.client.post(
            f"{self.base}/chat",
            json={
                "session_id": session_id,
                "step": 3,
                "message": message,
                "workspace": {},
                "workspace_revision": revision,
                "confirmed_steps": [],
                "workspace_events": [],
            },
        )
        response.raise_for_status()
        return response.json(), time.perf_counter() - started

    async def run_case(self, case: dict) -> dict:
        session_id = f"{case['id']}_{uuid.uuid4().hex[:8]}"
        await self.seed(session_id, case.get("seed", {}))
        last_proposal_id = None
        turns = []
        errors = []
        for index, turn in enumerate(case["turns"], 1):
            before = await self.workspace(session_id)
            before_revision = before["revision"]
            if turn.get("action") == "commit":
                await self.commit(
                    session_id, turn["field"], turn["value"], before_revision
                )
                continue
            if turn.get("action") == "reject_last":
                if not last_proposal_id:
                    errors.append(f"turn {index}: no proposal to reject")
                    continue
                response = await self.client.post(
                    f"{self.base}/workspace/proposals/{last_proposal_id}/reject",
                    json={"actor": "copilot_eval", "reason": "eval rejection"},
                )
                response.raise_for_status()
                continue

            data, latency = await self.chat(
                session_id, turn["message"], before_revision
            )
            after = await self.workspace(session_id)
            proposal = next(
                (block for block in data.get("blocks", [])
                 if block.get("type") == "workspace_proposal"),
                None,
            )
            if proposal:
                last_proposal_id = proposal.get("changes", {}).get("proposal_id")
            tool = data.get("meta", {}).get("tool")
            expected = turn["expect"]
            kind = expected["kind"]
            turn_errors = []
            if kind == "proposal":
                if tool != "workspace_proposal" or not proposal:
                    turn_errors.append(f"expected proposal, got tool={tool}")
                elif proposal.get("changes", {}).get("field") != expected["field"]:
                    turn_errors.append(
                        f"field={proposal.get('changes', {}).get('field')} expected={expected['field']}"
                    )
                if after["revision"] != before_revision:
                    turn_errors.append("unauthorized pre-approval mutation")
            elif kind == "clarification":
                if tool != "workspace_clarification":
                    turn_errors.append(f"expected clarification, got tool={tool}")
                if after["revision"] != before_revision:
                    turn_errors.append("clarification mutated workspace")
            elif kind == "no_mutation":
                if proposal or data.get("workspace_update"):
                    turn_errors.append("unexpected proposal/workspace_update")
                if after["revision"] != before_revision:
                    turn_errors.append("unexpected mutation")
            elif kind == "approval":
                if tool != "workspace_confirmed":
                    turn_errors.append(f"expected approval, got tool={tool}")
                if after["revision"] != before_revision + 1:
                    turn_errors.append("approval did not advance exactly one revision")
                if (data.get("workspace_update") or {}).get("field") != expected["field"]:
                    turn_errors.append("approval applied wrong field")
            elif kind == "conflict":
                if tool != "workspace_conflict":
                    turn_errors.append(f"expected conflict, got tool={tool}")
                if after["revision"] != before_revision:
                    turn_errors.append("conflict changed workspace")
            else:
                turn_errors.append(f"unknown expected kind: {kind}")
            errors.extend(f"turn {index}: {error}" for error in turn_errors)
            turns.append({
                "index": index,
                "kind": kind,
                "tool": tool,
                "latency_s": round(latency, 3),
                "before_revision": before_revision,
                "after_revision": after["revision"],
                "errors": turn_errors,
                "text": data.get("text", "")[:240],
            })
        return {
            "id": case["id"],
            "session_id": session_id,
            "ok": not errors,
            "errors": errors,
            "turns": turns,
        }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", default="http://localhost:8080/api/agent")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--start", type=int, default=0,
                        help="Zero-based case offset for focused reruns")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--label", default="copilot-v1")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.start:
        cases = cases[args.start:]
    if args.limit:
        cases = cases[:args.limit]
    semaphore = asyncio.Semaphore(max(1, args.concurrency))
    headers = {}
    api_key = os.getenv("AGENT_API_KEY", "")
    if api_key:
        headers["X-API-Key"] = api_key
    async with httpx.AsyncClient(headers=headers, timeout=180) as client:
        runner = Runner(client, args.agent_url)

        async def guarded(case):
            async with semaphore:
                try:
                    result = await runner.run_case(case)
                except Exception as exc:
                    result = {
                        "id": case.get("id"), "ok": False,
                        "errors": [f"{type(exc).__name__}: {exc}"], "turns": [],
                    }
                print(
                    f"{result['id']}: {'PASS' if result['ok'] else 'FAIL'} "
                    f"{'; '.join(result['errors'])}"
                )
                return result

        results = await asyncio.gather(*(guarded(case) for case in cases))
    latencies = [
        turn["latency_s"] for result in results for turn in result.get("turns", [])
    ]
    sorted_latencies = sorted(latencies)
    p95 = sorted_latencies[
        min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.95))
    ] if sorted_latencies else None
    summary = {
        "cases": len(results),
        "passed": sum(result["ok"] for result in results),
        "failed": sum(not result["ok"] for result in results),
        "turns": sum(len(result.get("turns", [])) for result in results),
        "mean_latency_s": round(statistics.mean(latencies), 3) if latencies else None,
        "p95_latency_s": p95,
        "unauthorized_mutations": sum(
            "mutation" in error
            for result in results for error in result.get("errors", [])
        ),
    }
    report = {
        "label": args.label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": results,
    }
    report_dir = ROOT / "eval" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{args.label}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("== SUMMARY ==")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report -> {report_path}")
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
