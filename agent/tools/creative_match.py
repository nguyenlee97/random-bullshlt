"""
Creative-to-zone assignment scoring.
Handles both banner (ratio match) and skin (name match) zones.
"""
from __future__ import annotations
import re


def _parse_dims(size_str: str) -> tuple[int, int] | None:
    m = re.match(r"(\d+)[xX×](\d+)", size_str or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def score_file_for_zone(file: dict, zone: dict) -> tuple[int, list[str]]:
    """Score a creative file against a zone. Returns (score, warnings)."""
    score = 0
    warnings: list[str] = []
    fname = (file.get("name") or "").lower()

    # Skin zones: match on name
    is_skin_zone = zone.get("format") == "skin" or zone.get("size") == "skin"
    if is_skin_zone:
        if "skin" in fname:
            score += 10
        else:
            score -= 5
            warnings.append("Zone dạng skin, creative nên đặt tên chứa 'skin'")
        return score, warnings

    # Banner zones: name + ratio matching
    zone_id_lower = zone.get("id", "").lower()
    zone_size = (zone.get("size") or "").lower()

    if any(part in fname for part in zone_id_lower.split("_")[:2]):
        score += 3
    if zone_size in fname:
        score += 5

    zone_dims = _parse_dims(zone.get("size", ""))
    fw, fh = file.get("width", 0), file.get("height", 0)

    if zone_dims and fw > 0 and fh > 0:
        zw, zh = zone_dims
        z_ratio = zw / zh
        f_ratio = fw / fh
        diff = abs(z_ratio - f_ratio) / z_ratio if z_ratio > 0 else 1

        if diff < 0.02:
            score += 8
        elif diff < 0.08:
            score += 4
        elif diff < 0.15:
            score += 1
            warnings.append(f"Tỷ lệ hơi lệch ({diff*100:.0f}%)")
        else:
            score -= 4
            warnings.append(f"Tỷ lệ không phù hợp ({diff*100:.0f}% lệch)")

    file_ext = (file.get("type", "") or fname.rsplit(".", 1)[-1]).lower()
    if zone.get("format") == "video" and "mp4" not in file_ext and "webm" not in file_ext:
        warnings.append("Zone yêu cầu video, creative là ảnh")
        score -= 2

    return score, warnings


def auto_assign(zones: list[dict], files: list[dict]) -> dict:
    """
    Auto-assign best creative file to each zone.
    Returns: { assignments: {zoneId: fileIdx}, warnings: [{zoneId, message}], scores: {zoneId: {fileIdx: score}} }
    """
    assignments: dict[str, int] = {}
    all_warnings: list[dict] = []
    scores: dict[str, dict] = {}

    for zone in zones:
        zid = zone["id"]
        best_score, best_idx, zone_warnings = -999, 0, []

        for idx, f in enumerate(files):
            s, w = score_file_for_zone(f, zone)
            scores.setdefault(zid, {})[idx] = s
            if s > best_score:
                best_score, best_idx, zone_warnings = s, idx, w

        assignments[zid] = best_idx
        for msg in zone_warnings:
            all_warnings.append({"zoneId": zid, "message": msg})

    return {"assignments": assignments, "warnings": all_warnings, "scores": scores}
