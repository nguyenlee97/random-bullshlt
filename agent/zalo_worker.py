"""Restart-safe Zalo inbound, Autopilot-progress and outbound workers."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import uuid

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import config


_runner: asyncio.Task | None = None
_stop = asyncio.Event()
_worker_id = f"zalo-worker-{uuid.uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _collections():
    from zalo_channel import _collections as channel_collections
    return await channel_collections()


async def enqueue_text(
    *, thread: dict, text: str, idempotency_key: str,
    event_id: str | None = None, run_id: str | None = None,
) -> dict:
    now = _now()
    doc = {
        "_id": f"zout_{uuid.uuid4().hex}",
        "idempotency_key": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
        "channel": "zalo_oa", "oa_id": config.ZALO_OA_ID,
        "thread_id": thread["thread_id"],
        "external_uid": thread["external_uid"],
        "kind": "text", "text": str(text)[:2000],
        "event_id": event_id, "run_id": run_id,
        "category": "live_reply" if event_id else "campaign_progress",
        "status": "queued", "attempts": 0,
        "next_attempt_at": now, "lease_owner": None,
        "lease_expires_at": None, "created_at": now, "updated_at": now,
    }
    collections = await _collections()
    if collections is None:
        return doc
    try:
        await collections["outbound"].insert_one(doc)
    except DuplicateKeyError:
        existing = await collections["outbound"].find_one({
            "idempotency_key": doc["idempotency_key"],
        })
        return existing or doc
    return doc


async def enqueue_image(
    *, thread: dict, image_url: str, idempotency_key: str,
    event_id: str | None = None,
) -> dict:
    now = _now()
    doc = {
        "_id": f"zout_{uuid.uuid4().hex}",
        "idempotency_key": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
        "channel": "zalo_oa", "oa_id": config.ZALO_OA_ID,
        "thread_id": thread["thread_id"], "external_uid": thread["external_uid"],
        "kind": "image", "image_url": image_url,
        "event_id": event_id, "category": "live_reply",
        "status": "queued", "attempts": 0, "next_attempt_at": now,
        "lease_owner": None, "lease_expires_at": None,
        "created_at": now, "updated_at": now,
    }
    collections = await _collections()
    if collections is None:
        return doc
    try:
        await collections["outbound"].insert_one(doc)
    except DuplicateKeyError:
        existing = await collections["outbound"].find_one({
            "idempotency_key": doc["idempotency_key"],
        })
        return existing or doc
    return doc


async def _claim_event() -> dict | None:
    collections = await _collections()
    if collections is None:
        return None
    now = _now()
    return await collections["events"].find_one_and_update(
        {
            "event_name": {"$in": ["user_send_text", "user_send_image"]},
            "$or": [
                {"status": {"$in": ["received", "retry"]}, "$or": [
                    {"next_attempt_at": {"$lte": now}},
                    {"next_attempt_at": {"$exists": False}},
                ]},
                {"status": "processing", "lease_expires_at": {"$lt": now}},
            ],
        },
        {"$set": {
            "status": "processing", "lease_owner": _worker_id,
            "lease_expires_at": now + timedelta(seconds=max(10, config.ZALO_WORKER_LEASE_SECONDS)),
            "updated_at": now,
        }, "$inc": {"attempts": 1}},
        sort=[("received_at", 1)], return_document=ReturnDocument.AFTER,
    )


async def _process_event_once() -> bool:
    event = await _claim_event()
    if not event:
        return False
    collections = await _collections()
    try:
        from zalo_campaign_agent import get_or_create_thread, handle_channel_event
        parts = await handle_channel_event(event)
        thread = await get_or_create_thread(event["external_uid"])
        for index, part in enumerate(parts):
            if isinstance(part, dict) and part.get("kind") == "image":
                await enqueue_image(
                    thread=thread, image_url=part["image_url"],
                    idempotency_key=f"event:{event['event_key']}:{index}:image",
                    event_id=event.get("external_event_id"),
                )
            else:
                await enqueue_text(
                    thread=thread, text=str(part),
                    idempotency_key=f"event:{event['event_key']}:{index}",
                    event_id=event.get("external_event_id"),
                )
        await collections["events"].update_one(
            {"_id": event["_id"], "lease_owner": _worker_id},
            {"$set": {
                "status": "processed", "processed_at": _now(),
                "result": {"outbound_parts": len(parts)},
                "lease_owner": None, "lease_expires_at": None,
            }},
        )
    except Exception as exc:
        attempts = int(event.get("attempts", 1))
        terminal = attempts >= max(1, config.ZALO_WORKER_MAX_ATTEMPTS)
        await collections["events"].update_one(
            {"_id": event["_id"], "lease_owner": _worker_id},
            {"$set": {
                "status": "failed" if terminal else "retry",
                "error": str(exc)[:500],
                "next_attempt_at": _now() + timedelta(seconds=min(300, 2 ** attempts)),
                "lease_owner": None, "lease_expires_at": None,
            }},
        )
    return True


async def _claim_outbound() -> dict | None:
    if not config.ZALO_OUTBOUND_ENABLED:
        return None
    collections = await _collections()
    if collections is None:
        return None
    now = _now()
    return await collections["outbound"].find_one_and_update(
        {"$or": [
            {"status": {"$in": ["queued", "retry"]}, "next_attempt_at": {"$lte": now}},
            {"status": "sending", "lease_expires_at": {"$lt": now}},
        ]},
        {"$set": {
            "status": "sending", "lease_owner": _worker_id,
            "lease_expires_at": now + timedelta(seconds=max(10, config.ZALO_WORKER_LEASE_SECONDS)),
            "updated_at": now,
        }, "$inc": {"attempts": 1}},
        sort=[("created_at", 1)], return_document=ReturnDocument.AFTER,
    )


async def _send_outbound_once() -> bool:
    item = await _claim_outbound()
    if not item:
        return False
    collections = await _collections()
    try:
        from zalo_oa_api import send_image, send_text
        if item.get("kind") == "image":
            receipt = await send_image(item["external_uid"], item["image_url"])
        else:
            receipt = await send_text(item["external_uid"], item["text"])
        await collections["outbound"].update_one(
            {"_id": item["_id"], "lease_owner": _worker_id},
            {"$set": {
                "status": "sent", "sent_at": _now(), "provider_receipt": receipt,
                "lease_owner": None, "lease_expires_at": None,
            }},
        )
    except Exception as exc:
        attempts = int(item.get("attempts", 1))
        retryable = bool(getattr(exc, "retryable", True))
        terminal = not retryable or attempts >= max(1, config.ZALO_WORKER_MAX_ATTEMPTS)
        await collections["outbound"].update_one(
            {"_id": item["_id"], "lease_owner": _worker_id},
            {"$set": {
                "status": "failed" if terminal else "retry",
                "error": str(exc)[:500],
                "next_attempt_at": _now() + timedelta(seconds=min(300, 2 ** attempts)),
                "lease_owner": None, "lease_expires_at": None,
            }},
        )
    return True


_MILESTONE_TASKS = {
    "retrieve_audience": "Đã chuẩn bị audience và targeting.",
    "analyze_creatives": "Đã chuẩn bị và kiểm tra creative.",
    "run_order_guard": "Setup, placement và forecast đã sẵn sàng.",
    "create_setup_report": "Campaign đã launch và báo cáo setup đã sẵn sàng.",
}


def _progress_message(run: dict, event: dict) -> str | None:
    event_type = event.get("type")
    payload = event.get("payload") or {}
    if event_type == "run_created":
        return f"Autopilot {run['run_id']}: đã nhận brief và bắt đầu thực thi."
    task_id = str(payload.get("task_id") or "")
    task = next((item for item in run.get("tasks", []) if item.get("task_id") == task_id), None)
    if event_type == "task_completed" and task and task.get("key") in _MILESTONE_TASKS:
        return f"Autopilot {run['run_id']}: {_MILESTONE_TASKS[task['key']]}"
    if event_type == "task_waiting_review" and task:
        label = task.get("title") or task.get("key")
        if task.get("key") == "launch_approval":
            return (
                f"Autopilot {run['run_id']} đang chờ XÁC NHẬN LAUNCH ở bước “{label}”. "
                "Trả lời “Xác nhận” hoặc mở web workspace để review."
            )
        return (
            f"Autopilot {run['run_id']} đang chờ duyệt bước quan trọng “{label}”. "
            "Trả lời “Xác nhận” để tiếp tục hoặc “Hủy” để dừng."
        )
    if event_type in {"task_failed", "run_cancelled"}:
        return f"Autopilot {run['run_id']}: {event_type.replace('_', ' ')}."
    return None


async def _process_progress_once() -> bool:
    collections = await _collections()
    if collections is None:
        return False
    subscription = await collections["subscriptions"].find_one(
        {"status": "active"}, sort=[("updated_at", 1)]
    )
    if not subscription:
        return False
    try:
        from autopilot.service import get_run, list_events
        run = await get_run(subscription["run_id"])
        events = await list_events(subscription["run_id"])
        delivered = set(subscription.get("delivered_event_ids") or [])
        thread = await collections["threads"].find_one({"_id": subscription["thread_id"]})
        if not thread:
            await collections["subscriptions"].update_one(
                {"_id": subscription["_id"]}, {"$set": {"status": "orphaned", "updated_at": _now()}}
            )
            return True
        new_ids = []
        for event in events:
            event_id = event["event_id"]
            if event_id in delivered:
                continue
            new_ids.append(event_id)
            text = _progress_message(run, event)
            if text:
                await enqueue_text(
                    thread=thread, text=text,
                    idempotency_key=f"run-event:{event_id}", run_id=run["run_id"],
                )
        terminal_key = f"terminal:{run.get('status')}"
        terminal_sent = set(subscription.get("terminal_markers") or [])
        terminal_markers = []
        if run.get("status") in {"completed", "failed", "cancelled"} and terminal_key not in terminal_sent:
            terminal_markers.append(terminal_key)
            await enqueue_text(
                thread=thread,
                text=f"Autopilot {run['run_id']} đã {run['status']}. Mở workspace: {config.ZALO_WEB_WORKSPACE_URL}/?conversation={thread.get('active_campaign_conversation_id') or thread.get('conversation_id')}",
                idempotency_key=f"run:{run['run_id']}:{terminal_key}", run_id=run["run_id"],
            )
        update = {"updated_at": _now()}
        if new_ids:
            update["delivered_event_ids"] = list(delivered.union(new_ids))[-300:]
        if terminal_markers:
            update["terminal_markers"] = list(terminal_sent.union(terminal_markers))
            update["status"] = "completed"
        await collections["subscriptions"].update_one(
            {"_id": subscription["_id"]}, {"$set": update}
        )
    except Exception as exc:
        await collections["subscriptions"].update_one(
            {"_id": subscription["_id"]},
            {"$set": {"error": str(exc)[:500], "updated_at": _now()}},
        )
    return True


async def process_available_once() -> dict:
    """Deterministic single-cycle entrypoint used by tests and readiness drills."""
    inbound = await _process_event_once()
    progress = await _process_progress_once()
    outbound = await _send_outbound_once()
    return {"inbound": inbound, "progress": progress, "outbound": outbound}


async def _loop() -> None:
    while not _stop.is_set():
        did_work = False
        try:
            result = await process_available_once()
            did_work = any(result.values())
        except asyncio.CancelledError:
            raise
        except Exception:
            did_work = False
        if not did_work:
            try:
                await asyncio.wait_for(
                    _stop.wait(), timeout=max(0.2, config.ZALO_WORKER_POLL_SECONDS)
                )
            except asyncio.TimeoutError:
                pass


async def start_worker() -> None:
    global _runner
    if _runner and not _runner.done():
        return
    _stop.clear()
    _runner = asyncio.create_task(_loop(), name="zalo-channel-worker")


async def stop_worker() -> None:
    global _runner
    _stop.set()
    if _runner:
        _runner.cancel()
        try:
            await _runner
        except asyncio.CancelledError:
            pass
    _runner = None


def worker_running() -> bool:
    return bool(_runner and not _runner.done())
