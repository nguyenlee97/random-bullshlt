"""Strict Responses tools and deterministic execution for OpenAI campaigns.

The schemas in this module are owned by the OpenAI component. They reuse the
same domain services as the GreenNode registry, but never import or call the
GreenNode model client.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from session import set_pending_proposal
from tools.registry import execute_tool
from workspace.intent import InvalidWorkspaceIntent, resolve_legacy_update
from workspace.service import create_proposal, get_workspace


READ_TOOL_NAMES = {
    "get_zone_list",
    "search_zones",
    "get_audience_list",
    "explain_step",
    "get_order_status",
    "get_targeting_options",
}
MUTATION_TOOL_NAME = "propose_workspace_change"
MAX_TOOL_RESULT_CHARS = 24_000


def _nullable_string(description: str, *, enum: list[str] | None = None) -> dict:
    schema: dict[str, Any] = {
        "type": ["string", "null"],
        "description": description,
    }
    if enum:
        schema["enum"] = [*enum, None]
    return schema


OPENAI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "get_zone_list",
        "description": (
            "List advertising zones and live booking conflicts. Use for a broad "
            "zone overview; pass the campaign dates when known."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "objective": _nullable_string(
                    "Campaign objective.",
                    enum=["awareness", "consideration", "conversion", "retention"],
                ),
                "start_date": _nullable_string("Campaign start date YYYY-MM-DD."),
                "end_date": _nullable_string("Campaign end date YYYY-MM-DD."),
            },
            "required": ["objective", "start_date", "end_date"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_zones",
        "description": (
            "Search advertising zones by name, site, format, objective, or metric "
            "intent and include live booking conflicts."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": _nullable_string("Zone/site/format search phrase."),
                "objective": _nullable_string(
                    "Campaign objective.",
                    enum=["awareness", "consideration", "conversion", "retention"],
                ),
                "start_date": _nullable_string("Campaign start date YYYY-MM-DD."),
                "end_date": _nullable_string("Campaign end date YYYY-MM-DD."),
            },
            "required": ["query", "objective", "start_date", "end_date"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_audience_list",
        "description": (
            "Search the authoritative DMP audience catalog. Use for current "
            "segment discovery, not for general advertising advice."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Vietnamese or English audience search phrase.",
                },
                "type": _nullable_string(
                    "Optional DMP segment type.", enum=["Behavior", "Interest"],
                ),
            },
            "required": ["query", "type"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": MUTATION_TOOL_NAME,
        "description": (
            "Create a validated workspace proposal when the user explicitly asks "
            "to change campaign state. This never applies the change; the user "
            "must approve the visible proposal in a later turn."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "enum": [
                        "brief", "brief.brand", "brief.objective", "brief.kpi",
                        "brief.budget", "brief.startDate", "brief.endDate",
                        "brief.notes", "segment", "targeting", "creative.files",
                        "setup.selectedZoneIds", "assignments",
                    ],
                    "description": "Canonical workspace field to propose changing.",
                },
                "value_json": {
                    "type": "string",
                    "description": (
                        "JSON-encoded proposed value or catalog references. Never "
                        "invent audience, zone, creative, or targeting IDs."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": "Short user-facing reason for the proposal.",
                },
            },
            "required": ["field", "value_json", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "explain_step",
        "description": "Explain one existing Guided campaign workflow step.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "step_name": {
                    "type": "string",
                    "enum": ["brief", "audience", "creative", "setup", "result"],
                },
            },
            "required": ["step_name"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_order_status",
        "description": "Read the current status of one campaign order or recent orders.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": _nullable_string("Order ID such as ORD-2026-005."),
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_targeting_options",
        "description": "Read the authoritative targeting option catalog.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
]


def responses_tools(*, allow_mutation: bool = True) -> list[dict]:
    return [
        deepcopy(tool)
        for tool in OPENAI_TOOL_DEFINITIONS
        if allow_mutation or tool["name"] != MUTATION_TOOL_NAME
    ]


def allowed_capabilities() -> list[str]:
    return [tool["name"] for tool in OPENAI_TOOL_DEFINITIONS]


def _brief_from_workspace(workspace: dict | None) -> dict:
    value = workspace or {}
    artifact = value.get("artifacts", {}).get("brief", {}).get("value")
    if isinstance(artifact, dict):
        return artifact
    brief = value.get("brief")
    return brief if isinstance(brief, dict) else {}


def _step_for_field(field: str) -> int:
    if field == "brief" or field.startswith("brief."):
        return 0
    if field in {"segment", "targeting"}:
        return 1
    if field.startswith("creative"):
        return 2
    if field in {"setup.selectedZoneIds", "assignments"}:
        return 3
    return -1


def _proposal_warning(field: str, confirmed_steps: list[int]) -> tuple[bool, str]:
    step = _step_for_field(field)
    locked = step in confirmed_steps
    if not locked:
        return False, ""
    labels = ["Brief", "Audience", "Creative", "Setup", "Kết quả", "Báo cáo", "Email"]
    downstream = labels[step + 1:]
    warning = (
        f"⚠️ Bước {labels[step]} đã được xác nhận. Nếu thay đổi, các bước sau "
        f"({', '.join(downstream)}) sẽ được tính lại."
    ) if downstream else ""
    return True, warning


def _proposal_suggestions(field: str) -> list[dict]:
    if field == "brief" or field.startswith("brief."):
        return [
            {"label": "✅ Xác nhận brief", "action": "send", "text": "Đồng ý, áp dụng đề xuất này"},
            {"label": "✏️ Chỉnh sửa thêm", "action": "prefill", "text": "Tôi muốn chỉnh sửa: "},
        ]
    if field in {"segment", "targeting"}:
        return [
            {"label": "✅ Áp dụng đề xuất", "action": "send", "text": "Đồng ý, áp dụng đề xuất này"},
            {"label": "✏️ Điều chỉnh", "action": "prefill", "text": "Tôi muốn điều chỉnh: "},
        ]
    if field in {"setup.selectedZoneIds", "assignments"}:
        return [
            {"label": "✅ Duyệt đề xuất", "action": "send", "text": "Đồng ý, áp dụng đề xuất này"},
            {"label": "➕ Điều chỉnh zone", "action": "prefill", "text": "Điều chỉnh zone: "},
        ]
    return []


def _bounded_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, default=str)
    if len(payload) <= MAX_TOOL_RESULT_CHARS:
        return payload
    return json.dumps({
        "truncated": True,
        "preview": payload[:MAX_TOOL_RESULT_CHARS],
    }, ensure_ascii=False)


async def execute_openai_tool(
    name: str,
    args: dict,
    *,
    session_id: str,
    message: str,
    workspace: dict | None,
    confirmed_steps: list[int],
) -> dict:
    """Execute one allowlisted tool and return model/UI-safe result metadata."""
    if name in READ_TOOL_NAMES:
        safe_args = dict(args)
        if name in {"get_zone_list", "search_zones"}:
            brief = _brief_from_workspace(workspace)
            safe_args["start_date"] = safe_args.get("start_date") or brief.get("startDate")
            safe_args["end_date"] = safe_args.get("end_date") or brief.get("endDate")
        result = await execute_tool(name, safe_args)
        return {"output": _bounded_json(result), "ui": None, "mutated": False}

    if name != MUTATION_TOOL_NAME:
        raise ValueError(f"OpenAI tool is not allowlisted: {name}")

    try:
        value = json.loads(args.get("value_json", ""))
    except (TypeError, json.JSONDecodeError) as exc:
        raise InvalidWorkspaceIntent("Giá trị đề xuất không phải JSON hợp lệ") from exc

    canonical = await get_workspace(session_id)
    field, value, reason = await resolve_legacy_update(
        str(args.get("field") or ""),
        value,
        canonical,
        str(args.get("reason") or ""),
        source_message=message,
    )
    proposal = await create_proposal(
        session_id,
        field,
        value,
        base_revision=canonical["revision"],
        actor="openai_campaign_copilot",
        reason=reason,
    )
    changes = {
        "field": field,
        "value": value,
        "reason": reason,
        "proposal_id": proposal["proposal_id"],
        "base_revision": proposal["base_revision"],
        "affected_artifacts": proposal["affected_artifacts"],
    }
    await set_pending_proposal(session_id, changes)
    is_locked, warning = _proposal_warning(field, confirmed_steps)
    ui = {
        "block": {
            "type": "workspace_proposal",
            "changes": changes,
            "is_locked": is_locked,
            "warning": warning,
        },
        "suggestions": _proposal_suggestions(field),
        "changes": changes,
    }
    result = {
        "status": "pending_user_confirmation",
        "proposal_id": proposal["proposal_id"],
        "field": field,
        "reason": reason,
        "note": "The proposal is visible to the user and has not been applied.",
    }
    return {"output": _bounded_json(result), "ui": ui, "mutated": False}
