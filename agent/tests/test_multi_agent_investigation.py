"""Real JS scenario and Chromium observations; model responses are scripted.

These tests prove orchestration/contracts, not a live model's diagnostic quality.
"""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import subprocess
from unittest.mock import AsyncMock

import pytest

from evaluation.agent_model import Decision
from evaluation.evidence_tools import EvidenceTools, inspect_document
from evaluation.multi_agent import orchestrate, _validated_finish
from evaluation.probes import InvestigationContext
from tests.test_l2_investigation import baseline_records, BASELINE_INPUT, ORDER, ZONE_MAP, PLACEMENT


def scenario(preset='click_overlay', **parameters):
    result = subprocess.run(['node', '-e', '''
const fs=require('node:fs');const {applyScenario}=require('./lib/reportScenarios');
const x=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(applyScenario(x.rows,x.config)));
'''], input=json.dumps({'rows': baseline_records(), 'config': {'presetId': preset, 'targetPlacementId': PLACEMENT, **parameters}}),
        text=True, encoding='utf-8', capture_output=True, check=True, timeout=10,
        cwd=Path(__file__).resolve().parents[2] / 'backend')
    return json.loads(result.stdout)


def context(data):
    return InvestigationContext(campaign_id='ORD-2026-001', scope=PLACEMENT, issue_type='ctr_regression',
        baseline_records=baseline_records(), active_records=data['records'], baseline_input=BASELINE_INPUT,
        order=ORDER, zone_map=ZONE_MAP, evaluation_dates=['2026-08-09', '2026-08-10'])


def decision(action='finish', target='', *, refs=(), summary='Evidence checked.', assessment='supported_hypothesis', contradictions=()):
    return dict(action=action, target=target, summary=summary, assessment=assessment,
                evidence_ids=list(refs), contradictions=list(contradictions))


def job():
    return {'job_id': 'IVR-test', 'campaign_id': 'ORD-2026-001', 'incident_id': 'INC-ABC123',
            'dataset_revision': 2, 'policy_version': 'policy-test', 'trigger': 'test',
            'tasks': {}, 'evidence': {}, 'model_calls': 0, 'attempts': 1}


def incident():
    return {'campaign_id': 'ORD-2026-001', 'incident_id': 'INC-ABC123', 'scope': PLACEMENT,
            'issue_type': 'ctr_regression', 'dataset_revision': 2, 'state': 'open'}


class Journal:
    def __init__(self, value=None):
        self.value = value or job()
        self.snapshots = []

    async def __call__(self, changes, *, spend_call=False):
        if spend_call:
            if self.value['model_calls'] >= 24:
                raise RuntimeError('budget exhausted')
            self.value['model_calls'] += 1
        self.value.update(deepcopy(changes))
        self.snapshots.append(deepcopy(self.value))


class ScriptedModel:
    def __init__(self):
        self.inputs = []

    async def __call__(self, role, payload, *, tools, image=None):
        self.inputs.append((role, deepcopy(payload)))
        evidence = payload['evidence']
        if role == 'performance' and not evidence:
            return decision('tool', 'metrics_window')
        if role == 'creative' and not evidence:
            return decision('tool', 'inspect_render')
        if role == 'creative' and payload.get('required_tools_remaining'):
            return decision('tool', payload['required_tools_remaining'][0])
        refs = [e['evidence_id'] for e in evidence]
        render = next((e for e in evidence if e['probe_id'] == 'inspect_render'), None)
        summary = 'Vùng click bị chặn.' if render and render.get('finding') == 'hit_target_mismatch' else 'Chưa thấy bằng chứng vùng click bị chặn.'
        result = decision(refs=refs, summary=summary)
        if render and render.get('finding') == 'hit_target_mismatch':
            result['cause_code'] = 'click_obstruction'
        return result


