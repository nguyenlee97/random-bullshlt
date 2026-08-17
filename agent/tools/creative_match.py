"""
Creative-to-zone assignment scoring.
Banner zones: ratio match on measured-or-reported dimensions.
Skin zones (Phase 3): MEASURED layout (creative_intel) beats the legacy
`"skin" in filename` heuristic; filename remains the last-resort fallback.
"""
from __future__ import annotations
import re


# One shared tolerance for Guided assignment, Autopilot format coverage, and
# final placement ranking.  A 45% ratio delta is useful as a UI warning band,
# but is too loose for an autonomous launch.  Fifteen percent preserves the
# existing manual matcher boundary while still accepting correctly composed
# assets exported at a different pixel size.
STRONG_RATIO_DIFF = 0.02
GOOD_RATIO_DIFF = 0.08
MAX_RATIO_DIFF = 0.15


def _parse_dims(size_str: str) -> tuple[int, int] | None:
    m = re.match(r"(\d+)[xX×](\d+)", size_str or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def dimension_match(
    file_width: int | float,
    file_height: int | float,
    target_width: int | float,
    target_height: int | float,
) -> tuple[str, float | None]:
    """Classify a measured asset against a target rectangle.

    Exact pixels are preferred.  Otherwise the aspect-ratio delta determines
    whether the delivery frame can safely use the asset.  The returned mode is
    intentionally shared with ``zone_ranker`` and Autopilot coverage checks.
    """
    try:
        fw, fh = float(file_width), float(file_height)
        tw, th = float(target_width), float(target_height)
    except (TypeError, ValueError):
        return "unknown_dimensions", None
    if min(fw, fh, tw, th) <= 0:
        return "unknown_dimensions", None
    if fw == tw and fh == th:
        return "exact_size", 0.0
    target_ratio = tw / th
    diff = abs(target_ratio - (fw / fh)) / target_ratio
    if diff < STRONG_RATIO_DIFF:
        return "strong_ratio", diff
    if diff < GOOD_RATIO_DIFF:
        return "same_ratio", diff
    if diff < MAX_RATIO_DIFF:
        return "acceptable_ratio", diff
    return "incompatible_ratio", diff


def _normalized_hint(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower().replace("×", "x"))


def _assignment_platform(value: object) -> str:
    identity = _normalized_hint(value)
    if not identity:
        return ""
    if "znews" in identity or "zingnews" in identity or identity.startswith("zn"):
        return "znews"
    if "baomoi" in identity or "zuma" in identity or identity.startswith("bm"):
        return "baomoi"
    if "zingmp3" in identity or "zmp3" in identity:
        return "zmp3"
    return ""


def _assignment_role(value: object) -> str:
    identity = _normalized_hint(value)
    if not identity:
        return ""
    if "sideleft" in identity or "stickyleft" in identity or identity.endswith("left"):
        return "side_left"
    if "sideright" in identity or "stickyright" in identity or identity.endswith("right"):
        return "side_right"
    if "sidebanner" in identity or "skyscraper" in identity:
        return "side"
    if "background" in identity or "roadblock" in identity:
        return "background"
    if (
        "masthead" in identity
        or "topbanner" in identity
        or "topdesktop" in identity
        or "topmobile" in identity
    ):
        return "masthead"
    if "sidebarbox" in identity or "box300x250" in identity or "zumabox" in identity:
        return "box"
    return ""


def _role_identity_score(zone_role: str, file_role: str) -> int:
    if not zone_role or not file_role:
        return 0
    if zone_role == file_role:
        return 12
    if zone_role in {"side_left", "side_right"} and file_role == "side":
        return 12
    if zone_role == "side" and file_role in {"side_left", "side_right"}:
        return 10
    if (
        (zone_role == "side_left" and file_role == "side_right")
        or (zone_role == "side_right" and file_role == "side_left")
    ):
        return -30
    return -20


def creative_assignment_identity_score(file: dict, zone: dict) -> tuple[int, list[str]]:
    """Score explicit platform, placement role and left/right identity.

    Known platform or direction conflicts are hard negatives. Missing identity
    remains neutral so measured geometry can still act as a safe fallback.
    """
    file_identity = " ".join(str(value or "") for value in (
        file.get("name"),
        file.get("formatId"),
        file.get("intendedFormat"),
    ))
    zone_identity = " ".join(str(value or "") for value in (
        zone.get("id"),
        zone.get("name"),
        zone.get("platform"),
        zone.get("channel"),
        zone.get("placement"),
        zone.get("creativeContractId"),
    ))
    file_platform = _assignment_platform(file_identity)
    zone_platform = _assignment_platform(zone_identity)
    file_role = _assignment_role(file_identity)
    zone_role = _assignment_role(zone_identity)

    score = 0
    warnings: list[str] = []
    if file_platform and zone_platform:
        if file_platform == zone_platform:
            score += 12
        else:
            score -= 40
            warnings.append(
                f"Creative thuộc {file_platform}, không khớp nền tảng {zone_platform}"
            )

    role_score = _role_identity_score(zone_role, file_role)
    score += role_score
    if role_score < 0:
        warnings.append(
            f"Creative role {file_role} không khớp placement role {zone_role}"
        )
    return score, warnings


def match_file_to_format(file: dict, format_spec: dict) -> dict:
    """Match an uploaded file to one planned format.

    A structured ``formatId`` or the canonical format token in the filename is
    explicit operator intent and therefore wins over measured geometry.  Ratio
    remains an advisory in that tier.  Without canonical identity, geometry is
    authoritative and the shared ratio boundary still applies.
    """
    target_width = int(format_spec.get("width") or 0)
    target_height = int(format_spec.get("height") or 0)
    format_id = str(format_spec.get("format_id") or format_spec.get("format_key") or "")
    intended_format = str(format_spec.get("intended_format") or "banner").lower()
    filename_hint = _normalized_hint(file.get("name"))
    format_hint = _normalized_hint(format_id)
    size_hint = _normalized_hint(f"{target_width}x{target_height}")
    canonical_identity = bool(
        (file.get("formatId") and str(file.get("formatId")) == format_id)
        or (format_hint and format_hint in filename_hint)
    )
    weak_size_hint = bool(size_hint and size_hint in filename_hint)
    skin_hint = bool(
        str(file.get("intendedFormat") or "").lower() == "skin"
        or "skin" in filename_hint
        or "background" in filename_hint
        or (file.get("formatId") and str(file.get("formatId")) == format_id)
    )

    intel = file.get("intel") or {}
    width = intel.get("width") or file.get("width") or 0
    height = intel.get("height") or file.get("height") or 0
    mode, ratio_diff = dimension_match(width, height, target_width, target_height)
    if canonical_identity:
        return {
            "matched": True,
            "mode": "explicit_identity",
            "ratio_diff": ratio_diff,
            "explicit_hint": True,
            "ratio_advisory": mode == "incompatible_ratio",
            "measured_mode": mode,
        }
    dimensions_accepted = mode in {
        "exact_size", "strong_ratio", "same_ratio", "acceptable_ratio",
    }

    if intended_format == "skin" and not skin_hint:
        return {"matched": False, "mode": "missing_skin_hint", "ratio_diff": ratio_diff}
    if dimensions_accepted:
        return {
            "matched": True,
            "mode": mode,
            "ratio_diff": ratio_diff,
            "explicit_hint": skin_hint,
        }
    if mode == "unknown_dimensions" and (
        weak_size_hint or (intended_format == "skin" and skin_hint)
    ):
        return {
            "matched": True,
            "mode": "explicit_format_hint",
            "ratio_diff": None,
            "explicit_hint": True,
        }
    return {"matched": False, "mode": mode, "ratio_diff": ratio_diff}


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


def _contract_identity_bonus(file: dict, format_spec: dict) -> int:
    """Prefer explicit format intent when several assets share safe geometry."""
    format_id = str(
        format_spec.get("format_id") or format_spec.get("format_key") or ""
    )
    target_width = int(format_spec.get("width") or 0)
    target_height = int(format_spec.get("height") or 0)
    filename_hint = _normalized_hint(file.get("name"))
    format_hint = _normalized_hint(format_id)
    size_hint = _normalized_hint(f"{target_width}x{target_height}")

    if file.get("formatId") and str(file.get("formatId")) == format_id:
        return 8
    if format_hint and format_hint in filename_hint:
        return 6
    if size_hint and size_hint in filename_hint:
        return 3
    return 0


def high_confidence_assignment_identity(file: dict, zone: dict) -> bool:
    """Return true only for canonical, contract-resolved creative identity."""
    if not zone.get("creativeContractId"):
        return False
    from autopilot.placement_planning import format_spec_for_zone

    spec = format_spec_for_zone(zone)
    if not spec:
        return False
    format_id = str(spec.get("format_id") or spec.get("format_key") or "")
    format_hint = _normalized_hint(format_id)
    filename_hint = _normalized_hint(file.get("name"))
    return bool(
        (file.get("formatId") and str(file.get("formatId")) == format_id)
        or (format_hint and format_hint in filename_hint)
    )


def _ratio_distance_for_zone(file: dict, zone: dict) -> tuple[str, float | None]:
    """Return measured compatibility mode and distance for assignment ordering."""
    intel = file.get("intel") or {}
    width = intel.get("width") or file.get("width") or 0
    height = intel.get("height") or file.get("height") or 0
    target_width = target_height = 0
    if zone.get("creativeContractId"):
        from autopilot.placement_planning import format_spec_for_zone

        spec = format_spec_for_zone(zone) or {}
        target_width = spec.get("width") or 0
        target_height = spec.get("height") or 0
    else:
        dims = _parse_dims(zone.get("size", ""))
        if dims:
            target_width, target_height = dims
    return dimension_match(width, height, target_width, target_height)


def score_file_for_zone(
    file: dict,
    zone: dict,
    *,
    prefer_contract_identity: bool = False,
) -> tuple[int, list[str]]:
    """Score a creative file against a zone. Returns (score, warnings)."""
    score = 0
    warnings: list[str] = []
    fname = (file.get("name") or "").lower()
    intel = file.get("intel") or {}
    identity_score, identity_warnings = creative_assignment_identity_score(file, zone)

    # Phase 3: files flagged needs_review may not be auto-assigned silently
    if intel.get("effective_status", intel.get("status")) == "needs_review":
        warnings.append("Creative đang chờ review (creative-intel) — kiểm tra trước khi book")
        score -= 3

    if zone.get("creativeContractId"):
        from autopilot.placement_planning import format_spec_for_zone

        spec = format_spec_for_zone(zone)
        if not spec:
            return -5, ["Creative contract của placement chưa được hỗ trợ"]
        match = match_file_to_format(file, spec)
        if match.get("matched"):
            mode = match.get("mode")
            if prefer_contract_identity:
                if mode == "explicit_identity":
                    # The contract is the canonical source of truth. Some
                    # intentionally shared formats (for example category
                    # backgrounds) have a legacy publisher name in formatId.
                    # Do not reclassify them as cross-publisher mismatches.
                    score += 100 + _contract_identity_bonus(file, spec)
                    if match.get("ratio_advisory"):
                        warnings.append(
                            "Creative khớp tên/format chuẩn; tỷ lệ đo được lệch "
                            f"{float(match.get('ratio_diff') or 0) * 100:.0f}%"
                        )
                else:
                    score += {
                        "exact_size": 12,
                        "strong_ratio": 10,
                        "same_ratio": 7,
                        "acceptable_ratio": 4,
                        "explicit_format_hint": 1,
                    }.get(mode, 1)
                    score += _contract_identity_bonus(file, spec)
                    score += identity_score
                    warnings.extend(identity_warnings)
            else:
                score += 10 if mode in {
                    "exact_size", "strong_ratio", "explicit_identity",
                } else 7
        else:
            score -= 7
            # Positive name hints must never rescue incompatible measured
            # geometry. Hard identity conflicts still prevent a tied fallback.
            if prefer_contract_identity and identity_score < 0:
                score += identity_score
                warnings.extend(identity_warnings)
            warnings.append(
                f"Creative không khớp contract {zone.get('creativeContractId')} "
                f"({match.get('mode')})"
            )
        return score, warnings

    # Skin zones — measured layout first, filename hack last
    is_skin_zone = zone.get("format") == "skin" or zone.get("size") == "skin"
    if is_skin_zone and prefer_contract_identity:
        score += identity_score
        warnings.extend(identity_warnings)
        zone_role = _assignment_role(
            f"{zone.get('id', '')} {zone.get('name', '')} "
            f"{zone.get('creativeContractId', '')}"
        )
        if zone_role in {"side", "side_left", "side_right"}:
            # Side rails are catalogued as skin inventory but use a dedicated
            # portrait side asset, not a full-page background takeover.
            if _assignment_role(f"{file.get('name', '')} {file.get('formatId', '')}"):
                return score, warnings
            warnings.append("Creative chưa thể hiện rõ role side/left/right")
        elif intel.get("is_skin") is True:
            score += 10
        elif intel.get("is_skin") is False:
            score -= 5
            warnings.append("Ảnh không có layout skin/toàn trang (đo từ pixel thật)")
        elif "skin" in fname:                       # no intel → legacy heuristic
            score += 4
        else:
            score -= 5
            warnings.append("Zone dạng skin, creative nên đặt tên chứa 'skin'")
        return score, warnings
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
    if prefer_contract_identity:
        score += identity_score
        warnings.extend(identity_warnings)
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
        mode, diff = dimension_match(fw, fh, zw, zh)

        if mode in {"exact_size", "strong_ratio"}:
            score += 8
        elif mode == "same_ratio":
            score += 4
        elif mode == "acceptable_ratio":
            score += 1
            warnings.append(f"Tỷ lệ hơi lệch ({diff*100:.0f}%)")
        elif mode == "incompatible_ratio":
            # Preserve the distance so the final fallback deterministically
            # chooses the closest ratio instead of the first uploaded file.
            score = min(score - 4 - round(float(diff or 1) * 100), -4)
            warnings.append(f"Tỷ lệ không phù hợp ({diff*100:.0f}% lệch)")

    file_ext = (file.get("type", "") or fname.rsplit(".", 1)[-1]).lower()
    if zone.get("format") == "video" and "mp4" not in file_ext and "webm" not in file_ext:
        warnings.append("Zone yêu cầu video, creative là ảnh")
        score -= 2

    return score, warnings


def auto_assign(
    zones: list[dict],
    files: list[dict],
    *,
    prefer_contract_identity: bool = False,
) -> dict:
    """
    Auto-assign best creative file to each zone.
    Returns: { assignments: {zoneId: fileIdx}, warnings: [{zoneId, message}], scores: {zoneId: {fileIdx: score}} }
    """
    assignments: dict[str, int] = {}
    all_warnings: list[dict] = []
    scores: dict[str, dict] = {}

    for zone in zones:
        zid = zone["id"]

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

        ranked_candidates = []
        for idx, f in eligible:
            s, w = score_file_for_zone(
                f,
                zone,
                prefer_contract_identity=prefer_contract_identity,
            )
            mode, ratio_diff = _ratio_distance_for_zone(f, zone)
            explicit_identity = (
                prefer_contract_identity
                and high_confidence_assignment_identity(f, zone)
            )
            compatible_ratio = mode in {
                "exact_size", "strong_ratio", "same_ratio", "acceptable_ratio",
            }
            # MongoDB/BSON document keys must be strings. JSON clients already
            # observe object keys as strings, so normalize at the source.
            scores.setdefault(zid, {})[str(idx)] = s
            ranked_candidates.append((
                1 if explicit_identity else 0,
                1 if compatible_ratio else 0,
                -float(ratio_diff) if ratio_diff is not None else float("-inf"),
                s,
                -idx,
                idx,
                w,
                mode,
            ))

        best = max(ranked_candidates)
        _, ratio_safe, _, _, _, best_idx, zone_warnings, _ = best

        assignments[zid] = best_idx
        if not ratio_safe and not high_confidence_assignment_identity(files[best_idx], zone):
            all_warnings.append({
                "zoneId": zid,
                "message": "Dùng creative có tỷ lệ gần nhất để tiếp tục",
                "kind": "closest_ratio_fallback",
            })
        for msg in zone_warnings:
            all_warnings.append({"zoneId": zid, "message": msg})

    fallback_zone_ids = sorted({
        warning["zoneId"] for warning in all_warnings
        if warning.get("kind") == "closest_ratio_fallback"
    })
    return {
        "assignments": assignments,
        "warnings": all_warnings,
        "scores": scores,
        "fallback_zone_ids": fallback_zone_ids,
    }
