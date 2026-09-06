"""Queue/worker contracts with an in-memory Mongo adapter, not a DB smoke test."""
import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config import config
from evaluation import investigation_jobs as jobs, investigation_worker as worker, routes, store, service, investigator
from tests.test_multi_agent_investigation import incident, scenario, context, ScriptedModel


class MemoryJobCollection:
    """Subset used by the queue; unknown query operators fail the test."""
    def __init__(self):
        self.docs = {}

    def matches(self, doc, query):
        for key, expected in query.items():
            if key == '$or':
                if not any(self.matches(doc, q) for q in expected):
                    return False
                continue
            actual = doc.get(key)
            if isinstance(expected, dict):
                for op, value in expected.items():
                    assert op in {'$lt', '$lte', '$gt', '$gte', '$in'}
                    if actual is None:
                        return False
                    if not {'$lt': lambda: actual < value, '$lte': lambda: actual <= value,
                            '$gt': lambda: actual > value, '$gte': lambda: actual >= value,
                            '$in': lambda: actual in value}[op]():
                        return False
            elif actual != expected:
                return False
        return True

    def update(self, doc, changes, inserted=False):
        for op, fields in changes.items():
            assert op in {'$set', '$unset', '$inc', '$setOnInsert'}
            for key, value in fields.items():
                if op == '$set' or (op == '$setOnInsert' and inserted):
                    doc[key] = deepcopy(value)
                elif op == '$unset':
                    doc.pop(key, None)
                elif op == '$inc':
                    doc[key] = doc.get(key, 0) + value

    async def create_index(self, *args, **kwargs):
        pass

    async def find_one(self, query):
        return deepcopy(next((d for d in self.docs.values() if self.matches(d, query)), None))

    async def update_one(self, query, changes, upsert=False):
        doc = next((d for d in self.docs.values() if self.matches(d, query)), None)
        inserted = False
        if doc is None and upsert:
            doc = {'_id': query['_id']}
            self.docs[doc['_id']] = doc
            inserted = True
        if doc is not None:
            self.update(doc, changes, inserted)

    async def update_many(self, query, changes):
        for doc in self.docs.values():
            if self.matches(doc, query):
                self.update(doc, changes)

    async def find_one_and_update(self, query, changes, **kwargs):
        doc = next((d for d in self.docs.values() if self.matches(d, query)), None)
        if doc is None:
            return None
        self.update(doc, changes)
        return deepcopy(doc)

    def find(self, query, projection=None):
        docs = [deepcopy(d) for d in self.docs.values() if self.matches(d, query)]
        for doc in docs:
            for key, value in (projection or {}).items():
                if value == 0:
                    doc.pop(key, None)
        class Cursor:
            def sort(self, key, direction):
                docs.sort(key=lambda d: d[key], reverse=direction < 0)
                return self
            def limit(self, count):
                del docs[count:]
                return self
            async def to_list(self, _):
                return docs
        return Cursor()


@pytest.fixture
def queue(monkeypatch):
    col = MemoryJobCollection()
    monkeypatch.setattr(jobs, 'collection', AsyncMock(return_value=col))
    monkeypatch.setattr(config, 'EVALUATION_MULTI_AGENT_ENABLED', True)
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'test-key-no-network')
    return col


POLICY = {'enabled': True, 'level': 'L2', 'version': 'policy-1'}


@pytest.mark.asyncio
async def test_atomic_dedup_claim_and_fenced_progress(queue):
    submitted = await asyncio.gather(*(jobs.enqueue('ORD-2026-001', incident(), POLICY) for _ in range(8)))
    assert len({j['job_id'] for j in submitted}) == len(queue.docs) == 1
    claimed = await asyncio.gather(*(jobs.claim() for _ in range(8)))
    assert len([j for j in claimed if j]) == 1
    job = next(j for j in claimed if j)
    await jobs.checkpoint(job, {'tasks': {'performance': {'status': 'running'}}}, spend_call=True)
    assert job['model_calls'] == 1
    stored = queue.docs[job['job_id']]
    stored['lease_until'] = jobs.now() - timedelta(seconds=1)
    new_owner = await jobs.claim()
    assert new_owner['attempts'] == 2 and new_owner['model_calls'] == 1
    with pytest.raises(RuntimeError):
        await jobs.checkpoint(job, {'status': 'completed'})
    await jobs.checkpoint(new_owner, {'status': 'completed'})
    replay = await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    assert replay['status'] == 'completed'
    assert 'lease_token' not in replay


