"""Exercise the real local creative upload and durable HTTP analysis queue."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "agent/.env")

TERMINAL = {"auto_approved", "needs_review"}


def _headers() -> dict[str, str]:
    key = os.getenv("AGENT_API_KEY", "")
    return {"X-API-Key": key} if key else {}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", default="http://localhost:8080")
    parser.add_argument("--backend-url", default="http://localhost:3000")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--label", default="creative-queue-v1")
    args = parser.parse_args()

    manifest = json.loads(
        (ROOT / "eval/creative_set/manifest.json").read_text("utf-8")
    )
    run_id = uuid.uuid4().hex[:10]
    sessions: dict[str, str] = {}
    uploads: list[dict] = []

    async with httpx.AsyncClient(timeout=30) as client:
        for case in manifest:
            brand = case["brief"]["brand"]
            session_id = sessions.setdefault(
                brand, f"creative_load_{run_id}_{len(sessions) + 1}"
            )
            if not any(item["session_id"] == session_id for item in uploads):
                response = await client.post(
                    f"{args.agent_url}/api/agent/commit-workspace",
                    headers=_headers(),
                    json={
                        "session_id": session_id,
                        "field": "brief",
                        "value": case["brief"],
                    },
                )
                response.raise_for_status()

            path = ROOT / case["path"]
            response = await client.post(
                f"{args.backend_url}/api/creative/upload",
                files={"file": (path.name, path.read_bytes(), "image/png")},
            )
            response.raise_for_status()
            uploaded = response.json()
            uploads.append(
                {
                    "case_id": case["id"],
                    "session_id": session_id,
                    "id": f"load-{case['id']}",
                    "name": path.name,
                    "type": "image/png",
                    "intendedFormat": "skin" if case["expected_skin"] else "banner",
                    "url": uploaded["url"],
                    "filename": uploaded["filename"],
                }
            )

        queued_at = time.perf_counter()
        jobs: list[dict] = []
        by_session: dict[str, list[dict]] = defaultdict(list)
        for item in uploads:
            by_session[item["session_id"]].append(item)
        for session_id, items in by_session.items():
            response = await client.post(
                f"{args.agent_url}/api/agent/creative-analyze",
                headers=_headers(),
                json={"session_id": session_id, "files": items},
            )
            response.raise_for_status()
            jobs.extend(response.json().get("jobs", []))

        deadline = time.monotonic() + args.timeout
        final: list[dict] = []
        while time.monotonic() < deadline:
            final = []
            for session_id in by_session:
                response = await client.get(
                    f"{args.agent_url}/api/agent/creative-intel",
                    headers=_headers(),
                    params={"session_id": session_id},
                )
                response.raise_for_status()
                final.extend(response.json().get("files", []))
            matching = [item for item in final if item.get("analysis_id") in {
                job.get("analysis_id") for job in jobs
            }]
            if len(matching) == len(manifest) and all(
                item.get("status") in TERMINAL for item in matching
            ):
                final = matching
                break
            await asyncio.sleep(0.5)
        else:
            raise TimeoutError(f"creative queue did not finish within {args.timeout}s")

        total_seconds = time.perf_counter() - queued_at
        durations = []
        end_to_end = []
        for item in final:
            started = item.get("started_at")
            completed = item.get("completed_at")
            created = item.get("created_at")
            if started and completed:
                durations.append(
                    (datetime.fromisoformat(completed) - datetime.fromisoformat(started)).total_seconds()
                )
            if created and completed:
                end_to_end.append(
                    (datetime.fromisoformat(completed) - datetime.fromisoformat(created)).total_seconds()
                )
        statuses = Counter(item.get("status") for item in final)
        summary = {
            "n": len(final),
            "jobs_returned": len(jobs),
            "terminal_rate": round(len(final) / len(manifest), 3),
            "status_counts": dict(statuses),
            "total_queue_seconds": round(total_seconds, 3),
            "worker_task_p50_seconds": round(sorted(durations)[len(durations) // 2], 3)
            if durations else None,
            "worker_task_p95_seconds": round(
                sorted(durations)[max(0, int(len(durations) * 0.95) - 1)], 3
            ) if durations else None,
            "end_to_end_p50_seconds": round(
                sorted(end_to_end)[len(end_to_end) // 2], 3
            ) if end_to_end else None,
            "end_to_end_p95_seconds": round(
                sorted(end_to_end)[max(0, int(len(end_to_end) * 0.95) - 1)], 3
            ) if end_to_end else None,
            "within_20_seconds_rate": round(
                sum(value <= 20 for value in end_to_end) / len(end_to_end), 3
            ) if end_to_end else None,
            "attempts_max": max((item.get("attempts", 0) for item in final), default=0),
            "missing_analysis_ids": sum(not item.get("analysis_id") for item in final),
        }
        report = {
            "label": args.label,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "cases": final,
        }
        output = ROOT / "eval/reports" / f"{args.label}.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"report={output}")

        for item in uploads:
            try:
                await client.delete(
                    f"{args.backend_url}/api/creative/{item['filename']}"
                )
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
