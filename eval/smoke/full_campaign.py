"""Run disposable local campaign flows through the real agent and backend.

The smoke proves creative gating, order guard, backend idempotency, and cleanup.
It intentionally uses one stable demo creative so failures point at orchestration
rather than model-quality variance.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "agent/.env")

TERMINAL = {"auto_approved", "needs_review"}
FIXTURE = ROOT / "agent_frontend/public/demo-creatives/elsa/znews-top-banner.png"


def _headers() -> dict[str, str]:
    key = os.getenv("AGENT_API_KEY", "")
    return {"X-API-Key": key} if key else {}


def _metadata(payload: dict) -> dict:
    return payload.get("metadata") or payload.get("meta") or {}


def _order_id(payload: dict) -> str:
    for block in payload.get("blocks") or []:
        if block.get("type") != "campaign_list":
            continue
        campaigns = block.get("campaigns") or []
        if campaigns:
            return str(campaigns[0].get("id") or "")
    return ""


async def _commit(client: httpx.AsyncClient, agent_url: str, session: str,
                  field: str, value: dict) -> None:
    response = await client.post(
        f"{agent_url}/api/agent/commit-workspace",
        headers=_headers(),
        json={"session_id": session, "field": field, "value": value},
    )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError(f"workspace commit failed for {field}: {response.text}")


async def _wait_for_verdict(client: httpx.AsyncClient, agent_url: str,
                            session: str, analysis_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = await client.get(
            f"{agent_url}/api/agent/creative-intel",
            headers=_headers(),
            params={"session_id": session},
        )
        response.raise_for_status()
        for item in response.json().get("files", []):
            if item.get("analysis_id") == analysis_id and item.get("status") in TERMINAL:
                return item
        await asyncio.sleep(0.25)
    raise TimeoutError(f"creative {analysis_id} did not finish within {timeout}s")


async def _wait_ready(client: httpx.AsyncClient, agent_url: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = await client.get(f"{agent_url}/ready", headers=_headers())
            response.raise_for_status()
            payload = response.json()
            if payload.get("ready") is True or payload.get("status") == "ready":
                return payload
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
        await asyncio.sleep(0.5)
    raise TimeoutError(f"agent did not become ready: {last_error}")


async def _one_flow(client: httpx.AsyncClient, args, index: int,
                    segment: dict, zone_id: str) -> dict:
    started = time.perf_counter()
    run_id = uuid.uuid4().hex[:10]
    session = f"full_smoke_{run_id}"
    idempotency_key = f"full-smoke-{run_id}"
    start_date = date.today() + timedelta(days=30)
    end_date = start_date + timedelta(days=14)
    uploaded: dict | None = None
    order_id = ""
    result: dict | None = None

    brief = {
        "brand": "ELSA Speak",
        "objective": "awareness",
        "kpi": "Reach",
        "budget": 25,
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "notes": "English speaking and language learning application",
    }

    try:
        await _commit(client, args.agent_url, session, "brief", brief)
        recommendation = await client.get(
            f"{args.agent_url}/api/agent/dmp-recommend",
            headers=_headers(),
            params={"session_id": session},
        )
        recommendation.raise_for_status()
        recommended_segments = recommendation.json().get("recommendations") or []
        selected_segment = recommended_segments[0] if recommended_segments else segment
        await _commit(
            client,
            args.agent_url,
            session,
            "segment",
            {
                "attrs": [selected_segment],
                "size": selected_segment.get("sizeMin") or 1,
            },
        )

        response = await client.post(
            f"{args.backend_url}/api/creative/upload",
            files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "image/png")},
        )
        response.raise_for_status()
        uploaded = response.json()

        file_stub = {
            "id": f"smoke-creative-{run_id}",
            "name": FIXTURE.name,
            "type": "image/png",
            "intendedFormat": "banner",
            "url": uploaded["url"],
        }
        response = await client.post(
            f"{args.agent_url}/api/agent/creative-analyze",
            headers=_headers(),
            json={"session_id": session, "files": [file_stub]},
        )
        response.raise_for_status()
        job = response.json()["jobs"][0]
        analysis_id = job["analysis_id"]
        verdict = await _wait_for_verdict(
            client, args.agent_url, session, analysis_id, args.timeout
        )
        if verdict.get("effective_status") != "auto_approved":
            raise RuntimeError(
                f"stable smoke creative was not auto-approved: "
                f"{verdict.get('review_reasons')}"
            )

        facts = verdict.get("deterministic") or {}
        creative = {
            **file_stub,
            "size": facts.get("bytes") or 0,
            "width": facts.get("width") or 0,
            "height": facts.get("height") or 0,
            "analysisId": analysis_id,
            "analysisStatus": verdict.get("status"),
            "reviewReasons": verdict.get("review_reasons") or [],
            "deterministic": facts,
            "vlm": verdict.get("vlm") or {},
            "override": verdict.get("override") or {},
        }
        await _commit(
            client, args.agent_url, session, "creative", {"files": [creative]}
        )

        assignment = await client.post(
            f"{args.agent_url}/api/agent/chat",
            headers=_headers(),
            json={
                "session_id": session,
                "step": 3,
                "message": "",
                "formData": {
                    "setup": {"phase": 1, "selectedZoneIds": [zone_id]}
                },
            },
        )
        assignment.raise_for_status()
        assignment_tool = _metadata(assignment.json()).get("tool")
        if assignment_tool != "creative_match":
            raise RuntimeError(f"creative assignment failed: {assignment.json()}")

        setup = {
            "phase": 2,
            "selectedZoneIds": [zone_id],
            "assignments": {zone_id: 0},
            "fileUrls": {"0": uploaded["url"]},
            "idempotencyKey": idempotency_key,
        }
        request = {
            "session_id": session,
            "step": 3,
            "message": "",
            "formData": {"setup": setup},
        }
        first = await client.post(
            f"{args.agent_url}/api/agent/chat", headers=_headers(), json=request
        )
        first.raise_for_status()
        first_payload = first.json()
        if _metadata(first_payload).get("tool") != "order_create":
            raise RuntimeError(f"first order attempt failed: {first_payload.get('text')}")
        order_id = _order_id(first_payload)
        if not order_id:
            raise RuntimeError(f"order_create returned no order id: {first_payload}")

        second = await client.post(
            f"{args.agent_url}/api/agent/chat", headers=_headers(), json=request
        )
        second.raise_for_status()
        duplicate_order_id = _order_id(second.json())
        if duplicate_order_id != order_id:
            raise RuntimeError(
                f"idempotency failed: first={order_id}, retry={duplicate_order_id}"
            )

        fetched = await client.get(f"{args.backend_url}/api/orders/{order_id}")
        fetched.raise_for_status()

        result_response = await client.post(
            f"{args.agent_url}/api/agent/chat",
            headers=_headers(),
            json={"session_id": session, "step": 4, "message": "", "formData": {}},
        )
        result_response.raise_for_status()
        result_tool = _metadata(result_response.json()).get("tool")

        report_response = await client.get(
            f"{args.agent_url}/api/agent/report-entry",
            headers=_headers(),
            params={"session_id": session},
        )
        report_response.raise_for_status()
        report_tool = _metadata(report_response.json()).get("tool")

        result = {
            "flow": index,
            "session_id": session,
            "trace_id": session,
            "analysis_id": analysis_id,
            "selected_segment_ids": [selected_segment.get("_id")],
            "zone_id": zone_id,
            "assignment_tool": assignment_tool,
            "order_id": order_id,
            "duplicate_retry_order_id": duplicate_order_id,
            "idempotency_pass": True,
            "result_tool": result_tool,
            "report_tool": report_tool,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "cleanup": {"order": False, "creative": False},
        }
        return result
    finally:
        if order_id:
            deleted = await client.delete(f"{args.backend_url}/api/orders/{order_id}")
            if result is not None:
                result["cleanup"]["order"] = deleted.status_code == 200
        if uploaded:
            deleted = await client.delete(
                f"{args.backend_url}/api/creative/{uploaded['filename']}"
            )
            if result is not None:
                result["cleanup"]["creative"] = deleted.status_code == 200


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", default="http://localhost:8080")
    parser.add_argument("--backend-url", default="http://localhost:3000")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--label", default="full-campaign-smoke")
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=45) as client:
        await _wait_ready(client, args.agent_url, args.timeout)
        dmp = await client.get(f"{args.backend_url}/api/dmp/attributes")
        dmp.raise_for_status()
        segments = dmp.json()
        if not segments:
            raise RuntimeError("DMP catalog is empty")
        segment = next(
            (item for item in segments if item.get("_id") and item.get("sizeMin")),
            segments[0],
        )
        zones = await client.get(f"{args.backend_url}/api/zones")
        zones.raise_for_status()
        placement = next(
            item for item in zones.json().get("placements", [])
            if item.get("format") == "banner"
        )

        flows = []
        for index in range(1, args.runs + 1):
            # Assign before returning so the finally block can annotate cleanup.
            result = await _one_flow(client, args, index, segment, placement["id"])
            flows.append(result)

    summary = {
        "runs": len(flows),
        "successful_runs": sum(bool(item.get("order_id")) for item in flows),
        "idempotency_passes": sum(item.get("idempotency_pass") is True for item in flows),
        "unique_orders": len({item["order_id"] for item in flows}),
        "cleanup_passes": sum(all(item["cleanup"].values()) for item in flows),
        "p95_seconds": round(
            sorted(item["duration_seconds"] for item in flows)[
                max(0, int(len(flows) * 0.95) - 1)
            ],
            3,
        ),
    }
    report = {
        "label": args.label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "flows": flows,
    }
    output = ROOT / "eval/reports" / f"{args.label}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report={output}")

    required_counts = (
        "successful_runs",
        "idempotency_passes",
        "unique_orders",
        "cleanup_passes",
    )
    if any(summary[name] != args.runs for name in required_counts):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
