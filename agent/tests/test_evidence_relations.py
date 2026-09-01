from copy import deepcopy
from dataclasses import replace
from unittest.mock import AsyncMock
import asyncio

import pytest

from evaluation.decision_contract import DecisionError, validated_finish, ModelResponseError
from evaluation.evidence_relations import allowed_links, build_hypotheses, relation
from evaluation.evidence_tools import EvidenceTools
from evaluation.multi_agent import orchestrate
from evaluation.probes import probe_config_drift
from evaluation.investigation_resume import snapshot_signature
from tests.test_investigation_completion import render_evidence, finish
from tests.test_multi_agent_investigation import scenario, context, job, incident, Journal, ScriptedModel


def metadata():
    return {'probe_id': 'creative_compatibility', 'finding': 'size_mismatch', 'source': 'derived', 'status': 'anomaly'}


def test_policy_runtime_timestamps_do_not_invalidate_evidence_but_thresholds_do():
    ctx = context(scenario())
    ctx.policy = {'updated_at': 'first', 'next_run_at': 'first', 'lease_token': 'first'}
    before = snapshot_signature(job(), ctx, None)
    ctx.policy.update(updated_at='second', next_run_at='second', lease_token='second', last_scheduled_at='second')
    assert snapshot_signature(job(), ctx, None) == before
    ctx.policy['ctr_min_impressions'] = 1234
    assert snapshot_signature(job(), ctx, None) != before


def test_healthy_render_counters_overlay_not_metadata_or_config():
    evidence = {'render': render_evidence(False), 'size': metadata(),
                'delivery': {'probe_id': 'delivery_pattern', 'status': 'ok', 'finding': 'stable', 'source': 'report_dataset'}}
    result = validated_finish(finish(['render', 'size', 'delivery'], cause_code='creative_contract_mismatch',
        counter_evidence_ids=['render'], contradictions=['Healthy rendering excludes metadata and config.']), evidence, typed=True)
    assert result['assessment'] == 'supported_hypothesis'
    assert result['counter_evidence_ids'] == [] and result['contradictions'] == []
    assert 'excludes metadata' not in str(result)
    cards = {h['hypothesis_id']: h for h in result['hypotheses']}
    assert cards['click_obstruction']['status'] == 'contradicted'
    assert cards['creative_contract_mismatch']['status'] == 'supported'
    assert cards['configuration_drift']['status'] == 'unknown'
    assert all(relation(code, evidence['delivery']) == 'context' for code in cards)


def test_wrong_typed_relation_and_forged_ref_rejected():
    for ref, kind, code in [('render', 'supports', 'invalid_evidence_relation'), ('foreign', 'context', 'unknown_evidence')]:
        with pytest.raises(DecisionError) as error:
            validated_finish(finish(['render'], evidence_links=[{
                'hypothesis_id': 'creative_contract_mismatch', 'evidence_id': ref, 'relation': kind}]),
                {'render': render_evidence(False)}, typed=True)
        assert error.value.code == code


def test_actual_conflict_remains_ambiguous_even_if_model_ignores_counterevidence():
    result = validated_finish(finish(['blocked'], cause_code='click_obstruction'),
        {'blocked': render_evidence(), 'clear': render_evidence(False)}, typed=True)
    assert result['assessment'] == 'ambiguous' and result['counter_evidence_ids'] == ['clear']
    assert result['hypotheses'][0]['status'] == 'conflicting'


def test_unavailable_or_scenario_signals_never_support_or_refute_a_hypothesis():
    observations = {'missing': {**render_evidence(False), 'status': 'unavailable'},
                    'flag': {**render_evidence(), 'source': 'scenario_fact'}}
    assert all(h['status'] == 'unknown' for h in build_hypotheses(observations))
    assert all(link['relation'] in {'context', 'unavailable'} for link in allowed_links(observations))


def test_config_comparison_exposes_missing_fields_instead_of_claiming_all_match():
    ctx = context(scenario())
    missing = probe_config_drift(replace(ctx, baseline_input={'brand': 'x'}, order={'brand': 'x'}))
    assert missing['status'] == 'unavailable' and not missing['evidence']['compared_fields']
    partial = probe_config_drift(replace(ctx, baseline_input={'budget': 100}, order={'budget': 100}))
    assert partial['evidence']['compared_fields'] == ['budget']
    card = next(h for h in build_hypotheses({'config': partial}) if h['hypothesis_id'] == 'configuration_drift')
    assert card['status'] == 'contradicted' and card['missing_evidence']


