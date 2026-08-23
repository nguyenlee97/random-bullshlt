from __future__ import annotations

import httpx

from config import config
from evaluation.engine import evaluate_records
from evaluation.store import (
    find_existing_run, get_policy, list_incidents, resolve_stale_incidents,
    save_run, upsert_incidents,
)


def _headers(actor: str = "agent_ui") -> dict:
    return {"x-report-internal-key": config.REPORT_INTERNAL_API_KEY, "x-report-actor": actor}


async def report_request(method: str, path: str, json: dict | None = None) -> dict:
    if not config.REPORT_INTERNAL_API_KEY:
        raise RuntimeError("REPORT_INTERNAL_API_KEY is not configured")
    async with httpx.AsyncClient(base_url=config.BACKEND_URL, timeout=120.0) as client:
        response = await client.request(method, path, json=json, headers=_headers())
    if response.status_code >= 400:
        raise RuntimeError(response.json().get("error") or f"report service returned {response.status_code}")
    return response.json()


async def run_evaluation(campaign_id: str, trigger: str = "manual", force: bool = False) -> dict:
    dataset = await report_request("GET", f"/api/reports/internal/datasets/{campaign_id}")
    revision = int((dataset.get("state") or {}).get("activeRevision") or 1)
    policy = await get_policy(campaign_id)
    if not force:
        existing = await find_existing_run(campaign_id, revision, policy["version"])
        if existing:
            return {**existing, "no_op": True, "incidents": await list_incidents(campaign_id)}
    issues = evaluate_records(
        (dataset.get("baseline") or {}).get("records") or [],
        (dataset.get("active") or {}).get("records") or [],
        policy,
    )
    run = await save_run(campaign_id, revision, policy["version"], issues, trigger)
    incidents = await upsert_incidents(campaign_id, run, issues)
    await resolve_stale_incidents(
        campaign_id, {item["incident_id"] for item in incidents}, run["run_id"],
    )
    zalo_alerts = 0
    if incidents:
        try:
            from zalo_incidents import notify_incidents
            zalo_alerts = await notify_incidents(campaign_id, incidents, revision)
        except Exception:
            # Evaluation truth must survive a channel outage; the durable alert
            # queue is retried when it was reached successfully.
            zalo_alerts = 0
    return {
        **run, "no_op": False, "incidents": await list_incidents(campaign_id),
        "zalo_alerts": zalo_alerts,
    }
