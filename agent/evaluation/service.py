from __future__ import annotations

from urllib.parse import quote
import httpx

from config import config
from evaluation.engine import evaluate_records
from evaluation.store import (
    acquire_campaign_lease, release_campaign_lease, finish_run,
    find_existing_run, get_policy, list_incidents, resolve_stale_incidents,
    save_run, upsert_incidents,
    renew_campaign_lease, schedule_retry,
)


class ReportServiceError(RuntimeError):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


async def report_request(method: str, path: str, json: dict | None = None) -> dict:
    if not config.REPORT_INTERNAL_API_KEY:
        raise ReportServiceError('REPORT_INTERNAL_API_KEY is not configured', 503)
    try:
        async with httpx.AsyncClient(base_url=config.BACKEND_URL, timeout=120.0) as client:
            response = await client.request(method, path, json=json, headers={
                'x-report-internal-key': config.REPORT_INTERNAL_API_KEY,
            })
    except httpx.RequestError as exc:
        raise ReportServiceError('Report service could not be reached; retry with the same request ID.') from exc
    if response.status_code >= 400:
        try:
            message = response.json().get('error') or 'report service failed'
        except ValueError:
            message = 'report service failed'
        raise ReportServiceError(message, response.status_code if response.status_code in {400, 404, 409, 503} else 502)
    return response.json()


async def run_evaluation(campaign_id: str, trigger: str = 'manual', force: bool = False,
                         expected_revision: int | None = None) -> dict:
    policy = await get_policy(campaign_id)
    if not policy['enabled']:
        return {'status': 'disabled', 'no_op': True, 'incidents': await list_incidents(campaign_id)}
    token = await acquire_campaign_lease(campaign_id)
    if not token:
        raise ReportServiceError('Campaign evaluation is already running; retry shortly.', 409)
    run = None
    try:
        policy = await get_policy(campaign_id)
        if not policy['enabled']:
            return {'status': 'disabled', 'no_op': True, 'incidents': await list_incidents(campaign_id)}
        dataset = await report_request('GET', f'/api/reports/internal/datasets/{quote(campaign_id, safe="")}')
        revision = int((dataset.get('state') or {}).get('activeRevision') or 1)
        if expected_revision is not None and revision != expected_revision:
            raise ReportServiceError('Dataset changed; evaluate the current revision.', 409)
        if not force:
            existing = await find_existing_run(campaign_id, revision, policy['version'])
            mode = 'multi_agent' if config.EVALUATION_MULTI_AGENT_ENABLED else 'deterministic_playbook'
            same_model = mode != 'multi_agent' or (existing or {}).get('investigation_model') == config.EVALUATION_AGENT_MODEL
            if existing and same_model and existing.get('investigation_mode', 'deterministic_playbook') == mode:
                return {**existing, 'no_op': True, 'incidents': await list_incidents(campaign_id)}
        baseline = (dataset.get('baseline') or {}).get('records') or []
        active = (dataset.get('active') or {}).get('records') or []
        issues = evaluate_records(baseline, active, policy)
        async def checkpoint():
            if not await renew_campaign_lease(campaign_id, token):
                raise ReportServiceError('Evaluation lease expired; retry.', 409)
            current_policy = await get_policy(campaign_id)
            if current_policy['version'] != policy['version']:
                raise ReportServiceError('Evaluation policy changed; retry.', 409)
            current = await report_request('GET', f'/api/reports/internal/datasets/{quote(campaign_id, safe="")}')
            if (current.get('state') or {}).get('activeRevision') != revision:
                raise ReportServiceError('Dataset changed during evaluation; retry.', 409)
        await checkpoint()
        run = await save_run(campaign_id, revision, policy['version'], issues, trigger)
        incidents = await upsert_incidents(campaign_id, run, issues)
        # Missing measurement cannot establish that an earlier fault recovered.
        if not any(issue['issue_type'] == 'data_quality' for issue in issues):
            await resolve_stale_incidents(campaign_id, {i['incident_id'] for i in incidents}, run['run_id'])
        actionable = [i for i in incidents if i['state'] not in {'dismissed', 'false_positive'}]
        investigations = {}
        errors = []
        if policy['level'] in {'L2', 'L3'}:
            from evaluation.investigator import investigate_incident
            for incident in actionable:
                await checkpoint()
                try:
                    if config.EVALUATION_MULTI_AGENT_ENABLED:
                        from evaluation.investigation_jobs import enqueue
                        await enqueue(campaign_id, incident, policy, trigger='auto_l2')
                        continue
                    investigations[incident['incident_id']] = await investigate_incident(
                        campaign_id, incident, trigger='auto_l2', dataset=dataset, policy=policy)
                    if investigations[incident['incident_id']].get('assessment') == 'insufficient_evidence':
                        errors.append({'stage': 'investigation', 'incident_id': incident['incident_id'], 'error': 'insufficient_evidence'})
                except Exception as exc:
                    errors.append({'stage': 'investigation', 'incident_id': incident['incident_id'], 'error': str(exc)[:240]})
        alerts = 0
        await checkpoint()
        try:
            from zalo_incidents import notify_incidents
            enriched = [{**i, 'investigation': investigations.get(i['incident_id'])} for i in actionable]
            alerts = await notify_incidents(campaign_id, enriched, revision)
        except Exception as exc:
            errors.append({'stage': 'notification', 'error': str(exc)[:240]})
        run = await finish_run(run['run_id'], 'retryable' if errors else 'completed',
            errors=errors, investigated_count=len(investigations), zalo_alerts=alerts,
            evaluation_level=policy['level'],
            investigation_mode='multi_agent' if config.EVALUATION_MULTI_AGENT_ENABLED else 'deterministic_playbook',
            investigation_model=config.EVALUATION_AGENT_MODEL if config.EVALUATION_MULTI_AGENT_ENABLED else None)
        if errors:
            await schedule_retry(campaign_id)
        return {**run, 'no_op': False, 'incidents': await list_incidents(campaign_id)}
    except Exception as exc:
        if run:
            await finish_run(run['run_id'], 'failed', errors=[{'stage': 'evaluation', 'error': str(exc)[:240]}])
        await schedule_retry(campaign_id)
        raise
    finally:
        await release_campaign_lease(campaign_id, token)
