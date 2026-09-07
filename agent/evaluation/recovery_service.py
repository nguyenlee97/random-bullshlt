"""Shared Web/Zalo service for the first guarded L3 recovery action."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from campaign_config import config_hash, get_campaign_config, update_campaign_config
from config import config
from evaluation.recovery_registry import RecoveryGuardError, build_restore_spec
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
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


async def create_restore_proposal(campaign_id: str, incident_id: str, *,
                                  actor: dict, request_id: str, channel: str = "web") -> dict:
    if not config.EVALUATION_L3_PROPOSALS_ENABLED:
        raise RecoveryError("L3 proposals are disabled", 409)
    if len(str(request_id or "").strip()) < 8:
        raise RecoveryError("request_id must contain at least 8 characters", 422)
    await _assert_owner(campaign_id, actor)
    policy = await get_policy(campaign_id)
    if not policy.get("enabled") or policy.get("level") != "L3":
        raise RecoveryError("Campaign policy must enable L3", 409)
    incident = await get_incident(campaign_id, incident_id)
    if not incident:
        raise RecoveryError("Incident not found", 404)
    if incident.get("state") in {"resolved", "dismissed", "false_positive", "expired"}:
        raise RecoveryError("Incident is closed", 409)
    try:
        spec = await build_restore_spec(campaign_id, incident)
    except RecoveryGuardError as exc:
        raise RecoveryError(str(exc), 409) from exc

    clean_request = str(request_id).strip()
    request_key = hashlib.sha256(
        f"{campaign_id}|{incident_id}|{spec['action_id']}|{clean_request}".encode()
    ).hexdigest()
    proposal_id = f"RP-{uuid.uuid4().hex[:10].upper()}"
    code = approval_code(proposal_id)
    now = _now()
    bundle = incident.get("investigation") or {}
    proposal = {
        "proposal_id": proposal_id, "request_key": request_key,
        "campaign_id": campaign_id, "incident_id": incident_id,
        "dataset_revision": incident.get("dataset_revision"),
        "policy_version": incident.get("policy_version"),
        "bundle_id": bundle.get("bundle_id"),
        **spec,
        "status": "awaiting_approval", "active": True, "version": 1,
        "approval_nonce_hash": _nonce_hash(code),
        "created_by": _actor(actor), "channel": channel,
        "created_at": now, "updated_at": now,
        "expires_at": now + timedelta(minutes=15),
    }
    await recovery_store.supersede_active(campaign_id, incident_id, request_key)
    stored, created = await recovery_store.create_proposal(proposal)
    if created:
        await recovery_store.append_event(_event(
            proposal_id, "proposal_created", actor=_actor(actor), channel=channel,
            dataset_revision=incident.get("dataset_revision"),
        ))
        await transition_incident(campaign_id, incident_id, "awaiting_approval",
                                  f"Recovery proposal {proposal_id} awaiting approval")
    result = recovery_store.public(stored)
    result["approval_code"] = approval_code(stored["proposal_id"])
    result["created"] = created
    return result


async def get_recovery_proposal(proposal_id: str) -> dict:
    value = await recovery_store.get_proposal(proposal_id)
    if not value:
        raise RecoveryError("Proposal not found", 404)
    result = recovery_store.public(value)
    if value.get("status") == "awaiting_approval":
        result["approval_code"] = approval_code(proposal_id)
    result["events"] = await recovery_store.proposal_events(proposal_id)
    return result


async def reject_proposal(proposal_id: str, *, actor: dict, expected_version: int) -> dict:
    current = await recovery_store.get_proposal(proposal_id)
    if not current:
        raise RecoveryError("Proposal not found", 404)
    await _assert_owner(current["campaign_id"], actor)
    value = await recovery_store.transition(
        proposal_id, expected_statuses={"awaiting_approval"},
        expected_version=expected_version,
        updates={"status": "rejected", "active": False, "rejected_by": _actor(actor), "rejected_at": _now()},
    )
    if not value:
        raise RecoveryError("Proposal changed or is no longer awaiting approval", 409)
    await recovery_store.append_event(_event(proposal_id, "proposal_rejected", actor=_actor(actor)))
    await transition_incident(current["campaign_id"], current["incident_id"], "investigating",
                              f"Recovery proposal {proposal_id} rejected")
    return recovery_store.public(value)


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
    if proposal.get("status") != "awaiting_approval":
        raise RecoveryError("Proposal is no longer awaiting approval", 409)
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
