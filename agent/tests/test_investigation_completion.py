"""Server-enforced terminal turns, safe repair and symptom/cause separation."""
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from evaluation.decision_contract import DecisionError, ModelResponseError, validated_finish
from evaluation.evidence_tools import ROLE_TOOLS
from evaluation.multi_agent import orchestrate
from tests.test_multi_agent_investigation import context, scenario, incident, job, Journal, decision, ScriptedModel


def render_evidence(blocked=True):
    return {'probe_id': 'inspect_render', 'source': 'isolated_browser_observation',
            'status': 'anomaly' if blocked else 'ok',
            'finding': 'hit_target_mismatch' if blocked else 'render_observed',
            'evidence': {'visible': True, 'points': [{'reaches_creative': not blocked}],
                         'local_clicks_before': 0, 'local_clicks_after': 0 if blocked else 1}}


def finish(refs, **values):
    return {**decision(refs=refs), **values}


@pytest.mark.asyncio
async def test_three_tools_then_server_removes_tools_for_reserved_final_turn():
    data, journal, seen = scenario(), Journal(), []
    async def hungry(role, payload, *, tools, image=None):
        seen.append((role, list(tools), payload['remaining_tool_calls'] if role!='coordinator' else None))
        if role != 'coordinator' and tools:
            return decision('tool', next(iter(tools)))
        return finish([e['evidence_id'] for e in payload['evidence']])
    bundle = await orchestrate(job(), incident(), context(data), data['runtimeFixture'],
        progress=journal, guard=AsyncMock(), model=hungry, renderer=AsyncMock(return_value=render_evidence()))
    task = bundle['tasks']['performance']
    assert len(task['tool_calls']) == 3 and task['status'] == 'completed'
    assert [s for s in seen if s[0]=='performance'][-1][1:] == ([], 0)
    assert journal.value['model_calls'] == 12 and not bundle['partial']
    assert bundle['assessment'] == 'ambiguous'  # Symptom-only findings are not causal.


@pytest.mark.asyncio
async def test_one_invalid_citation_repair_preserves_evidence_without_repeating_tools():
    data, journal = scenario(), Journal()
    normal, errors = ScriptedModel(), 0
    async def model(role, payload, **kwargs):
        nonlocal errors
        if role == 'performance' and payload['evidence'] and errors == 0:
            errors += 1
            return decision(refs=['secret-invented-citation'])
        if role == 'performance' and payload['evidence']:
            assert payload['protocol_correction']['code'] == 'unknown_evidence'
            assert 'secret-invented' not in str(payload)
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(job(), incident(), context(data), data['runtimeFixture'],
        progress=journal, guard=AsyncMock(), model=model, renderer=AsyncMock(return_value=render_evidence()))
    task = bundle['tasks']['performance']
    assert task['status'] == 'completed' and task['tool_calls'] == ['metrics_window']
    assert task['repairs_used'] == 1 and task['validation_errors'][0]['code'] == 'unknown_evidence'
    assert journal.value['model_calls'] == 9 and 'secret-invented' not in str(bundle)


@pytest.mark.asyncio
async def test_persistent_validation_failure_has_one_repair_and_specific_terminal_code():
    data, normal = scenario(), ScriptedModel()
    async def broken(role, payload, **kwargs):
        if role == 'performance' and payload['evidence']:
            return decision(refs=['not-observed'])
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(job(), incident(), context(data), data['runtimeFixture'],
        progress=Journal(), guard=AsyncMock(), model=broken, renderer=AsyncMock(return_value=render_evidence()))
    task = bundle['tasks']['performance']
    assert task['status']=='failed' and task['error_code']=='unknown_evidence'
    assert [e['repair_requested'] for e in task['validation_errors']] == [True, False]
    assert bundle['partial'] and bundle['cause_status'] != 'supported_hypothesis'


@pytest.mark.asyncio
async def test_arbitrary_tool_is_not_repaired_or_executed():
    data, normal = scenario(), ScriptedModel()
    async def bad(role, payload, **kwargs):
        if role=='performance': return decision('tool', 'delete_campaign')
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(job(), incident(), context(data), None,
        progress=Journal(), guard=AsyncMock(), model=bad)
    task=bundle['tasks']['performance']
    assert task['error_code']=='unauthorized_tool' and task['repairs_used']==0 and task['tool_calls']==[]
    assert bundle['mutations']==[]


