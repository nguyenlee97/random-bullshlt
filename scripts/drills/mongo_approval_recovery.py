"""Verify an approval is durable and fail-safe across a local Mongo outage."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import subprocess
import time

import httpx


ROOT = Path(__file__).resolve().parents[2]


def _docker(*args: str) -> None:
    subprocess.run(
        ["docker", "compose", *args], cwd=ROOT, check=True,
        capture_output=True, text=True,
    )


def _wait_ready(client: httpx.Client, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if client.get("http://127.0.0.1:8080/ready").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise TimeoutError("agent readiness did not recover")


def _wait_mongo(timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Health.Status}}",
             "random-bullshlt-mongo-1"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip() == "healthy":
            return
        time.sleep(1)
    raise TimeoutError("Mongo did not become healthy")


def _wait_strategy(client: httpx.Client, base: str, run_id: str,
                   timeout: float = 30) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"{base}/autopilot/runs/{run_id}").json()
        task = next(item for item in run["tasks"] if item["key"] == "generate_strategy")
        if task["status"] == "waiting_review":
            return task
        if task["status"] == "failed":
            raise AssertionError(f"strategy failed: {task.get('error')}")
        time.sleep(0.25)
    raise TimeoutError("strategy did not reach waiting_review")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5175/agent/api/agent")
    parser.add_argument("--namespace", default="fe5-mongo")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    session_id = f"sess_{args.namespace}_{int(time.time() * 1000)}"
    run_id = ""
    mongo_stopped = False
    result: dict[str, object] = {"session_id": session_id}
    client = httpx.Client(timeout=20)
    start = date.today() + timedelta(days=30)
    try:
        workspace = client.get(
            f"{args.base}/workspace", params={"session_id": session_id}
        ).json()
        preferences = client.post(f"{args.base}/workspace/preferences", json={
            "session_id": session_id, "experience_mode": "autopilot",
            "approval_policy": "review_every_stage",
            "base_revision": workspace["revision"], "actor": "fe5_mongo",
            "idempotency_key": f"{session_id}:preferences",
        })
        preferences.raise_for_status()
        commit = client.post(f"{args.base}/commit-workspace", json={
            "session_id": session_id, "field": "brief",
            "value": {
                "brand": "FE5 Mongo Interruption", "objective": "awareness",
                "budget": 25, "startDate": start.isoformat(),
                "endDate": (start + timedelta(days=14)).isoformat(),
                "notes": "safe local recovery fixture",
            },
            "base_revision": preferences.json()["workspace_revision"],
            "actor": "fe5_mongo", "idempotency_key": f"{session_id}:brief",
        })
        commit.raise_for_status()
        started = client.post(f"{args.base}/autopilot/runs", json={
            "session_id": session_id, "approval_policy": "review_every_stage",
            "creative_source": "upload", "actor": "fe5_mongo",
            "idempotency_key": f"{session_id}:run",
        })
        started.raise_for_status()
        run_id = started.json()["run_id"]
        strategy = _wait_strategy(client, args.base, run_id)

        _docker("stop", "mongo")
        mongo_stopped = True
        time.sleep(1)
        result["ready_during_outage"] = client.get(
            "http://127.0.0.1:8080/ready"
        ).status_code
        interrupted = client.post(
            f"{args.base}/autopilot/runs/{run_id}/tasks/{strategy['task_id']}/review",
            json={"approved": True, "actor": "fe5_mongo",
                  "reason": "outage must fail closed"},
        )
        result["review_during_outage"] = interrupted.status_code
        if interrupted.status_code < 500:
            raise AssertionError(
                f"approval did not fail closed during Mongo outage: {interrupted.status_code}"
            )
    finally:
        if mongo_stopped:
            _docker("up", "-d", "--no-deps", "mongo")
            _wait_mongo()
            _docker("restart", "agent")
            _wait_ready(client)

    try:
        strategy = _wait_strategy(client, args.base, run_id)
        result["state_after_recovery"] = strategy["status"]
        approved = client.post(
            f"{args.base}/autopilot/runs/{run_id}/tasks/{strategy['task_id']}/review",
            json={"approved": True, "actor": "fe5_mongo",
                  "reason": "post-recovery approval"},
        )
        approved.raise_for_status()
        approved_task = next(
            item for item in approved.json()["tasks"]
            if item["key"] == "generate_strategy"
        )
        result["approval_after_recovery"] = approved_task["status"]
    finally:
        if run_id:
            client.post(f"{args.base}/autopilot/runs/{run_id}/cancel", json={
                "actor": "fe5_mongo", "reason": "recovery drill cleanup",
            })
        cleanup = client.delete(f"{args.base}/sessions/{session_id}")
        result["cleanup"] = "PASS" if cleanup.status_code == 200 else "FAIL"
        client.close()

    result["passed"] = (
        result.get("ready_during_outage") == 503
        and int(result.get("review_during_outage", 0)) >= 500
        and result.get("state_after_recovery") == "waiting_review"
        and result.get("approval_after_recovery") == "succeeded"
        and result.get("cleanup") == "PASS"
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        path = ROOT / args.report
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
