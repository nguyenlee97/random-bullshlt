"""Read-only Q&A contracts. Scripted model and Mongo-shaped adapter, no live services."""
import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config import config
from evaluation import questions as qa, routes
from tests.test_investigation_jobs import MemoryJobCollection
from tests.test_multi_agent_investigation import decision


CAMPAIGN, INCIDENT = 'ORD-2026-001', 'INC-ABC123'
BODY = dict(question='Vì sao vùng click bị che?', request_id='request-123', expected_revision=2, expected_bundle_id='bundle-2')


@pytest.fixture
def env(monkeypatch):
    evidence = {'evidence_id': 'EV-one', 'campaign_id': CAMPAIGN, 'scope': 'zone-a',
                'dataset_revision': 2, 'probe_id': 'inspect_render', 'source': 'isolated_browser_observation',
                'status': 'anomaly', 'evidence': {'blocked_points': 5}, 'screenshot_base64': 'not-for-model'}
    bundle = {'mode': 'multi_agent', 'bundle_id': 'bundle-2', 'campaign_id': CAMPAIGN, 'incident_id': INCIDENT,
              'dataset_revision': 2, 'policy_version': 'policy-1', 'assessment': 'ambiguous', 'partial': True,
              'probes': [evidence]}
    incident = {'campaign_id': CAMPAIGN, 'incident_id': INCIDENT, 'scope': 'zone-a', 'dataset_revision': 2,
                'state': 'open', 'title': 'CTR thấp', 'investigation': bundle}
    policy = {'enabled': True, 'level': 'L2', 'version': 'policy-1'}
    dataset = {'state': {'activeRevision': 2}}
    col = MemoryJobCollection()
    model = AsyncMock(return_value=decision(refs=['EV-one'], summary='Hit-test bị chặn; chưa chứng minh nguyên nhân CTR.', assessment='ambiguous'))
    monkeypatch.setattr(config, 'EVALUATION_MULTI_AGENT_ENABLED', True)
    monkeypatch.setattr(qa, 'get_incident', AsyncMock(return_value=incident))
    monkeypatch.setattr(qa, 'get_policy', AsyncMock(return_value=policy))
    monkeypatch.setattr(qa, 'report_request', AsyncMock(return_value=dataset))
    monkeypatch.setattr(qa, 'collection', AsyncMock(return_value=col))
    monkeypatch.setattr(qa, 'decide', model)
    return incident, policy, dataset, col, model


@pytest.mark.asyncio
async def test_grounded_answer_replay_history_and_no_shared_context(env):
    incident, _, _, _, model = env
    before = deepcopy(incident)
    result = await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert result == await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert model.await_count == 1
    assert model.call_args.kwargs == {'tools': {}}
    assert model.call_args.args[0] == 'incident_qa'
    assert 'screenshot_base64' not in str(model.call_args.args[1])
    assert result['citations'][0]['evidence_id'] == 'EV-one'
    assert result['dataset_revision'] == 2 and result['bundle_id'] == 'bundle-2'
    assert incident == before
    assert await qa.history(CAMPAIGN, INCIDENT) == [result]
    assert await qa.history('OTHER', INCIDENT) == []


@pytest.mark.asyncio
async def test_typed_qa_rejects_false_cross_hypothesis_exclusions_in_public_prose(env):
    from evaluation.evidence_relations import VERSION, build_hypotheses
    from tests.test_investigation_completion import render_evidence
    incident, _, _, _, model = env
    bundle = incident['investigation']
    render = {**bundle['probes'][0], **render_evidence(False)}
    size = {**render, 'evidence_id': 'EV-size', 'probe_id': 'creative_compatibility',
            'source': 'derived', 'status': 'anomaly', 'finding': 'size_mismatch', 'summary': 'Metadata mismatch.'}
    bundle.update(relationship_version=VERSION, probes=[render, size], cause_code='creative_contract_mismatch',
                  assessment='supported_hypothesis', partial=False,
                  hypotheses=build_hypotheses({'EV-one': render, 'EV-size': size}))
    model.return_value = {**decision(refs=['EV-one', 'EV-size'], summary='Healthy render rules out all config drift.'),
                          'cause_code': 'creative_contract_mismatch', 'counter_evidence_ids': ['EV-one']}
    answer = await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert answer['assessment'] == 'supported_hypothesis'
    assert 'rules out' not in answer['answer']
    assert answer['claim_scope'] == 'creative_metadata'
    assert model.call_args.args[1]['allowed_evidence_links']
    assert model.await_count == 1


