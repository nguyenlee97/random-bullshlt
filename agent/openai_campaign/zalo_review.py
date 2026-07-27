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
    "plan_placement_intent": "Placement shortlist",
    "assign_creatives": "Phân bổ creative",
    "launch_approval": "Xác nhận launch",
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
    lines = [
        f"Danh sách đang chờ duyệt: {len(attrs)} segment"
        + (f" · quy mô cộng gộp khoảng {_compact_number(value.get('size'))}" if value.get("size") else "")
    ]
    for index, item in enumerate(attrs, 1):
        if not isinstance(item, dict):
            continue
        size = _range(item.get("sizeMin"), item.get("sizeMax"))
        line = f"{index}. {_name(item, f'Segment {index}')}"
        if size:
            line += f" · {size}"
        reason = _plain(item.get("reason") or item.get("description"), 105)
        if reason:
            line += f"\n   Lý do: {reason}"
        lines.append(line)
    if not attrs:
        lines.append("Không tìm thấy segment hợp lệ trong artifact đang chờ duyệt.")
    return lines


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
    lines = [f"Shortlist đang chờ duyệt: {len(zones)} placement"]
    for index, zone in enumerate(zones, 1):
        if not isinstance(zone, dict):
            continue
        label = _name(zone, f"Placement {index}")
        identity = _plain(zone.get("id"), 50)
        context = _plain(
            zone.get("channel")
            or zone.get("siteId")
            or zone.get("format")
            or zone.get("size"),
            45,
        )
        details = [item for item in (identity, context) if item]
        metric = []
        if zone.get("cpm") is not None:
            metric.append(f"CPM {_integer(zone.get('cpm'))}đ")
        if zone.get("reach") is not None:
            metric.append(f"reach {_compact_number(zone.get('reach'))}")
        suffix = " · ".join([*details, *metric])
        lines.append(f"{index}. {label}" + (f" · {suffix}" if suffix else ""))
    if zones:
        lines.append("CPM và reach là số liệu catalog/ước tính, không phải delivery thực tế.")
    else:
        lines.append("Không có placement khả dụng trong artifact đang chờ duyệt.")
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
    lines = [f"Phân bổ đang chờ duyệt: {len(assignments)} placement"]
    for index, (zone_id, file_index) in enumerate(assignments.items(), 1):
        zone_label = zone_names.get(str(zone_id), _plain(zone_id, 70))
        try:
            file = files[int(file_index)]
        except (IndexError, TypeError, ValueError):
            file = {}
        creative_name = _name(file, f"Creative #{file_index}") if isinstance(file, dict) else f"Creative #{file_index}"
        lines.append(f"{index}. {zone_label} → {creative_name}")
    warnings = value.get("warnings") or []
    incompatible = value.get("incompatible_placements") or []
    if warnings:
        lines.append(f"⚠ Có {len(warnings)} cảnh báo tương thích creative.")
    if incompatible:
        lines.append("⚠ Chưa tương thích: " + ", ".join(_plain(item, 50) for item in incompatible))
    if not assignments:
        lines.append("Chưa có mapping placement → creative hoàn chỉnh.")
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
        action = "Trả lời “Xác nhận” để duyệt toàn bộ danh sách, “Hủy” để dừng, hoặc hỏi thêm về segment."
    elif key == "derive_targeting":
        lines = _targeting_lines(value)
        action = "Trả lời “Xác nhận” để duyệt targeting, “Hủy” để dừng, hoặc hỏi thêm trước khi quyết định."
    elif key == "plan_placement_intent":
        lines = _placement_lines(value)
        action = "Trả lời “Xác nhận” để duyệt shortlist, “Hủy” để dừng, hoặc mở workspace để thay đổi placement."
    elif key == "assign_creatives":
        lines = _assignment_lines(value, workspace)
        action = "Trả lời “Xác nhận” để duyệt mapping, “Hủy” để dừng, hoặc mở workspace để đối chiếu creative."
    elif key == "launch_approval":
        lines = _launch_lines(value, workspace)
        action = "Trả lời “Xác nhận” để launch hoặc “Hủy” để dừng."
    else:
        lines = [_plain(value.get("message") or "Đầu ra đã sẵn sàng để review.", 300)]
        action = "Trả lời “Xác nhận” để tiếp tục hoặc “Hủy” để dừng."

    footer = action + _workspace_link(workspace_url)
    return _compose(header, lines, footer)
