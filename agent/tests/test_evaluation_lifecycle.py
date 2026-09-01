"""Real JS scenarios -> L1/store/L2/API, with external I/O mocked."""
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from evaluation import store, service, investigator, routes
from tests.test_l2_investigation import apply_scenario, baseline_records, ORDER, ZONE_MAP, BASELINE_INPUT

CAMPAIGN = 'ORD-2026-001'
PRESETS = {
    'healthy_baseline': set(),
    'low_impression_zone': {'delivery_drop'},
    'low_ctr': {'ctr_regression'},
    'creative_failure': {'creative_failure'},
    'click_tracking_failure': {'click_tracking_failure'},
    'config_drift': {'config_drift'},
    'poor_placement': {'ctr_regression'},
    'tracking_delay': {'data_quality'},
    'multiple_issues': {'delivery_drop', 'ctr_regression'},
    'recovery_success': set(),
    'recovery_ineffective': {'delivery_drop'},
}


@pytest.fixture
def env(monkeypatch):
    for name in ['_mem_policies', '_mem_runs', '_mem_incidents', '_mem_investigations']:
        monkeypatch.setattr(store, name, {})
    monkeypatch.setattr(store, '_collections', AsyncMock(return_value=None))
    baseline = baseline_records()
    dataset = {'state': {'activeRevision': 1},
               'baseline': {'records': baseline, 'input': BASELINE_INPUT},
               'active': {'records': deepcopy(baseline), 'input': BASELINE_INPUT}}

    async def request(method, path, json=None):
        assert method == 'GET', 'L1/L2 must not mutate report facts'
        return deepcopy(dataset)

    monkeypatch.setattr(service, 'report_request', AsyncMock(side_effect=request))
    monkeypatch.setattr(investigator, '_load_order', AsyncMock(return_value=ORDER))
    monkeypatch.setattr(investigator, '_load_zone_map', AsyncMock(return_value=ZONE_MAP))
    import zalo_incidents
    notify = AsyncMock(return_value=0)
    monkeypatch.setattr(zalo_incidents, 'notify_incidents', notify)
    return dataset, notify


def scenario(dataset, preset, revision):
    dataset['state']['activeRevision'] = revision
    dataset['active']['records'] = apply_scenario(dataset['baseline']['records'], preset)


@pytest.mark.asyncio
@pytest.mark.parametrize('preset,expected', PRESETS.items())
async def test_js_preset_to_actual_l1_l2_pipeline(env, preset, expected):
    dataset, notify = env
    scenario(dataset, preset, 2)
    await store.save_policy(CAMPAIGN, {'level': 'L2'})
    before = deepcopy(dataset)
    result = await service.run_evaluation(CAMPAIGN, trigger='test')
    assert result['status'] == 'completed'
    assert expected <= {i['issue_type'] for i in result['incidents']}
    if not expected:
        assert result['incidents'] == []
    for incident in result['incidents']:
        bundle = incident['investigation']
        assert bundle['supported'] and bundle['dataset_revision'] == 2
        assert bundle['mutations'] == []
        assert bundle['score_semantics'] == 'relative_rule_support_not_probability'
        assert len(await store.investigation_history(CAMPAIGN, incident['incident_id'])) == 1
        assert all(not option['available'] for option in bundle['recovery_options'])
        assert bundle['recovery_context']['verification'] == 'not_verified'
    assert dataset == before
    notify.assert_awaited_once()
    assert (await service.run_evaluation(CAMPAIGN))['no_op'] is True
    assert notify.await_count == 1


@pytest.mark.asyncio
async def test_policy_change_invalidates_cached_l1_run(env):
    dataset, _ = env
    scenario(dataset, 'low_ctr', 2)
    first = await service.run_evaluation(CAMPAIGN)
    assert all(not i.get('investigation') for i in first['incidents'])
    old = await store.get_policy(CAMPAIGN)
    updated = await store.save_policy(CAMPAIGN, {'level': 'L2'})
    assert old['version'] != updated['version']
    again = await service.run_evaluation(CAMPAIGN)
    assert not again['no_op'] and again['investigated_count'] > 0
    unchanged = await store.save_policy(CAMPAIGN, {'level': 'L2'})
    assert unchanged['version'] == updated['version']


