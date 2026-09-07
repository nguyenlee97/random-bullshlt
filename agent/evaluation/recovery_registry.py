"""Deterministic recovery action registry. No model can execute an action."""
from __future__ import annotations

from campaign_config import EDITABLE_FIELDS, config_changes, get_campaign_config, get_campaign_config_revision


ACTION_ID = "restore_config_revision"


class RecoveryGuardError(ValueError):
    pass


def _config_probe(bundle: dict) -> dict | None:
    return next((item for item in (bundle.get("probes") or [])
                 if item.get("probe_id") == "config_drift"), None)


def _supported_config_cause(bundle: dict) -> bool:
    if bundle.get("mode") == "multi_agent":
        return (
            bundle.get("assessment") == "supported_hypothesis"
            and bundle.get("cause_status") == "supported_hypothesis"
            and bundle.get("cause_code") == "configuration_drift"
            and not (bundle.get("review") or {}).get("contradictions")
            and not bundle.get("partial")
        )
    top = bundle.get("top_hypothesis") or {}
    return (
        bundle.get("assessment") == "supported_hypothesis"
        and top.get("hypothesis_id") == "config_drift"
        and not bundle.get("ambiguous")
    )


async def build_restore_spec(campaign_id: str, incident: dict) -> dict:
    if incident.get("issue_type") != "config_drift" or incident.get("scope") != "campaign":
        raise RecoveryGuardError("Only a campaign-scoped config_drift incident is supported")
    incident_evidence = incident.get("evidence") or {}
    if incident_evidence.get("source") != "campaign_config_revision":
        raise RecoveryGuardError("Scenario-only drift cannot authorize L3")
    bundle = incident.get("investigation") or {}
    if not bundle or bundle.get("dataset_revision") != incident.get("dataset_revision"):
        raise RecoveryGuardError("Current L2 evidence is required")
    if bundle.get("policy_version") != incident.get("policy_version"):
        raise RecoveryGuardError("L2 evidence policy is stale")
    probe = _config_probe(bundle)
    if not probe or probe.get("status") != "anomaly" or probe.get("source") != "derived":
        raise RecoveryGuardError("Live derived config evidence is required")
    if not _supported_config_cause(bundle):
        raise RecoveryGuardError("L2 did not establish a supported config cause")

    target_revision = int(incident_evidence.get("baseline_revision", -1))
    target = await get_campaign_config_revision(campaign_id, target_revision)
    current = await get_campaign_config(campaign_id)
    if not target:
        raise RecoveryGuardError("Target config revision is unavailable")
    if int(current["revision"]) != int(incident_evidence.get("current_revision", -1)):
        raise RecoveryGuardError("Campaign config changed; run evaluation again")
    changes = config_changes(current["config"], target["config"])
    if not changes:
        raise RecoveryGuardError("Campaign config already matches the target revision")
    patch = {item["field"]: item["after"] for item in changes}
    rollback_patch = {item["field"]: item["before"] for item in changes}
    if set(patch) - EDITABLE_FIELDS:
        raise RecoveryGuardError("Recovery diff contains unsupported fields")
    return {
        "action_id": ACTION_ID,
        "source_config_revision": int(current["revision"]),
        "source_config_hash": incident_evidence.get("current_hash"),
        "target_config_revision": target_revision,
        "target_config_hash": target["config_hash"],
        "target_provenance": target["provenance"],
        "patch": patch,
        "rollback_patch": rollback_patch,
        "changes": changes,
        "risk": "medium",
        "expected_impact": "Khôi phục các trường cấu hình về revision được hiển thị trong proposal.",
        "verification": {
            "kind": "config_equals_target_revision",
            "target_hash": target["config_hash"],
            "resolve_issue_types": ["config_drift"],
            "note": "Chỉ xác minh config; không khẳng định KPI đã phục hồi.",
        },
        "reversible": True,
    }
