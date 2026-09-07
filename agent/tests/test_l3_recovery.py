from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config import config
from evaluation import recovery_registry, recovery_service, recovery_store, service as evaluation_service
from evaluation.probes import InvestigationContext, probe_config_drift


CAMPAIGN = "ORD-L3"
INCIDENT = "INC-L3A123"
ACTOR = {"user_id": "owner-1", "anonymous_id": None}


def incident(source="campaign_config_revision"):
    return {
        "incident_id": INCIDENT, "campaign_id": CAMPAIGN,
        "issue_type": "config_drift", "scope": "campaign", "state": "investigating",
        "dataset_revision": 4, "policy_version": "policy-1",
        "evidence": {
            "source": source, "baseline_revision": 0, "current_revision": 1,
            "current_hash": "current-hash",
        },
        "investigation": {
            "bundle_id": "bundle-1", "dataset_revision": 4, "policy_version": "policy-1",
            "assessment": "supported_hypothesis", "ambiguous": False,
            "top_hypothesis": {"hypothesis_id": "config_drift"},
            "probes": [{"probe_id": "config_drift", "status": "anomaly", "source": "derived"}],
        },
    }


def test_config_probe_prefers_live_revision_evidence_over_scenario_signal():
    ctx = InvestigationContext(
        campaign_id=CAMPAIGN,
        active_records=[{"scenario": {"signals": {"configDrift": True}}}],
        incident_evidence={
            "source": "campaign_config_revision", "baseline_revision": 0,
            "baseline_hash": "base", "current_hash": "changed",
            "changes": [{"field": "daily", "before": 10, "after": 15}],
        },
    )
    result = probe_config_drift(ctx)
    assert result["source"] == "derived"
    assert result["finding"] == "field_changed"
    assert result["evidence"]["baseline_reference"] == "campaign_config_revision:0"


@pytest.fixture(autouse=True)
def reset_recovery(monkeypatch):
    recovery_store._mem_proposals.clear()
    recovery_store._mem_events.clear()
    monkeypatch.setattr(recovery_store, "_collections", AsyncMock(return_value=None))
    monkeypatch.setattr(config, "EVALUATION_L3_PROPOSALS_ENABLED", True)
    monkeypatch.setattr(config, "EVALUATION_L3_EXECUTION_ENABLED", True)
    monkeypatch.setattr(config, "EVALUATION_L3_LAB_ENABLED", True)
    monkeypatch.setattr(config, "EVALUATION_L3_WORKFLOWS_ENABLED", True)
    monkeypatch.setattr(config, "EVALUATION_L3_ESCALATIONS_ENABLED", True)
    monkeypatch.setattr(config, "EVALUATION_L3_ACTION_ALLOWLIST", "")
    monkeypatch.setattr(config, "REPORT_INTERNAL_API_KEY", "test-l3-secret")


@pytest.mark.asyncio
async def test_registry_requires_real_drift_and_builds_exact_restore_patch(monkeypatch):
    current = {
        "revision": 1,
        "config": {"objective": "awareness", "budget": 150, "daily": 15,
                   "startDate": "2026-09-01", "endDate": "2026-09-30"},
    }
    target = {
        "revision": 0, "config_hash": "target-hash",
        "provenance": "first_config_revision_before_snapshot",
        "config": {"objective": "awareness", "budget": 100, "daily": 10,
                   "startDate": "2026-09-01", "endDate": "2026-09-30"},
    }
    monkeypatch.setattr(recovery_registry, "get_campaign_config", AsyncMock(return_value=current))
    monkeypatch.setattr(recovery_registry, "get_campaign_config_revision", AsyncMock(return_value=target))
    value = await recovery_registry.build_restore_spec(CAMPAIGN, incident())
    assert value["patch"] == {"budget": 100, "daily": 10}
    assert value["rollback_patch"] == {"budget": 150, "daily": 15}
    assert value["target_config_revision"] == 0

    with pytest.raises(recovery_registry.RecoveryGuardError, match="Scenario-only"):
        await recovery_registry.build_restore_spec(CAMPAIGN, incident("scenario_fact"))

    multi = incident()
    multi["investigation"] = {
        "mode": "multi_agent", "bundle_id": "bundle-2", "dataset_revision": 4,
        "policy_version": "policy-1", "assessment": "supported_hypothesis",
        "cause_status": "supported_hypothesis", "cause_code": "configuration_drift",
        "partial": False, "review": {"contradictions": []},
        "probes": [{"probe_id": "config_drift", "status": "anomaly", "source": "derived"}],
    }
    value = await recovery_registry.build_restore_spec(CAMPAIGN, multi)
    assert value["action_id"] == "restore_config_revision"