@pytest.mark.asyncio
async def test_recurrence_reopens_same_incident_and_quality_gap_does_not_resolve(env):
    dataset, _ = env
    scenario(dataset, 'low_ctr', 2)
    first = await service.run_evaluation(CAMPAIGN)
    incident_id = next(i['incident_id'] for i in first['incidents'] if i['issue_type'] == 'ctr_regression')
    dataset['state']['activeRevision'] = 3
    dataset['active']['records'] = []
    await service.run_evaluation(CAMPAIGN)
    assert (await store.get_incident(CAMPAIGN, incident_id))['state'] == 'open'
    scenario(dataset, 'healthy_baseline', 4)
    await service.run_evaluation(CAMPAIGN)
    assert (await store.get_incident(CAMPAIGN, incident_id))['state'] == 'resolved'
    scenario(dataset, 'low_ctr', 5)
    await service.run_evaluation(CAMPAIGN)
    assert (await store.get_incident(CAMPAIGN, incident_id))['state'] == 'open'
    await store.transition_incident(CAMPAIGN, incident_id, 'dismissed')
    scenario(dataset, 'low_ctr', 6)
    await service.run_evaluation(CAMPAIGN)
    assert (await store.get_incident(CAMPAIGN, incident_id))['state'] == 'dismissed'


@pytest.mark.asyncio
async def test_notification_failure_is_retryable_not_cached_as_complete(env):
    dataset, notify = env
    scenario(dataset, 'low_ctr', 2)
    notify.side_effect = RuntimeError('outbox temporarily unavailable')
    first = await service.run_evaluation(CAMPAIGN)
    assert first['status'] == 'retryable'
    notify.side_effect = None
    second = await service.run_evaluation(CAMPAIGN)
    assert second['status'] == 'completed' and not second['no_op']
    assert notify.await_count == 2
    policy = await store.get_policy(CAMPAIGN)
    assert await store.find_existing_run(CAMPAIGN, 2, policy['version'])


@pytest.mark.asyncio
async def test_policy_and_revision_guards_before_manual_l2_writes(env):
    dataset, _ = env
    scenario(dataset, 'low_ctr', 2)
    first = await service.run_evaluation(CAMPAIGN)
    incident = first['incidents'][0]
    with pytest.raises(PermissionError):
        await investigator.investigate_incident(CAMPAIGN, incident)
    await store.save_policy(CAMPAIGN, {'level': 'L2'})
    scenario(dataset, 'low_ctr', 3)
    with pytest.raises(ValueError, match='stale'):
        await investigator.investigate_incident(CAMPAIGN, incident)
    assert not store._mem_investigations
    with pytest.raises(KeyError):
        await store.transition_incident('OTHER', incident['incident_id'], 'dismissed')
    assert (await store.get_incident(CAMPAIGN, incident['incident_id']))['state'] == 'open'


@pytest.mark.asyncio
async def test_bundle_history_survives_new_revision_and_stale_bundle_is_hidden(env):
    dataset, _ = env
    scenario(dataset, 'low_ctr', 2)
    await store.save_policy(CAMPAIGN, {'level': 'L2'})
    first = await service.run_evaluation(CAMPAIGN)
    incident = first['incidents'][0]
    old_bundle = incident['investigation']
    await store.save_policy(CAMPAIGN, {'level': 'L1'})
    scenario(dataset, 'low_ctr', 3)
    await service.run_evaluation(CAMPAIGN)
    refreshed = await store.get_incident(CAMPAIGN, incident['incident_id'])
    assert refreshed['investigation'] is None
    with pytest.raises(ValueError):
        await store.attach_investigation(CAMPAIGN, incident['incident_id'], old_bundle)
    assert len(await store.investigation_history(CAMPAIGN, incident['incident_id'])) == 1


@pytest.mark.asyncio
async def test_campaign_lease_rejects_overlap_and_releases_on_error(env):
    dataset, _ = env
    token = await store.acquire_campaign_lease(CAMPAIGN)
    with pytest.raises(service.ReportServiceError) as error:
        await service.run_evaluation(CAMPAIGN)
    assert error.value.status == 409
    await store.release_campaign_lease(CAMPAIGN, token)
    with pytest.raises(service.ReportServiceError):
        await service.run_evaluation(CAMPAIGN, expected_revision=999)
    assert await store.acquire_campaign_lease(CAMPAIGN) is not None


