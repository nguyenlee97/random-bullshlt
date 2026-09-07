"""Shared Web/Zalo service for guarded polymorphic L3 proposals."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from campaign_config import config_hash, get_campaign_config, update_campaign_config
from config import config
from evaluation.recovery_contracts import SCHEMA_VERSION
from evaluation.recovery_registry import (
    RecoveryGuardError, build_proposal_spec, build_restore_spec, recovery_candidates,
)
from evaluation import recovery_store
from evaluation.store import get_incident, get_policy, transition_incident


class RecoveryError(RuntimeError):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _actor(value: dict) -> dict:
    return {
        "user_id": value.get("user_id"),
        "anonymous_id": None if value.get("user_id") else value.get("anonymous_id"),
    }


async def _assert_owner(campaign_id: str, actor: dict) -> None:
    from campaign_directory import get_campaign_directory_entry
    if not await get_campaign_directory_entry(actor, campaign_id):
        raise RecoveryError("Campaign not found", 404)


def _secret() -> bytes:
    value = config.REPORT_INTERNAL_API_KEY or config.ZALO_OA_SECRET
    return str(value or "").encode()


def approval_code(proposal_id: str) -> str:
    secret = _secret()
    if not secret:
        raise RecoveryError("L3 approval secret is not configured", 503)
    return hmac.new(secret, proposal_id.encode(), hashlib.sha256).hexdigest()[:8].upper()


def _nonce_hash(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def _event(proposal_id: str, kind: str, **details) -> dict:
    return {
        "event_id": f"RCE-{uuid.uuid4().hex[:14].upper()}",
        "proposal_id": proposal_id, "kind": kind, **details,
    }


def _parse_time(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    # PyMongo returns naive UTC datetimes unless the client is configured with
    # tz_aware=True. Normalize both persisted and serialized timestamps before
    # comparing them with the service's timezone-aware clock.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def _proposal_context(campaign_id: str, incident_id: str, *, actor: dict) -> tuple[dict, dict]:
    if not config.EVALUATION_L3_PROPOSALS_ENABLED:
        raise RecoveryError("L3 proposals are disabled", 409)
    await _assert_owner(campaign_id, actor)
    policy = await get_policy(campaign_id)
    if not policy.get("enabled") or policy.get("level") != "L3":
        raise RecoveryError("Campaign policy must enable L3", 409)
    incident = await get_incident(campaign_id, incident_id)
    if not incident:
        raise RecoveryError("Incident not found", 404)
    if incident.get("state") in {"resolved", "dismissed", "false_positive", "expired"}:
        raise RecoveryError("Incident is closed", 409)
    return policy, incident


def _proposal_status(spec: dict) -> str:
    return "awaiting_approval" if spec.get("kind") == "executable_action" else "awaiting_acknowledgement"


def _action_enabled(spec: dict) -> bool:
    allowed = {item.strip() for item in str(config.EVALUATION_L3_ACTION_ALLOWLIST or "").split(",") if item.strip()}
    if allowed and spec.get("action_id") not in allowed:
        return False
    if spec.get("kind") == "operator_workflow" and not config.EVALUATION_L3_WORKFLOWS_ENABLED:
        return False
    if spec.get("kind") == "engineering_escalation" and not config.EVALUATION_L3_ESCALATIONS_ENABLED:
        return False
    return True


def _assert_action_enabled(spec: dict) -> None:
    if not _action_enabled(spec):
        raise RecoveryError("Recovery action is not enabled in this runtime", 409)


async def _create_from_spec(campaign_id: str, incident_id: str, *, actor: dict,
                            request_id: str, channel: str, policy: dict,
                            incident: dict, spec: dict) -> dict:
    if len(str(request_id or "").strip()) < 8:
        raise RecoveryError("request_id must contain at least 8 characters", 422)
    _assert_action_enabled(spec)
    try:
        kind = spec["kind"]
        action_id = spec["action_id"]
    except KeyError as exc:
        raise RecoveryError("Recovery action contract is incomplete", 500) from exc
    clean_request = str(request_id).strip()
    request_key = hashlib.sha256(
        f"{campaign_id}|{incident_id}|{action_id}|{clean_request}".encode()
    ).hexdigest()
    proposal_id = f"RP-{uuid.uuid4().hex[:10].upper()}"
    now = _now()
    bundle = incident.get("investigation") or {}
    status = _proposal_status(spec)
    ttl = timedelta(minutes=15) if kind == "executable_action" else (
        timedelta(days=1) if kind == "operator_workflow" else timedelta(days=7)
    )
    proposal = {
        "schema_version": SCHEMA_VERSION,
        "proposal_id": proposal_id, "request_key": request_key,
        "campaign_id": campaign_id, "incident_id": incident_id,
        "issue_type": incident.get("issue_type"), "scope": incident.get("scope"),
        "dataset_revision": incident.get("dataset_revision"),
        "policy_version": incident.get("policy_version"),
        "bundle_id": bundle.get("bundle_id"),
        **spec, "status": status, "active": True, "version": 1,
        "steps": [{**step, "status": "pending"} for step in spec.get("instructions") or []],
        "created_by": _actor(actor), "channel": channel,
        "created_at": now, "updated_at": now,
        "expires_at": now + ttl,
        "expiry_policy": "15_minutes" if kind == "executable_action" else (
            "24_hours" if kind == "operator_workflow" else "7_days"
        ),
    }
    if kind == "executable_action":
        proposal["approval_nonce_hash"] = _nonce_hash(approval_code(proposal_id))
    await recovery_store.supersede_active(campaign_id, incident_id, request_key)
    stored, created = await recovery_store.create_proposal(proposal)
    if created:
        await recovery_store.append_event(_event(
            proposal_id, "proposal_created", actor=_actor(actor), channel=channel,
            dataset_revision=incident.get("dataset_revision"),
        ))
        # Existing incident state names are retained for compatibility. A
        # workflow/escalation is still an investigation until acknowledged.
        target = "awaiting_approval" if status == "awaiting_approval" else "investigating"
        await transition_incident(campaign_id, incident_id, target,
                                  f"Recovery proposal {proposal_id} {status}")
    result = recovery_store.public(stored)
    if stored.get("kind") == "executable_action" and stored.get("status") == "awaiting_approval":
        result["approval_code"] = approval_code(stored["proposal_id"])
    result["created"] = created
    return result


async def list_recovery_candidates(campaign_id: str, incident_id: str, *, actor: dict) -> list[dict]:
    _policy, incident = await _proposal_context(campaign_id, incident_id, actor=actor)
    try:
        return [item for item in await recovery_candidates(campaign_id, incident)
                if _action_enabled(item)]
    except RecoveryGuardError as exc:
        raise RecoveryError(str(exc), 409) from exc


async def create_recovery_proposal(campaign_id: str, incident_id: str, *,
                                   actor: dict, request_id: str,
                                   candidate_id: str | None = None,
                                   channel: str = "web") -> dict:
    policy, incident = await _proposal_context(campaign_id, incident_id, actor=actor)
    try:
        spec = await build_proposal_spec(campaign_id, incident, candidate_id)
    except RecoveryGuardError as exc:
        raise RecoveryError(str(exc), 409) from exc
    return await _create_from_spec(
        campaign_id, incident_id, actor=actor, request_id=request_id, channel=channel,
        policy=policy, incident=incident, spec=spec,
    )


async def create_restore_proposal(campaign_id: str, incident_id: str, *,
                                  actor: dict, request_id: str, channel: str = "web") -> dict:
    """Backward-compatible entry point for the original config executor."""
    policy, incident = await _proposal_context(campaign_id, incident_id, actor=actor)
    try:
        legacy = await build_restore_spec(campaign_id, incident)
    except RecoveryGuardError as exc:
        raise RecoveryError(str(exc), 409) from exc
    spec = {
        "action_version": 1, "kind": "executable_action",
        "label": "Khôi phục campaign config về revision đã duyệt",
        "instructions": [], "execution_environment": "production",
        "production_executor": "restore_config_revision", "lab_intervention": None,
        "cause_code": "configuration_drift", "evidence_blockers": [],
        **legacy,
    }
    return await _create_from_spec(
        campaign_id, incident_id, actor=actor, request_id=request_id, channel=channel,
        policy=policy, incident=incident, spec=spec,
    )


async def get_recovery_proposal(proposal_id: str) -> dict:
    value = await recovery_store.get_proposal(proposal_id)
    if not value:
        raise RecoveryError("Proposal not found", 404)
    result = recovery_store.public(value)
    if value.get("kind", "executable_action") == "executable_action" and value.get("status") == "awaiting_approval":
        result["approval_code"] = approval_code(proposal_id)
    result["events"] = await recovery_store.proposal_events(proposal_id)
    return result


async def reject_proposal(proposal_id: str, *, actor: dict, expected_version: int) -> dict:
    current = await recovery_store.get_proposal(proposal_id)
    if not current:
        raise RecoveryError("Proposal not found", 404)
    await _assert_owner(current["campaign_id"], actor)
    value = await recovery_store.transition(
        proposal_id, expected_statuses={"awaiting_approval", "awaiting_acknowledgement", "waiting_operator", "waiting_external", "ready_to_verify"},
        expected_version=expected_version,
        updates={"status": "rejected", "active": False, "rejected_by": _actor(actor), "rejected_at": _now()},
    )
    if not value:
        raise RecoveryError("Proposal changed or is no longer active", 409)
    await recovery_store.append_event(_event(proposal_id, "proposal_rejected", actor=_actor(actor)))
    await transition_incident(current["campaign_id"], current["incident_id"], "investigating",
                              f"Recovery proposal {proposal_id} rejected")
    return recovery_store.public(value)


async def acknowledge_proposal(proposal_id: str, *, actor: dict,
                               expected_version: int, channel: str = "web") -> dict:
    current = await recovery_store.get_proposal(proposal_id)
    if not current:
        raise RecoveryError("Proposal not found", 404)
    await _assert_owner(current["campaign_id"], actor)
    if current.get("kind") not in {"operator_workflow", "engineering_escalation"}:
        raise RecoveryError("Executable actions require approval, not acknowledgement", 409)
    if _parse_time(current["expires_at"]) <= _now():
        await recovery_store.transition(
            proposal_id, expected_statuses={"awaiting_acknowledgement"},
            updates={"status": "expired", "active": False, "expired_at": _now()},
        )
        raise RecoveryError("Proposal expired", 409)
    policy = await get_policy(current["campaign_id"])
    incident = await get_incident(current["campaign_id"], current["incident_id"])
    if (not incident or policy.get("version") != current.get("policy_version")
            or (incident.get("investigation") or {}).get("bundle_id") != current.get("bundle_id")):
        raise RecoveryError("Proposal evidence is stale; investigate again", 409)
    next_status = "waiting_operator" if current["kind"] == "operator_workflow" else "waiting_external"
    value = await recovery_store.transition(
        proposal_id, expected_statuses={"awaiting_acknowledgement"},
        expected_version=expected_version,
        updates={"status": next_status, "acknowledged_by": _actor(actor),
                 "acknowledged_at": _now(), "acknowledgement_channel": channel},
    )
    if not value:
        raise RecoveryError("Proposal changed or is no longer awaiting acknowledgement", 409)
    await recovery_store.append_event(_event(
        proposal_id, "proposal_acknowledged", actor=_actor(actor), channel=channel,
        next_status=next_status,
    ))
    return recovery_store.public(value)


async def complete_workflow_step(proposal_id: str, *, actor: dict, step_id: str,
                                 expected_version: int, note: str = "") -> dict:
    current = await recovery_store.get_proposal(proposal_id)
    if not current:
        raise RecoveryError("Proposal not found", 404)
    await _assert_owner(current["campaign_id"], actor)
    if current.get("kind") not in {"operator_workflow", "engineering_escalation"}:
        raise RecoveryError("Executable actions do not have operator steps", 409)
    expected = {"waiting_operator", "waiting_external"}
    if current.get("status") not in expected:
        raise RecoveryError("Proposal is not waiting for a workflow step", 409)
    if _parse_time(current["expires_at"]) <= _now():
        await recovery_store.transition(
            proposal_id, expected_statuses=expected,
            updates={"status": "expired", "active": False, "expired_at": _now()},
        )
        raise RecoveryError("Proposal expired", 409)
    steps = [dict(item) for item in current.get("steps") or []]
    selected = next((item for item in steps if item.get("step_id") == step_id), None)
    if not selected:
        raise RecoveryError("Unknown workflow step", 404)
    selected.update({"status": "completed", "completed_by": _actor(actor),
                     "completed_at": _now(), "note": str(note or "")[:500]})
    ready = all(item.get("status") == "completed" for item in steps if item.get("required", True))
    value = await recovery_store.transition(
        proposal_id, expected_statuses=expected, expected_version=expected_version,
        updates={"steps": steps, "status": "ready_to_verify" if ready else current["status"]},
    )
    if not value:
        raise RecoveryError("Proposal changed while completing the workflow step", 409)
    await recovery_store.append_event(_event(
        proposal_id, "workflow_step_completed", actor=_actor(actor), step_id=step_id,
        ready_to_verify=ready,
    ))
    return recovery_store.public(value)


async def apply_lab_intervention(proposal_id: str, *, actor: dict,
                                 expected_version: int, request_id: str,
                                 outcome: str = "success") -> dict:
    """Apply an allowlisted intervention only to the active synthetic dataset."""
    if not config.EVALUATION_L3_LAB_ENABLED:
        raise RecoveryError("L3 Scenario Lab interventions are disabled", 409)
    if len(str(request_id or "").strip()) < 8:
        raise RecoveryError("request_id must contain at least 8 characters", 422)
    if outcome not in {"success", "ineffective"}:
        raise RecoveryError("Lab outcome must be success or ineffective", 422)
    current = await recovery_store.get_proposal(proposal_id)
    if not current:
        raise RecoveryError("Proposal not found", 404)
    await _assert_owner(current["campaign_id"], actor)
    if current.get("execution_environment") != "scenario_lab" or not current.get("lab_intervention"):
        raise RecoveryError("Proposal has no Scenario Lab intervention", 409)
    if current.get("kind") not in {"operator_workflow", "engineering_escalation"}:
        raise RecoveryError("Scenario Lab intervention requires an acknowledged workflow", 409)
    expected_statuses = {"waiting_operator", "waiting_external", "ready_to_verify"}
    if current.get("status") not in expected_statuses:
        raise RecoveryError("Acknowledge the proposal before applying its Lab intervention", 409)
    if _parse_time(current["expires_at"]) <= _now():
        await recovery_store.transition(
            proposal_id, expected_statuses=expected_statuses,
            updates={"status": "expired", "active": False, "expired_at": _now()},
        )
        raise RecoveryError("Proposal expired", 409)
    if not await recovery_store.durable_available():
        raise RecoveryError("Durable L3 storage is unavailable; no Lab mutation was performed", 503)

    from evaluation.service import report_request, run_evaluation
    applied = current.get("lab_result")
    if not applied:
        dataset = await report_request("GET", f"/api/reports/internal/datasets/{current['campaign_id']}")
        active = dataset.get("active") or {}
        if active.get("kind") not in {"scenario", "recovery"}:
            raise RecoveryError("Active report dataset is not a synthetic Scenario Lab revision", 409)
        if int((dataset.get("state") or {}).get("activeRevision") or 0) != int(current["dataset_revision"]):
            raise RecoveryError("Scenario dataset changed; investigate and create a new proposal", 409)
    claimed = await recovery_store.transition(
        proposal_id, expected_statuses=expected_statuses, expected_version=expected_version,
        updates={"status": "executing", "lab_request_id": request_id,
                 "lab_outcome_requested": outcome, "lab_started_at": _now()},
    )
    if not claimed:
        raise RecoveryError("Proposal changed or another Lab execution already claimed it", 409)
    await recovery_store.append_event(_event(
        proposal_id, "lab_execution_claimed", actor=_actor(actor),
        intervention_type=current["lab_intervention"],
    ))
    try:
        if not applied:
            applied = await report_request(
                "POST", f"/api/reports/internal/scenarios/{current['campaign_id']}/recovery/apply",
                {
                    "requestId": request_id,
                    "expectedRevision": int(current["dataset_revision"]),
                    "proposalId": proposal_id,
                    "actionId": current["action_id"],
                    "interventionType": current["lab_intervention"],
                    "outcome": outcome,
                    "targetPlacementId": None if current.get("scope") == "campaign" else current.get("scope"),
                    "createdBy": str(actor.get("user_id") or actor.get("anonymous_id") or "owned_actor"),
                },
            )
            await recovery_store.transition(
                proposal_id, expected_statuses={"executing"},
                updates={"lab_result": applied},
            )
            await recovery_store.append_event(_event(
                proposal_id, "lab_revision_published", dataset_revision=applied["revision"],
            ))
        try:
            evaluation = await run_evaluation(
                current["campaign_id"], trigger="l3_lab_intervention",
                expected_revision=applied["revision"],
            )
        except Exception as exc:
            retryable = await recovery_store.transition(
                proposal_id, expected_statuses={"executing"},
                updates={"status": "ready_to_verify", "active": True, "lab_result": applied,
                         "verification_error": str(exc)[:240]},
            )
            await recovery_store.append_event(_event(
                proposal_id, "lab_verification_retryable", error=str(exc)[:240],
                dataset_revision=applied["revision"],
            ))
            return {**recovery_store.public(retryable), "evaluation": {
                "status": "retryable", "error": str(exc)[:240],
                "dataset_revision": applied["revision"],
            }}
        if evaluation.get("status") not in {"completed", "replayed"}:
            retryable = await recovery_store.transition(
                proposal_id, expected_statuses={"executing"},
                updates={"status": "ready_to_verify", "active": True, "lab_result": applied,
                         "verification_error": str(evaluation.get("error") or "evaluation incomplete")[:240]},
            )
            return {**recovery_store.public(retryable), "evaluation": evaluation}
        active_incidents = [item for item in evaluation.get("incidents") or []
                            if item.get("state") not in {"resolved", "dismissed", "false_positive", "expired"}]
        same_issue = any(
            item.get("issue_type") == current.get("issue_type")
            and item.get("scope") == current.get("scope")
            for item in active_incidents
        )
        status = "ineffective" if same_issue else "resolved"
        finished = await recovery_store.transition(
            proposal_id, expected_statuses={"executing"},
            updates={"status": status, "active": False, "lab_result": applied,
                     "verification_result": status, "finished_at": _now()},
        )
        await recovery_store.append_event(_event(
            proposal_id, "lab_verification_completed", result=status,
            dataset_revision=applied["revision"],
        ))
        return {**recovery_store.public(finished), "evaluation": evaluation}
    except Exception as exc:
        await recovery_store.transition(
            proposal_id, expected_statuses={"executing"},
            updates={"status": "failed", "active": False,
                     "failure": str(exc)[:240], "finished_at": _now()},
        )
        await recovery_store.append_event(_event(
            proposal_id, "lab_execution_failed", error=str(exc)[:240],
        ))
        if isinstance(exc, RecoveryError):
            raise
        raise RecoveryError("Scenario Lab recovery failed; no production state was changed", 502) from exc


async def approve_and_execute(proposal_id: str, *, actor: dict, code: str,
                              expected_version: int, channel: str = "web",
                              require_durable: bool = True) -> dict:
    if not config.EVALUATION_L3_EXECUTION_ENABLED:
        raise RecoveryError("L3 execution is disabled", 409)
    proposal = await recovery_store.get_proposal(proposal_id)
    if not proposal:
        raise RecoveryError("Proposal not found", 404)
    if proposal.get("status") in {"resolved", "rolled_back"}:
        return await get_recovery_proposal(proposal_id)
    if proposal.get("kind", "executable_action") != "executable_action":
        raise RecoveryError("This proposal is not an executable action", 409)
    if proposal.get("status") != "awaiting_approval":
        raise RecoveryError("Proposal is no longer awaiting approval", 409)
    if proposal.get("production_executor", "restore_config_revision") != "restore_config_revision":
        raise RecoveryError("No production executor is registered for this action", 409)
    if proposal.get("execution_environment", "production") != "production":
        raise RecoveryError("Scenario Lab actions cannot reach the production executor", 409)
    await _assert_owner(proposal["campaign_id"], actor)
    if _parse_time(proposal["expires_at"]) <= _now():
        await recovery_store.transition(
            proposal_id, expected_statuses={"awaiting_approval"},
            updates={"status": "expired", "active": False, "expired_at": _now()},
        )
        await transition_incident(proposal["campaign_id"], proposal["incident_id"], "investigating",
                                  f"Recovery proposal {proposal_id} expired")
        raise RecoveryError("Proposal expired", 409)
    if not hmac.compare_digest(_nonce_hash(code), proposal["approval_nonce_hash"]):
        raise RecoveryError("Approval code is invalid", 409)
    policy = await get_policy(proposal["campaign_id"])
    incident = await get_incident(proposal["campaign_id"], proposal["incident_id"])
    if (not incident or policy.get("version") != proposal.get("policy_version")
            or (incident.get("investigation") or {}).get("bundle_id") != proposal.get("bundle_id")):
        raise RecoveryError("Proposal evidence is stale; investigate again", 409)
    state = await get_campaign_config(proposal["campaign_id"])
    if int(state["revision"]) != int(proposal["source_config_revision"]):
        raise RecoveryError("Campaign config changed; create a new proposal", 409)
    if require_durable and not await recovery_store.durable_available():
        raise RecoveryError("Durable L3 storage is unavailable; no mutation was performed", 503)

    execution_key = f"{proposal_id}:v{proposal['version']}"
    claimed = await recovery_store.transition(
        proposal_id, expected_statuses={"awaiting_approval"},
        expected_version=expected_version,
        updates={
            "status": "executing", "execution_key": execution_key,
            "approved_by": _actor(actor), "approved_at": _now(), "approval_channel": channel,
            "before_snapshot": state["config"], "before_hash": config_hash(state["config"]),
        },
    )
    if not claimed:
        current = await recovery_store.get_proposal(proposal_id)
        if current and current.get("status") in {"resolved", "rolled_back"}:
            return await get_recovery_proposal(proposal_id)
        raise RecoveryError("Proposal changed or another execution already claimed it", 409)
    await recovery_store.append_event(_event(proposal_id, "execution_claimed", actor=_actor(actor), channel=channel))
    await transition_incident(proposal["campaign_id"], proposal["incident_id"], "recovering",
                              f"Executing {proposal['action_id']} via {proposal_id}")

    try:
        mutation = await update_campaign_config(
            proposal["campaign_id"], actor=actor,
            expected_revision=int(proposal["source_config_revision"]),
            request_id=f"l3-{proposal_id.lower()}-v{proposal['version']}",
            patch=proposal["patch"], note=f"Approved L3 recovery {proposal_id}",
        )
        await recovery_store.append_event(_event(
            proposal_id, "mutation_completed", config_revision=mutation.get("revision"),
            changes=mutation.get("changes"),
        ))
        await transition_incident(proposal["campaign_id"], proposal["incident_id"], "verifying",
                                  f"Verifying {proposal_id}")
        after = await get_campaign_config(proposal["campaign_id"])
        after_hash = config_hash(after["config"])
        if after_hash != proposal["target_config_hash"]:
            raise RecoveryError("Config verification failed after mutation", 409)
        completed = await recovery_store.transition(
            proposal_id, expected_statuses={"executing"},
            updates={
                "status": "resolved", "active": False, "resolved_at": _now(),
                "after_snapshot": after["config"], "after_hash": after_hash,
                "result_config_revision": after["revision"],
                "verification_result": "target_hash_matched",
            },
        )
        await recovery_store.append_event(_event(
            proposal_id, "verification_succeeded", after_hash=after_hash,
            config_revision=after["revision"],
        ))
        await transition_incident(proposal["campaign_id"], proposal["incident_id"], "resolved",
                                  f"Recovery {proposal_id} verified against target config hash")
        return recovery_store.public(completed)
    except Exception as exc:
        # Compensate only when our mutation is still the latest revision. A
        # concurrent edit always wins and requires human escalation.
        rollback = None
        try:
            current = await get_campaign_config(proposal["campaign_id"])
            if int(current["revision"]) == int(proposal["source_config_revision"]) + 1:
                rollback = await update_campaign_config(
                    proposal["campaign_id"], actor=actor,
                    expected_revision=int(current["revision"]),
                    request_id=f"l3-rollback-{proposal_id.lower()}-v{proposal['version']}",
                    patch=proposal["rollback_patch"], note=f"Compensating rollback for {proposal_id}",
                )
        except Exception as rollback_exc:
            rollback = {"error": str(rollback_exc)[:200]}
        status = "rolled_back" if rollback and not rollback.get("error") else "failed"
        failed = await recovery_store.transition(
            proposal_id, expected_statuses={"executing"},
            updates={"status": status, "active": False, "failure": str(exc)[:240],
                     "rollback": rollback, "finished_at": _now()},
        )
        await recovery_store.append_event(_event(
            proposal_id, "execution_failed", error=str(exc)[:240], rollback=rollback,
        ))
        await transition_incident(proposal["campaign_id"], proposal["incident_id"], "failed",
                                  f"Recovery {proposal_id} {status}: {str(exc)[:120]}")
        if isinstance(exc, RecoveryError):
            raise
        raise RecoveryError("Recovery failed; audit contains rollback status", 502) from exc