@pytest.mark.asyncio
async def test_repeated_tool_selection_repairs_once_with_existing_evidence():
    data, normal = scenario(), ScriptedModel()
    async def model(role, payload, **kwargs):
        if role=='performance' and payload['evidence'] and 'protocol_correction' not in payload:
            return decision('tool', 'metrics_window')
        return await normal(role, payload, **kwargs)
    bundle=await orchestrate(job(), incident(), context(data), None, progress=Journal(), guard=AsyncMock(), model=model)
    task=bundle['tasks']['performance']
    assert task['status']=='completed' and task['tool_calls']==['metrics_window']
    assert task['validation_errors'][0]['code']=='duplicate_tool'


@pytest.mark.asyncio
async def test_final_phase_cannot_dispatch_a_fourth_tool_even_after_repair():
    data, normal = scenario(), ScriptedModel()
    async def model(role, payload, *, tools, image=None):
        if role=='performance':
            return decision('tool', next(iter(tools)) if tools else 'spend_pacing')
        return await normal(role, payload, tools=tools, image=image)
    bundle=await orchestrate(job(), incident(), context(data), None, progress=Journal(), guard=AsyncMock(), model=model)
    task=bundle['tasks']['performance']
    assert task['status']=='failed' and task['error_code']=='finish_required'
    assert len(task['tool_calls'])==3 and task['repairs_used']==1


def test_symptom_evidence_never_supports_a_cause_or_publisher_claim():
    evidence={'metric': {'probe_id':'metrics_window','status':'anomaly','source':'report_dataset'}}
    result=validated_finish(finish(['metric']), evidence)
    assert result['assessment']=='ambiguous' and result['cause_status']=='unresolved'
    assert result['claim_scope']=='unknown' and result['limitations']
    with pytest.raises(DecisionError) as error:
        validated_finish(finish(['metric'], cause_code='click_obstruction'), evidence)
    assert error.value.code=='unsupported_cause'


def test_matching_independent_observation_supports_only_local_document_hypothesis():
    evidence={'render': render_evidence()}
    result=validated_finish(finish(['render'], cause_code='click_obstruction'), evidence)
    assert result['assessment']=='supported_hypothesis' and result['claim_scope']=='isolated_document'
    assert 'publisher' in result['limitations'][0]
    for wrong in [render_evidence(False), {**render_evidence(), 'source':'scenario_fact'}]:
        with pytest.raises(DecisionError, match='independently'):
            validated_finish(finish(['render'], cause_code='click_obstruction'), {'render':wrong})


def test_opposing_evidence_must_be_owned_and_prevents_supported_assessment():
    evidence={'render':render_evidence(), 'other':render_evidence(False)}
    result=validated_finish(finish(['render'], cause_code='click_obstruction', counter_evidence_ids=['other']), evidence)
    assert result['assessment']=='ambiguous' and result['cause_status']=='unresolved'
    with pytest.raises(DecisionError) as error:
        validated_finish(finish(['render'], counter_evidence_ids=['foreign']), evidence)
    assert error.value.code=='unknown_evidence'


def test_size_mismatch_is_metadata_evidence_not_ctr_causality():
    evidence={'size': {'probe_id':'creative_compatibility','finding':'size_mismatch','source':'derived','status':'anomaly'}}
    result=validated_finish(finish(['size'], cause_code='creative_contract_mismatch'), evidence)
    assert result['claim_scope']=='creative_metadata' and 'CTR' in result['limitations'][0]


