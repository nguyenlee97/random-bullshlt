"""Background L2 queue, independent of the periodic L1 scheduler."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from urllib.parse import quote

from evaluation import investigation_jobs as jobs

_runner = None
_stop = asyncio.Event()


class StaleInvestigation(ValueError):
    pass


async def process_once() -> bool:
    job = await jobs.claim()
    if not job:
        return False
    from evaluation.store import get_incident, get_policy, attach_investigation
    from evaluation.service import report_request
    from evaluation.investigator import build_context
    from evaluation.multi_agent import orchestrate
    from evaluation.investigation_resume import snapshot_signature

    async def guard():
        from config import config
        incident = await get_incident(job['campaign_id'], job['incident_id'])
        policy = await get_policy(job['campaign_id'])
        if (not incident or incident.get('dataset_revision') != job['dataset_revision']
            or incident.get('state') in {'resolved', 'dismissed', 'false_positive', 'expired'}
            or not policy['enabled'] or policy['level'] not in {'L2', 'L3'}
            or not config.EVALUATION_MULTI_AGENT_ENABLED or job.get('model') != config.EVALUATION_AGENT_MODEL
            or job.get('engine_version') != jobs.VERSION
            or policy['version'] != job['policy_version']):
            raise StaleInvestigation('Incident or policy changed; evaluation must run again')
        dataset = await report_request('GET', '/api/reports/internal/datasets/' + quote(job['campaign_id'], safe=''))
        if (dataset.get('state') or {}).get('activeRevision') != job['dataset_revision']:
            raise StaleInvestigation('Dataset changed; old investigation was not published')
        return incident, policy, dataset

    async def progress(changes, *, spend_call=False):
        await jobs.checkpoint(job, changes, spend_call=spend_call)

    try:
        incident, policy, dataset = await guard()
        bundle = job.get('bundle')
        if not bundle:
            ctx = await build_context(job['campaign_id'], incident, policy=policy, dataset=dataset)
            bundle = await asyncio.wait_for(orchestrate(job, incident, ctx,
                (dataset.get('active') or {}).get('runtimeFixture'), progress=progress, guard=guard), timeout=240)
            await guard()
            await progress({'bundle': bundle})
        current_incident, current_policy, current_dataset = await guard()
        current_ctx = await build_context(job['campaign_id'], current_incident, policy=current_policy, dataset=current_dataset)
        if bundle.get('snapshot_signature') != snapshot_signature(job, current_ctx, (current_dataset.get('active') or {}).get('runtimeFixture')):
            raise StaleInvestigation('Evidence input changed; old investigation was not published')
        await progress({})  # lease-fence before publishing a result
        await attach_investigation(job['campaign_id'], job['incident_id'], bundle)
        await guard()
        from zalo_incidents import notify_incidents
        count = await notify_incidents(job['campaign_id'], [{**incident, 'investigation': bundle}], job['dataset_revision'])
        await progress({'status': 'partial' if bundle.get('partial') else 'completed',
                        'completed_at': jobs.now(), 'notification_enqueue_count': count, 'error': None})
    except asyncio.CancelledError:
        # Leave running lease to be reclaimed. No untracked background task.
        raise
    except Exception as exc:
        stale = isinstance(exc, StaleInvestigation)
        status = 'stale' if stale else 'queued' if job['attempts'] < jobs.MAX_ATTEMPTS else 'failed'
        try:
            await progress({'status': status, 'error': type(exc).__name__ + ': investigation could not finish',
                            'next_attempt_at': jobs.now() + timedelta(seconds=30)})
        except RuntimeError:
            pass  # Another worker owns the lease; never write through it.
    return True


async def _loop():
    while not _stop.is_set():
        try:
            if await process_once():
                continue
        except Exception as exc:
            print('[evaluation-l2] worker unavailable:', type(exc).__name__)
        try:
            await asyncio.wait_for(_stop.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass


async def start_worker():
    global _runner
    if _runner and not _runner.done():
        return
    await jobs.ensure_indexes()
    from evaluation.questions import ensure_indexes
    await ensure_indexes()
    _stop.clear()
    _runner = asyncio.create_task(_loop(), name='evaluation-investigations')


async def stop_worker():
    global _runner
    _stop.set()
    if _runner:
        _runner.cancel()
        await asyncio.gather(_runner, return_exceptions=True)
    _runner = None