@pytest.mark.asyncio
async def test_scope_policy_budget_and_restart_limits(queue):
    for bad in [{**POLICY, 'level': 'L1'}, {**POLICY, 'enabled': False}]:
        with pytest.raises(PermissionError):
            await jobs.enqueue('ORD-2026-001', incident(), bad)
    with pytest.raises(PermissionError):
        await jobs.enqueue('OTHER', incident(), POLICY)
    with pytest.raises(ValueError):
        await jobs.enqueue('ORD-2026-001', {**incident(), 'state': 'dismissed'}, POLICY)
    await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    job = await jobs.claim()
    queue.docs[job['job_id']]['model_calls'] = jobs.MAX_MODEL_CALLS
    with pytest.raises(RuntimeError):
        await jobs.checkpoint(job, spend_call=True)
    queue.docs[job['job_id']].update(attempts=3, lease_until=jobs.now() - timedelta(seconds=1))
    assert await jobs.claim() is None
    assert queue.docs[job['job_id']]['status'] == 'failed'


@pytest.mark.asyncio
async def test_partial_retry_keeps_budget_and_completed_tasks(queue):
    await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    job = await jobs.claim()
    await jobs.checkpoint(job, {'status': 'partial', 'bundle': {'old': True},
                               'tasks': {'performance': {'status': 'completed'}}}, spend_call=True)
    auto = await jobs.enqueue('ORD-2026-001', incident(), POLICY, trigger='auto_l2')
    assert auto['status'] == 'partial'
    manual = await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    assert manual['status'] == 'queued' and 'bundle' not in manual
    assert manual['model_calls'] == 1 and manual['tasks']['performance']['status'] == 'completed'


@pytest.mark.asyncio
async def test_stale_snapshot_can_be_rechecked_manually_without_resetting_budget(queue):
    await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    job = await jobs.claim()
    await jobs.checkpoint(job, {'status': 'stale', 'bundle': {'snapshot_signature': 'old'},
                               'snapshot_signature': 'old'}, spend_call=True)
    auto = await jobs.enqueue('ORD-2026-001', incident(), POLICY, trigger='auto_l2')
    assert auto['status'] == 'stale'
    manual = await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    assert manual['status'] == 'queued' and 'bundle' not in manual and manual['model_calls'] == 1


@pytest.mark.asyncio
async def test_mongo_unavailable_does_not_claim_durable_queue(monkeypatch):
    import session
    monkeypatch.setattr(session, '_ensure_mongo', AsyncMock(return_value=False))
    with pytest.raises(RuntimeError, match='requires MongoDB'):
        await jobs.collection()


@pytest.fixture
def worker_env(queue, monkeypatch):
    data = scenario()
    dataset = {'state': {'activeRevision': 2}, 'active': data, 'baseline': {'records': context(data).baseline_records}}
    monkeypatch.setattr(store, 'get_incident', AsyncMock(return_value=incident()))
    monkeypatch.setattr(store, 'get_policy', AsyncMock(return_value=POLICY))
    monkeypatch.setattr(service, 'report_request', AsyncMock(return_value=dataset))
    monkeypatch.setattr(investigator, 'build_context', AsyncMock(return_value=context(data)))
    attach = AsyncMock()
    monkeypatch.setattr(store, 'attach_investigation', attach)
    import evaluation.multi_agent as multi, zalo_incidents
    monkeypatch.setattr(multi, 'decide', ScriptedModel())
    notify = AsyncMock(return_value=1)
    monkeypatch.setattr(zalo_incidents, 'notify_incidents', notify)
    return dataset, attach, notify


@pytest.mark.asyncio
async def test_worker_completes_and_notification_retry_reuses_bundle(queue, worker_env):
    _, attach, notify = worker_env
    notify.side_effect = [RuntimeError('outbox down'), 1]
    job = await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    await worker.process_once()
    stored = queue.docs[job['job_id']]
    assert stored['status'] == 'queued' and 'bundle' in stored
    calls = stored['model_calls']
    stored['next_attempt_at'] = jobs.now() - timedelta(seconds=1)
    await worker.process_once()
    assert stored['status'] == 'completed' and stored['model_calls'] == calls
    assert attach.await_count == 2 and notify.await_count == 2
    assert attach.call_args_list[0].args[2]['bundle_id'] == attach.call_args_list[1].args[2]['bundle_id']


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['dataset', 'policy', 'dismiss', 'engine'])
async def test_worker_stale_context_never_publishes(queue, worker_env, monkeypatch, change):
    dataset, attach, notify = worker_env
    job = await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    if change == 'dataset':
        dataset['state']['activeRevision'] = 3
    elif change == 'policy':
        monkeypatch.setattr(store, 'get_policy', AsyncMock(return_value={**POLICY, 'level': 'L1'}))
    elif change == 'dismiss':
        monkeypatch.setattr(store, 'get_incident', AsyncMock(return_value={**incident(), 'state': 'dismissed'}))
    else:
        queue.docs[job['job_id']]['engine_version'] = 'multi-agent-v1'
    await worker.process_once()
    assert queue.docs[job['job_id']]['status'] == 'stale'
    attach.assert_not_awaited()
    notify.assert_not_awaited()


