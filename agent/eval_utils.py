"""Small, dependency-free helpers shared by the agent tests and eval runner.

This module intentionally lives inside the agent build context so the exact
same ID-normalization behavior is testable in the reproducible container.
"""


def resolve_segments(ids: list[str], golden_to_segment: dict[str, str]) -> set[str]:
    """Resolve reseed-sensitive Mongo IDs to stable segment IDs."""
    return {golden_to_segment.get(value, value) for value in ids}


def rec_segment_ids(
    recommendations: list[dict], label_to_segment: dict[str, str]
) -> list[str]:
    """Return stable segment IDs, falling back to a catalog label join."""
    values: list[str] = []
    for rec in recommendations:
        value = rec.get("segmentId")
        if not value:
            value = label_to_segment.get(rec.get("fullLabel") or rec.get("name", ""))
        if value:
            values.append(value)
    return values
