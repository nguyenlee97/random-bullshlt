"""Deterministic two-pass placement and creative-format planning.

Placement intent is deliberately creative-agnostic. It identifies catalog and
inventory candidates from the approved campaign inputs. The format planner then
selects the smallest bounded set of exact asset formats needed to cover the best
candidates. Final placement ranking happens only after real creative verdicts.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from handlers.image_gen import AD_FORMATS


SKIN_FORMAT_ID = "znews-Background"
EXACT_FORMAT_BY_SIZE = {
    "300x250": "zuma-box",
    "300x600": "display-halfpage-300x600",
    "1160x250": "znews-masthead-1160x250",
    "1160x280": "zuma-baomoi-masthead",
    "2032x528": "zmp3-top-banner",
}
FORMAT_BY_CREATIVE_CONTRACT = {
    "znews-category-masthead-v1": "znews-top-banner",
    "baomoi-category-masthead-v1": "zuma-baomoi-masthead",
    "category-background-v1": "znews-Background",
    "znews-category-side-left-v1": "znews-side-banner",
    "znews-category-side-right-v1": "znews-side-banner",
    "baomoi-category-side-left-v1": "zuma-Left",
    "baomoi-category-side-right-v1": "zuma-Right",
    "display-box-300x250-v1": "zuma-box",
    "display-halfpage-300x600-v1": "display-halfpage-300x600",
    "znews-home-inline-v1": "znews-middle-banner",
    "zingmp3-masthead-v1": "zmp3-top-banner",
    "smoney-top-desktop-v1": "smoney-top-desktop",
    "smoney-top-mobile-v1": "smoney-top-mobile",
    "smoney-screener-desktop-v1": "smoney-screener-desktop",
    "smoney-screener-mobile-v1": "smoney-screener-mobile",
    "dicungcon-bridge-desktop-v1": "dicungcon-bridge-desktop",
    "dicungcon-bridge-mobile-v1": "dicungcon-bridge-mobile",
    "zagoo-interstitial-desktop-v1": "zagoo-interstitial-desktop",
    "zagoo-interstitial-mobile-v1": "zagoo-interstitial-mobile",
}


def normalize_size(value: Any) -> str:
    return str(value or "").lower().replace("×", "x").replace(" ", "")


def format_spec_for_zone(zone: dict) -> dict | None:
    """Return a generation spec only when backed by the known format catalog."""
    size = normalize_size(zone.get("size"))
    is_skin = size == "skin" or str(zone.get("format", "")).lower() == "skin"
    format_id = FORMAT_BY_CREATIVE_CONTRACT.get(zone.get("creativeContractId"))
    if not format_id:
        format_id = SKIN_FORMAT_ID if is_skin else EXACT_FORMAT_BY_SIZE.get(size)
    fmt = AD_FORMATS.get(format_id or "")
    if not fmt:
        return None
    return {
        "format_key": format_id,
        "format_id": format_id,
        "width": int(fmt["width"]),
        "height": int(fmt["height"]),
        "media_type": "image",
        "intended_format": "skin" if format_id == SKIN_FORMAT_ID else "banner",
        "zone_size": "skin" if is_skin else size,
    }


def build_creative_format_plan(
    placement_intent: dict,
    *,
    source: str,
    max_assets: int = 3,
) -> dict:
    """Group ranked candidates by exact format and choose a bounded cover set."""
    if source not in {"upload", "ai_generate"}:
        raise ValueError(f"unsupported creative source: {source}")
    cap = max(1, min(int(max_assets or 1), 10))
    candidates = placement_intent.get("candidates") or placement_intent.get("zones") or []
    groups: dict[str, dict] = {}
    unsupported: list[str] = []

    for rank, zone in enumerate(candidates, start=1):
        spec = format_spec_for_zone(zone)
        zone_id = str(zone.get("id") or "")
        if not zone_id:
            continue
        if spec is None:
            unsupported.append(zone_id)
            continue
        group = groups.setdefault(spec["format_key"], {
            **spec,
            "zone_ids": [],
            "best_candidate_rank": rank,
            "aggregate_candidate_score": 0.0,
            "variants": 1,
            "required": True,
        })
        group["zone_ids"].append(zone_id)
        group["aggregate_candidate_score"] += float(zone.get("score") or 0)

    ordered = sorted(
        groups.values(),
        key=lambda item: (
            item["best_candidate_rank"],
            -item["aggregate_candidate_score"],
            item["format_key"],
        ),
    )
    selected = deepcopy(ordered[:cap])
    omitted = [
        zone_id
        for group in ordered[cap:]
        for zone_id in group["zone_ids"]
    ]
    covered = [zone_id for group in selected for zone_id in group["zone_ids"]]
    return {
        "kind": "placement_aware_creative_format_plan",
        "source": source,
        "placement_intent_revision": int(
            placement_intent.get("artifact_revision")
            or placement_intent.get("revision")
            or 0
        ),
        "formats": selected,
        "max_assets": cap,
        "estimated_provider_calls": len(selected) if source == "ai_generate" else 0,
        "covered_zone_ids": covered,
        "unsupported_zone_ids": unsupported,
        "omitted_by_cost_cap_zone_ids": omitted,
        "selection_method": "candidate_rank_then_format_dedup_v1",
    }
