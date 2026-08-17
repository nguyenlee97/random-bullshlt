"""Timed local session-isolation soak using the non-model guided control plane."""

from __future__ import annotations

import argparse
import asyncio
import json
import time

import httpx

from load_test import Results, percentile, user_flow


async def main_async(args) -> int:
    results = Results()
    limits = httpx.Limits(max_connections=max(20, args.users * 2))
    started = time.perf_counter()
    cycle = 0
    async with httpx.AsyncClient(base_url=args.url, timeout=10, limits=limits) as client:
        while time.perf_counter() - started < args.duration:
            cycle_started = time.perf_counter()
            await asyncio.gather(*(
                user_flow(client, results, worker, cycle)
                for worker in range(args.users)
            ), return_exceptions=True)
            cycle += 1
            remaining = args.interval - (time.perf_counter() - cycle_started)
            if remaining > 0:
                await asyncio.sleep(remaining)

    duration = time.perf_counter() - started
    summary = {
        "profile": "one-hour-session-isolation-soak-no-model-no-order",
        "duration_s": round(duration, 2),
        "cycles": cycle,
        "users_per_cycle": args.users,
        "sessions": results.sessions,
        "requests": results.requests,
        "rps": round(results.requests / duration, 2),
        "latency_p50_s": round(percentile(results.latencies, 0.50), 4),
        "latency_p95_s": round(percentile(results.latencies, 0.95), 4),
        "latency_p99_s": round(percentile(results.latencies, 0.99), 4),
        "errors": len(results.errors),
        "session_leaks": results.leaks,
        "passed": not results.errors and results.leaks == 0,
    }
    print(json.dumps(summary, indent=2), flush=True)
    if results.errors:
        print("sample_errors=", results.errors[:10], flush=True)
    return 0 if summary["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5175/agent")
    parser.add_argument("--duration", type=float, default=3600)
    parser.add_argument("--users", type=int, default=5)
    parser.add_argument("--interval", type=float, default=10)
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