@pytest.mark.asyncio
async def test_resume_after_provider_timeouts_retains_observation_and_global_budget(monkeypatch):
    data, journal, normal = scenario(), Journal(), ScriptedModel()
    calls, execute = [], EvidenceTools.execute
    async def spy(self, role, tool):
        calls.append((role, tool))
        return await execute(self, role, tool)
    monkeypatch.setattr(EvidenceTools, 'execute', spy)
    async def failing(role, payload, **kwargs):
        if role == 'creative' and payload['evidence']:
            raise ModelResponseError('model_timeout')
        return await normal(role, payload, **kwargs)
    first = await orchestrate(job(), incident(), context(data), data['runtimeFixture'], progress=journal,
        guard=AsyncMock(), model=failing, renderer=AsyncMock(return_value=render_evidence()))
    assert first['partial'] and first['tasks']['creative']['error_code'] == 'model_timeout'
    previous = journal.value['model_calls']
    journal.value['attempts'] = 2
    resumed = await orchestrate(journal.value, incident(), context(data), data['runtimeFixture'], progress=journal,
        guard=AsyncMock(), model=normal, renderer=AsyncMock(return_value=render_evidence()))
    assert not resumed['partial'] and journal.value['model_calls'] == previous + 3  # metadata selection + final + coordinator
    assert calls.count(('creative', 'inspect_render')) == 1
    assert resumed['tasks']['creative']['reused_evidence_count'] == 1
    assert all('duration_ms' in t for t in resumed['tasks']['creative']['timings'])
    assert any(t.get('error_code') == 'model_timeout' for t in resumed['tasks']['creative']['timings'])


@pytest.mark.asyncio
async def test_resume_invalidates_old_evidence_when_catalog_changes():
    data, journal = scenario(), Journal()
    await orchestrate(job(), incident(), context(data), data['runtimeFixture'], progress=journal,
        guard=AsyncMock(), model=ScriptedModel(), renderer=AsyncMock(return_value=render_evidence()))
    changed = deepcopy(context(data))
    changed.zone_map['new_catalog_entry'] = {'width': 999}
    model = ScriptedModel()
    result = await orchestrate(journal.value, incident(), changed, data['runtimeFixture'], progress=journal,
        guard=AsyncMock(), model=model, renderer=AsyncMock(return_value=render_evidence()))
    assert {'performance', 'creative', 'coordinator'} == {r for r, _ in model.inputs}
    assert result['completion']['reused_evidence'] == 0


@pytest.mark.asyncio
async def test_foreign_scope_evidence_is_not_reused():
    data, journal = scenario(), Journal()
    await orchestrate(job(), incident(), context(data), data['runtimeFixture'], progress=journal,
        guard=AsyncMock(), model=ScriptedModel(), renderer=AsyncMock(return_value=render_evidence()))
    for item in journal.value['evidence'].values():
        item['scope'] = 'OTHER'
    result = await orchestrate(journal.value, incident(), context(data), data['runtimeFixture'], progress=journal,
        guard=AsyncMock(), model=ScriptedModel(), renderer=AsyncMock(return_value=render_evidence()))
    assert result['completion']['reused_evidence'] == 0
    assert all(e['scope'] != 'OTHER' for e in result['probes'])


@pytest.mark.asyncio
async def test_cancelled_tool_is_replayed_without_buying_same_model_decision_again():
    data, journal, entered = scenario(), Journal(), asyncio.Event()
    async def slow_renderer(_html):
        entered.set()
        await asyncio.Future()
    task = asyncio.create_task(orchestrate(job(), incident(), context(data), data['runtimeFixture'], progress=journal,
        guard=AsyncMock(), model=ScriptedModel(), renderer=slow_renderer))
    await asyncio.wait_for(entered.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert journal.value['tasks']['creative']['pending_tool'] == 'inspect_render'
    assert journal.value['tasks']['creative']['status'] == 'interrupted'
    model = ScriptedModel()
    result = await orchestrate(journal.value, incident(), context(data), data['runtimeFixture'], progress=journal,
        guard=AsyncMock(), model=model, renderer=AsyncMock(return_value=render_evidence()))
    creative_inputs = [payload for role, payload in model.inputs if role == 'creative']
    assert len(creative_inputs) == 2 and creative_inputs[0]['evidence']  # still needs metadata, never repeats render
    assert creative_inputs[0]['tools_already_collected'] == ['inspect_render']
    assert not result['partial']
