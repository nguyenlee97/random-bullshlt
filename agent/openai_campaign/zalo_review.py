"""Deterministic Zalo review summaries for OpenAI Campaign Autopilot.

This module deliberately contains no model calls. A review notification is an
authorization boundary, so the message must be rendered from the exact pending
artifact that will be committed when the operator confirms.
"""
from __future__ import annotations

from typing import Any


_MAX_MESSAGE_LENGTH = 1950

_TASK_TITLES = {
    "retrieve_audience": "Audience đề xuất",
    "derive_targeting": "Targeting đề xuất",
    "plan_placement_intent": "Ad zone đề xuất ban đầu",
    "analyze_creatives": "Kiểm tra creative",
    "assign_creatives": "Phân bổ creative",
    "launch_approval": "Xác nhận launch",
}

_MILESTONE_TITLES = {
    "validate_brief": "Brief đã xác nhận",
    "retrieve_audience": "Audience đã chuẩn bị",
    "derive_targeting": "Targeting đã chuẩn bị",
    "analyze_creatives": "Creative đã kiểm tra",
    "rank_placements": "Ad placement đã chọn",
}

_TARGETING_LABELS = {
    "age": "Độ tuổi",
    "ages": "Độ tuổi",
    "gender": "Giới tính",
    "genders": "Giới tính",
    "geo": "Khu vực",
    "location": "Khu vực",
    "locations": "Khu vực",
    "device": "Thiết bị",
    "devices": "Thiết bị",
    "exclude": "Loại trừ",
    "exclusions": "Loại trừ",
}


def _artifact(workspace: dict, name: str) -> Any:
    return ((workspace.get("artifacts") or {}).get(name) or {}).get("value")


def _task_value(task: dict) -> dict:
    pending = (task.get("pending_artifact") or {}).get("value")
    value = pending if pending is not None else task.get("result")
    return value if isinstance(value, dict) else {}


