"""OpenAI placement inventory policy.

The canonical catalog retains retired placement IDs so historical campaign
snapshots remain resolvable. OpenAI recommendation and selection flows use
this policy to expose only inventory that can render in the normal customer
walkthrough.
"""
from __future__ import annotations

from collections.abc import Iterable


CATEGORY_MASTHEAD_FAMILY = "category_masthead"
CATEGORY_BACKGROUND_FAMILY = "category_background"


def _publisher_key(zone: dict) -> str:
    publisher = str(zone.get("publisher") or zone.get("siteId") or "").lower()
    zone_id = str(zone.get("id") or "").lower()
    if "znews" in publisher or zone_id.startswith("znews_"):
        return "znews"
    if "baomoi" in publisher or zone_id.startswith("baomoi_"):
        return "baomoi"
    return publisher


def is_openai_recommendable_zone(zone: dict) -> bool:
    """Return whether a catalog row can enter an OpenAI placement flow.

    The publisher/family checks protect mixed-version deployments as well as
    the canonical lifecycle state. ZNews category pages use masthead hero
    inventory, while BaoMoi category pages retain their background hero.
    """
    if str(zone.get("lifecycleStatus") or "active").lower() != "active":
        return False
    publisher = _publisher_key(zone)
    family = zone.get("placementFamily")
    if publisher == "znews" and family == CATEGORY_BACKGROUND_FAMILY:
        return False
    if publisher == "baomoi" and family == CATEGORY_MASTHEAD_FAMILY:
        return False
    return True


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