@pytest.mark.asyncio
async def test_registry_maps_supported_l2_causes_to_server_owned_actions(monkeypatch):
    monkeypatch.setattr(evaluation_service, "report_request", AsyncMock(return_value={
        "active": {"kind": "scenario"}, "state": {"activeRevision": 4},
    }))
    value = incident("metrics_window")
    value.update({"issue_type": "ctr_regression", "scope": "zone-a"})
    value["investigation"]["top_hypothesis"] = {"hypothesis_id": "creative_format_mismatch"}
    candidates = await recovery_registry.recovery_candidates(CAMPAIGN, value)
    assert [item["candidate_id"] for item in candidates] == ["prepare_creative_replacement"]
    assert candidates[0]["execution_environment"] == "scenario_lab"
    assert candidates[0]["production_executor"] is None

    value["investigation"].update({"assessment": "ambiguous", "ambiguous": True})
    candidates = await recovery_registry.recovery_candidates(CAMPAIGN, value)
    assert [item["candidate_id"] for item in candidates] == ["hold_optimization_and_recheck"]

    monkeypatch.setattr(evaluation_service, "report_request", AsyncMock(return_value={
        "active": {"kind": "scenario"}, "state": {"activeRevision": 5},
    }))
    with pytest.raises(recovery_registry.RecoveryGuardError, match="stale"):
        await recovery_registry.recovery_candidates(CAMPAIGN, value)


def spec():
    return {
        "action_id": "restore_config_revision", "source_config_revision": 1,
        "source_config_hash": "current-hash", "target_config_revision": 0,
        "target_config_hash": "target-hash", "target_provenance": "revision-zero",
        "patch": {"budget": 100}, "rollback_patch": {"budget": 150},
        "changes": [{"field": "budget", "before": 150, "after": 100}],
        "risk": "medium", "expected_impact": "restore",
        "verification": {"kind": "config_equals_target_revision", "target_hash": "target-hash",
                         "resolve_issue_types": ["config_drift"], "note": "config only"},
        "reversible": True,
    }


def workflow_spec():
    return {
        "action_id": "request_measurement_reconciliation", "action_version": 1,
        "label": "Đối soát measurement", "kind": "operator_workflow",
        "supported_issue_types": ["click_tracking_failure"],
        "supported_causes": ["click_measurement_gap"], "risk": "low",
        "instructions": [
            {"step_id": "step-1", "label": "Đối chiếu serving và click", "required": True},
            {"step_id": "step-2", "label": "Chạy Evaluation lại", "required": True},
        ],
        "lab_intervention": "restore_click_measurement", "production_executor": None,
        "cause_code": "click_measurement_gap", "execution_environment": "scenario_lab",
        "evidence_blockers": [],
    }


