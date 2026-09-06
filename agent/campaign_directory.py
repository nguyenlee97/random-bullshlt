"""Owner-scoped campaign homepage read model.

Conversations appear as campaign workspaces from the first turn. Before an
ad-server order exists the entry is a draft; after launch the same entry becomes
an operational campaign. Clients never select an owner ID or read global orders.
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from copy import deepcopy
from datetime import date
from typing import Any
from urllib.parse import urlparse

_ORDER_FETCH_CONCURRENCY = 8
_COPILOT_STEPS = (
    "Brief", "Audience", "Creative", "Setup Camp", "Kết quả", "Report", "Email",
)


def _mode(value: object) -> str:
    return "autopilot" if value == "autopilot" else "copilot"


def _conversation_route(
    conversation_id: str | None, mode: object, *, read_only: bool = False,
) -> str | None:
    if not conversation_id:
        return None
    history_mode = "autopilot" if _mode(mode) == "autopilot" else "copilot"
    return (
        f"/agent/{history_mode}/history/{conversation_id}"
        f"{'?readonly=1' if read_only else ''}"
    )


def _run_requires_review(summary: dict | None) -> bool:
    return bool(
        summary
        and summary.get("status") == "waiting_review"
        and summary.get("run_id")
        and summary.get("current_task")
    )


def _action_required(summary: dict | None) -> dict | None:
    if not _run_requires_review(summary):
        return None
    task_key = str(summary.get("current_task"))
    return {
        "kind": "workflow_review",
        "run_id": str(summary["run_id"]),
        "task_key": task_key,
        "label": f"Duyệt bước {task_key.replace('_', ' ')}",
    }


def _date_value(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except (TypeError, ValueError):
        return None


def _order_lifecycle(order: dict, *, today: date | None = None) -> str:
    """Return operational truth without rewriting the source order status.

    Several legacy orders remain ``active`` after their booked date range.  The
    directory treats a campaign whose end date is in the past as completed,
    while retaining the source status in the order summary for audit/debugging.
    """
    status = str(order.get("status") or "pending").strip().lower()
    if status in {"archived", "failed", "cancelled", "deleted"}:
        return "archived" if status in {"cancelled", "deleted"} else status
    end_date = _date_value(order.get("endDate") or order.get("end_date"))
    if end_date and end_date < (today or date.today()):
        return "completed"
    start_date = _date_value(order.get("startDate") or order.get("start_date"))
    if start_date and start_date > (today or date.today()):
        return "scheduled"
    return status if status in {
        "active", "paused", "completed", "archived", "failed",
    } else "operational"


def _safe_http_url(value: object) -> str | None:
    candidate = str(value or "").strip()
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    return candidate if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _order_preview(values: object, *, kind: str, limit: int = 6) -> list[dict]:
    """Expose a small, presentation-safe owned-order preview for Management."""
    if not isinstance(values, list):
        return []
    previews: list[dict] = []
    for index, value in enumerate(values[:limit]):
        if isinstance(value, dict):
            identity = str(
                value.get("id") or value.get("_id") or value.get("zone_id")
                or value.get("creative_id") or value.get("name") or index + 1
            )
            label = str(
                value.get("name") or value.get("label") or value.get("zone_name")
                or value.get("title") or value.get("file_name") or identity
            )
            detail_parts = [
                str(value.get(key) or "").strip()
                for key in ("publisher", "format", "size", "dimensions")
            ]
            detail = " · ".join(dict.fromkeys(part for part in detail_parts if part))
            url = _safe_http_url(
                value.get("siteUrl") if kind == "placement" else value.get("url")
            )
        else:
            identity = str(value)
            label = identity
            detail = ""
            url = None
        previews.append({
            "id": identity, "label": label, "detail": detail, "kind": kind,
            "url": url,
        })
    return previews


def _order_summary(order_id: str, order: dict, *, order_count: int = 1) -> dict:
    placements = order.get("placements") or []
    placement_values = order.get("placementSnapshots") or placements
    creatives = order.get("creatives") or order.get("creative") or []
    if isinstance(creatives, dict):
        creatives = [creatives] if any(creatives.values()) else []
    warnings = order.get("warnings") or []
    explicit_daily = order.get("daily") or order.get("daily_budget")
    daily_budget = explicit_daily
    daily_budget_source = "explicit" if explicit_daily else None
    start_date = _date_value(order.get("startDate") or order.get("start_date"))
    end_date = _date_value(order.get("endDate") or order.get("end_date"))
    budget = order.get("budget")
    if not daily_budget and start_date and end_date and end_date >= start_date:
        try:
            daily_budget = round(float(budget) / ((end_date - start_date).days + 1))
            daily_budget_source = "derived"
        except (TypeError, ValueError, ZeroDivisionError):
            daily_budget = None
    return {
        "id": str(order.get("id") or order.get("_id") or order_id),
        "status": str(order.get("status") or "pending").lower(),
        "objective": order.get("objective"),
        "budget": budget,
        "daily_budget": daily_budget,
        "daily_budget_source": daily_budget_source,
        "start_date": order.get("startDate") or order.get("start_date"),
        "end_date": order.get("endDate") or order.get("end_date"),
        "placement_count": len(placements) if isinstance(placements, list) else 0,
        "creative_count": len(creatives) if isinstance(creatives, list) else 0,
        "placement_preview": _order_preview(placement_values, kind="placement"),
        "creative_preview": _order_preview(creatives, kind="creative"),
        "warning_count": len(warnings) if isinstance(warnings, list) else 0,
        "order_count": order_count,
    }


def _copilot_progress(session: dict | None) -> dict:
    confirmed = {
        int(value) for value in ((session or {}).get("confirmed_steps") or [])
        if isinstance(value, int) and 0 <= value < len(_COPILOT_STEPS)
    }
    completed = len(confirmed)
    current = next(
        (index for index in range(len(_COPILOT_STEPS)) if index not in confirmed),
        len(_COPILOT_STEPS) - 1,
    )
    return {
        "kind": "steps", "completed": completed, "total": len(_COPILOT_STEPS),
        "percent": round(completed / len(_COPILOT_STEPS) * 100),
        "current_key": str(current), "current_label": _COPILOT_STEPS[current],
    }


def _autopilot_progress(summary: dict | None) -> dict:
    total = max(0, int((summary or {}).get("task_total") or 0))
    completed = min(total, max(0, int((summary or {}).get("task_completed") or 0)))
    task_key = str((summary or {}).get("current_task") or "brief")
    return {
        "kind": "tasks", "completed": completed, "total": total,
        "percent": round(completed / total * 100) if total else 0,
        "current_key": task_key,
        "current_label": task_key.replace("_", " ").strip().title(),
    }


def _progress(conversation: dict, session: dict | None) -> dict:
    if _mode(conversation.get("experience_mode")) == "autopilot":
        return _autopilot_progress(conversation.get("latest_run_summary"))
    return _copilot_progress(session)


def _updated_at(*values: object) -> object | None:
    return next((value for value in values if value is not None), None)


async def _owned_conversations_and_references(actor: dict) -> tuple[list[dict], list[dict]]:
    from campaign_ownership import list_owned_campaign_references, preserve_session_campaigns
    from identity import list_conversations

    conversations = await list_conversations(actor, include_archived=True)
    for conversation in conversations:
        if conversation.get("session_id"):
            await preserve_session_campaigns(conversation["session_id"])
    return conversations, await list_owned_campaign_references(actor)


async def _fetch_owned_orders(references: Iterable[dict]) -> list[dict]:
    from tools.order_api import fetch_order

    semaphore = asyncio.Semaphore(_ORDER_FETCH_CONCURRENCY)

    async def fetch(reference: dict) -> dict | None:
        order_id = str(reference.get("order_id") or "").strip()
        if not order_id:
            return None
        try:
            async with semaphore:
                order = await fetch_order(order_id)
        except Exception:
            return None
        return {"reference": deepcopy(reference), "campaign_id": order_id, "order": order}

    results = await asyncio.gather(*(fetch(reference) for reference in references))
    return [item for item in results if item is not None]


async def list_owned_order_campaigns(actor: dict) -> list[dict]:
    """Return raw orders for trusted internal consumers such as Zalo OA."""
    _, references = await _owned_conversations_and_references(actor)
    campaigns = await _fetch_owned_orders(references)
    campaigns.sort(
        key=lambda item: str(
            item["order"].get("updatedAt") or item["order"].get("createdAt") or ""
        ), reverse=True,
    )
    return [
        {**item["reference"], "campaign_id": item["campaign_id"], "order": item["order"]}
        for item in campaigns
    ]


async def list_campaign_directory(
    actor: dict, *, include_archived: bool = False, limit: int = 50,
    campaign_id: str | None = None,
) -> list[dict]:
    """Return one campaign-centric card per conversation plus retained orders."""
    from session import get_session_progress_summaries

    conversations, references = await _owned_conversations_and_references(actor)
    if campaign_id:
        references = [
            item for item in references
            if str(item.get("order_id") or "") == campaign_id
        ]
        conversation_ids = {
            str(item.get("conversation_id") or "") for item in references
            if item.get("conversation_id")
        }
        conversations = [
            item for item in conversations
            if str(item.get("conversation_id") or "") in conversation_ids
        ]
    session_progress = await get_session_progress_summaries([
        item.get("session_id") for item in conversations if item.get("session_id")
    ])
    order_campaigns = await _fetch_owned_orders(references)
    conversation_ids = {
        str(item.get("conversation_id")) for item in conversations if item.get("conversation_id")
    }
    orders_by_conversation: dict[str, list[dict]] = {}
    orphan_orders: list[dict] = []
    for campaign in order_campaigns:
        conversation_id = str(campaign["reference"].get("conversation_id") or "")
        if conversation_id and conversation_id in conversation_ids:
            orders_by_conversation.setdefault(conversation_id, []).append(campaign)
        else:
            orphan_orders.append(campaign)

    items: list[dict[str, Any]] = []
    for conversation in conversations:
        conversation_id = str(conversation.get("conversation_id") or "")
        mode = _mode(conversation.get("experience_mode"))
        linked_orders = orders_by_conversation.get(conversation_id, [])
        linked_orders.sort(
            key=lambda item: str(
                item["order"].get("updatedAt") or item["order"].get("createdAt") or ""
            ), reverse=True,
        )
        primary = linked_orders[0] if linked_orders else None
        order = primary["order"] if primary else None
        campaign_id = primary["campaign_id"] if primary else None
        summary = conversation.get("latest_run_summary") or {}
        action_required = _action_required(summary)
        archived = bool(conversation.get("archived_at"))
        read_only = bool(order) or summary.get("status") == "completed"
        lifecycle = (
            "archived" if archived else _order_lifecycle(order) if order
            else "needs_review" if action_required else "draft"
        )
        items.append({
            "entry_id": f"conversation:{conversation_id}",
            "conversation_id": conversation_id,
            "campaign_id": campaign_id,
            "order_ids": [item["campaign_id"] for item in linked_orders],
            "title": conversation.get("title") or (order or {}).get("brand") or "Campaign mới",
            "brand": (order or {}).get("brand") or None,
            "experience_mode": mode,
            "phase": "operational" if order else "draft",
            "lifecycle": lifecycle,
            "activity": summary.get("status") or "editing",
            "progress": _progress(
                conversation,
                session_progress.get(str(conversation.get("session_id") or "")),
            ),
            "action_required": action_required,
            "ownership": conversation.get("ownership"),
            "can_claim": bool(conversation.get("can_claim")),
            "archived_at": conversation.get("archived_at"),
            "order": _order_summary(
                campaign_id, order, order_count=len(linked_orders),
            ) if order else None,
            "routes": {
                "manage": f"/manage/campaigns/{campaign_id}" if campaign_id else None,
                "conversation": _conversation_route(
                    conversation_id, mode, read_only=read_only,
                ),
            },
            "read_only": read_only,
            "updated_at": _updated_at(
                (order or {}).get("updatedAt"), summary.get("updated_at"),
                conversation.get("updated_at"),
            ),
        })

    for campaign in orphan_orders:
        reference, order = campaign["reference"], campaign["order"]
        campaign_id = campaign["campaign_id"]
        lifecycle = _order_lifecycle(order)
        items.append({
            "entry_id": f"campaign:{campaign_id}", "conversation_id": None,
            "campaign_id": campaign_id, "order_ids": [campaign_id],
            "title": order.get("brand") or reference.get("conversation_title") or campaign_id,
            "brand": order.get("brand") or None,
            "experience_mode": _mode(reference.get("experience_mode")),
            "phase": "operational", "lifecycle": lifecycle, "activity": "none",
            "progress": None, "action_required": None, "ownership": None,
            "can_claim": False, "archived_at": None,
            "order": _order_summary(campaign_id, order),
            "routes": {
                "manage": f"/manage/campaigns/{campaign_id}", "conversation": None,
            },
            "read_only": True,
            "updated_at": _updated_at(
                order.get("updatedAt"), order.get("createdAt"), reference.get("updated_at"),
            ),
        })

    if not include_archived:
        items = [item for item in items if item["lifecycle"] != "archived"]
    priority = {
        "active": 0, "operational": 0, "paused": 0,
        "needs_review": 1, "draft": 2, "scheduled": 2, "failed": 2,
        "completed": 3, "archived": 5,
    }
    grouped: list[dict] = []
    for value in sorted({priority.get(item.get("lifecycle"), 4) for item in items}):
        group = [item for item in items if priority.get(item.get("lifecycle"), 4) == value]
        group.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        grouped.extend(group)
    result = grouped[:max(1, min(int(limit), 100))]
    from evaluation.store import campaign_health_summaries
    try:
        health = await campaign_health_summaries([item['campaign_id'] for item in result if item.get('campaign_id')])
    except Exception:
        health = {}  # A monitoring outage must not hide the campaign directory.
    for item in result:
        if item.get('campaign_id'):
            item['evaluation_summary'] = health.get(item['campaign_id'], {'status': 'unavailable', 'open_count': None})
    return result


async def get_campaign_directory_entry(actor: dict, campaign_id: str) -> dict | None:
    """Resolve one owned campaign independently of homepage pagination."""
    clean_id = str(campaign_id or "").strip()
    if not clean_id:
        return None
    items = await list_campaign_directory(
        actor, include_archived=True, limit=1, campaign_id=clean_id,
    )
    return items[0] if items else None
