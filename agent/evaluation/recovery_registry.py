"""Deterministic recovery action registry. No model can execute an action."""
from __future__ import annotations

from campaign_config import EDITABLE_FIELDS, config_changes, get_campaign_config, get_campaign_config_revision
from evaluation.recovery_contracts import ACTION_DEFINITIONS, action_definition, canonical_cause


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


def _candidate(definition: dict, *, cause: str, incident: dict,
               execution_environment: str, blockers: list[str] | None = None) -> dict:
    value = {
        **definition,
        "candidate_id": definition["action_id"],
        "cause_code": cause,
        "issue_type": incident.get("issue_type"),
        "scope": incident.get("scope"),
        "execution_environment": execution_environment,
        "evidence_blockers": list(blockers or []),
        "available": not blockers,
    }
    if execution_environment != "production":
        value["production_executor"] = None
    return value


async def recovery_candidates(campaign_id: str, incident: dict) -> list[dict]:
    """Return only server-selected actions for the incident's current evidence.

    Scenario labels are deliberately ignored. Synthetic eligibility is derived
    from the incident evidence source, while cause selection comes from L2.
    """
    bundle = incident.get("investigation") or {}
    current_evidence = (
        bundle
        and bundle.get("dataset_revision") == incident.get("dataset_revision")
        and bundle.get("policy_version") == incident.get("policy_version")
    )
    cause = canonical_cause(bundle) if current_evidence else "none"
    issue = str(incident.get("issue_type") or "")
    scenario_only = (incident.get("evidence") or {}).get("source") == "scenario_fact"
    if not scenario_only and issue != "config_drift":
        dataset = None
        try:
            from evaluation.service import report_request
            dataset = await report_request("GET", f"/api/reports/internal/datasets/{campaign_id}")
            scenario_only = (dataset.get("active") or {}).get("kind") in {"scenario", "recovery"}
        except Exception:
            # Environment uncertainty removes the Lab executor; it never adds
            # production mutation authority.
            scenario_only = False
        if dataset and int((dataset.get("state") or {}).get("activeRevision") or 0) != int(incident.get("dataset_revision") or 0):
            raise RecoveryGuardError("Incident evidence is stale; run evaluation again")
    environment = "scenario_lab" if scenario_only else "production"
    candidates: list[dict] = []
    lab_fallbacks = {
        "config_drift": "restore_config_fixture",
        "data_quality": "backfill_attribution_fixture",
        "delivery_drop": "restore_delivery",
        "pacing_error": "restore_delivery",
        "ctr_regression": "restore_click_measurement",
        "robust_trend_drop": "restore_click_measurement",
        "creative_failure": "replace_creative_fixture",
        "click_tracking_failure": "restore_click_measurement",
    }

    # The sole production mutation remains the previously guarded exact config
    # restore. Scenario drift may use only its synthetic Lab intervention.
    if issue == "config_drift" and not scenario_only:
        try:
            spec = await build_restore_spec(campaign_id, incident)
            definition = action_definition(ACTION_ID)
            candidates.append({**_candidate(
                definition, cause="configuration_drift", incident=incident,
                execution_environment="production",
            ), "spec": spec})
        except RecoveryGuardError:
            pass

    for definition in ACTION_DEFINITIONS.values():
        if definition["action_id"] == ACTION_ID:
            continue
        issue_match = issue in definition["supported_issue_types"]
        cause_match = cause in definition["supported_causes"]
        # When L2 has no supported cause, only the fail-safe hold workflow is
        # eligible. This prevents generic symptoms from authorizing a fix.
        if not issue_match or not cause_match:
            continue
        selected_definition = action_definition(definition["action_id"])
        if (scenario_only and definition["action_id"] == "hold_optimization_and_recheck"
                and not selected_definition.get("lab_intervention")):
            selected_definition["lab_intervention"] = lab_fallbacks.get(issue)
        candidates.append(_candidate(
            selected_definition, cause=cause, incident=incident,
            execution_environment=environment,
        ))

    # Synthetic config drift gets a non-production workflow whose allowlisted
    # Lab intervention restores the fixture. It can never reach config update.
    if scenario_only and issue == "config_drift" and not candidates:
        definition = action_definition("hold_optimization_and_recheck")
        definition["lab_intervention"] = lab_fallbacks["config_drift"]
        candidates.append(_candidate(
            definition, cause=cause, incident=incident,
            execution_environment="scenario_lab",
        ))
    return candidates


async def build_proposal_spec(campaign_id: str, incident: dict, candidate_id: str | None = None) -> dict:
    candidates = await recovery_candidates(campaign_id, incident)
    if not candidates:
        raise RecoveryGuardError("No recovery action is supported by the current L2 evidence")
    selected = next((item for item in candidates if item["candidate_id"] == candidate_id), None)
    if candidate_id and not selected:
        raise RecoveryGuardError("Recovery candidate is not supported by the current L2 evidence")
    selected = selected or candidates[0]
    definition = action_definition(selected["action_id"])
    spec = selected.pop("spec", None) or {}
    return {
        **definition,
        **spec,
        "cause_code": selected["cause_code"],
        "execution_environment": selected["execution_environment"],
        "evidence_blockers": selected["evidence_blockers"],
        # Candidate selection may narrow a static action for the active
        # environment (for example, attach a symptom-specific Scenario Lab
        # intervention to the fail-safe hold workflow). Preserve those
        # server-owned constraints when materializing the proposal.
        "lab_intervention": selected.get("lab_intervention"),
        "production_executor": selected.get("production_executor"),
    }


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
