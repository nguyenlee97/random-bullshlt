"""OpenAI placement inventory policy.

The canonical catalog retains retired placement IDs so historical campaign
snapshots remain resolvable. OpenAI recommendation and selection flows use
this policy to expose only inventory that can render in the normal customer
walkthrough.
"""
from __future__ import annotations

from collections.abc import Iterable


CATEGORY_MASTHEAD_FAMILY = "category_masthead"


def is_openai_recommendable_zone(zone: dict) -> bool:
    """Return whether a catalog row can enter an OpenAI placement flow.

    The family check intentionally protects deployments still serving the
    previous np6-2026-03 catalog, where category mastheads are marked active.
    ZNews hides them in its default skin mode and BaoMoi clears them whenever
    category background inventory is live.
    """
    if str(zone.get("lifecycleStatus") or "active").lower() != "active":
        return False
    return zone.get("placementFamily") != CATEGORY_MASTHEAD_FAMILY


def filter_openai_recommendable_zones(zones: Iterable[dict]) -> list[dict]:
    return [zone for zone in zones if is_openai_recommendable_zone(zone)]


def filter_openai_zone_tool_result(result: dict) -> dict:
    """Remove unavailable inventory from an OpenAI list/search tool result."""
    if not isinstance(result, dict) or not isinstance(result.get("zones"), list):
        return result
    filtered = filter_openai_recommendable_zones(result["zones"])
    removed = len(result["zones"]) - len(filtered)
    output = {**result, "zones": filtered}
    if "total" in output:
        output["total"] = max(0, int(output.get("total") or 0) - removed)
    output["retired_inventory_excluded"] = removed
    if "note" in output:
        output["note"] = (
            "Không tìm thấy zone khả dụng."
            if not filtered
            else f"Tìm thấy {len(filtered)} zone khả dụng."
        )
    return output
