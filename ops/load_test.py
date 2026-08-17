"""Disposable local control-plane load test; performs no model calls or orders."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
import uuid
from dataclasses import dataclass, field

import httpx


@dataclass
class Results:
    latencies: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requests: int = 0
    sessions: int = 0
    leaks: int = 0


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return ordered[index]


async def checked(client, results, method, path, **kwargs):
    started = time.perf_counter()
    try:
        response = await client.request(method, path, **kwargs)
        results.latencies.append(time.perf_counter() - started)
        results.requests += 1
        if response.status_code >= 400:
            results.errors.append(f"{method} {path}: {response.status_code}")
        response.raise_for_status()
        return response.json()
    except Exception as error:
        if not isinstance(error, httpx.HTTPStatusError):
            results.errors.append(f"{method} {path}: {type(error).__name__}")
        raise


async def user_flow(client: httpx.AsyncClient, results: Results, worker: int, iteration: int):
    session_id = f"load_{worker}_{iteration}_{uuid.uuid4().hex[:10]}"
    results.sessions += 1
    try:
        await checked(client, results, "GET", "/health")
        workspace = await checked(
            client, results, "GET", "/api/agent/workspace", params={"session_id": session_id}
        )
        if workspace.get("session_id") != session_id:
            results.leaks += 1
        await checked(client, results, "POST", "/api/agent/workspace/preferences", json={
            "session_id": session_id,
            "experience_mode": "guided",
            "base_revision": workspace.get("revision", 0),
            "idempotency_key": session_id,
        })
        await checked(client, results, "POST", "/api/agent/chat", json={
            "message": "", "step": -1, "session_id": session_id,
        })
    finally:
        try:
            await checked(client, results, "DELETE", f"/api/agent/sessions/{session_id}")
        except Exception:
            pass


async def main_async(args) -> int:
    results = Results()
    limits = httpx.Limits(
        max_connections=max(args.users * 2, 20),
        max_keepalive_connections=max(args.users, 10),
    )
    async with httpx.AsyncClient(base_url=args.url, timeout=args.timeout, limits=limits) as client:
        started = time.perf_counter()

        async def worker(number: int):
            for iteration in range(args.iterations):
                try:
                    await user_flow(client, results, number, iteration)
                except Exception:
                    continue

        await asyncio.gather(*(worker(number) for number in range(args.users)))
        duration = time.perf_counter() - started

    summary = {
        "profile": "guided-control-plane-no-model-no-order",
        "users": args.users,
        "iterations_per_user": args.iterations,
        "sessions": results.sessions,
        "requests": results.requests,
        "duration_s": round(duration, 3),
        "rps": round(results.requests / duration, 2),
        "latency_p50_s": round(percentile(results.latencies, 0.50), 4),
        "latency_p95_s": round(percentile(results.latencies, 0.95), 4),
        "latency_p99_s": round(percentile(results.latencies, 0.99), 4),
        "errors": len(results.errors),
        "session_leaks": results.leaks,
        "passed": (
            not results.errors
            and results.leaks == 0
            and percentile(results.latencies, 0.95) < args.p95_slo
        ),
    }
    print(json.dumps(summary, indent=2))
    if results.errors:
        print("sample_errors=", results.errors[:10])
    return 0 if summary["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5175/agent")
    parser.add_argument("--users", type=int, default=15)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--p95-slo", type=float, default=3.0)
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
