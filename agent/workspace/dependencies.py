"""Artifact dependency rules used for impact previews and invalidation."""
from __future__ import annotations


ARTIFACTS = (
    "brief",
    "strategy",
    "audience",
    "targeting",
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
    "brief": {"strategy", "audience", "targeting", "creative_verdict", "placements"},
    "strategy": {"audience", "targeting", "creative_verdict", "placements"},
    "audience": {"targeting", "forecast"},
    "targeting": {"forecast"},
    "creative": {"creative_verdict"},
    "creative_verdict": {"assignments"},
    "placements": {"assignments", "forecast"},
    "assignments": {"forecast"},
    "forecast": {"order_draft"},
    "order_draft": {"order"},
    "order": {"report"},
    "report": set(),
}


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