def test_job_api_authorizes_before_queue_and_returns_202(queue, monkeypatch):
    monkeypatch.setattr(routes, 'resolve_actor', AsyncMock(return_value={'user_id': 'owner'}))
    references = AsyncMock(return_value=[{'order_id': 'ORD-2026-001'}])
    monkeypatch.setattr(routes, 'list_owned_campaign_references', references)
    monkeypatch.setattr(routes, 'get_incident', AsyncMock(return_value=incident()))
    monkeypatch.setattr(routes, 'get_policy', AsyncMock(return_value=POLICY))
    legacy = AsyncMock()
    monkeypatch.setattr(routes, 'investigate_incident', legacy)
    app = FastAPI()
    app.include_router(routes.evaluation_router)
    with TestClient(app) as client:
        base = '/evaluation/campaigns/ORD-2026-001'
        response = client.post(base + '/incidents/INC-ABC123/actions', json={'action': 'investigate'})
        assert response.status_code == 202
        job_id = response.json()['investigation_job']['job_id']
        assert client.get(base + '/investigations/' + job_id).status_code == 200
        references.return_value = []
        assert client.get(base + '/investigations/' + job_id).status_code == 404
        assert client.post(base + '/incidents/INC-ABC123/actions', json={'action': 'investigate'}).status_code == 404
    assert len(queue.docs) == 1
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_zalo_enqueue_does_not_touch_campaign_or_approval_context(queue, monkeypatch):
    import zalo_incidents, zalo_campaign_agent
    monkeypatch.setattr(zalo_campaign_agent, 'owned_campaigns', AsyncMock(return_value=[{'campaign_id': 'ORD-2026-001'}]))
    monkeypatch.setattr(store, 'list_incidents', AsyncMock(return_value=[incident()]))
    monkeypatch.setattr(store, 'get_policy', AsyncMock(return_value=POLICY))
    update = AsyncMock()
    monkeypatch.setattr(zalo_campaign_agent, '_update_thread', update)
    thread = {'active_campaign_id': 'ORD-OTHER', 'pending_action': {'kind': 'autopilot_approval'}}
    before = deepcopy(thread)
    reply, after = await zalo_incidents.handle_incident_reply(thread, '2 INC-ABC123')
    assert 'chạy nền' in reply and after == before
    assert len(queue.docs) == 1
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_l1_queues_l2_and_alerts_without_waiting_for_model(queue, monkeypatch):
    for name in ['_mem_policies', '_mem_runs', '_mem_incidents', '_mem_investigations']:
        monkeypatch.setattr(store, name, {})
    monkeypatch.setattr(store, '_collections', AsyncMock(return_value=None))
    data = scenario()
    dataset = {'state': {'activeRevision': 2}, 'baseline': {'records': context(data).baseline_records}, 'active': data}
    monkeypatch.setattr(service, 'report_request', AsyncMock(return_value=dataset))
    legacy = AsyncMock(side_effect=AssertionError('must not run inline'))
    monkeypatch.setattr(investigator, 'investigate_incident', legacy)
    import zalo_incidents
    notify = AsyncMock(return_value=1)
    monkeypatch.setattr(zalo_incidents, 'notify_incidents', notify)
    await store.save_policy('ORD-2026-001', {'level': 'L2'})
    result = await service.run_evaluation('ORD-2026-001')
    assert result['status'] == 'completed' and result['investigation_mode'] == 'multi_agent'
    assert queue.docs and all(doc['status'] == 'queued' for doc in queue.docs.values())
    assert all(doc['model_calls'] == 0 for doc in queue.docs.values())
    notify.assert_awaited_once()
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_rechecks_revision_after_specialists_and_before_publication(queue, worker_env, monkeypatch):
    dataset, attach, notify = worker_env
    from evaluation import multi_agent
    normal = ScriptedModel()
    async def changed(role, payload, **kwargs):
        result = await normal(role, payload, **kwargs)
        if role == 'coordinator':
            dataset['state']['activeRevision'] = 3
        return result
    monkeypatch.setattr(multi_agent, 'decide', changed)
    job = await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    await worker.process_once()
    assert queue.docs[job['job_id']]['status'] == 'stale'
    attach.assert_not_awaited()
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_rechecks_catalog_before_publishing_cached_bundle(queue, worker_env, monkeypatch):
    _, attach, notify = worker_env
    notify.side_effect = [RuntimeError('outbox down'), 1]
    queued = await jobs.enqueue('ORD-2026-001', incident(), POLICY)
    await worker.process_once()
    stored = queue.docs[queued['job_id']]
    assert stored['status'] == 'queued' and stored['bundle']['snapshot_signature']
    changed = deepcopy(investigator.build_context.return_value)
    changed.zone_map['changed'] = {'size': '1x1'}
    investigator.build_context.return_value = changed
    stored['next_attempt_at'] = jobs.now() - timedelta(seconds=1)
    await worker.process_once()
    assert stored['status'] == 'stale'
    assert attach.await_count == notify.await_count == 1
