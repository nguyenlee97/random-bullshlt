"""Verify local order retry idempotency across a backend outage."""
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


def _wait_url(url: str, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=2) as client:
        while time.monotonic() < deadline:
            try:
                if client.get(url).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(1)
    raise TimeoutError(f"service did not recover: {url}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="fe5-backend")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    key = f"{args.namespace}:order:{int(time.time() * 1000)}"
    start = date.today() + timedelta(days=90)
    payload = {
        "brand": "FE5 Backend Recovery", "objective": "awareness",
        "status": "pending", "budget": 1_000_000,
        "startDate": start.isoformat(),
        "endDate": (start + timedelta(days=3)).isoformat(),
        "placements": [], "creatives": [],
        "dmp": {"include": [], "exclude": []},
        "idempotencyKey": key,
    }
    result: dict[str, object] = {"idempotency_key": key}
    order_id = ""
    backend_stopped = False
    try:
        _docker("stop", "backend")
        backend_stopped = True
        # Readiness performs a bounded dependency check, so allow that check to
        # complete instead of mistaking its timeout window for a hung service.
        with httpx.Client(timeout=15) as client:
            result["ready_during_outage"] = client.get(
                "http://127.0.0.1:8080/ready"
            ).status_code
            try:
                client.post("http://127.0.0.1:3000/api/orders", json=payload)
                result["create_during_outage"] = "unexpected_success"
            except httpx.HTTPError:
                result["create_during_outage"] = "connection_failed"
    finally:
        if backend_stopped:
            _docker("up", "-d", "--no-deps", "backend")
            _wait_url("http://127.0.0.1:3000/api/health")
            _wait_url("http://127.0.0.1:8080/ready")

    try:
        with httpx.Client(timeout=20) as client:
            first = client.post("http://127.0.0.1:3000/api/orders", json=payload)
            first.raise_for_status()
            second = client.post("http://127.0.0.1:3000/api/orders", json=payload)
            second.raise_for_status()
            order_id = first.json()["id"]
            result.update({
                "first_status": first.status_code,
                "retry_status": second.status_code,
                "first_order_id": order_id,
                "retry_order_id": second.json()["id"],
                "deduplicated": second.json().get("deduplicated") is True,
            })
    finally:
        if order_id:
            with httpx.Client(timeout=20) as client:
                cleanup = client.delete(
                    f"http://127.0.0.1:3000/api/orders/{order_id}"
                )
                result["cleanup"] = "PASS" if cleanup.status_code == 200 else "FAIL"

    result["passed"] = (
        result.get("ready_during_outage") == 503
        and result.get("create_during_outage") == "connection_failed"
        and result.get("first_status") == 201
        and result.get("retry_status") == 200
        and result.get("first_order_id") == result.get("retry_order_id")
        and result.get("deduplicated") is True
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
