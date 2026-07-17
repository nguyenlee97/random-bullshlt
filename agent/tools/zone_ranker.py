"""
Zone scoring algorithm — Python port of n8n Ad Zone Ranker v4.
Handles both banner (pixel sizes) and skin (format-only match) zones.
Reach is RAW numbers from API (not millions).
"""
from __future__ import annotations
import re

# Objective weights (same as agent_frontend scoring)
OBJECTIVE_WEIGHTS = {
    "awareness":     {"reach": 0.40, "vi": 0.35, "ctr": 0.05, "efficiency": 0.20},
    "consideration": {"reach": 0.30, "vi": 0.35, "ctr": 0.20, "efficiency": 0.15},
    "conversion":    {"reach": 0.10, "vi": 0.20, "ctr": 0.50, "efficiency": 0.20},
    "retention":     {"reach": 0.20, "vi": 0.50, "ctr": 0.20, "efficiency": 0.10},
}

TIER_LABELS = {
    "homepage-masthead": "masthead trang chủ premium",
    "homepage-inline": "banner inline trang chủ",
    "background-skin": "background skin",
    "large-middle-unit": "banner cỡ lớn trong nội dung",
    "content-pr-box": "PR box trong nội dung",
    "homepage-side-left": "side skin trang chủ",
    "homepage-side-right": "side skin trang chủ",
    "category-side-left": "side skin trang chuyên mục",
    "category-side-right": "side skin trang chuyên mục",
    "standard-box": "box tiêu chuẩn",
}


def _parse_dims(size_str: str) -> tuple[int, int] | None:
    m = re.match(r"(\d+)[xX×](\d+)", size_str or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _score_zone(zone: dict, objective: str, max_reach: float) -> float:
    w = OBJECTIVE_WEIGHTS.get(objective, OBJECTIVE_WEIGHTS["awareness"])
    reach_norm = min(zone.get("reach", 0) / (max(max_reach, 1) / 100), 100)
    efficiency = (100000 / zone["cpm"]) if zone.get("cpm", 0) > 0 else 0
    return (
        reach_norm * w["reach"]
        + zone.get("vi", 0) * w["vi"]
        + zone.get("ctr", 0) * w["ctr"]
        + efficiency * w["efficiency"]
    )


def _kpi_bonus(zone: dict, kpi: str, max_reach: float) -> float:
    kpi_lower = (kpi or "").lower()
    bonus = 0.0
    if ("vtr" in kpi_lower or "video" in kpi_lower) and zone.get("format") == "video":
        bonus += 0.15
    if "reach" in kpi_lower or "impress" in kpi_lower:
        bonus += 0.10 * min(zone.get("reach", 0) / max(max_reach, 1), 1)
    if "ctr" in kpi_lower:
        bonus += 0.05 * zone.get("ctr", 0)
    return bonus


def _size_compat(zone: dict, files: list[dict]) -> tuple[float, str]:
    """Score creative-zone size compatibility. Handles skin zones."""
    from tools.creative_match import dimension_match

    if not files:
        return 0.0, "no_creative"

    # Skin zones: match by creative name containing "skin"
    if zone.get("size") == "skin" or zone.get("format") == "skin":
        for f in files:
            intel = f.get("intel") or {}
            if (
                intel.get("is_skin") is True
                or f.get("intendedFormat") == "skin"
                or "skin" in (f.get("name") or "").lower()
            ):
                return 0.20, "skin_match"
        return 0.0, "no_skin_creative"

    zone_dims = _parse_dims(zone.get("size", ""))
    if not zone_dims:
        return 0.0, "no_zone_size"
    zw, zh = zone_dims

    best_bonus, best_mode = -1.0, "no_match"
    for f in files:
        intel = f.get("intel") or {}
        fw = intel.get("width") or f.get("width", 0)
        fh = intel.get("height") or f.get("height", 0)
        if fw <= 0 or fh <= 0:
            continue
        if fw == zw and fh == zh:
            return 0.30, "exact_size"
        mode, diff = dimension_match(fw, fh, zw, zh)
        if mode == "strong_ratio":
            bonus = 0.24
        elif mode == "same_ratio":
            bonus = 0.20
        elif mode == "acceptable_ratio":
            bonus = 0.08
        elif mode == "incompatible_ratio":
            bonus, mode = max(-0.35, 0.12 - float(diff or 1)), "nearest_ratio"
        else:
            bonus = 0.0
        if bonus > best_bonus:
            best_bonus, best_mode = bonus, mode

    return (best_bonus if best_bonus > -1 else 0.0), best_mode


async def rank_zones(
    objective: str,
    budget: float = 0,
    kpi: str = "",
    creative_files: list[dict] | None = None,
    limit: int = 6,
) -> list[dict]:
    """
    Fetch zones from API, score + rank. Returns top `limit`.
    Each result has: score, reason, est_impressions, match_mode.
    """
    from tools.zone_catalog import get_all_zones
    zones = await get_all_zones()
    scored = []
    n = min(limit, len(zones))
    max_reach = max((float(zone.get("reach") or 0) for zone in zones), default=1)

    for zone in zones:
        base = _score_zone(zone, objective, max_reach)
        bonus = _kpi_bonus(zone, kpi, max_reach)
        size_bonus, match_mode = _size_compat(zone, creative_files or [])
        total = base + bonus + size_bonus

        est_imp = None
        if budget > 0 and zone.get("cpm", 0) > 0:
            budget_per_zone = (budget * 1_000_000) / n
            est_imp = round(budget_per_zone / zone["cpm"] * 1000)

        scored.append({
            **zone,
            "score": round(total, 4),
            "reason": (
                f"{TIER_LABELS.get(zone.get('inventoryTier'), 'Inventory')} phù hợp "
                f"mục tiêu {objective}; reach và CPM lấy từ catalog demo có phân tầng."
            ),
            "est_impressions": est_imp,
            "match_mode": match_mode,
        })

    scored.sort(key=lambda z: z["score"], reverse=True)
    return scored[:limit]