@pytest.mark.asyncio
async def test_shared_service_approves_executes_and_replays_once(monkeypatch):
    policy = {"enabled": True, "level": "L3", "version": "policy-1"}
    transition_incident = AsyncMock()
    monkeypatch.setattr(recovery_service, "_assert_owner", AsyncMock())
    monkeypatch.setattr(recovery_service, "get_policy", AsyncMock(return_value=policy))
    monkeypatch.setattr(recovery_service, "get_incident", AsyncMock(return_value=incident()))
    monkeypatch.setattr(recovery_service, "build_restore_spec", AsyncMock(return_value=spec()))
    monkeypatch.setattr(recovery_service, "transition_incident", transition_incident)
    source = {"revision": 1, "config": {"budget": 150}}
    target = {"revision": 2, "config": {"budget": 100}}
    monkeypatch.setattr(recovery_service, "config_hash", lambda value: "target-hash" if value["budget"] == 100 else "current-hash")
    monkeypatch.setattr(recovery_service, "get_campaign_config", AsyncMock(side_effect=[source, target]))
    update = AsyncMock(return_value={"revision": 2, "changes": {"budget": {"before": 150, "after": 100}}})
    monkeypatch.setattr(recovery_service, "update_campaign_config", update)

    proposal = await recovery_service.create_restore_proposal(
        CAMPAIGN, INCIDENT, actor=ACTOR, request_id="request-l3-0001",
    )
    assert proposal["status"] == "awaiting_approval"
    result = await recovery_service.approve_and_execute(
        proposal["proposal_id"], actor=ACTOR, code=proposal["approval_code"],
        expected_version=proposal["version"], require_durable=False,
    )
    assert result["status"] == "resolved"
    assert result["result_config_revision"] == 2
    assert update.await_count == 1
    replay = await recovery_service.approve_and_execute(
        proposal["proposal_id"], actor=ACTOR, code=proposal["approval_code"],
        expected_version=proposal["version"], require_durable=False,
    )
    assert replay["status"] == "resolved"
    assert update.await_count == 1
    assert [call.args[2] for call in transition_incident.await_args_list] == [
        "awaiting_approval", "recovering", "verifying", "resolved",
    ]


@pytest.mark.asyncio
async def test_wrong_code_and_missing_durable_store_fail_before_mutation(monkeypatch):
    monkeypatch.setattr(recovery_service, "_assert_owner", AsyncMock())
    monkeypatch.setattr(recovery_service, "get_policy", AsyncMock(return_value={"enabled": True, "level": "L3", "version": "policy-1"}))
    monkeypatch.setattr(recovery_service, "get_incident", AsyncMock(return_value=incident()))
    monkeypatch.setattr(recovery_service, "build_restore_spec", AsyncMock(return_value=spec()))
    monkeypatch.setattr(recovery_service, "transition_incident", AsyncMock())
    update = AsyncMock()
    monkeypatch.setattr(recovery_service, "update_campaign_config", update)
    state = {"revision": 1, "config": {"budget": 150}}
    monkeypatch.setattr(recovery_service, "get_campaign_config", AsyncMock(return_value=state))
    proposal = await recovery_service.create_restore_proposal(
        CAMPAIGN, INCIDENT, actor=ACTOR, request_id="request-l3-0002",
    )
    with pytest.raises(recovery_service.RecoveryError, match="invalid"):
        await recovery_service.approve_and_execute(
            proposal["proposal_id"], actor=ACTOR, code="DEADBEEF",
            expected_version=proposal["version"], require_durable=True,
        )
    with pytest.raises(recovery_service.RecoveryError, match="Durable"):
        await recovery_service.approve_and_execute(
            proposal["proposal_id"], actor=ACTOR, code=proposal["approval_code"],
            expected_version=proposal["version"], require_durable=True,
        )
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_verification_compensates_only_latest_revision(monkeypatch):
    monkeypatch.setattr(recovery_service, "_assert_owner", AsyncMock())
    monkeypatch.setattr(recovery_service, "get_policy", AsyncMock(return_value={"enabled": True, "level": "L3", "version": "policy-1"}))
    monkeypatch.setattr(recovery_service, "get_incident", AsyncMock(return_value=incident()))
    monkeypatch.setattr(recovery_service, "build_restore_spec", AsyncMock(return_value=spec()))
    monkeypatch.setattr(recovery_service, "transition_incident", AsyncMock())
    source = {"revision": 1, "config": {"budget": 150}}
    mismatch = {"revision": 2, "config": {"budget": 110}}
    monkeypatch.setattr(recovery_service, "get_campaign_config", AsyncMock(side_effect=[source, mismatch, mismatch]))
    monkeypatch.setattr(recovery_service, "config_hash", lambda value: {
        150: "current-hash", 110: "mismatch-hash",
    }[value["budget"]])
    update = AsyncMock(side_effect=[{"revision": 2}, {"revision": 3}])
    monkeypatch.setattr(recovery_service, "update_campaign_config", update)
    proposal = await recovery_service.create_restore_proposal(
        CAMPAIGN, INCIDENT, actor=ACTOR, request_id="request-l3-rollback",
    )
    with pytest.raises(recovery_service.RecoveryError, match="verification failed"):
        await recovery_service.approve_and_execute(
            proposal["proposal_id"], actor=ACTOR, code=proposal["approval_code"],
            expected_version=proposal["version"], require_durable=False,
        )
    assert update.await_count == 2
    assert update.await_args_list[1].kwargs["patch"] == {"budget": 150}
    stored = await recovery_store.get_proposal(proposal["proposal_id"])
    assert stored["status"] == "rolled_back"


