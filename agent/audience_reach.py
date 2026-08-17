"""Canonical, server-owned unique audience reach estimation.

The current DMP catalog exposes marginal ranges but no overlap matrix or union
endpoint.  We therefore return a calibrated estimate (never an exact count),
bounded by the product's 60M addressable Vietnam universe.  Every campaign
flow and the browser UI consumes this contract; no client-side union formula is
allowed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import prod
from typing import Any


AUDIENCE_UNIVERSE = 60_000_000
ESTIMATE_VERSION = "vn-calibrated-union-v2"


def _identity(segment: dict[str, Any]) -> str:
    source = segment.get("source") if isinstance(segment.get("source"), dict) else {}
    explicit = str(
        segment.get("segmentId")
        or segment.get("_id")
        or segment.get("code")
        or source.get("segmentId")
        or source.get("recordId")
        or segment.get("fullLabel")
        or segment.get("name")
        or ""
    ).strip()
    if explicit:
        return explicit
    # Legacy payloads occasionally omit IDs.  A stable content fingerprint
    # keeps those estimable without allowing duplicated rows to inflate reach.
    return "legacy:" + "|".join(str(segment.get(key) or "").strip() for key in (
        "type", "category", "sizeMin", "sizeMax", "est_size",
    ))


def _range(segment: dict[str, Any]) -> tuple[int, int] | None:
    low = int(segment.get("sizeMin") or segment.get("est_size") or 0)
    high = int(segment.get("sizeMax") or segment.get("est_size") or 0)
    if low <= 0 and high <= 0:
        return None
    if low <= 0:
        low = high
    if high <= 0:
        high = low
    return min(low, high, AUDIENCE_UNIVERSE), min(max(low, high), AUDIENCE_UNIVERSE)


def _union(values: list[int]) -> int:
    """Monotonic correlated-union fallback for marginal audience sizes.

    The largest segment contributes its catalog marginal.  Additional segments
    contribute 45% of their remaining independent probability, reflecting the
    high overlap expected in interest/behaviour catalogs.  This is deliberately
    conservative, deterministic, order-independent, and universe capped.
    """
    if not values:
        return 0
    probabilities = sorted(
        (min(max(value, 0), AUDIENCE_UNIVERSE) / AUDIENCE_UNIVERSE for value in values),
        reverse=True,
    )
    adjusted = [probabilities[0], *(value * 0.45 for value in probabilities[1:])]
    return min(
        AUDIENCE_UNIVERSE,
        round(AUDIENCE_UNIVERSE * (1 - prod(1 - value for value in adjusted))),
    )


def estimate_unique_reach(segments: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    known: list[tuple[dict[str, Any], tuple[int, int]]] = []
    unknown_ids: list[str] = []
    selected_ids: list[str] = []

    for segment in segments or []:
        if not isinstance(segment, dict):
            continue
        segment_id = _identity(segment)
        key = segment_id.casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        selected_ids.append(segment_id)
        segment_range = _range(segment)
        if segment_range is None:
            unknown_ids.append(segment_id)
        else:
            known.append((segment, segment_range))

    source_dates = [
        str(segment.get("sizeEstimatedAt"))
        for segment, _ in known
        if segment.get("sizeEstimatedAt")
    ]
    updated_at = max(source_dates) if source_dates else None
    catalog_versions = sorted({
        str(segment.get("sizeEstimateVersion") or "catalog")
        for segment, _ in known
    })
    catalog_version = "+".join(catalog_versions) or "unknown"

    if not known:
        return {
            "selected_segment_ids": selected_ids,
            "unique_reach": None,
            "range": None,
            "method": "unavailable",
            "universe": AUDIENCE_UNIVERSE,
            "confidence": "low",
            "source_updated_at": updated_at,
            "catalog_version": catalog_version,
            "estimate_version": ESTIMATE_VERSION,
            "unknown_segment_ids": unknown_ids,
            "status": "unavailable",
        }

    lows = [item[1][0] for item in known]
    highs = [item[1][1] for item in known]
    centers = [round((low + high) / 2) for low, high in (item[1] for item in known)]
    any_modeled = any(segment.get("sizeSource") == "modeled_estimate" for segment, _ in known)
    confidence = "low" if unknown_ids else ("medium" if any_modeled else "high")

    return {
        "selected_segment_ids": selected_ids,
        "unique_reach": _union(centers),
        "range": {"low": _union(lows), "high": _union(highs)},
        "method": "calibrated_estimate",
        "universe": AUDIENCE_UNIVERSE,
        "confidence": confidence,
        "source_updated_at": updated_at,
        "catalog_version": catalog_version,
        "estimate_version": ESTIMATE_VERSION,
        "unknown_segment_ids": unknown_ids,
        "status": "partial" if unknown_ids else "available",
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }


def audience_selection(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Workspace representation backed by the canonical reach contract."""
    reach = estimate_unique_reach(segments)
    return {
        "attrs": segments,
        "size": reach["unique_reach"] or 0,
        "sizeKnown": reach["unique_reach"] is not None,
        "reach": reach,
    }