@pytest.mark.asyncio
async def test_snapshot_bound_qa_rejects_catalog_change_even_without_dataset_revision_change(env, monkeypatch):
    from evaluation import investigator
    from evaluation.investigation_resume import snapshot_signature
    from evaluation.probes import InvestigationContext
    incident, policy, dataset, _, model = env
    ctx = InvestigationContext(campaign_id=CAMPAIGN, scope='zone-a', policy=policy)
    bundle = incident['investigation']
    bundle['snapshot_signature'] = snapshot_signature(bundle, ctx, None)
    monkeypatch.setattr(investigator, 'build_context', AsyncMock(return_value=ctx))
    assert (await qa.answer(CAMPAIGN, INCIDENT, **BODY))['bundle_id'] == 'bundle-2'
    ctx.policy.update(updated_at='later', next_run_at='later')
    assert (await qa.answer(CAMPAIGN, INCIDENT, **BODY))['bundle_id'] == 'bundle-2'
    ctx.zone_map['zone-a'] = {'size': 'new-size'}
    with pytest.raises(qa.QuestionError, match='catalog'):
        await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert model.await_count == 1  # Even a cached answer is now stale.


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['dataset', 'policy', 'bundle', 'revision', 'no_l2', 'disabled'])
async def test_stale_or_missing_evidence_rejected_before_model(env, change):
    incident, policy, dataset, _, model = env
    if change == 'dataset': dataset['state']['activeRevision'] = 3
    if change == 'policy': policy['version'] = 'policy-2'
    if change == 'bundle': incident['investigation']['bundle_id'] = 'bundle-3'
    if change == 'revision': incident['dataset_revision'] = 3
    if change == 'no_l2': incident['investigation'] = None
    if change == 'disabled': policy['level'] = 'L1'
    with pytest.raises(qa.QuestionError):
        await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    model.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_after_call_and_stale_cached_result_never_returned(env):
    _, _, dataset, col, model = env
    async def change(*args, **kwargs):
        dataset['state']['activeRevision'] = 3
        return decision(refs=['EV-one'])
    model.side_effect = change
    with pytest.raises(qa.QuestionError):
        await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert not any(d.get('response') for d in col.docs.values())
    dataset['state']['activeRevision'] = 2
    model.side_effect = None
    await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    dataset['state']['activeRevision'] = 3
    with pytest.raises(qa.QuestionError):
        await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert model.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [decision('tool', 'dismiss', refs=['EV-one']), decision(refs=['made-up']), decision(refs=[])])
async def test_invalid_citation_or_action_fails_closed(env, bad):
    *_, col, model = env
    model.return_value = bad
    with pytest.raises(qa.QuestionError):
        await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert not any(d.get('response') for d in col.docs.values())


@pytest.mark.asyncio
async def test_evidence_from_other_campaign_scope_or_revision_excluded(env):
    incident, _, _, _, model = env
    probe = incident['investigation']['probes'][0]
    incident['investigation']['probes'] += [{**probe, 'evidence_id': 'OTHER', 'campaign_id': 'OTHER'},
        {**probe, 'evidence_id': 'OLD', 'dataset_revision': 1}, {**probe, 'evidence_id': 'ZONE', 'scope': 'other'}]
    await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert [e['evidence_id'] for e in model.call_args.args[1]['evidence']] == ['EV-one']