@pytest.mark.asyncio
async def test_coordinator_has_one_repair_and_cannot_exceed_two_delegations():
    data, journal, repaired = scenario(), Journal(), False
    async def model(role, payload, *, tools, image=None):
        nonlocal repaired
        if role=='coordinator':
            if tools: return decision('delegate', next(iter(tools)))
            if not repaired:
                repaired=True
                return decision('delegate','creative')
        elif tools:
            return decision('tool',next(iter(tools)))
        return finish([e['evidence_id'] for e in payload['evidence']])
    limited = {**incident(), 'issue_type': 'data_quality'}
    bundle=await orchestrate(job(), limited, context(data), data['runtimeFixture'],
        progress=journal, guard=AsyncMock(), model=model, renderer=AsyncMock(return_value=render_evidence()))
    task=bundle['tasks']['coordinator']
    assert task['status']=='completed' and len(task['tool_calls'])==2 and task['repairs_used']==1
    assert journal.value['model_calls'] <= 24


@pytest.mark.asyncio
async def test_transient_timeout_retries_decision_once_without_repeating_collected_tools():
    data, normal, failed = scenario(), ScriptedModel(), False
    async def model(role, payload, **kwargs):
        nonlocal failed
        if role == 'performance' and payload['evidence'] and not failed:
            failed = True
            raise ModelResponseError('model_timeout')
        return await normal(role, payload, **kwargs)
    journal = Journal()
    bundle = await orchestrate(job(), incident(), context(data), data['runtimeFixture'],
        progress=journal, guard=AsyncMock(), model=model, renderer=AsyncMock(return_value=render_evidence()))
    task = bundle['tasks']['performance']
    assert task['status'] == 'completed' and task['tool_calls'] == ['metrics_window']
    assert task['repairs_used'] == 1 and task['validation_errors'][0]['kind'] == 'provider'
    assert journal.value['model_calls'] == 9


@pytest.mark.asyncio
async def test_timeout_and_protocol_failure_share_one_retry_budget():
    data, normal = scenario(), ScriptedModel()
    async def model(role, payload, **kwargs):
        if role == 'performance':
            if 'protocol_correction' not in payload:
                raise ModelResponseError('model_timeout')
            return decision(refs=['invented'])
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(job(), incident(), context(data), None,
        progress=Journal(), guard=AsyncMock(), model=model)
    task = bundle['tasks']['performance']
    assert task['status'] == 'failed' and task['error_code'] == 'required_evidence'
    assert task['repairs_used'] == 1
    assert [e['repair_requested'] for e in task['validation_errors']] == [True, False]


@pytest.mark.asyncio
async def test_early_creative_finish_must_collect_render_even_after_metadata():
    data, normal = scenario(), ScriptedModel()
    async def model(role, payload, **kwargs):
        if role == 'creative':
            if not payload['evidence']:
                return decision('tool', 'creative_compatibility')
            if 'inspect_render' not in payload['tools_already_collected']:
                if 'protocol_correction' in payload:
                    assert payload['protocol_correction']['code'] == 'required_evidence'
                    return decision('tool', 'inspect_render')
                return decision(refs=[e['evidence_id'] for e in payload['evidence']])
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(job(), incident(), context(data), None,
        progress=Journal(), guard=AsyncMock(), model=model)
    task = bundle['tasks']['creative']
    assert task['status'] == 'completed'
    assert task['execution_status'] == 'completed'
    assert task['evidence_status'] == 'insufficient'  # Missing fixture is explicit, never healthy.
    assert task['tool_calls'] == ['creative_compatibility', 'inspect_render']
    assert task['repairs_used'] == 1


@pytest.mark.asyncio
async def test_unavailable_probe_completes_execution_but_keeps_evidence_gap_visible():
    data = scenario()
    bundle = await orchestrate(job(), incident(), context(data), None,
        progress=Journal(), guard=AsyncMock(), model=ScriptedModel())
    creative = bundle['tasks']['creative']
    assert creative['execution_status'] == 'completed'
    assert creative['evidence_status'] == 'insufficient'
    assert bundle['completion']['execution_complete']
    assert bundle['completion']['unavailable_probes'] >= 1
    assert bundle['completion']['roles_with_insufficient_evidence'] >= 1
    assert not bundle['partial']