@pytest.mark.asyncio
async def test_real_scenario_l1_and_browser_observation_not_a_flag():
    from evaluation.engine import evaluate_records
    data = scenario()
    issues = evaluate_records(baseline_records(), data['records'])
    assert 'ctr_regression' in {i['issue_type'] for i in issues}
    assert not {'creative_failure', 'click_tracking_failure'} & {i['issue_type'] for i in issues}
    ctx = context(data)
    adapter = EvidenceTools(ctx, 2, data['runtimeFixture'])
    before = deepcopy(data)
    result = await adapter.execute('creative', 'inspect_render')
    assert result['source'] == 'isolated_browser_observation'
    assert result['finding'] == 'hit_target_mismatch'
    assert result['evidence']['local_clicks_after'] == 0
    assert all(not p['reaches_creative'] for p in result['evidence']['points'])
    assert result['screenshot_base64'].startswith('iVBOR')
    assert data == before
    healthy = scenario('healthy_baseline')
    other = await EvidenceTools(ctx, 2, healthy['runtimeFixture']).execute('creative', 'inspect_render')
    assert other['status'] == 'ok'
    assert other['evidence']['local_clicks_after'] == 1


@pytest.mark.asyncio
async def test_multi_agent_collects_independent_evidence_and_coordinator_cites_it():
    data, journal, model = scenario(), Journal(), ScriptedModel()
    bundle = await orchestrate(job(), incident(), context(data), data['runtimeFixture'],
                               progress=journal, guard=AsyncMock(), model=model)
    assert bundle['mode'] == 'multi_agent'
    assert bundle['cause_code'] == 'click_obstruction' and bundle['claim_scope'] == 'isolated_document'
    assert bundle['hypotheses'][0]['status'] == 'supported'
    assert 'chưa chứng minh nguyên nhân KPI' in bundle['summary']
    assert set(bundle['tasks']) == {'performance', 'creative', 'coordinator'}
    assert all(t['status'] == 'completed' for t in bundle['tasks'].values())
    assert {e['probe_id'] for e in bundle['probes']} == {'metrics_window', 'inspect_render', 'creative_compatibility'}
    assert journal.value['model_calls'] == 6
    assert bundle['mutations'] == [] and bundle['recovery_options'] == []
    assert any(v['tasks'].get('performance', {}).get('status') == 'running' for v in journal.snapshots)
    model_input = json.dumps(model.inputs)
    for hidden in ['click_overlay', 'presetId', 'scenario', 'clickTelemetryFailure', 'runtimeFixture', 'OPENAI_API_KEY']:
        assert hidden not in model_input


@pytest.mark.asyncio
async def test_counterfactual_same_metrics_different_document_changes_conclusion():
    data, healthy = scenario(), scenario('healthy_baseline')
    bundle = await orchestrate(job(), incident(), context(data), healthy['runtimeFixture'],
                               progress=Journal(), guard=AsyncMock(), model=ScriptedModel())
    assert bundle['hypotheses'][0]['status'] == 'contradicted'
    assert bundle['cause_code'] == 'none' and bundle['cause_status'] == 'unresolved'


@pytest.mark.asyncio
async def test_readonly_boundary_denies_arbitrary_or_cross_role_tools():
    data = scenario()
    adapter = EvidenceTools(context(data), 2, None)
    for name in ['create_order', 'pause_campaign', 'fetch_all_orders', 'http://169.254.169.254', 'inspect_render']:
        with pytest.raises(PermissionError):
            await adapter.execute('performance', name)
    missing = await adapter.execute('creative', 'inspect_render')
    assert missing['status'] == 'unavailable'


@pytest.mark.asyncio
async def test_specialist_failure_is_visible_partial_without_fabricated_recovery():
    data, normal = scenario(), ScriptedModel()
    async def model(role, payload, **kwargs):
        if role == 'creative':
            raise RuntimeError('provider unavailable')
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(job(), incident(), context(data), None,
                               progress=Journal(), guard=AsyncMock(), model=model)
    assert bundle['partial'] and bundle['assessment'] == 'ambiguous'
    assert bundle['tasks']['creative']['status'] == 'failed'


@pytest.mark.asyncio
async def test_coordinator_failure_is_partial_and_cannot_claim_completion():
    data, normal = scenario(), ScriptedModel()
    async def model(role, payload, **kwargs):
        if role == 'coordinator':
            raise RuntimeError('bad response')
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(job(), incident(), context(data), None,
                               progress=Journal(), guard=AsyncMock(), model=model)
    assert bundle['partial'] and bundle['assessment'] == 'insufficient_evidence'
    assert bundle['tasks']['coordinator']['status'] == 'failed'


