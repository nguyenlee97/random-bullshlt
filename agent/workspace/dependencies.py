"""Artifact dependency rules used for impact previews and invalidation."""
from __future__ import annotations


ARTIFACTS = (
    "brief",
    "strategy",
    "audience",
    "targeting",
    "placement_intent",
    "creative_format_plan",
    "creative",
    "creative_verdict",
    "placements",
    "assignments",
    "forecast",
    "order_draft",
    "order",
    "report",
)

FIELD_TO_ARTIFACT = {
    "brief": "brief",
    "strategy": "strategy",
    "segment": "audience",
    "targeting": "targeting",
    "creative": "creative",
    "setup": "placements",
    "reco_zones": "placements",
    "assignments": "assignments",
    "report_context": "report",
    "report": "report",
}

DEPENDENTS = {
    "brief": {"strategy", "creative_verdict"},
    "strategy": {"audience", "creative_verdict", "placement_intent"},
    "audience": {"targeting", "placement_intent", "forecast"},
    "targeting": {"placement_intent", "forecast"},
    "placement_intent": {"creative_format_plan", "placements"},
    # Creative source is run-specific. AI-generated assets are invalidated by
    # the Autopilot task graph and their format-plan revision key; uploaded
    # assets must not become stale merely because targeting/placement changed.
    "creative_format_plan": set(),
    "creative": {"creative_verdict"},
    # Final placement ranking is a second pass over actual approved creatives.
    "creative_verdict": {"placements"},
    "placements": {"assignments", "forecast"},
    "assignments": {"forecast"},
    "forecast": {"order_draft"},
    "order_draft": {"order"},
    "order": {"report"},
    "report": set(),
}


def _build_direct_dependencies() -> dict[str, set[str]]:
    result = {artifact: set() for artifact in ARTIFACTS}
    for source, dependents in DEPENDENTS.items():
        for dependent in dependents:
            result.setdefault(dependent, set()).add(source)
    return result


DIRECT_DEPENDENCIES = _build_direct_dependencies()


def artifact_for_field(field: str) -> str:
    root = field.split(".", 1)[0]
    if root not in FIELD_TO_ARTIFACT:
        raise ValueError(f"unsupported workspace field: {field}")
    return FIELD_TO_ARTIFACT[root]


def downstream(artifact: str) -> list[str]:
    """Return the deterministic transitive dependency closure."""
    found: set[str] = set()
    pending = list(DEPENDENTS.get(artifact, set()))
    while pending:
        item = pending.pop()
        if item in found:
            continue
        found.add(item)
        pending.extend(DEPENDENTS.get(item, set()))
    return [name for name in ARTIFACTS if name in found]


def direct_inputs(artifact: str) -> list[str]:
    """Return immediate upstream artifacts in deterministic workflow order."""
    if artifact not in ARTIFACTS:
        raise ValueError(f"unsupported artifact: {artifact}")
    dependencies = DIRECT_DEPENDENCIES.get(artifact, set())
    return [name for name in ARTIFACTS if name in dependencies]


def build_recompute_plan(workspace: dict) -> dict:
    """Build a deterministic plan diff after one or more non-linear edits.

    Values are deliberately retained when stale. This lets the UI explain and
    selectively recompute affected work while proving which approved artifacts
    are safe to reuse.
    """
    artifacts = workspace.get("artifacts", {})
    recompute: list[dict] = []
    reusable: list[dict] = []
    for name in ARTIFACTS:
        item = artifacts.get(name, {}) or {}
        status = item.get("status", "missing")
        value = item.get("value")
        if status == "stale":
            inputs = direct_inputs(name)
            stale_inputs = [
                dependency for dependency in inputs
                if artifacts.get(dependency, {}).get("status") == "stale"
            ]
            recompute.append({
                "artifact": name,
                "action": "recompute",
                "status": "blocked" if stale_inputs else "ready",
                "reason": item.get("stale_reason", "upstream artifact changed"),
                "stale_at_revision": item.get("stale_at_revision"),
                "input_artifacts": inputs,
                "blocked_by": stale_inputs,
                "previous_revision": item.get("revision", 0),
                "has_previous_value": value not in (None, {}, []),
            })
        elif status == "approved" and value not in (None, {}, []):
            reusable.append({
                "artifact": name,
                "action": "reuse",
                "revision": item.get("revision", 0),
                "reason": "inputs unchanged",
            })

    return {
        "workspace_id": workspace.get("workspace_id") or workspace.get("_id"),
        "session_id": workspace.get("session_id"),
        "workspace_revision": workspace.get("revision", 0),
        "has_changes": bool(recompute),
        "recompute": recompute,
        "recompute_order": [item["artifact"] for item in recompute],
        "ready": [item["artifact"] for item in recompute if item["status"] == "ready"],
        "blocked": [item["artifact"] for item in recompute if item["status"] == "blocked"],
        "reuse": reusable,
        "reuse_count": len(reusable),
    }