@pytest.mark.asyncio
async def test_persistent_coordinator_protocol_error_uses_safe_terminal_fallback():
    data, normal = scenario(), ScriptedModel()
    async def invalid_coordinator(role, payload, **kwargs):
        if role == 'coordinator':
            result = decision(refs=[e['evidence_id'] for e in payload['evidence']])
            result['cause_code'] = 'click_obstruction'
            result['evidence_links'] = [{
                'hypothesis_id': 'configuration_drift',
                'evidence_id': payload['evidence'][0]['evidence_id'],
                'relation': 'supports',
            }]
            return result
        return await normal(role, payload, **kwargs)
    bundle = await orchestrate(job(), incident(), context(data), data['runtimeFixture'],
        progress=Journal(), guard=AsyncMock(), model=invalid_coordinator,
        renderer=AsyncMock(return_value=render_evidence()))
    coordinator = bundle['tasks']['coordinator']
    assert coordinator['status'] == coordinator['execution_status'] == 'completed'
    assert coordinator['fallback']['kind'] == 'deterministic_safe_summary'
    assert coordinator['fallback']['reason'] == 'invalid_evidence_relation'
    assert bundle['assessment'] == 'ambiguous'
    assert bundle['cause_code'] == 'none'
    assert bundle['recovery_options'] == [] and not bundle['recovery_eligibility']['eligible']


@pytest.mark.asyncio
async def test_no_catalog_alternative_is_completed_observation_not_worker_failure():
    data = scenario('poor_placement')
    ctx = context(data)
    ctx.zone_map = deepcopy(ctx.zone_map)
    ctx.zone_map.pop('Znews_Family_Masthead')
    bundle = await orchestrate(job(), incident(), ctx, data['runtimeFixture'],
        progress=Journal(), guard=AsyncMock(), model=ScriptedModel(),
        renderer=AsyncMock(return_value=render_evidence(False)))
    placement = bundle['tasks']['placement']
    probe = next(item for item in bundle['probes'] if item['probe_id'] == 'placement_benchmark')
    assert placement['status'] == placement['execution_status'] == 'completed'
    assert placement['evidence_status'] == 'unavailable'
    assert probe['status'] == 'unavailable' and probe['finding'] == 'no_alternatives'
    assert bundle['completion']['execution_complete'] and not bundle['partial']
    assert not bundle['recovery_eligibility']['eligible']


@pytest.mark.asyncio
async def test_compatible_catalog_alternative_completes_with_sufficient_evidence():
    data = scenario('poor_placement')
    bundle = await orchestrate(job(), incident(), context(data), data['runtimeFixture'],
        progress=Journal(), guard=AsyncMock(), model=ScriptedModel(),
        renderer=AsyncMock(return_value=render_evidence(False)))
    placement = bundle['tasks']['placement']
    probe = next(item for item in bundle['probes'] if item['probe_id'] == 'placement_benchmark')
    assert placement['execution_status'] == 'completed'
    assert placement['evidence_status'] == 'sufficient'
    assert probe['finding'] == 'below_benchmark_with_compatible_alternatives'
    assert probe['evidence']['booking_availability_verified'] is False
    assert not bundle['recovery_eligibility']['eligible']


@pytest.mark.asyncio
async def test_clear_render_cannot_finish_without_metadata_and_last_slots_are_reserved():
    data, normal = scenario(), ScriptedModel()
    async def model(role, payload, *, tools, image=None):
        if role == 'creative':
            if not payload['evidence']:
                return decision('tool', 'click_telemetry')
            if 'inspect_render' not in payload['tools_already_collected']:
                assert set(tools) == {'inspect_render', 'creative_compatibility'}
                return decision('tool', 'inspect_render')
            if 'creative_compatibility' not in payload['tools_already_collected']:
                assert set(tools) == {'creative_compatibility'}
                if 'protocol_correction' not in payload:
                    return decision(refs=[e['evidence_id'] for e in payload['evidence']])
                assert payload['protocol_correction']['code'] == 'required_evidence'
                return decision('tool', 'creative_compatibility')
        return await normal(role, payload, tools=tools, image=image)
    bundle = await orchestrate(job(), incident(), context(data), data['runtimeFixture'], progress=Journal(),
        guard=AsyncMock(), model=model, renderer=AsyncMock(return_value=render_evidence(False)))
    task = bundle['tasks']['creative']
    assert task['status'] == 'completed'
    assert task['tool_calls'] == ['click_telemetry', 'inspect_render', 'creative_compatibility']
    assert task['repairs_used'] == 1
