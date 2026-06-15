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

# Per-zone reason templates (zone id → Vietnamese reason)
ZONE_REASONS: dict[str, str] = {
    "ZingNews_Masthead":        "Vị trí đầu trang ZingNews, phủ rộng 2.4M — premium awareness.",
    "ZingNews_Masthead_Inline_1": "Inline masthead ZingNews, VI 66% — tốt cho consideration.",
    "ZingNews_Halfpage":        "Halfpage 300×600 ZingNews, VI 61% — hiển thị lâu.",
    "ZingNews_PrBox_2":         "PR Box ZingNews, CTR 0.55% + conversion fit.",
    "BaoMoi_Masthead":          "BaoMoi Masthead, reach 38M — phủ rộng nhất toàn catalog.",
    "BaoMoi_Background":        "BaoMoi Skin Background, VI 70% + CTR 1.25% — consideration.",
    "BaoMoi_StickyLeft":        "BaoMoi Sticky Left, CTR 1.6% cao — conversion tốt.",
    "BaoMoi_StickyRight":       "BaoMoi Sticky Right, VI 93% — brand recall cao.",
    "BaoMoi_Box1":              "BaoMoi Box1 300×250, CPM 15K — tiết kiệm ngân sách.",
    "BaoMoi_Box2":              "BaoMoi Box2 300×600, CPM 13K rẻ nhất — phủ rộng budget thấp.",
    "ZingMP3_Masthead":         "ZingMP3 Masthead, VI 97% + CTR 1.4% — cao nhất catalog.",
    "Znews_CongNghe_Background": "Skin Tech ZingNews, VI 92% — brand recall premium.",
    "Znews_TheThao_Background":  "Skin Sports, reach 2.2M — phủ audience thể thao.",
    "Znews_GiaiTri_Background":  "Skin Giải Trí, reach 2M — lifestyle brands.",
    "Znews_DoiSong_Background":  "Skin Đời Sống, reach 1.85M — FMCG/lifestyle.",
    "Znews_SucKhoe_Background":  "Skin Sức Khoẻ, reach 1.75M — healthcare brands.",
    "Znews_KinhDoanh_Background":"Skin Kinh Doanh, VI 100% — B2B/finance premium.",
    "Znews_CongNghe_SidebarBox": "Sidebar Tech 300×250, CTR 0.9% — conversion Tech.",
    "Znews_TheThao_SidebarBox":  "Sidebar Sports, VI 95% — awareness sports.",
    "Znews_GiaiTri_SidebarBox":  "Sidebar Giải Trí, CTR 1.05% — consideration entertainment.",
    "Znews_SucKhoe_SidebarBox":  "Sidebar Sức Khoẻ, reach 20M — healthcare.",
    "Znews_DoiSong_SidebarBox":  "Sidebar Đời Sống, CPM 16K — tối ưu ngân sách.",
    "Znews_KinhDoanh_SidebarBox":"Sidebar Kinh Doanh, CPM 14K — B2B cost-efficient.",
}

_MAX_REACH = 38_000_000  # BaoMoi_Masthead — used for normalization


def _parse_dims(size_str: str) -> tuple[int, int] | None:
    m = re.match(r"(\d+)[xX×](\d+)", size_str or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _score_zone(zone: dict, objective: str) -> float:
    w = OBJECTIVE_WEIGHTS.get(objective, OBJECTIVE_WEIGHTS["awareness"])
    reach_norm = min(zone.get("reach", 0) / (_MAX_REACH / 100), 100)
    efficiency = (100000 / zone["cpm"]) if zone.get("cpm", 0) > 0 else 0
    return (
        reach_norm * w["reach"]
        + zone.get("vi", 0) * w["vi"]
        + zone.get("ctr", 0) * w["ctr"]
        + efficiency * w["efficiency"]
    )


def _kpi_bonus(zone: dict, kpi: str) -> float:
    kpi_lower = (kpi or "").lower()
    bonus = 0.0
    if ("vtr" in kpi_lower or "video" in kpi_lower) and zone.get("format") == "video":
        bonus += 0.15
    if "reach" in kpi_lower or "impress" in kpi_lower:
        bonus += 0.10 * min(zone.get("reach", 0) / _MAX_REACH, 1)
    if "ctr" in kpi_lower:
        bonus += 0.05 * zone.get("ctr", 0)
    return bonus


def _size_compat(zone: dict, files: list[dict]) -> tuple[float, str]:
    """Score creative-zone size compatibility. Handles skin zones."""
    if not files:
        return 0.0, "no_creative"

    # Skin zones: match by creative name containing "skin"
    if zone.get("size") == "skin" or zone.get("format") == "skin":
        for f in files:
            if "skin" in (f.get("name") or "").lower():
                return 0.20, "skin_match"
        return 0.0, "no_skin_creative"

    zone_dims = _parse_dims(zone.get("size", ""))
    if not zone_dims:
        return 0.0, "no_zone_size"
    zw, zh = zone_dims
    zone_ratio = zw / zh

    best_bonus, best_mode = -1.0, "no_match"
    for f in files:
        fw, fh = f.get("width", 0), f.get("height", 0)
        if fw <= 0 or fh <= 0:
            continue
        if fw == zw and fh == zh:
            return 0.30, "exact_size"
        diff = abs(zone_ratio - fw / fh) / zone_ratio
        if diff <= 0.03:
            bonus, mode = 0.20, "same_ratio"
        else:
            bonus, mode = max(-0.35, 0.12 - diff), "nearest_ratio"
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

    for zone in zones:
        base = _score_zone(zone, objective)
        bonus = _kpi_bonus(zone, kpi)
        size_bonus, match_mode = _size_compat(zone, creative_files or [])
        total = base + bonus + size_bonus

        est_imp = None
        if budget > 0 and zone.get("cpm", 0) > 0:
            budget_per_zone = (budget * 1_000_000) / n
            est_imp = round(budget_per_zone / zone["cpm"] * 1000)

        scored.append({
            **zone,
            "score": round(total, 4),
            "reason": ZONE_REASONS.get(zone["id"], f"Phù hợp mục tiêu {objective}."),
            "est_impressions": est_imp,
            "match_mode": match_mode,
        })

    scored.sort(key=lambda z: z["score"], reverse=True)
    return scored[:limit]
