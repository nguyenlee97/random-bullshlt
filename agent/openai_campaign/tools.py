"""Strict Responses tools and deterministic execution for OpenAI campaigns.

The schemas in this module are owned by the OpenAI component. They reuse the
same domain services as the GreenNode registry, but never import or call the
GreenNode model client.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from typing import Any

from audience_reach import estimate_unique_reach
from autopilot.capabilities import validate_brief_value
from openai_campaign.knowledge import search_ad_knowledge
from session import set_pending_proposal
from tools.audience_library import get_all_segments, search_audience
from tools.order_api import fetch_zone_conflicts, public_conflict_details
from tools.registry import execute_tool
from tools.zone_catalog import get_all_zones
from workspace.intent import InvalidWorkspaceIntent, resolve_legacy_update
from workspace.service import create_proposal, get_workspace


READ_TOOL_NAMES = {
    "search_ad_knowledge",
    "search_audience_catalog",
    "get_audience_reach",
    "get_zone_details",
    "get_zone_availability",
    "compare_zones",
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
        "name": "search_ad_knowledge",
        "description": (
            "Search the versioned Advertising Agent knowledge base for campaign "
            "setup, metric definitions, workflow policy and product terminology."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The user's knowledge question."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_audience_catalog",
        "description": (
            "Search current authoritative DMP segments for one or more audience "
            "topics. For a multi-topic request, put each distinct concept in a "
            "separate query instead of joining them into one phrase."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 6,
                    "description": (
                        "One concise English catalog search phrase per user "
                        "concept. Translate Vietnamese concepts for the primarily "
                        "English catalog; for example: ['coffee', 'beverages', "
                        "'office workers']. Never combine independent concepts "
                        "into one query."
                    ),
                },
                "type": _nullable_string("Optional DMP segment type.", enum=["Behavior", "Interest"]),
            },
            "required": ["queries", "type"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_audience_reach",
        "description": (
            "Calculate canonical deduplicated unique reach for concrete current "
            "DMP segment IDs. Do not pass invented IDs or topic words."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "segment_ids": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Authoritative segment IDs returned by catalog search.",
                },
            },
            "required": ["segment_ids"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_zone_details",
        "description": "Read current catalog details for one authoritative ad-zone ID.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"zone_id": {"type": "string"}},
            "required": ["zone_id"], "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_zone_availability",
        "description": "Check live booking conflicts for zone IDs and an exact date range.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "zone_ids": {"type": "array", "items": {"type": "string"}},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["zone_ids", "start_date", "end_date"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "compare_zones",
        "description": "Compare current catalog metrics and live availability for 2-8 zone IDs.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "zone_ids": {"type": "array", "items": {"type": "string"}},
                "start_date": _nullable_string("Optional campaign start date YYYY-MM-DD."),
                "end_date": _nullable_string("Optional campaign end date YYYY-MM-DD."),
            },
            "required": ["zone_ids", "start_date", "end_date"],
            "additionalProperties": False,
        },
    },
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
        "description": "Read one campaign order or recent orders owned by the current actor.",
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


def _segment_id(segment: dict) -> str:
    return str(segment.get("segmentId") or segment.get("_id") or segment.get("code") or "")


def _zone_view(zone: dict) -> dict:
    return {
        key: zone.get(key) for key in (
            "id", "channel", "format", "size", "reach", "vi", "ctr",
            "cpm", "obj", "siteId", "siteUrl",
        )
    }


async def _execute_read_tool(name: str, args: dict) -> dict:
    if name == "search_ad_knowledge":
        return search_ad_knowledge(str(args.get("query") or ""))
    if name == "search_audience_catalog":
        queries = list(dict.fromkeys(
            str(item).strip()
            for item in args.get("queries") or []
            if str(item).strip()
        ))[:6]
        if not queries:
            raise ValueError("At least one audience catalog query is required")

        # Each query is one semantic concept chosen by the model. Search them
        # independently because the DMP API treats q as one regex phrase, then
        # merge authoritative rows without changing the current selection.
        result_sets = await asyncio.gather(*(
            search_audience(query, type_filter=args.get("type"), limit=10)
            for query in queries
        ))
        merged: dict[str, dict] = {}
        matched_queries: dict[str, list[str]] = {}
        query_results: list[dict] = []
        for query, items in zip(queries, result_sets):
            ids: list[str] = []
            for item in items:
                identity = _segment_id(item)
                if not identity:
                    continue
                ids.append(identity)
                merged.setdefault(identity, item)
                matched_queries.setdefault(identity, []).append(query)
            query_results.append({"query": query, "segment_ids": ids})

        segments = list(merged.values())[:30]
        return {
            "catalog": "dmp_attributes", "catalog_freshness": "live_query",
            "query_results": query_results,
            "unmatched_queries": [
                item["query"] for item in query_results if not item["segment_ids"]
            ],
            "segments": [{
                "segment_id": _segment_id(item),
                "name": item.get("fullLabel") or item.get("name"),
                "type": item.get("type"), "category": item.get("category"),
                "size_min": item.get("sizeMin"), "size_max": item.get("sizeMax"),
                "size_updated_at": item.get("sizeEstimatedAt"),
                "size_version": item.get("sizeEstimateVersion"),
                "matched_queries": matched_queries.get(_segment_id(item), []),
            } for item in segments],
            "no_result": not segments,
        }
    if name == "get_audience_reach":
        requested = list(dict.fromkeys(str(item) for item in args.get("segment_ids") or []))[:50]
        catalog = await get_all_segments(limit=1000)
        by_id = {_segment_id(item): item for item in catalog if _segment_id(item)}
        resolved = [by_id[item] for item in requested if item in by_id]
        result = estimate_unique_reach(resolved)
        result["requested_segment_ids"] = requested
        result["unresolved_segment_ids"] = [item for item in requested if item not in by_id]
        return result
    if name in {"get_zone_details", "get_zone_availability", "compare_zones"}:
        zones = await get_all_zones()
        zone_map = {str(item.get("id")): item for item in zones if item.get("id")}
        if name == "get_zone_details":
            zone_id = str(args.get("zone_id") or "")
            return {
                "zone": _zone_view(zone_map[zone_id]) if zone_id in zone_map else None,
                "catalog_freshness": "live_query", "unresolved_zone_ids": [] if zone_id in zone_map else [zone_id],
            }
        requested = list(dict.fromkeys(str(item) for item in args.get("zone_ids") or []))[:8]
        start_date = str(args.get("start_date") or "")
        end_date = str(args.get("end_date") or "")
        conflicts = await fetch_zone_conflicts(start_date, end_date) if start_date and end_date else {}
        entries = [{
            **_zone_view(zone_map[item]),
            "availability": "booked" if item in conflicts else (
                "available" if start_date and end_date else "unknown_dates_required"
            ),
            "conflict": public_conflict_details(conflicts.get(item)),
        } for item in requested if item in zone_map]
        return {
            "zones": entries, "start_date": start_date or None, "end_date": end_date or None,
            "catalog_freshness": "live_query",
            "availability_freshness": "live_query" if start_date and end_date else "not_queried",
            "unresolved_zone_ids": [item for item in requested if item not in zone_map],
        }
    raise ValueError(f"Unknown OpenAI read tool: {name}")


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
    from security import redact_pii

    value = redact_pii(value)
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
        if name in {
            "search_ad_knowledge", "search_audience_catalog", "get_audience_reach",
            "get_zone_details", "get_zone_availability", "compare_zones",
        }:
            result = await _execute_read_tool(name, safe_args)
        else:
            result = await execute_tool(
                name, safe_args, session_id=session_id
            )
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
    if field.startswith("brief.") and validate_brief_value(
        canonical.get("artifacts", {}).get("brief", {}).get("value")
    )[1]:
        raise InvalidWorkspaceIntent(
            "Brief ban đầu chưa đầy đủ; phải đề xuất toàn bộ field `brief` "
            "thay vì một field con."
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