@pytest.mark.asyncio
async def test_concurrent_duplicates_and_changed_request_id_payload(env):
    *_, model = env
    started, release = asyncio.Event(), asyncio.Event()
    async def slow(*args, **kwargs):
        started.set()
        await release.wait()
        return decision(refs=['EV-one'])
    model.side_effect = slow
    task = asyncio.create_task(qa.answer(CAMPAIGN, INCIDENT, **BODY))
    try:
        await started.wait()
        with pytest.raises(qa.QuestionError):
            await qa.answer(CAMPAIGN, INCIDENT, **BODY)
        with pytest.raises(qa.QuestionError):
            await qa.answer(CAMPAIGN, INCIDENT, **{**BODY, 'question': 'Câu khác'})
    finally:
        release.set()
        await task
    assert model.await_count == 1


@pytest.mark.asyncio
async def test_revision_budget_and_lease_fence(env):
    _, _, _, col, model = env
    async def steal(*args, **kwargs):
        for doc in col.docs.values():
            if doc.get('status') == 'running': doc['lease_until'] = qa.now() - timedelta(seconds=1)
        return decision(refs=['EV-one'])
    model.side_effect = steal
    with pytest.raises(qa.QuestionError):
        await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert not any(d.get('response') for d in col.docs.values())
    col.docs[f'budget:{CAMPAIGN}:{INCIDENT}:2']['calls'] = 30
    with pytest.raises(qa.QuestionError) as exc:
        await qa.answer(CAMPAIGN, INCIDENT, **{**BODY, 'request_id': 'another-id'})
    assert exc.value.status == 429 and model.await_count == 1


def test_api_checks_ownership_before_qa_and_history(monkeypatch, env):
    from fastapi import HTTPException
    app = FastAPI()
    app.include_router(routes.evaluation_router)
    client = TestClient(app)
    access = AsyncMock(side_effect=HTTPException(404, 'campaign not found'))
    monkeypatch.setattr(routes, '_assert_campaign_access', access)
    body = dict(question=BODY['question'], requestId='request-123', expectedRevision=2, expectedBundleId='bundle-2')
    path = f'/evaluation/campaigns/{CAMPAIGN}/incidents/{INCIDENT}/questions'
    assert client.post(path, json=body).status_code == 404
    assert client.get(path).status_code == 404
    env[-1].assert_not_awaited()
    access.side_effect = None
    assert client.post(path, json=body).status_code == 200
    assert client.post(path, json={**body, 'question': ' '}).status_code == 422


@pytest.mark.asyncio
async def test_storage_unavailable_is_not_a_memory_fallback(monkeypatch):
    import session
    monkeypatch.setattr(session, '_ensure_mongo', AsyncMock(return_value=False))
    with pytest.raises(qa.QuestionError) as exc:
        await qa.collection()
    assert exc.value.status == 503


@pytest.mark.asyncio
async def test_provider_failure_is_bounded_and_partial_cannot_become_certain(env):
    *_, model = env
    model.side_effect = RuntimeError('provider unavailable')
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    with pytest.raises(qa.QuestionError):
        await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert model.await_count == 2
    model.side_effect = None
    model.return_value = decision(refs=['EV-one'], assessment='supported_hypothesis')
    response = await qa.answer(CAMPAIGN, INCIDENT, **{**BODY, 'request_id': 'new-question'})
    assert response['assessment'] == 'ambiguous'


@pytest.mark.asyncio
async def test_qa_cannot_introduce_new_cause_and_exposes_uncertainty(env):
    incident, _, _, _, model = env
    from tests.test_investigation_completion import render_evidence
    incident['investigation']['probes'][0].update(render_evidence())
    model.return_value = {**decision(refs=['EV-one']), 'cause_code':'click_obstruction'}
    with pytest.raises(qa.QuestionError, match='tự thêm nguyên nhân'):
        await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    model.return_value = decision(refs=['EV-one'])
    answer=await qa.answer(CAMPAIGN, INCIDENT, **BODY)
    assert answer['cause_status']=='unresolved' and answer['claim_scope']=='unknown'
    assert answer['limitations']