@pytest.mark.asyncio
async def test_coordinator_can_delegate_an_additional_specialist():
    data, normal = scenario(), ScriptedModel()
    async def model(role, payload, **kwargs):
        if role == 'coordinator' and 'setup' not in payload['tasks']:
            return decision('delegate', 'setup')
        if role == 'setup' and not payload['evidence']:
            return decision('tool', 'config_drift')
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(job(), incident(), context(data), None,
                               progress=Journal(), guard=AsyncMock(), model=model)
    assert bundle['tasks']['setup']['tool_calls'] == ['config_drift']
    assert bundle['tasks']['coordinator']['tool_calls'] == ['delegate_setup']


@pytest.mark.asyncio
async def test_guard_change_prevents_final_publish():
    data = scenario()
    async def guard():
        raise ValueError('stale dataset')
    with pytest.raises(ValueError, match='stale dataset'):
        await orchestrate(job(), incident(), context(data), None, progress=Journal(), guard=guard, model=ScriptedModel())


@pytest.mark.asyncio
async def test_forged_citation_and_model_mutation_are_not_executed():
    data = scenario()
    async def malicious(role, payload, **kwargs):
        if role == 'coordinator':
            return decision(refs=['EVD-made-up'])
        return decision('tool', 'create_order')
    bundle = await orchestrate(job(), incident(), context(data), None,
                               progress=Journal(), guard=AsyncMock(), model=malicious)
    assert bundle['assessment'] == 'insufficient_evidence'
    assert bundle['probes'] == [] and bundle['mutations'] == []


def test_missing_evidence_and_contradictions_cannot_become_supported():
    assert _validated_finish(decision(), {})['assessment'] == 'insufficient_evidence'
    assert _validated_finish(decision(refs=['a']), {'a': {'status': 'unavailable'}})['assessment'] == 'insufficient_evidence'
    assert _validated_finish(decision(refs=['a'], contradictions=['conflict']), {'a': {'status': 'ok'}})['assessment'] == 'ambiguous'
    with pytest.raises(ValueError):
        _validated_finish(decision(refs=['invented']), {})
    with pytest.raises(ValueError):
        Decision.model_validate({**decision(), 'campaign_id': 'OTHER'})


@pytest.mark.asyncio
async def test_persisted_model_budget_survives_restart():
    data, value = scenario(), job()
    value['model_calls'] = 24
    model = AsyncMock()
    bundle = await orchestrate(value, incident(), context(data), None,
                               progress=Journal(value), guard=AsyncMock(), model=model)
    model.assert_not_awaited()
    assert bundle['partial'] and bundle['assessment'] == 'insufficient_evidence'


@pytest.mark.asyncio
async def test_completed_specialists_resume_without_duplicate_calls():
    data, journal, model = scenario(), Journal(), ScriptedModel()
    await orchestrate(job(), incident(), context(data), data['runtimeFixture'], progress=journal, guard=AsyncMock(), model=model)
    previous = journal.value['model_calls']
    resumed = ScriptedModel()
    await orchestrate(journal.value, incident(), context(data), data['runtimeFixture'], progress=journal, guard=AsyncMock(), model=resumed)
    assert [role for role, _ in resumed.inputs] == ['coordinator']
    assert journal.value['model_calls'] == previous + 1


@pytest.mark.asyncio
async def test_retry_reclaims_a_previously_delegated_failed_specialist():
    data, value, roles = scenario(), job(), []
    value['tasks']['setup'] = {'role': 'setup', 'status': 'failed', 'tool_calls': []}
    normal = ScriptedModel()
    async def model(role, payload, **kwargs):
        roles.append(role)
        if role == 'setup' and not payload['evidence']:
            return decision('tool', 'config_drift')
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(value, incident(), context(data), None,
                               progress=Journal(value), guard=AsyncMock(), model=model)
    assert roles.count('setup') == 2
    assert bundle['tasks']['setup']['status'] == 'completed'
