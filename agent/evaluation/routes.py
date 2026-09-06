from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from campaign_ownership import list_owned_campaign_references
from evaluation.investigator import investigate_incident
from evaluation.investigation_jobs import VERSION as INVESTIGATION_VERSION
from evaluation.service import report_request, run_evaluation
from evaluation.store import (
    get_incident, get_policy, list_incidents, save_policy, transition_incident, latest_run, investigation_history, health_summary,
)
from identity import resolve_actor
from config import config


evaluation_router = APIRouter(tags=["live-evaluation"])


def _scenario_acceptance(scenario: dict, evaluation: dict) -> dict:
    """Compare the preset's minimum L1 contract with the observed revision.

    Expectations are returned to the UI only after Evaluation. They never enter
    the investigation context or a model prompt, so the test answer cannot leak
    into L2 evidence collection.
    """
    contract = scenario.get('expectation') or {}
    expected = sorted({str(value) for value in contract.get('l1IssueTypes') or []})
    revision = scenario.get('revision')
    closed = {'resolved', 'dismissed', 'false_positive', 'expired'}
    observed = sorted({
        str(item.get('issue_type')) for item in evaluation.get('incidents') or []
        if item.get('dataset_revision') == revision and item.get('state') not in closed
    })
    missing = sorted(set(expected) - set(observed))
    status = str(evaluation.get('status') or 'unknown')
    comparable = status in {'completed', 'retryable'}
    return {
        'status': 'matched' if comparable and not missing else 'not_matched' if comparable else 'not_evaluated',
        'expected_minimum_issue_types': expected,
        'observed_issue_types': observed,
        'missing_issue_types': missing,
        'additional_issue_types': sorted(set(observed) - set(expected)),
        'note': contract.get('note') or '',
    }


class PolicyUpdate(BaseModel):
    enabled: bool | None = None
    level: str | None = None
    schedule_minutes: int | None = Field(default=None, ge=5, le=1440)
    delivery_ratio_threshold: float | None = Field(default=None, ge=0.1, le=1.0)
    persistence_windows: int | None = Field(default=None, ge=1, le=10)
    ctr_relative_drop_threshold: float | None = Field(default=None, ge=0.05, le=1.0)
    ctr_z_threshold: float | None = Field(default=None, ge=-10.0, le=0.0)
    ctr_min_impressions: int | None = Field(default=None, ge=0, le=1_000_000)
    pacing_low_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    pacing_high_threshold: float | None = Field(default=None, ge=1.0, le=10.0)


class EvaluationRunRequest(BaseModel):
    force: bool = False


class ScenarioRequest(BaseModel):
    presetId: str
    targetPlacementId: str | None = None
    windowDays: int = Field(default=3, ge=1, le=30)
    persistenceWindows: int = Field(default=2, ge=1, le=10)
    impact: float = Field(default=0.75, ge=0, le=1)
    seed: str = "default"
    requestId: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_-]{8,100}$')
    expectedRevision: int | None = Field(default=None, ge=1)


class IncidentActionRequest(BaseModel):
    action: str
    note: str = ""


class IncidentQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    requestId: str = Field(pattern=r'^[A-Za-z0-9_-]{8,100}$')
    expectedRevision: int = Field(ge=1)
    expectedBundleId: str = Field(min_length=1, max_length=120)


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
    run = await latest_run(campaign_id)
    jobs, job_error = [], None
    if config.EVALUATION_MULTI_AGENT_ENABLED:
        from evaluation.investigation_jobs import list_jobs
        try:
            jobs = await list_jobs(campaign_id)
        except RuntimeError:
            job_error = 'Investigation storage unavailable'
    return {
        "campaign_id": campaign_id, "policy": policy, "incidents": incidents, 'last_run': run,
        'worker_enabled': config.EVALUATION_WORKER_ENABLED,
        'summary': health_summary(incidents, run),
        'investigation_mode': 'multi_agent' if config.EVALUATION_MULTI_AGENT_ENABLED else 'deterministic_playbook',
        'investigation_jobs': jobs, 'investigation_error': job_error,
        'investigation_engine_version': INVESTIGATION_VERSION,
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
        raise HTTPException(status_code=getattr(exc, 'status', 502), detail=str(exc)) from exc


@evaluation_router.get("/evaluation/campaigns/{campaign_id}/scenarios")
async def scenario_workspace(request: Request, campaign_id: str):
    await _assert_campaign_access(request, campaign_id)
    try:
        return await report_request("GET", f"/api/reports/internal/scenarios/{campaign_id}")
    except RuntimeError as exc:
        raise HTTPException(status_code=getattr(exc, 'status', 502), detail=str(exc)) from exc


@evaluation_router.post("/evaluation/campaigns/{campaign_id}/scenarios/preview")
async def preview(request: Request, campaign_id: str, body: ScenarioRequest):
    await _assert_campaign_access(request, campaign_id)
    try:
        return await report_request(
            "POST", f"/api/reports/internal/scenarios/{campaign_id}/preview",
            body.model_dump(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=getattr(exc, 'status', 502), detail=str(exc)) from exc


@evaluation_router.post("/evaluation/campaigns/{campaign_id}/scenarios/apply")
async def apply_and_evaluate(request: Request, campaign_id: str, body: ScenarioRequest):
    actor = await _assert_campaign_access(request, campaign_id)
    if not body.requestId or body.expectedRevision is None:
        raise HTTPException(status_code=422, detail='requestId and expectedRevision are required')
    try:
        scenario = await report_request(
            "POST", f"/api/reports/internal/scenarios/{campaign_id}/apply",
            {**body.model_dump(), 'createdBy': str(actor.get('user_id') or actor.get('anonymous_id') or 'owned_actor')},
        )
        try:
            evaluation = await run_evaluation(campaign_id, trigger="scenario_apply", expected_revision=scenario['revision'])
        except Exception as exc:
            # The report already committed. A retry must reuse the same scenario request.
            evaluation = {'status': 'retryable', 'error': str(exc)[:240], 'dataset_revision': scenario['revision']}
        return {"scenario": scenario, "evaluation": evaluation,
                "acceptance": _scenario_acceptance(scenario, evaluation)}
    except RuntimeError as exc:
        raise HTTPException(status_code=getattr(exc, 'status', 502), detail=str(exc)) from exc


@evaluation_router.get("/evaluation/campaigns/{campaign_id}/incidents/{incident_id}")
async def incident_detail(request: Request, campaign_id: str, incident_id: str):
    await _assert_campaign_access(request, campaign_id)
    incident = await get_incident(campaign_id, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="incident not found")
    return {
        "incident": incident,
        "investigation": incident.get("investigation"),
        "investigation_state": incident.get("investigation_state", "not_started"),
        'history': await investigation_history(campaign_id, incident_id),
    }


@evaluation_router.post("/evaluation/campaigns/{campaign_id}/incidents/{incident_id}/actions")
async def incident_action(request: Request, campaign_id: str, incident_id: str,
                          body: IncidentActionRequest):
    await _assert_campaign_access(request, campaign_id)
    if body.action == "investigate":
        incident = await get_incident(campaign_id, incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="incident not found")
        policy = await get_policy(campaign_id)
        try:
            if config.EVALUATION_MULTI_AGENT_ENABLED:
                from evaluation.investigation_jobs import enqueue
                job = await enqueue(campaign_id, incident, policy)
                return JSONResponse(status_code=202, content={'investigation_job': job})
            # Read-only: this runs diagnostic probes and attaches evidence. It
            # never changes campaign, order, or report state.
            bundle = await investigate_incident(
                campaign_id, incident, trigger="manual", policy=policy,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=getattr(exc, 'status', 502), detail=str(exc)) from exc
        refreshed = await get_incident(campaign_id, incident_id)
        return {"incident": refreshed, "investigation": bundle}

    state_map = {
        "dismiss": "dismissed",
        "false_positive": "false_positive",
    }
    if body.action in {'prepare_recovery', 'start_recovery', 'verify', 'resolve'}:
        raise HTTPException(status_code=409, detail='L3 executor unavailable. No recovery or verification was performed.')
    state = state_map.get(body.action)
    if not state:
        raise HTTPException(status_code=400, detail="unsupported incident action")
    try:
        return await transition_incident(campaign_id, incident_id, state, body.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@evaluation_router.post('/evaluation/campaigns/{campaign_id}/incidents/{incident_id}/questions')
async def ask_incident(request: Request, campaign_id: str, incident_id: str, body: IncidentQuestionRequest):
    await _assert_campaign_access(request, campaign_id)
    from evaluation.questions import answer, QuestionError
    try:
        return await answer(campaign_id, incident_id, question=body.question, request_id=body.requestId,
                            expected_revision=body.expectedRevision, expected_bundle_id=body.expectedBundleId)
    except QuestionError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail='Chưa trả lời được câu hỏi. Có thể thử lại cùng yêu cầu.') from exc


@evaluation_router.get('/evaluation/campaigns/{campaign_id}/incidents/{incident_id}/questions')
async def incident_questions(request: Request, campaign_id: str, incident_id: str):
    await _assert_campaign_access(request, campaign_id)
    if not await get_incident(campaign_id, incident_id):
        raise HTTPException(status_code=404, detail='incident not found')
    from evaluation.questions import history
    try:
        return {'questions': await history(campaign_id, incident_id)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail='Chưa tải được lịch sử hỏi đáp.') from exc


@evaluation_router.get('/evaluation/campaigns/{campaign_id}/investigations/{job_id}')
async def investigation_job_detail(request: Request, campaign_id: str, job_id: str):
    await _assert_campaign_access(request, campaign_id)
    from evaluation.investigation_jobs import get_job
    try:
        job = await get_job(campaign_id, job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail='Investigation storage unavailable') from exc
    if not job:
        raise HTTPException(status_code=404, detail='investigation not found')
    return job