@pytest.mark.asyncio
async def test_incomplete_sources_and_stale_write_are_explicit(env, monkeypatch):
    dataset, _ = env
    scenario(dataset, 'low_ctr', 2)
    await store.save_policy(CAMPAIGN, {'level': 'L2'})
    first = await service.run_evaluation(CAMPAIGN)
    incident = first['incidents'][0]
    history_count = len(store._mem_investigations)
    stale = deepcopy(dataset)
    stale['state']['activeRevision'] = 3
    monkeypatch.setattr(investigator, '_load_dataset', AsyncMock(return_value=stale))
    with pytest.raises(ValueError, match='changed during'):
        await investigator.investigate_incident(CAMPAIGN, incident, dataset=dataset)
    assert len(store._mem_investigations) == history_count
    # A bundle whose every source is missing must not manufacture a winning cause.
    from evaluation.probes import InvestigationContext
    from evaluation.playbooks import supported_issue_types
    assert set(supported_issue_types()) == {
        'delivery_drop', 'ctr_regression', 'creative_failure', 'data_quality',
        'click_tracking_failure', 'config_drift', 'pacing_error', 'robust_trend_drop'}
    empty = InvestigationContext(campaign_id=CAMPAIGN, scope=incident['scope'])
    bundle = investigator.build_bundle(incident, empty, trigger='test', dataset_revision=2)
    assert bundle['assessment'] == 'insufficient_evidence'
    assert bundle['top_hypothesis'] is None and bundle['recovery_options'] == []


@pytest.mark.asyncio
async def test_directory_summary_is_batch_read_only_and_does_not_enable_monitoring(env):
    dataset, _ = env
    assert (await store.campaign_health_summaries(['UNSEEN']))['UNSEEN']['status'] == 'not_evaluated'
    assert not store._mem_policies
    scenario(dataset, 'low_ctr', 2)
    result = await service.run_evaluation(CAMPAIGN)
    summary = (await store.campaign_health_summaries([CAMPAIGN]))[CAMPAIGN]
    assert summary['open_count'] == len(result['incidents'])
    assert summary['status'] == 'bad'


def test_owned_api_and_disabled_l3_actions(env, monkeypatch):
    async def actor(account, anonymous, require_any=True):
        if not account:
            raise PermissionError('sign in')
        return {'user_id': account}
    async def references(value):
        return [{'order_id': CAMPAIGN}] if value['user_id'] == 'owner' else []
    monkeypatch.setattr(routes, 'resolve_actor', actor)
    monkeypatch.setattr(routes, 'list_owned_campaign_references', references)
    app = FastAPI()
    app.include_router(routes.evaluation_router, prefix='/api/agent')
    with TestClient(app) as client:
        url = f'/api/agent/evaluation/campaigns/{CAMPAIGN}'
        assert client.get(url).status_code == 401
        client.cookies.set('aa_account', 'stranger')
        assert client.get(url).status_code == 404
        assert client.post(url + '/scenarios/apply', json={
            'presetId': 'healthy_baseline', 'requestId': 'request_123', 'expectedRevision': 1,
        }).status_code == 404
        client.cookies.set('aa_account', 'owner')
        assert client.get(url).status_code == 200
        for action in ['prepare_recovery', 'start_recovery', 'verify', 'resolve']:
            assert client.post(url + '/incidents/INC-TEST/actions', json={'action': action}).status_code == 409
        assert client.post(url + '/scenarios/apply', json={'presetId': 'low_ctr'}).status_code == 422
    service.report_request.assert_not_awaited()


def test_committed_scenario_reports_evaluation_retry_separately(env, monkeypatch):
    monkeypatch.setattr(routes, '_assert_campaign_access', AsyncMock(return_value={'user_id': 'owner'}))
    report = AsyncMock(return_value={'revision': 2, 'replayed': False})
    monkeypatch.setattr(routes, 'report_request', report)
    monkeypatch.setattr(routes, 'run_evaluation', AsyncMock(side_effect=RuntimeError('worker busy')))
    app = FastAPI()
    app.include_router(routes.evaluation_router)
    with TestClient(app) as client:
        result = client.post(f'/evaluation/campaigns/{CAMPAIGN}/scenarios/apply', json={
            'presetId': 'low_ctr', 'requestId': 'request_123', 'expectedRevision': 1,
        })
    assert result.status_code == 200
    assert result.json()['scenario']['revision'] == 2
    assert result.json()['evaluation']['status'] == 'retryable'
    assert report.call_args.args[2]['createdBy'] == 'owner'
