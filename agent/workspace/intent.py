"""Structured intent and deterministic domain commands for Campaign Copilot.

The model may classify a request and name user-provided references. It never
supplies authoritative campaign objects. Segment, targeting, zone, creative,
and assignment values are resolved and validated here before a durable
proposal can be created. Nothing in this module mutates a workspace directly.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date
import json
import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, Field

from config import config
from graph.structured import StructuredOutputError, structured
from tools.audience_library import get_all_segments, search_audience
from tools.order_api import fetch_zone_conflicts
from tools.targeting_options import get_targeting_options
from tools.zone_catalog import get_all_zones


WorkspaceField = Literal[
    "brief",
    "brief.brand",
    "brief.objective",
    "brief.kpi",
    "brief.budget",
    "brief.startDate",
    "brief.endDate",
    "brief.notes",
    "segment",
    "targeting",
    "creative.files",
    "setup.selectedZoneIds",
    "assignments",
    "none",
]
WorkspaceCommand = Literal[
    "set_brief_field",       # compatibility alias during migration
    "set_brief_fields",
    "select_audience_segments",
    "set_targeting_rules",
    "select_placements",
    "select_creative_files",
    "set_assignments",
    "none",
]
WorkspaceOperation = Literal["set", "replace", "add", "remove", "none"]


class WorkspaceIntent(BaseModel):
    """Strict command envelope returned by the intent model."""

    intent: Literal["propose_change", "other"]
    command: WorkspaceCommand
    field: WorkspaceField
    operation: WorkspaceOperation = "set"
    value: Any = None
    reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_clarification: bool = False
    clarification: str = ""

    model_config = {"extra": "forbid"}


class InvalidWorkspaceIntent(ValueError):
    """The model proposed a command that is unsafe or under-specified."""


_EDIT_VERBS = (
    "doi", "thay", "thay doi", "chuyen", "sua", "cap nhat", "chinh", "dat", "them", "bo",
    "xoa", "muon", "can", "gan", "chon", "giu", "update", "change", "set",
    "replace", "remove", "assign", "attach",
)
_WORKSPACE_TERMS = (
    "brand", "thuong hieu", "brief", "ngan sach", "budget", "muc tieu",
    "objective", "kpi", "ngay bat dau", "ngay ket thuc", "start date",
    "end date", "ghi chu", "notes", "audience", "doi tuong", "segment",
    "dmp", "targeting", "geo", "do tuoi", "gender", "gioi tinh", "device",
    "interest", "creative", "file", "anh", "video", "zone", "placement",
    "vi tri", "setup", "assignment",
    "zingnews", "znews", "baomoi", "zmp3", "masthead", "prbox", "sidebar",
)

_DECLINE_PHRASES = (
    "khong dong y", "khong ap dung", "dung doi", "dung thay", "khong doi",
    "khong thay doi", "tu choi de xuat", "huy de xuat",
)


def _plain(text: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD", text.lower().translate(str.maketrans({"đ": "d", "Đ": "D"}))
    )
    return " ".join(
        "".join(ch for ch in normalized if not unicodedata.combining(ch)).split()
    )


def looks_like_workspace_edit(message: str) -> bool:
    """Cheap prefilter so ordinary chat does not pay for a second model call."""
    text = _plain(message)
    return any(verb in text for verb in _EDIT_VERBS) and any(
        term in text for term in _WORKSPACE_TERMS
    )


def looks_like_brief_edit(message: str) -> bool:
    """Compatibility alias retained for the initial Copilot regression tests."""
    return looks_like_workspace_edit(message)


def is_explicit_decline(message: str) -> bool:
    text = _plain(message)
    return any(phrase in text for phrase in _DECLINE_PHRASES)


def _artifact_value(workspace: dict, artifact: str) -> Any:
    return deepcopy(
        workspace.get("artifacts", {}).get(artifact, {}).get("value")
    )


def _compact_context(workspace_or_brief: dict) -> dict:
    if "artifacts" not in workspace_or_brief:
        return {"brief": workspace_or_brief or {}}
    artifacts = workspace_or_brief.get("artifacts", {})
    audience = artifacts.get("audience", {}).get("value") or {}
    creative = artifacts.get("creative", {}).get("value") or {}
    placements = artifacts.get("placements", {}).get("value") or {}
    assignments = artifacts.get("assignments", {}).get("value") or {}
    return {
        "revision": workspace_or_brief.get("revision", 0),
        "brief": artifacts.get("brief", {}).get("value") or {},
        "audience": [
            {
                "_id": str(item.get("_id", "")),
                "segmentId": item.get("segmentId", ""),
                "fullLabel": item.get("fullLabel") or item.get("name", ""),
            }
            for item in audience.get("attrs", [])
        ],
        "targeting": artifacts.get("targeting", {}).get("value") or {},
        "creative": [
            {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "analysisId": item.get("analysisId", ""),
                "analysisStatus": item.get("analysisStatus", ""),
            }
            for item in creative.get("files", [])
        ],
        "placements": placements.get("selectedZoneIds", []),
        "assignments": assignments,
    }


def _messages(message: str, workspace: dict) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "Bạn là bộ phân loại lệnh chỉnh sửa workspace quảng cáo. Chỉ trả "
                "propose_change khi người dùng yêu cầu áp dụng một thay đổi cụ thể "
                "ngay bây giờ. Câu hỏi hướng dẫn, giả định, phủ định, hoặc chỉ thảo "
                "luận phải là other. Không suy diễn giá trị người dùng chưa nói. "
                "Nếu thiếu field hoặc giá trị mới, đặt requires_clarification=true. "
                "Dùng đúng command/field sau: set_brief_fields -> brief hoặc "
                "brief.*; select_audience_segments -> segment; set_targeting_rules "
                "-> targeting; select_placements -> setup.selectedZoneIds; "
                "select_creative_files -> creative.files; set_assignments -> "
                "assignments. Với danh sách, operation là replace/add/remove và value "
                "là danh sách ID hoặc tên CHÍNH XÁC người dùng nêu. Với targeting, "
                "value là object dimension -> list values. Với assignments, value là "
                "object zone ID/tên -> creative ID/tên. Không tạo ID hoặc catalog "
                "object. objective chỉ là awareness, consideration, conversion hoặc "
                "retention; budget là số triệu VND; ngày theo YYYY-MM-DD. Khi nhiều "
                "trường brief đổi, dùng field=brief và chỉ gồm trường được nêu."
            ),
        },
        {
            "role": "system",
            "content": "Workspace hiện tại (rút gọn): " + json.dumps(
                _compact_context(workspace), ensure_ascii=False, default=str
            ),
        },
        {"role": "user", "content": message},
    ]


def _classify_sync(message: str, workspace: dict) -> WorkspaceIntent:
    roles = ["critic", "generator"] if config.CRITIC_MODEL else ["generator"]
    last_error: Exception | None = None
    for role in roles:
        try:
            result, _ = structured(
                _messages(message, workspace),
                WorkspaceIntent,
                "workspace_intent",
                role=role,
                max_tokens=900,
            )
            return result
        except StructuredOutputError as exc:
            last_error = exc
    raise StructuredOutputError(f"workspace_intent failed: {last_error}")


async def classify_workspace_intent(
    message: str, workspace: dict
) -> WorkspaceIntent | None:
    if not looks_like_workspace_edit(message):
        return None
    return await asyncio.to_thread(_classify_sync, message, workspace)


def _text(value: Any, field: str, *, limit: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidWorkspaceIntent(f"{field} cần một giá trị văn bản rõ ràng")
    return value.strip()[:limit]


def _budget(value: Any) -> int | float:
    if isinstance(value, bool):
        raise InvalidWorkspaceIntent("budget phải là một số dương")
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.,-]", "", value).replace(",", ".")
        try:
            value = float(cleaned)
        except ValueError as exc:
            raise InvalidWorkspaceIntent("budget phải là một số dương") from exc
    if not isinstance(value, (int, float)) or value <= 0:
        raise InvalidWorkspaceIntent("budget phải là một số dương")
    return int(value) if float(value).is_integer() else round(float(value), 2)


def _iso_date(value: Any, field: str) -> str:
    text = _text(value, field, limit=10)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise InvalidWorkspaceIntent(f"{field} phải theo định dạng YYYY-MM-DD") from exc


def _validated_brief_field(field: str, value: Any) -> Any:
    if field == "brief.brand":
        return _text(value, field, limit=200)
    if field == "brief.objective":
        objective = _text(value, field, limit=40).lower()
        if objective not in {"awareness", "consideration", "conversion", "retention"}:
            raise InvalidWorkspaceIntent("objective không thuộc danh mục hỗ trợ")
        return objective
    if field == "brief.kpi":
        return _text(value, field)
    if field == "brief.budget":
        return _budget(value)
    if field in {"brief.startDate", "brief.endDate"}:
        return _iso_date(value, field)
    if field == "brief.notes":
        return _text(value, field, limit=4000)
    raise InvalidWorkspaceIntent(f"field không được phép: {field}")


def _validate_envelope(intent: WorkspaceIntent) -> None:
    if intent.requires_clarification:
        raise InvalidWorkspaceIntent(
            intent.clarification.strip() or "Anh/chị muốn thay đổi thành giá trị nào?"
        )
    if intent.field == "none":
        raise InvalidWorkspaceIntent("Anh/chị muốn thay đổi phần nào trong workspace?")


def validate_workspace_intent(
    intent: WorkspaceIntent, current_brief: dict
) -> tuple[str, Any, str] | None:
    """Synchronous brief-command validator retained as a public unit boundary."""
    if intent.intent != "propose_change" or intent.command not in {
        "set_brief_field", "set_brief_fields"
    }:
        return None
    _validate_envelope(intent)
    if intent.confidence < 0.70:
        return None
    if intent.field == "brief":
        if not isinstance(intent.value, dict) or not intent.value:
            raise InvalidWorkspaceIntent("Cần ít nhất một thay đổi cụ thể trong brief")
        allowed = {
            "brand", "objective", "kpi", "budget", "startDate", "endDate", "notes"
        }
        unknown = set(intent.value) - allowed
        if unknown:
            raise InvalidWorkspaceIntent(
                "Brief chứa trường không được phép: " + ", ".join(sorted(unknown))
            )
        merged = dict(current_brief or {})
        for key, value in intent.value.items():
            merged[key] = _validated_brief_field(f"brief.{key}", value)
        _validate_brief_dates(merged)
        return "brief", merged, intent.reason.strip()
    if not intent.field.startswith("brief."):
        raise InvalidWorkspaceIntent("Lệnh brief không được sửa artifact khác")
    value = _validated_brief_field(intent.field, intent.value)
    merged = dict(current_brief or {})
    merged[intent.field.split(".", 1)[1]] = value
    _validate_brief_dates(merged)
    return intent.field, value, intent.reason.strip()


def _validate_brief_dates(brief: dict) -> None:
    start, end = brief.get("startDate"), brief.get("endDate")
    if start and end and date.fromisoformat(str(start)) > date.fromisoformat(str(end)):
        raise InvalidWorkspaceIntent("Ngày kết thúc phải sau hoặc bằng ngày bắt đầu")


def _refs(value: Any, keys: tuple[str, ...]) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                return _refs(value[key], keys)
    raise InvalidWorkspaceIntent("Cần danh sách ID hoặc tên cụ thể")


def _ref_text(value: Any, keys: tuple[str, ...]) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in keys:
            raw = value.get(key)
            if raw not in (None, ""):
                return str(raw).strip()
    raise InvalidWorkspaceIntent("Tham chiếu catalog không hợp lệ")


def _resolve_exact(
    refs: list[Any], items: list[dict], keys: tuple[str, ...], label: str
) -> list[dict]:
    index: dict[str, list[dict]] = {}
    for item in items:
        for key in keys:
            raw = item.get(key)
            if raw not in (None, ""):
                bucket = index.setdefault(_plain(str(raw)), [])
                if item not in bucket:
                    bucket.append(item)
    result: list[dict] = []
    unknown: list[str] = []
    ambiguous: list[str] = []
    for raw in refs:
        ref = _ref_text(raw, keys)
        matches = index.get(_plain(ref), [])
        if not matches:
            unknown.append(ref)
        elif len(matches) > 1:
            ambiguous.append(ref)
        elif matches[0] not in result:
            result.append(matches[0])
    if ambiguous:
        raise InvalidWorkspaceIntent(
            f"{label} chưa đủ cụ thể: " + ", ".join(ambiguous)
        )
    if unknown:
        raise InvalidWorkspaceIntent(
            f"Không tìm thấy {label} trong catalog: " + ", ".join(unknown)
        )
    return result


def _identity(item: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        if item.get(key) not in (None, ""):
            return str(item[key])
    return json.dumps(item, sort_keys=True, default=str)


def _apply_collection_operation(
    current: list[dict], selected: list[dict], operation: WorkspaceOperation,
    keys: tuple[str, ...],
) -> list[dict]:
    current_map = {_identity(item, keys): item for item in current}
    selected_map = {_identity(item, keys): item for item in selected}
    if operation in {"set", "replace"}:
        return list(selected_map.values())
    if operation == "add":
        return list({**current_map, **selected_map}.values())
    if operation == "remove":
        return [item for key, item in current_map.items() if key not in selected_map]
    raise InvalidWorkspaceIntent("Operation không hợp lệ cho danh sách")


async def _resolve_audience(intent: WorkspaceIntent, workspace: dict) -> tuple[str, Any, str]:
    if intent.field != "segment":
        raise InvalidWorkspaceIntent("Lệnh audience chỉ được sửa segment")
    refs = _refs(intent.value, ("segments", "attrs", "ids", "values", "include"))
    current_value = _artifact_value(workspace, "audience") or {}
    current = current_value.get("attrs", [])
    catalog = await get_all_segments(limit=500)
    keys = ("_id", "segmentId", "fullLabel", "name")
    try:
        # A label may be ambiguous in the 300+ catalog but unambiguous among
        # the user's current selections. Removal should honor that local scope.
        resolution_pool = current if intent.operation == "remove" else catalog
        selected = _resolve_exact(refs, resolution_pool, keys, "segment")
    except InvalidWorkspaceIntent as exc:
        suggestions: list[str] = []
        for ref in refs[:3]:
            text = _ref_text(ref, keys)
            matches = await search_audience(text, limit=3)
            suggestions.extend(
                item.get("fullLabel") or item.get("name", "") for item in matches
            )
        hints = [item for item in dict.fromkeys(suggestions) if item]
        suffix = f". Gợi ý: {', '.join(hints[:5])}" if hints else ""
        raise InvalidWorkspaceIntent(str(exc) + suffix) from exc

    final_raw = _apply_collection_operation(current, selected, intent.operation, keys)
    from handlers.audience import _calc_audience_size, _normalize_dmp_attr
    attrs = [_normalize_dmp_attr(item) for item in final_raw]
    final = {
        **current_value,
        "attrs": attrs,
        "size": _calc_audience_size(attrs),
    }
    return "segment", final, intent.reason.strip()


def _targeting_allowed(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(value) for value in raw]
    if isinstance(raw, dict):
        return [
            str(value)
            for values in raw.values() if isinstance(values, list)
            for value in values
        ]
    return []


async def _resolve_targeting(intent: WorkspaceIntent, workspace: dict) -> tuple[str, Any, str]:
    if intent.field != "targeting" or not isinstance(intent.value, dict):
        raise InvalidWorkspaceIntent("Targeting cần object dimension -> danh sách giá trị")
    requested = intent.value.get("rules", intent.value)
    if not isinstance(requested, dict) or not requested:
        raise InvalidWorkspaceIntent("Cần ít nhất một targeting rule")
    options = await get_targeting_options()
    unknown_dimensions = set(requested) - set(options)
    if unknown_dimensions:
        raise InvalidWorkspaceIntent(
            "Targeting dimension không tồn tại: " + ", ".join(sorted(unknown_dimensions))
        )
    canonical: dict[str, list[str]] = {}
    invalid: list[str] = []
    for dimension, raw_values in requested.items():
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        allowed = _targeting_allowed(options.get(dimension))
        allowed_map = {_plain(value): value for value in allowed}
        resolved: list[str] = []
        for value in values:
            match = allowed_map.get(_plain(str(value)))
            if match is None:
                invalid.append(f"{dimension}={value}")
            elif match not in resolved:
                resolved.append(match)
        canonical[dimension] = resolved
    if invalid:
        raise InvalidWorkspaceIntent(
            "Targeting value không có trong catalog: " + ", ".join(invalid)
        )

    current = _artifact_value(workspace, "targeting") or {}
    final = deepcopy(current)
    for dimension, values in canonical.items():
        existing = list(final.get(dimension, []))
        if intent.operation in {"set", "replace"}:
            final[dimension] = values
        elif intent.operation == "add":
            final[dimension] = list(dict.fromkeys(existing + values))
        elif intent.operation == "remove":
            final[dimension] = [value for value in existing if value not in values]
        else:
            raise InvalidWorkspaceIntent("Operation targeting không hợp lệ")
    return "targeting", final, intent.reason.strip()


async def _resolve_placements(intent: WorkspaceIntent, workspace: dict) -> tuple[str, Any, str]:
    if intent.field != "setup.selectedZoneIds":
        raise InvalidWorkspaceIntent("Lệnh placement chỉ được sửa selectedZoneIds")
    refs = _refs(intent.value, ("zones", "placements", "ids", "values"))
    zones = await get_all_zones()
    keys = ("id", "testSiteZone")
    selected = _resolve_exact(refs, zones, keys, "zone")
    placements = _artifact_value(workspace, "placements") or {}
    current_ids = placements.get("selectedZoneIds", [])
    current = _resolve_exact(current_ids, zones, keys, "zone") if current_ids else []
    final_zones = _apply_collection_operation(current, selected, intent.operation, keys)
    final_ids = [str(item["id"]) for item in final_zones]

    brief = _artifact_value(workspace, "brief") or {}
    conflicts = await fetch_zone_conflicts(
        str(brief.get("startDate", "")), str(brief.get("endDate", ""))
    )
    blocked = [zone_id for zone_id in final_ids if zone_id in conflicts]
    if blocked:
        raise InvalidWorkspaceIntent(
            "Zone đã được đặt trong thời gian campaign: " + ", ".join(blocked)
        )
    return "setup.selectedZoneIds", final_ids, intent.reason.strip()


def _current_creatives(workspace: dict) -> list[dict]:
    creative = _artifact_value(workspace, "creative") or {}
    return creative.get("files", []) if isinstance(creative, dict) else []


async def _resolve_creatives(intent: WorkspaceIntent, workspace: dict) -> tuple[str, Any, str]:
    if intent.field != "creative.files":
        raise InvalidWorkspaceIntent("Lệnh creative chỉ được sửa danh sách files")
    refs = _refs(intent.value, ("files", "ids", "values"))
    current = _current_creatives(workspace)
    keys = ("id", "name", "filename", "analysisId")
    selected = _resolve_exact(refs, current, keys, "creative hiện có")
    if intent.operation == "add":
        raise InvalidWorkspaceIntent(
            "Không thể upload creative mới chỉ bằng chat; hãy upload file ở workspace"
        )
    final = _apply_collection_operation(current, selected, intent.operation, keys)
    return "creative.files", final, intent.reason.strip()


async def _resolve_assignments(intent: WorkspaceIntent, workspace: dict) -> tuple[str, Any, str]:
    if intent.field != "assignments":
        raise InvalidWorkspaceIntent("Lệnh assignment chỉ được sửa assignments")
    placements = _artifact_value(workspace, "placements") or {}
    zone_ids = placements.get("selectedZoneIds", [])
    zones = await get_all_zones()
    selected_zones = _resolve_exact(zone_ids, zones, ("id", "testSiteZone"), "zone") if zone_ids else []
    zone_index = {_plain(str(item["id"])): str(item["id"]) for item in selected_zones}
    files = _current_creatives(workspace)
    file_keys = ("id", "name", "analysisId")

    current = _artifact_value(workspace, "assignments") or {}
    if intent.operation == "remove":
        if isinstance(intent.value, dict) and not any(
            key in intent.value for key in ("zones", "placements", "ids", "values")
        ):
            refs = list(intent.value)
        else:
            refs = _refs(intent.value, ("zones", "placements", "ids", "values"))
        resolved = _resolve_exact(refs, selected_zones, ("id", "testSiteZone"), "zone")
        removed = {str(item["id"]) for item in resolved}
        final = {key: value for key, value in current.items() if key not in removed}
        return "assignments", final, intent.reason.strip()

    if not isinstance(intent.value, dict) or not intent.value:
        raise InvalidWorkspaceIntent("Assignments cần object zone -> creative")
    raw_assignments = intent.value.get("assignments", intent.value)
    if not isinstance(raw_assignments, dict) or not raw_assignments:
        raise InvalidWorkspaceIntent("Assignments cần object zone -> creative")
    resolved_assignments: dict[str, int] = {}
    for raw_zone, raw_file in raw_assignments.items():
        zone_id = zone_index.get(_plain(str(raw_zone)))
        if not zone_id:
            raise InvalidWorkspaceIntent(
                f"Zone không thuộc placements đã chọn: {raw_zone}"
            )
        matched = _resolve_exact([raw_file], files, file_keys, "creative hiện có")
        file_index = files.index(matched[0])
        resolved_assignments[zone_id] = file_index
    final = resolved_assignments if intent.operation == "replace" else {
        **current, **resolved_assignments
    }
    return "assignments", final, intent.reason.strip()


async def resolve_workspace_intent(
    intent: WorkspaceIntent, workspace: dict
) -> tuple[str, Any, str] | None:
    """Resolve a model command to a validated proposal field/value/reason."""
    if intent.intent != "propose_change" or intent.command == "none":
        return None
    _validate_envelope(intent)
    if intent.confidence < 0.70:
        return None
    if intent.command in {"set_brief_field", "set_brief_fields"}:
        return validate_workspace_intent(
            intent, _artifact_value(workspace, "brief") or {}
        )
    if intent.command == "select_audience_segments":
        return await _resolve_audience(intent, workspace)
    if intent.command == "set_targeting_rules":
        return await _resolve_targeting(intent, workspace)
    if intent.command == "select_placements":
        return await _resolve_placements(intent, workspace)
    if intent.command == "select_creative_files":
        return await _resolve_creatives(intent, workspace)
    if intent.command == "set_assignments":
        return await _resolve_assignments(intent, workspace)
    raise InvalidWorkspaceIntent(f"Command không được hỗ trợ: {intent.command}")


def _legacy_assignment_value(value: Any, workspace: dict) -> dict:
    """Convert legacy zone -> file-index payloads into authoritative references."""
    if not isinstance(value, dict):
        raise InvalidWorkspaceIntent("Assignments cần object zone -> creative")
    raw = value.get("assignments", value)
    if not isinstance(raw, dict) or not raw:
        action = str(value.get("action", ""))
        if action:
            raise InvalidWorkspaceIntent(
                "Lệnh tự động gắn creative phải chạy qua chức năng Auto Assign; "
                "chat không được tự tạo assignments"
            )
        raise InvalidWorkspaceIntent("Assignments cần object zone -> creative")

    files = _current_creatives(workspace)
    normalized: dict[str, Any] = {}
    for zone, raw_file in raw.items():
        if isinstance(raw_file, bool):
            raise InvalidWorkspaceIntent(f"Creative cho zone {zone} không hợp lệ")
        if isinstance(raw_file, int):
            if raw_file < 0 or raw_file >= len(files):
                raise InvalidWorkspaceIntent(
                    f"Creative index ngoài phạm vi cho zone {zone}: {raw_file}"
                )
            file = files[raw_file]
            normalized[str(zone)] = (
                file.get("id") or file.get("name") or file.get("filename")
            )
        elif isinstance(raw_file, dict):
            normalized[str(zone)] = _ref_text(
                raw_file, ("id", "name", "filename", "analysisId")
            )
        else:
            normalized[str(zone)] = raw_file
    return normalized


async def resolve_legacy_update(
    field: str,
    value: Any,
    workspace: dict,
    reason: str = "",
) -> tuple[str, Any, str]:
    """Coerce an old ``update_workspace`` payload into a typed safe command.

    This is the migration firewall for every proposal path that does not start
    in the structured intent node. The legacy model may provide references,
    but the returned value is always rebuilt from canonical workspace state or
    an authoritative catalog before it can be stored for approval.
    """
    if not isinstance(field, str) or not field.strip():
        raise InvalidWorkspaceIntent("Thiếu workspace field cần cập nhật")
    field = field.strip()
    command: WorkspaceCommand
    typed_field: WorkspaceField
    operation: WorkspaceOperation = "replace"
    typed_value = value

    if field == "brief" or field.startswith("brief."):
        command = "set_brief_fields"
        typed_field = field  # validated by resolve_workspace_intent
        operation = "set"
    elif field == "segment":
        command = "select_audience_segments"
        typed_field = "segment"
        if isinstance(value, dict):
            typed_value = value.get("attrs", value.get("segments", value))
    elif field == "targeting":
        command = "set_targeting_rules"
        typed_field = "targeting"
    elif field in {"creative", "creative.files"}:
        command = "select_creative_files"
        typed_field = "creative.files"
        if isinstance(value, dict):
            typed_value = value.get("files", value)
    elif field in {"setup.selectedZoneIds", "placements"}:
        command = "select_placements"
        typed_field = "setup.selectedZoneIds"
        if isinstance(value, dict):
            typed_value = value.get("selectedZoneIds", value.get("zones", value))
    elif field == "setup":
        if not isinstance(value, dict):
            raise InvalidWorkspaceIntent("Setup cần object có selectedZoneIds hoặc assignments")
        has_assignments = bool(value.get("assignments")) or bool(value.get("action"))
        has_zones = "selectedZoneIds" in value
        if has_assignments and has_zones:
            current = _artifact_value(workspace, "placements") or {}
            current_ids = [str(item) for item in current.get("selectedZoneIds", [])]
            requested_ids = [str(item) for item in value.get("selectedZoneIds", [])]
            if current_ids != requested_ids:
                raise InvalidWorkspaceIntent(
                    "Không thể đổi placements và assignments trong cùng một đề xuất; "
                    "hãy thực hiện từng thay đổi"
                )
        if has_assignments:
            command = "set_assignments"
            typed_field = "assignments"
            typed_value = _legacy_assignment_value(value, workspace)
        elif has_zones:
            command = "select_placements"
            typed_field = "setup.selectedZoneIds"
            typed_value = value["selectedZoneIds"]
        else:
            raise InvalidWorkspaceIntent("Setup thiếu selectedZoneIds hoặc assignments")
    elif field == "assignments":
        command = "set_assignments"
        typed_field = "assignments"
        typed_value = _legacy_assignment_value(value, workspace)
    else:
        raise InvalidWorkspaceIntent(f"Workspace field không được hỗ trợ: {field}")

    intent = WorkspaceIntent(
        intent="propose_change",
        command=command,
        field=typed_field,
        operation=operation,
        value=typed_value,
        reason=reason,
        confidence=1.0,
    )
    resolved = await resolve_workspace_intent(intent, workspace)
    if resolved is None:
        raise InvalidWorkspaceIntent("Đề xuất workspace không đủ rõ ràng")
    return resolved