def _plain(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def _integer(value: Any) -> str:
    try:
        return f"{round(float(value)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _compact_number(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "0"
    absolute = abs(number)
    if absolute >= 1_000_000_000:
        scaled, suffix = number / 1_000_000_000, "tỷ"
    elif absolute >= 1_000_000:
        scaled, suffix = number / 1_000_000, "triệu"
    elif absolute >= 1_000:
        scaled, suffix = number / 1_000, "nghìn"
    else:
        return _integer(number)
    rendered = f"{scaled:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{rendered} {suffix}"


def _range(low: Any, high: Any) -> str:
    try:
        low_number = float(low or 0)
        high_number = float(high or 0)
    except (TypeError, ValueError):
        return ""
    if low_number <= 0 and high_number <= 0:
        return ""
    if low_number > 0 and high_number > 0 and low_number != high_number:
        return f"{_compact_number(low_number)}–{_compact_number(high_number)}"
    return _compact_number(high_number or low_number)


def _name(item: dict, fallback: str) -> str:
    return _plain(
        item.get("fullLabel")
        or item.get("label")
        or item.get("name")
        or item.get("code")
        or item.get("_id")
        or fallback,
        100,
    )


def _workspace_link(url: str | None) -> str:
    clean = str(url or "").strip()
    return f"\nXem hoặc chỉnh chi tiết trên workspace: {clean}" if clean else ""


def _compose(header: str, lines: list[str], footer: str) -> str:
    """Keep review instructions intact even when a catalog payload is large."""
    chosen: list[str] = [header]
    suffix = "\n" + footer.strip()
    omitted = 0
    for index, line in enumerate(lines):
        candidate = "\n".join([*chosen, line]) + suffix
        if len(candidate) > _MAX_MESSAGE_LENGTH:
            omitted = len(lines) - index
            break
        chosen.append(line)
    if omitted:
        omission = f"… còn {omitted} mục; mở workspace để xem đầy đủ."
        while len("\n".join([*chosen, omission]) + suffix) > _MAX_MESSAGE_LENGTH and len(chosen) > 1:
            chosen.pop()
            omitted += 1
            omission = f"… còn {omitted} mục; mở workspace để xem đầy đủ."
        chosen.append(omission)
    return "\n".join(chosen) + suffix


def _audience_lines(value: dict) -> list[str]:
    attrs = value.get("attrs") or []
    adjacent = value.get("adjacent_attrs") or []
    if value.get("clarification_required"):
        return [
            "Agent chưa chọn audience vì brief chưa nêu đủ sản phẩm/dịch "
            "vụ, ngành hoặc người mua cụ thể.",
            value.get("clarification_prompt")
            or "Hãy bổ sung thông tin brief trên workspace rồi chạy lại audience.",
        ]
    selection_required = bool(value.get("selection_required"))
    candidates = (
        value.get("recommendations")
        or [*attrs, *adjacent]
        if selection_required else attrs
    )
    heading = (
        f"Danh sách audience đề xuất: {len(candidates)} segment"
        if selection_required
        else f"Audience đã chọn: {len(candidates)} segment"
    )
    if not selection_required and value.get("size"):
        heading += f" · quy mô cộng gộp khoảng {_compact_number(value.get('size'))}"
    lines = [heading]
    for index, item in enumerate(candidates, 1):
        if not isinstance(item, dict):
            continue
        size = _range(item.get("sizeMin"), item.get("sizeMax"))
        line = f"{index}. {_name(item, f'Segment {index}')}"
        if size:
            line += f" · {size}"
        lines.append(line)
    if not candidates:
        lines.append("Không tìm thấy segment hợp lệ trong artifact đang chờ duyệt.")
    return lines


def _brief_lines(value: dict, workspace: dict) -> list[str]:
    brief = _artifact(workspace, "brief") or value.get("brief") or {}
    objective_labels = {
        "awareness": "Nhận diện",
        "consideration": "Cân nhắc",
        "conversion": "Chuyển đổi",
        "retention": "Duy trì",
    }
    return [
        f"• Thương hiệu: {_plain(brief.get('brand') or '—', 100)}",
        f"• Mục tiêu: {objective_labels.get(brief.get('objective'), _plain(brief.get('objective') or '—', 60))}",
        f"• KPI: {_plain(brief.get('kpi') or '—', 160)}",
        f"• Ngân sách: {_integer(brief.get('budget'))} triệu VND",
        f"• Thời gian: {brief.get('startDate') or '—'} → {brief.get('endDate') or '—'}",
    ]


def _targeting_lines(value: dict) -> list[str]:
    lines = ["Targeting sẽ được áp dụng:"]
    for dimension, raw_values in value.items():
        if raw_values is None or raw_values == []:
            continue
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        rendered = ", ".join(_plain(item, 70) for item in values)
        label = _TARGETING_LABELS.get(str(dimension).lower(), str(dimension))
        lines.append(f"• {label}: {rendered}")
    if len(lines) == 1:
        lines.append("Artifact targeting hiện không có giá trị.")
    return lines


def _placement_lines(value: dict) -> list[str]:
    zones = value.get("candidates") or value.get("zones") or []
    lines = [
        f"Danh sách ad zone ứng viên đang chờ duyệt: {len(zones)} zone",
        "Đây là danh sách ban đầu trước khi kiểm tra creative; bước sau sẽ lọc "
        "lại độ tương thích trước khi phân bổ creative.",
        "Thứ tự ưu tiên dựa trên độ khớp brief/audience, strategy, CPM/reach "
        "và inventory còn trống.",
    ]
    for index, zone in enumerate(zones, 1):
        if not isinstance(zone, dict):
            continue
        label = _plain(_name(zone, f"Ad zone {index}"), 44)
        metric = []
        if zone.get("cpm") is not None:
            metric.append(f"CPM {_integer(zone.get('cpm'))}đ")
        if zone.get("reach") is not None:
            metric.append(f"reach {_compact_number(zone.get('reach'))}")
        line = f"{index}. {label}"
        if metric:
            line += " · " + " · ".join(metric)
        relevance = zone.get("topic_relevance") or {}
        matched = (
            relevance.get("matched_keywords")
            or relevance.get("matched_segments")
            or relevance.get("matched_subcategories")
            or relevance.get("matched_topics")
            or []
        )
        reason = ", ".join(_plain(item, 24) for item in matched[:2])
        if reason:
            line += f" · khớp: {reason}"
        lines.append(line)
    if zones:
        lines.append(
            "Gợi ý: CPM thấp giúp ngân sách mua được nhiều lượt hiển thị hơn; "
            "reach cao giúp phủ rộng hơn. Cả hai là dữ liệu catalog/ước tính, "
            "không phải delivery thực tế."
        )
    else:
        lines.append("Không có ad zone khả dụng trong artifact đang chờ duyệt.")
    return lines


def _ranked_placement_lines(value: dict) -> list[str]:
    zones = value.get("zones") or []
    lines = [f"Ad placement đã chọn: {len(zones)} zone"]
    for index, zone in enumerate(zones, 1):
        if not isinstance(zone, dict):
            continue
        label = _plain(_name(zone, f"Ad zone {index}"), 60)
        details = [
            _plain(zone.get("channel"), 35),
            _plain(zone.get("format"), 35),
        ]
        if zone.get("cpm") is not None:
            details.append(f"CPM {_integer(zone.get('cpm'))}đ")
        if zone.get("reach") is not None:
            details.append(f"reach {_compact_number(zone.get('reach'))}")
        details = [item for item in details if item]
        lines.append(
            f"{index}. {label}" + (f" · {' · '.join(details)}" if details else "")
        )
    if not zones:
        lines.append("Chưa có ad placement khả dụng.")
    return lines


def _assignment_lines(value: dict, workspace: dict) -> list[str]:
    assignments = value.get("assignments", value)
    assignments = assignments if isinstance(assignments, dict) else {}
    creative = _artifact(workspace, "creative") or {}
    files = creative.get("files") or []
    placements = _artifact(workspace, "placements") or {}
    intent = _artifact(workspace, "placement_intent") or {}
    zones = [*(placements.get("zones") or []), *(intent.get("candidates") or [])]
    zone_names = {
        str(item.get("id")): _name(item, str(item.get("id")))
        for item in zones
        if isinstance(item, dict) and item.get("id")
    }
    verdict_value = _artifact(workspace, "creative_verdict") or {}
    verdicts = verdict_value.get("files") or []
    unique_indexes = list(dict.fromkeys(
        file_index for file_index in assignments.values()
        if isinstance(file_index, int)
    ))
    labels = {
        file_index: f"Creative {chr(65 + position)}"
        for position, file_index in enumerate(unique_indexes)
    }
    lines = [f"Phân bổ đang chờ duyệt: {len(assignments)} ad zone"]
    for index, (zone_id, file_index) in enumerate(assignments.items(), 1):
        zone_label = zone_names.get(str(zone_id), _plain(zone_id, 70))
        try:
            file = files[int(file_index)]
        except (IndexError, TypeError, ValueError):
            file = {}
        creative_label = labels.get(file_index, f"Creative #{file_index}")
        size = (
            f"{file.get('width')}×{file.get('height')}"
            if isinstance(file, dict) and file.get("width") and file.get("height")
            else ""
        )
        lines.append(
            f"{index}. {zone_label} → {creative_label}"
            + (f" ({size})" if size else "")
        )
    if unique_indexes:
        lines.append("Creative dùng trong phân bổ:")
    status_labels = {
        "auto_approved": "đạt kiểm tra",
        "approved_override": "đã duyệt thủ công",
        "needs_review": "cần duyệt thủ công",
    }
    for file_index in unique_indexes:
        try:
            file = files[int(file_index)]
        except (IndexError, TypeError, ValueError):
            continue
        verdict = next(
            (
                item for item in verdicts
                if item.get("analysis_id") == file.get("analysisId")
                or (item.get("url") and item.get("url") == file.get("url"))
                or (item.get("name") and item.get("name") == file.get("name"))
            ),
            {},
        )
        status = (
            verdict.get("effective_status")
            or verdict.get("status")
            or file.get("analysisStatus")
            or "chưa có verdict"
        )
        lines.append(
            f"• {labels[file_index]}: "
            f"{file.get('formatId') or file.get('name') or 'asset'} · "
            f"{status_labels.get(status, status)}"
        )
        reasons = verdict.get("review_reasons") or file.get("reviewReasons") or []
        if reasons and status not in {"auto_approved", "approved_override"}:
            lines.append("  Cảnh báo: " + "; ".join(
                _plain(reason, 120) for reason in reasons[:2]
            ))
    warnings = value.get("warnings") or []
    incompatible = value.get("incompatible_placements") or []
    if warnings:
        lines.append(f"⚠ Có {len(warnings)} cảnh báo tương thích creative.")
    if incompatible:
        lines.append("⚠ Chưa tương thích: " + ", ".join(_plain(item, 50) for item in incompatible))
    if not assignments:
        lines.append("Chưa có mapping placement → creative hoàn chỉnh.")
    return lines


def assignment_media_parts(value: dict, workspace: dict) -> list[dict]:
    """Return each assigned image once, in the same A/B order as the summary."""
    assignments = value.get("assignments", value)
    assignments = assignments if isinstance(assignments, dict) else {}
    creative = _artifact(workspace, "creative") or {}
    files = creative.get("files") or []
    parts = []
    seen = set()
    for file_index in assignments.values():
        try:
            file = files[int(file_index)]
        except (IndexError, TypeError, ValueError):
            continue
        url = str(file.get("url") or "").strip()
        if not url.startswith("https://") or url in seen:
            continue
        seen.add(url)
        parts.append({"kind": "image", "image_url": url})
    return parts


def creative_media_parts(workspace: dict) -> list[dict]:
    creative = _artifact(workspace, "creative") or {}
    files = creative.get("files") or []
    parts = []
    seen = set()
    for file in files:
        if not isinstance(file, dict):
            continue
        url = str(file.get("url") or "").strip()
        if not url.startswith("https://") or url in seen:
            continue
        seen.add(url)
        parts.append({"kind": "image", "image_url": url})
    return parts


def _creative_analysis_lines(value: dict, workspace: dict) -> list[str]:
    creative = _artifact(workspace, "creative") or {}
    files = creative.get("files") or []
    verdict_value = _artifact(workspace, "creative_verdict") or {}
    verdicts = verdict_value.get("files") or []
    if value.get("reason") == "analysis_in_progress":
        return [
            f"Agent đang kiểm tra {len(files)} creative.",
            "Bạn không cần xác nhận khi phân tích chưa xong. Agent sẽ gửi kết quả "
            "hoặc cảnh báo cần duyệt ngay khi hoàn tất.",
        ]
    status_labels = {
        "auto_approved": "đạt kiểm tra",
        "approved_override": "đã duyệt",
        "needs_review": "cần kiểm tra",
    }
    lines = [f"Kết quả kiểm tra creative: {len(files)} file"]
    for index, file in enumerate(files, 1):
        verdict = next(
            (
                item for item in verdicts
                if item.get("analysis_id") == file.get("analysisId")
                or (item.get("url") and item.get("url") == file.get("url"))
                or (item.get("name") and item.get("name") == file.get("name"))
            ),
            {},
        )
        status = verdict.get("effective_status") or verdict.get("status") or "chưa có kết quả"
        lines.append(
            f"{index}. Creative {index} · {status_labels.get(status, status)}"
        )
        reasons = verdict.get("review_reasons") or []
        if reasons:
            lines.append("   Cảnh báo: " + "; ".join(
                _plain(reason, 120) for reason in reasons[:2]
            ))
    return lines


def _launch_lines(value: dict, workspace: dict) -> list[str]:
    brief = _artifact(workspace, "brief") or {}
    audience = _artifact(workspace, "audience") or {}
    targeting = _artifact(workspace, "targeting") or {}
    summary = value.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    placements_value = _artifact(workspace, "placements") or {}
    placements = placements_value.get("selectedZoneIds") or placements_value.get("selected_zone_ids") \
        or placements_value.get("zones") or summary.get("placements") or []
    placement_ids = [
        str(item.get("id")) if isinstance(item, dict) else str(item)
        for item in placements
    ]
    forecast = _artifact(workspace, "forecast") or {}
    guard_task = next(
        (item for item in workspace.get("_run_tasks", []) if item.get("key") == "run_order_guard"),
        {},
    )
    guard = guard_task.get("result") or {}
    brand = brief.get("brand") or summary.get("brand") or "—"
    budget_million = brief.get("budget")
    if budget_million is None:
        raw_budget = summary.get("budget")
        try:
            budget_million = float(raw_budget or 0) / 1_000_000
        except (TypeError, ValueError):
            budget_million = 0
    attrs = audience.get("attrs") or []
    target_summary = []
    for key in ("age", "gender", "geo", "device"):
        raw = targeting.get(key)
        if raw:
            values = raw if isinstance(raw, list) else [raw]
            target_summary.append(f"{_TARGETING_LABELS.get(key, key)}: {', '.join(map(str, values))}")
    lines = [
        "Kiểm tra lần cuối trước khi tạo order:",
        f"• Thương hiệu: {_plain(brand, 100)}",
        f"• Ngân sách: {_integer(budget_million)} triệu VND",
        f"• Thời gian: {brief.get('startDate') or '—'} → {brief.get('endDate') or '—'}",
        f"• Audience: {len(attrs)} segment",
        f"• Placement: {len(placement_ids)}"
        + (f" ({', '.join(_plain(item, 35) for item in placement_ids[:6])}"
           + (", …" if len(placement_ids) > 6 else "") + ")" if placement_ids else ""),
    ]
    if target_summary:
        lines.append("• Targeting: " + "; ".join(target_summary))
    if forecast:
        lines.append(
            "• Forecast ước tính: "
            f"reach {_compact_number(forecast.get('estimated_reach'))}, "
            f"impression {_compact_number(forecast.get('estimated_impressions'))}"
        )
    if guard:
        lines.append(f"• Kiểm tra an toàn order: {'Đạt' if guard.get('passed') else 'Không đạt'}")
    lines.append("⚠ “Xác nhận” ở bước này sẽ tạo và kích hoạt order.")
    return lines


def render_openai_review_message(
    run: dict,
    task: dict,
    *,
    workspace: dict | None = None,
    workspace_url: str | None = None,
) -> str:
    """Render the exact pending checkpoint without changing run state."""
    workspace = dict(workspace or {})
    workspace["_run_tasks"] = run.get("tasks") or []
    key = str(task.get("key") or "")
    value = _task_value(task)
    title = _TASK_TITLES.get(key, task.get("title") or key or "Checkpoint")
    header = f"Autopilot {run.get('run_id') or '—'} đang chờ duyệt: {title}"

    if key == "retrieve_audience":
        lines = _audience_lines(value)
        if value.get("clarification_required"):
            action = (
                "Chưa thể xác nhận bước này. Hãy mở workspace, bổ sung thông tin "
                "sản phẩm/người mua trong brief và chạy lại Autopilot."
            )
        elif value.get("selection_required"):
            action = (
                "Nhắn audience bạn muốn chọn bằng số hoặc tên, rồi gửi “Xác nhận” "
                "riêng để duyệt. Nhắn “Gợi ý lại audience” để nhận danh sách mới, "
                "hoặc “Hủy” để dừng."
            )
        else:
            action = (
                "Trả lời “Xác nhận” để duyệt audience đang được chọn. "
                "Nhắn audience khác bằng số hoặc tên để thay danh sách, rồi gửi "
                "“Xác nhận” riêng. Nhắn "
                "“Gợi ý lại audience” để Agent truy xuất danh sách mới, hoặc “Hủy” để dừng."
            )
    elif key == "derive_targeting":
        lines = _targeting_lines(value)
        action = "Trả lời “Xác nhận” để duyệt targeting, “Hủy” để dừng, hoặc hỏi thêm trước khi quyết định."
    elif key == "plan_placement_intent":
        lines = _placement_lines(value)
        action = (
            "Bạn có thể nhắn “Chọn zone 1,2,3” để chỉ giữ các zone đó; "
            "sau khi chỉnh, nhắn “Xác nhận” riêng để duyệt. Nhắn “Hủy” để dừng "
            "hoặc mở workspace để thay đổi ad zone."
        )
    elif key == "analyze_creatives":
        lines = _creative_analysis_lines(value, workspace)
        action = (
            "Nhắn “Xem creative” để nhận ảnh. Nếu một creative cần duyệt thủ công, "
            "hãy thay/tạo lại hoặc nhắn “Chấp nhận creative 1 vì …” với lý do cụ thể. "
            "Nhắn “Hủy” để dừng."
        )
    elif key == "assign_creatives":
        lines = _assignment_lines(value, workspace)
        action = (
            "Các ảnh được gửi ngay sau tin nhắn này. Trả lời “Xác nhận” để duyệt "
            "phân bổ, “Xem creative” để nhận lại ảnh, “Hủy” để dừng, hoặc mở "
            "workspace để chỉnh creative. Creative có cảnh báo phải được thay thế "
            "hoặc duyệt thủ công kèm lý do trước khi xác nhận."
        )
    elif key == "launch_approval":
        lines = _launch_lines(value, workspace)
        action = "Trả lời “Xác nhận” để launch hoặc “Hủy” để dừng."
    else:
        lines = [_plain(value.get("message") or "Đầu ra đã sẵn sàng để review.", 300)]
        action = "Trả lời “Xác nhận” để tiếp tục hoặc “Hủy” để dừng."

    footer = action + _workspace_link(workspace_url)
    return _compose(header, lines, footer)


def render_openai_milestone_message(
    run: dict,
    task: dict,
    *,
    workspace: dict | None = None,
    workspace_url: str | None = None,
) -> str:
    """Render an informational milestone without introducing an approval gate."""
    workspace = dict(workspace or {})
    key = str(task.get("key") or "")
    value = _task_value(task)
    header = (
        f"Autopilot {run.get('run_id') or '—'}: "
        f"{_MILESTONE_TITLES.get(key, task.get('title') or key)}"
    )
    if key == "validate_brief":
        lines = _brief_lines(value, workspace)
    elif key == "retrieve_audience":
        lines = _audience_lines(value)
    elif key == "derive_targeting":
        lines = _targeting_lines(value)
    elif key == "analyze_creatives":
        lines = _creative_analysis_lines(value, workspace)
    elif key == "rank_placements":
        lines = _ranked_placement_lines(value)
    else:
        lines = [_plain(value.get("message") or "Đầu ra đã sẵn sàng.", 300)]
    footer = "Đây là cập nhật thông tin; Autopilot đang tự tiếp tục." + _workspace_link(
        workspace_url
    )
    return _compose(header, lines, footer)
