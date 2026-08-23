from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from campaign_ownership import list_owned_campaign_references
from evaluation.service import report_request, run_evaluation
from evaluation.store import get_policy, list_incidents, save_policy, transition_incident
from identity import resolve_actor


evaluation_router = APIRouter(tags=["live-evaluation"])


class PolicyUpdate(BaseModel):
    enabled: bool | None = None
    level: str | None = None
    schedule_minutes: int | None = Field(default=None, ge=5, le=1440)
    delivery_ratio_threshold: float | None = Field(default=None, ge=0.1, le=1.0)
    persistence_windows: int | None = Field(default=None, ge=1, le=10)
    ctr_relative_drop_threshold: float | None = Field(default=None, ge=0.05, le=1.0)


class EvaluationRunRequest(BaseModel):
    force: bool = False


class ScenarioRequest(BaseModel):
    presetId: str
    targetPlacementId: str | None = None
    windowDays: int = Field(default=3, ge=1, le=30)
    persistenceWindows: int = Field(default=2, ge=1, le=10)
    impact: float = Field(default=0.75, ge=0, le=1)
    seed: str = "default"


class IncidentActionRequest(BaseModel):
    action: str
    note: str = ""


def _tokens(request: Request) -> tuple[str | None, str | None]:
    return (
        request.cookies.get("aa_account"),
        request.cookies.get("aa_anonymous") or request.headers.get("x-anonymous-token"),
    )


async def _assert_campaign_access(request: Request, campaign_id: str) -> dict:
    account, anonymous = _tokens(request)
    try:
        actor = await resolve_actor(account, anonymous, require_any=True)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    owned = await list_owned_campaign_references(actor)
    if campaign_id not in {str(item.get("order_id")) for item in owned}:
        raise HTTPException(status_code=404, detail="campaign not found")
    return actor


@evaluation_router.get("/evaluation/campaigns/{campaign_id}")
async def evaluation_detail(request: Request, campaign_id: str):
    await _assert_campaign_access(request, campaign_id)
    policy = await get_policy(campaign_id)
    incidents = await list_incidents(campaign_id)
    active_states = {
        "detected", "diagnosing", "open", "investigating", "awaiting_approval",
        "recovering", "verifying", "failed",
    }
    active = [item for item in incidents if item["state"] in active_states]
    return {
        "campaign_id": campaign_id, "policy": policy, "incidents": incidents,
        "summary": {
            "status": "bad" if any(item["severity"] in {"critical", "high"} for item in active)
            else "watch" if active else "healthy",
            "open_count": len(active),
            "critical_count": sum(item["severity"] == "critical" for item in active),
            "last_evaluated_at": incidents[0]["updated_at"] if incidents else None,
        },
    }


@evaluation_router.put("/evaluation/campaigns/{campaign_id}/policy")
async def update_policy(request: Request, campaign_id: str, body: PolicyUpdate):
    await _assert_campaign_access(request, campaign_id)
    updates = body.model_dump(exclude_none=True)
    if updates.get("level") not in {None, "L1", "L2", "L3"}:
        raise HTTPException(status_code=400, detail="level must be L1, L2, or L3")
    return await save_policy(campaign_id, updates)


@evaluation_router.post("/evaluation/campaigns/{campaign_id}/runs")
async def create_run(request: Request, campaign_id: str, body: EvaluationRunRequest):
    await _assert_campaign_access(request, campaign_id)
    try:
        return await run_evaluation(campaign_id, trigger="manual", force=body.force)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@evaluation_router.get("/evaluation/campaigns/{campaign_id}/scenarios")
async def scenario_workspace(request: Request, campaign_id: str):
    await _assert_campaign_access(request, campaign_id)
    try:
        return await report_request("GET", f"/api/reports/internal/scenarios/{campaign_id}")
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@evaluation_router.post("/evaluation/campaigns/{campaign_id}/scenarios/preview")
async def preview(request: Request, campaign_id: str, body: ScenarioRequest):
    await _assert_campaign_access(request, campaign_id)
    try:
        return await report_request(
            "POST", f"/api/reports/internal/scenarios/{campaign_id}/preview",
            body.model_dump(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@evaluation_router.post("/evaluation/campaigns/{campaign_id}/scenarios/apply")
async def apply_and_evaluate(request: Request, campaign_id: str, body: ScenarioRequest):
    await _assert_campaign_access(request, campaign_id)
    try:
        scenario = await report_request(
            "POST", f"/api/reports/internal/scenarios/{campaign_id}/apply",
            body.model_dump(),
        )
        evaluation = await run_evaluation(campaign_id, trigger="scenario_apply", force=True)
        return {"scenario": scenario, "evaluation": evaluation}
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@evaluation_router.post("/evaluation/campaigns/{campaign_id}/incidents/{incident_id}/actions")
async def incident_action(request: Request, campaign_id: str, incident_id: str,
                          body: IncidentActionRequest):
    await _assert_campaign_access(request, campaign_id)
    state_map = {
        "investigate": "investigating", "dismiss": "dismissed",
        "false_positive": "false_positive", "prepare_recovery": "awaiting_approval",
        "start_recovery": "recovering", "verify": "verifying", "resolve": "resolved",
    }
    state = state_map.get(body.action)
    if not state:
        raise HTTPException(status_code=400, detail="unsupported incident action")
    try:
        return await transition_incident(campaign_id, incident_id, state, body.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
