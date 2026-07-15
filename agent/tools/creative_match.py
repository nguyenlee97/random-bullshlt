"""
Creative-to-zone assignment scoring.
Banner zones: ratio match on measured-or-reported dimensions.
Skin zones (Phase 3): MEASURED layout (creative_intel) beats the legacy
`"skin" in filename` heuristic; filename remains the last-resort fallback.
"""
from __future__ import annotations
import re


def _parse_dims(size_str: str) -> tuple[int, int] | None:
    m = re.match(r"(\d+)[xX×](\d+)", size_str or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def enrich_files_with_intel(files: list[dict], intel_docs: list[dict]) -> list[dict]:
    """Attach creative_intel verdicts to files (matched by url, then name).
    Adds file["intel"] = {is_skin, width, height, status} when available."""
    by_url = {d.get("url"): d for d in intel_docs if d.get("url")}
    by_name = {d.get("name"): d for d in intel_docs if d.get("name")}
    out = []
    for f in files:
        doc = by_url.get(f.get("url")) or by_name.get(f.get("name"))
        if doc:
            det = doc.get("deterministic") or {}
            vlm = doc.get("vlm") or {}
            intended_format = doc.get("intended_format") or f.get("intendedFormat")
            if intended_format in {"skin", "banner", "video"}:
                is_skin = intended_format == "skin"
            else:
                is_skin = vlm.get("is_skin_takeover") if vlm else det.get("is_skin_layout")
            f = {**f, "intel": {
                "is_skin": is_skin,
                "intended_format": intended_format,
                "width": det.get("width"), "height": det.get("height"),
                "status": doc.get("status"),
                "effective_status": doc.get("effective_status", doc.get("status")),
                "analysis_id": doc.get("analysis_id"),
                "review_reasons": doc.get("review_reasons") or [],
                "override": doc.get("override") or {},
            }}
        else:
            f = {**f, "intel": {
                "status": "missing",
                "effective_status": "missing",
                "review_reasons": ["Chưa có creative-intel verdict"],
            }}
        out.append(f)
    return out


def score_file_for_zone(file: dict, zone: dict) -> tuple[int, list[str]]:
    """Score a creative file against a zone. Returns (score, warnings)."""
    score = 0
    warnings: list[str] = []
    fname = (file.get("name") or "").lower()
    intel = file.get("intel") or {}

    # Phase 3: files flagged needs_review may not be auto-assigned silently
    if intel.get("effective_status", intel.get("status")) == "needs_review":
        warnings.append("Creative đang chờ review (creative-intel) — kiểm tra trước khi book")
        score -= 3

    # Skin zones — measured layout first, filename hack last
    is_skin_zone = zone.get("format") == "skin" or zone.get("size") == "skin"
    if is_skin_zone:
        if intel.get("is_skin") is True:
            score += 10
        elif intel.get("is_skin") is False:
            score -= 5
            warnings.append("Ảnh không có layout skin/toàn trang (đo từ pixel thật)")
        elif "skin" in fname:                       # no intel → legacy heuristic
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
    # measured dimensions (real bytes) beat frontend-reported ones
    fw = intel.get("width") or file.get("width", 0)
    fh = intel.get("height") or file.get("height", 0)

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

        eligible = [
            (idx, f) for idx, f in enumerate(files)
            if (f.get("intel") or {}).get(
                "effective_status", (f.get("intel") or {}).get("status", "auto_approved")
            ) in {"auto_approved", "approved_override"}
        ]
        if not eligible:
            all_warnings.append({
                "zoneId": zid,
                "message": "Không có creative đã được phân tích và duyệt để tự động gán",
            })
            scores.setdefault(zid, {})
            continue

        for idx, f in eligible:
            s, w = score_file_for_zone(f, zone)
            # MongoDB/BSON document keys must be strings. JSON clients already
            # observe object keys as strings, so normalize at the source.
            scores.setdefault(zid, {})[str(idx)] = s
            if s > best_score:
                best_score, best_idx, zone_warnings = s, idx, w

        assignments[zid] = best_idx
        for msg in zone_warnings:
            all_warnings.append({"zoneId": zid, "message": msg})

    return {"assignments": assignments, "warnings": all_warnings, "scores": scores}
