"""Structured intent gate for safe Campaign Copilot workspace edits.

The conversational model remains responsible for general advice and tool use.
This module only handles likely, explicit edits to brief fields. It converts the
request into a small whitelisted command, validates the value, and lets the
graph create a durable proposal. Nothing here mutates the workspace directly.
"""
from __future__ import annotations

import asyncio
from datetime import date
import json
import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, Field

from config import config
from graph.structured import StructuredOutputError, structured


BriefField = Literal[
    "brief",
    "brief.brand",
    "brief.objective",
    "brief.kpi",
    "brief.budget",
    "brief.startDate",
    "brief.endDate",
    "brief.notes",
    "none",
]


class WorkspaceIntent(BaseModel):
    """Strict result returned by the intent model."""

    intent: Literal["propose_change", "other"]
    command: Literal["set_brief_field", "none"]
    field: BriefField
    value: Any = None
    reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_clarification: bool = False
    clarification: str = ""

    model_config = {"extra": "forbid"}


class InvalidWorkspaceIntent(ValueError):
    """The model proposed a command that is unsafe or under-specified."""


_EDIT_VERBS = (
    "doi", "thay doi", "sua", "cap nhat", "chinh", "dat", "them", "bo",
    "xoa", "muon", "can", "update", "change", "set", "replace", "remove",
)
_BRIEF_TERMS = (
    "brand", "thuong hieu", "brief", "ngan sach", "budget", "muc tieu",
    "objective", "kpi", "ngay bat dau", "ngay ket thuc", "start date",
    "end date", "ghi chu", "notes",
)


def _plain(text: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD", text.lower().translate(str.maketrans({"đ": "d", "Đ": "D"}))
    )
    return " ".join(
        "".join(ch for ch in normalized if not unicodedata.combining(ch)).split()
    )


def looks_like_brief_edit(message: str) -> bool:
    """Cheap prefilter so ordinary chat does not pay for a second model call."""
    text = _plain(message)
    return any(verb in text for verb in _EDIT_VERBS) and any(
        term in text for term in _BRIEF_TERMS
    )


def _messages(message: str, current_brief: dict) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "Bạn là bộ phân loại lệnh chỉnh sửa workspace quảng cáo. Chỉ trả "
                "propose_change khi người dùng yêu cầu áp dụng một thay đổi cụ thể "
                "ngay bây giờ. Câu hỏi hướng dẫn, giả định, phủ định, hoặc chỉ thảo "
                "luận phải là other. Không suy diễn giá trị người dùng chưa nói. "
                "Chỉ dùng command=set_brief_field và một field trong schema. Nếu có "
                "ý định sửa nhưng thiếu giá trị mới, đặt requires_clarification=true. "
                "objective chỉ được là awareness, consideration, conversion hoặc "
                "retention. budget là số triệu VND. Ngày theo YYYY-MM-DD. Khi nhiều "
                "trường brief được đổi, dùng field=brief và value chỉ gồm các trường "
                "được người dùng nêu rõ. Không tự điền dữ liệu còn thiếu."
            ),
        },
        {
            "role": "system",
            "content": "Brief hiện tại: " + json.dumps(
                current_brief or {}, ensure_ascii=False, default=str
            ),
        },
        {"role": "user", "content": message},
    ]


def _classify_sync(message: str, current_brief: dict) -> WorkspaceIntent:
    roles = ["critic", "generator"] if config.CRITIC_MODEL else ["generator"]
    last_error: Exception | None = None
    for role in roles:
        try:
            result, _ = structured(
                _messages(message, current_brief),
                WorkspaceIntent,
                "workspace_intent",
                role=role,
                max_tokens=700,
            )
            return result
        except StructuredOutputError as exc:
            last_error = exc
    raise StructuredOutputError(f"workspace_intent failed: {last_error}")


async def classify_workspace_intent(
    message: str, current_brief: dict
) -> WorkspaceIntent | None:
    if not looks_like_brief_edit(message):
        return None
    return await asyncio.to_thread(_classify_sync, message, current_brief)


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


def _validated_field(field: str, value: Any) -> Any:
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


def validate_workspace_intent(
    intent: WorkspaceIntent, current_brief: dict
) -> tuple[str, Any, str] | None:
    """Return a validated ``(field, value, reason)`` proposal command."""
    if intent.intent != "propose_change" or intent.command != "set_brief_field":
        return None
    if intent.requires_clarification:
        raise InvalidWorkspaceIntent(
            intent.clarification.strip() or "Anh/chị muốn thay đổi thành giá trị nào?"
        )
    if intent.confidence < 0.70:
        return None
    if intent.field == "none":
        raise InvalidWorkspaceIntent("Anh/chị muốn thay đổi trường nào trong brief?")

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
            merged[key] = _validated_field(f"brief.{key}", value)
        return "brief", merged, intent.reason.strip()

    return (
        intent.field,
        _validated_field(intent.field, intent.value),
        intent.reason.strip(),
    )