@pytest.mark.asyncio
async def test_expired_proposal_never_executes(monkeypatch):
    proposal_id = "RP-EXPIRED01"
    code = recovery_service.approval_code(proposal_id)
    value = {
        "proposal_id": proposal_id, "request_key": "expired-request", "campaign_id": CAMPAIGN,
        "incident_id": INCIDENT, "status": "awaiting_approval", "version": 1,
        "approval_nonce_hash": recovery_service._nonce_hash(code),
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    await recovery_store.create_proposal(value)
    monkeypatch.setattr(recovery_service, "_assert_owner", AsyncMock())
    monkeypatch.setattr(recovery_service, "transition_incident", AsyncMock())
    update = AsyncMock()
    monkeypatch.setattr(recovery_service, "update_campaign_config", update)
    with pytest.raises(recovery_service.RecoveryError, match="expired"):
        await recovery_service.approve_and_execute(
            proposal_id, actor=ACTOR, code=code, expected_version=1, require_durable=False,
        )
    update.assert_not_awaited()
    assert (await recovery_store.get_proposal(proposal_id))["status"] == "expired"


def test_persisted_naive_mongo_timestamp_is_normalized_to_utc():
    naive = datetime(2026, 9, 7, 10, 30, 0)
    parsed = recovery_service._parse_time(naive)
    assert parsed.tzinfo == timezone.utc
    assert parsed.isoformat() == "2026-09-07T10:30:00+00:00"


def test_persisted_v1_restore_proposal_reads_as_executable_v2_shape():
    value = recovery_store.public({
        "proposal_id": "RP-LEGACY001", "action_id": "restore_config_revision",
        "status": "awaiting_approval", "approval_nonce_hash": "secret",
    })
    assert value["kind"] == "executable_action"
    assert value["execution_environment"] == "production"
    assert "approval_nonce_hash" not in value


@pytest.mark.asyncio
async def test_workflow_acknowledgement_steps_and_lab_revision_are_separate_from_production(monkeypatch):
    workflow_incident = incident("scenario_fact")
    workflow_incident.update({"issue_type": "click_tracking_failure", "scope": "zone-a"})
    monkeypatch.setattr(recovery_service, "_assert_owner", AsyncMock())
    monkeypatch.setattr(recovery_service, "get_policy", AsyncMock(return_value={
        "enabled": True, "level": "L3", "version": "policy-1",
    }))
    monkeypatch.setattr(recovery_service, "get_incident", AsyncMock(return_value=workflow_incident))
    monkeypatch.setattr(recovery_service, "build_proposal_spec", AsyncMock(return_value=workflow_spec()))
    monkeypatch.setattr(recovery_service, "transition_incident", AsyncMock())
    proposal = await recovery_service.create_recovery_proposal(
        CAMPAIGN, INCIDENT, actor=ACTOR, request_id="workflow-request-1",
    )
    assert proposal["status"] == "awaiting_acknowledgement"
    assert "approval_code" not in proposal
    with pytest.raises(recovery_service.RecoveryError, match="not an executable"):
        await recovery_service.approve_and_execute(
            proposal["proposal_id"], actor=ACTOR, code="IGNORED1",
            expected_version=proposal["version"], require_durable=False,
        )
    acknowledged = await recovery_service.acknowledge_proposal(
        proposal["proposal_id"], actor=ACTOR, expected_version=proposal["version"],
    )
    assert acknowledged["status"] == "waiting_operator"
    first = await recovery_service.complete_workflow_step(
        proposal["proposal_id"], actor=ACTOR, step_id="step-1",
        expected_version=acknowledged["version"],
    )
    ready = await recovery_service.complete_workflow_step(
        proposal["proposal_id"], actor=ACTOR, step_id="step-2",
        expected_version=first["version"],
    )
    assert ready["status"] == "ready_to_verify"

    monkeypatch.setattr(recovery_store, "durable_available", AsyncMock(return_value=True))
    report = AsyncMock(side_effect=[
        {"state": {"activeRevision": 4}, "active": {"kind": "scenario"}},
        {"revision": 5, "parentRevision": 4, "recovery": {"outcome": "success"}},
    ])
    monkeypatch.setattr(evaluation_service, "report_request", report)
    monkeypatch.setattr(evaluation_service, "run_evaluation", AsyncMock(return_value={
        "status": "completed", "incidents": [], "dataset_revision": 5,
    }))
    result = await recovery_service.apply_lab_intervention(
        proposal["proposal_id"], actor=ACTOR, expected_version=ready["version"],
        request_id="lab-request-0001",
    )
    assert result["status"] == "resolved"
    assert result["lab_result"]["parentRevision"] == 4
    body = report.await_args_list[1].args[2]
    assert body["interventionType"] == "restore_click_measurement"
    assert body["actionId"] == "request_measurement_reconciliation"


def test_owner_scoped_recovery_api_uses_shared_service(monkeypatch):
    from evaluation import routes

    value = {
        "proposal_id": "RP-API123456", "campaign_id": CAMPAIGN,
        "incident_id": INCIDENT, "version": 1, "status": "awaiting_approval",
    }
    monkeypatch.setattr(routes, "_assert_campaign_access", AsyncMock(return_value=ACTOR))
    create = AsyncMock(return_value=value)
    detail = AsyncMock(return_value=value)
    approve = AsyncMock(return_value={**value, "status": "resolved"})
    reject = AsyncMock(return_value={**value, "status": "rejected"})
    candidates = AsyncMock(return_value=[])
    acknowledge = AsyncMock(return_value={**value, "status": "waiting_operator"})
    complete = AsyncMock(return_value={**value, "status": "ready_to_verify"})
    monkeypatch.setattr(recovery_service, "create_recovery_proposal", create)
    monkeypatch.setattr(recovery_service, "list_recovery_candidates", candidates)
    monkeypatch.setattr(recovery_service, "get_recovery_proposal", detail)
    monkeypatch.setattr(recovery_service, "approve_and_execute", approve)
    monkeypatch.setattr(recovery_service, "reject_proposal", reject)
    monkeypatch.setattr(recovery_service, "acknowledge_proposal", acknowledge)
    monkeypatch.setattr(recovery_service, "complete_workflow_step", complete)
    app = FastAPI()
    app.include_router(routes.evaluation_router)
    base = f"/evaluation/campaigns/{CAMPAIGN}"
    with TestClient(app) as client:
        assert client.post(
            f"{base}/incidents/{INCIDENT}/recovery-proposals",
            json={"requestId": "route-request-0001"},
        ).status_code == 200
        assert client.get(f"{base}/incidents/{INCIDENT}/recovery-candidates").status_code == 200
        assert client.get(f"{base}/recovery-proposals/{value['proposal_id']}").status_code == 200
        assert client.post(
            f"{base}/recovery-proposals/{value['proposal_id']}/approve",
            json={"approvalCode": "A1B2C3D4", "expectedVersion": 1},
        ).json()["status"] == "resolved"
        assert client.post(
            f"{base}/recovery-proposals/{value['proposal_id']}/reject",
            json={"expectedVersion": 1},
        ).json()["status"] == "rejected"
        assert client.post(
            f"{base}/recovery-proposals/{value['proposal_id']}/acknowledge",
            json={"expectedVersion": 1},
        ).json()["status"] == "waiting_operator"
        assert client.post(
            f"{base}/recovery-proposals/{value['proposal_id']}/steps/step-1/complete",
            json={"expectedVersion": 1, "note": "done"},
        ).json()["status"] == "ready_to_verify"
    create.assert_awaited_once_with(
        CAMPAIGN, INCIDENT, actor=ACTOR, request_id="route-request-0001",
        candidate_id=None, channel="web",
    )
    approve.assert_awaited_once_with(
        value["proposal_id"], actor=ACTOR, code="A1B2C3D4", expected_version=1, channel="web",
    )
