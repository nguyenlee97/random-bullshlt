"""Account-owned campaign operations for the Zalo OA channel.

This module is deliberately channel-shaped and workflow-agnostic: it resolves a
signed OA sender into the existing account/conversation authority, selects only
orders referenced by owned campaign sessions, and invokes the shared report or
Autopilot services. The LLM may extract a brief or summarize fetched data; it
never selects an owner, campaign ID, mutation or backend endpoint.
"""
from __future__ import annotations

import asyncio
import base64
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import re
import unicodedata
from urllib.parse import quote
import uuid

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import config


_mem_threads: dict[str, dict] = {}
_mem_subscriptions: dict[tuple[str, str], dict] = {}
_mem_media: dict[str, dict] = {}
_mem_lock = asyncio.Lock()

_CONFIRM = {
    "dong y", "xac nhan", "chap nhan", "duyet", "tiep tuc", "yes", "ok",
}
_REJECT = {"khong dong y", "tu choi", "huy", "huy bo", "khong"}

_GREETING_OR_HELP = {
    "alo", "ban lam duoc gi", "chao", "chao ban", "hello", "help", "hey",
    "hi", "menu", "tro giup", "xin chao", "xin chao ban",
}

_CAMPAIGN_OPERATION_TERMS = (
    "anh quang cao", "audience", "awareness", "bao cao", "budget",
    "cap nhat", "cau hinh", "chien dich nay", "chi tiet", "click",
    "consideration", "conversion", "creative", "ctr", "daily",
    "dang sao", "executive", "impression", "kich hoat lai", "live",
    "ngan sach", "pause", "placement", "reach", "report", "resume",
    "retention", "screenshot", "setup", "status", "sua", "tam dung",
    "target", "targeting", "the nao", "thay doi", "tiep tuc lai",
    "trang thai", "xem quang cao",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or "").lower())
    return " ".join(
        "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        .replace("đ", "d")
        .split()
    )


def _help_text() -> str:
    return (
        "Chào bạn 👋 Mình là trợ lý đồng hành cùng chiến dịch quảng cáo của bạn. "
        "Mình có thể giúp xem báo cáo, kiểm tra ảnh live, cấu hình hoặc tiến độ campaign.\n\n"
        "Nếu bạn muốn được hướng dẫn kỹ hơn, hãy nói với mình nhé.\n\n"
        "Hôm nay bạn muốn mình xem điều gì trước?"
    )


def _has_campaign_operation_intent(folded: str) -> bool:
    return any(term in folded for term in _CAMPAIGN_OPERATION_TERMS)


def _public(doc: dict) -> dict:
    value = deepcopy(doc)
    value.pop("_id", None)
    return value


async def _collections():
    from zalo_channel import _collections as channel_collections
    return await channel_collections()


def _thread_actor(thread: dict) -> dict:
    return {
        "user_id": thread.get("user_id"),
        "anonymous_id": thread.get("anonymous_id"),
        "account_session_id": None,
    }


async def get_or_create_thread(external_uid: str) -> dict:
    """Resolve a stable server-owned Zalo thread for one signed sender."""
    from identity import bootstrap_anonymous, create_conversation
    from zalo_channel import resolve_linked_user

    uid = str(external_uid or "").strip()
    if not uid:
        raise ValueError("signed Zalo sender is required")
    user_id = await resolve_linked_user(uid)
    collections = await _collections()
    query = {"channel": "zalo_oa", "oa_id": config.ZALO_OA_ID, "external_uid": uid}
    if collections is not None:
        existing = await collections["threads"].find_one(query)
    else:
        existing = next((item for item in _mem_threads.values() if all(
            item.get(key) == value for key, value in query.items()
        )), None)
    if existing:
        if user_id and existing.get("user_id") != user_id:
            anonymous_id = existing.get("anonymous_id")
            if anonymous_id:
                from identity import claim_channel_anonymous_conversations
                await claim_channel_anonymous_conversations(
                    user_id=user_id, anonymous_id=anonymous_id,
                )
            updates = {
                "user_id": user_id, "anonymous_id": None,
                "linked_at": _now(), "updated_at": _now(),
            }
            if collections is not None:
                await collections["threads"].update_one(
                    {"_id": existing["_id"]}, {"$set": updates}
                )
            else:
                existing.update(updates)
            existing.update(updates)
        return _public(existing)

    actor = {"user_id": user_id, "anonymous_id": None, "account_session_id": None}
    if not user_id:
        anonymous = await bootstrap_anonymous()
        actor["anonymous_id"] = anonymous["identity_id"]
    conversation = await create_conversation(
        actor, title="Trợ lý Zalo OA", experience_mode=None,
    )
    now = _now()
    thread_id = f"zth_{uuid.uuid4().hex}"
    doc = {
        "_id": thread_id, "thread_id": thread_id,
        **query, "user_id": actor.get("user_id"),
        "anonymous_id": actor.get("anonymous_id"),
        "conversation_id": conversation["conversation_id"],
        "session_id": conversation["session_id"],
        "active_campaign_id": None,
        "active_campaign_conversation_id": None,
        "active_campaign_session_id": None,
        "active_report_campaign_id": None,
        "active_report_view": None,
        "pending_report_request": None,
        "pending_action": None, "revision": 1,
        "created_at": now, "updated_at": now,
    }
    if collections is not None:
        try:
            await collections["threads"].insert_one(doc)
        except DuplicateKeyError:
            return _public(await collections["threads"].find_one(query))
    else:
        async with _mem_lock:
            duplicate = next((item for item in _mem_threads.values() if all(
                item.get(key) == value for key, value in query.items()
            )), None)
            if duplicate:
                return _public(duplicate)
            _mem_threads[thread_id] = doc
    return _public(doc)


async def _update_thread(thread: dict, updates: dict) -> dict:
    updates = {**deepcopy(updates), "updated_at": _now()}
    collections = await _collections()
    if collections is not None:
        doc = await collections["threads"].find_one_and_update(
            {"_id": thread["thread_id"]},
            {"$set": updates, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise KeyError("channel thread not found")
    else:
        doc = _mem_threads[thread["thread_id"]]
        doc.update(updates)
        doc["revision"] = int(doc.get("revision", 0)) + 1
    return _public(doc)


async def owned_campaigns(thread: dict) -> list[dict]:
    """Return orders from the durable registry owned by this channel actor."""
    from campaign_ownership import (
        list_owned_campaign_references,
        preserve_session_campaigns,
    )
    from identity import list_conversations
    from tools.order_api import fetch_order

    actor = _thread_actor(thread)
    # Additive migration: every surviving legacy conversation self-backfills on
    # read. Future conversation deletion also preserves these references first.
    conversations = await list_conversations(actor, include_archived=True)
    for conversation in conversations:
        session_id = conversation.get("session_id")
        if session_id:
            await preserve_session_campaigns(session_id)
    references = {
        item["order_id"]: item
        for item in await list_owned_campaign_references(actor)
    }

    async def fetch(item: tuple[str, dict]) -> dict | None:
        order_id, reference = item
        try:
            order = await fetch_order(order_id)
        except Exception:
            return None
        return {**reference, "campaign_id": order_id, "order": order}

    campaigns = [item for item in await asyncio.gather(*(fetch(item) for item in references.items())) if item]
    campaigns.sort(key=lambda item: str(item["order"].get("updatedAt") or item["order"].get("createdAt") or ""), reverse=True)
    return campaigns


def resolve_campaign(
    message: str, campaigns: list[dict], active_campaign_id: str | None = None,
    *, allow_context_fallback: bool = True,
) -> tuple[dict | None, list[dict]]:
    """Resolve only among already ownership-proven campaigns; never guess."""
    if not campaigns:
        return None, []
    folded = _fold(message)
    by_id = {str(item["campaign_id"]).lower(): item for item in campaigns}
    explicit_ids = [item for key, item in by_id.items() if key and key in message.lower()]
    if len(explicit_ids) == 1:
        return explicit_ids[0], []
    exact_names = []
    partial_names = []
    token_scores: list[tuple[int, dict]] = []
    for item in campaigns:
        name = _fold(item["order"].get("brand") or item.get("conversation_title") or "")
        if not name:
            continue
        if folded == name:
            exact_names.append(item)
        elif name in folded or (len(folded) >= 4 and folded in name):
            partial_names.append(item)
        name_tokens = {token for token in name.split() if len(token) >= 4}
        message_tokens = set(folded.split())
        token_scores.append((len(name_tokens.intersection(message_tokens)), item))
    if len(exact_names) == 1:
        return exact_names[0], []
    if len(partial_names) == 1:
        return partial_names[0], []
    if len(exact_names) > 1 or len(partial_names) > 1:
        return None, exact_names or partial_names
    best_score = max((score for score, _ in token_scores), default=0)
    token_matches = [item for score, item in token_scores if score == best_score and score > 0]
    if len(token_matches) == 1:
        return token_matches[0], []
    if len(token_matches) > 1:
        return None, token_matches
    if allow_context_fallback:
        active_key = str(active_campaign_id or "").lower()
        if active_key and active_key in by_id:
            return by_id[active_key], []
        if len(campaigns) == 1:
            return campaigns[0], []
        return None, campaigns
    return None, []


def _campaign_choices(campaigns: list[dict]) -> str:
    lines = ["Bạn đang nói về chiến dịch nào?"]
    for index, item in enumerate(campaigns[:8], 1):
        order = item["order"]
        lines.append(
            f"{index}. {order.get('brand') or item['campaign_id']} — "
            f"{order.get('status') or 'không rõ'} — {item['campaign_id']}"
        )
    lines.append("Trả lời bằng số, tên hoặc mã chiến dịch.")
    return "\n".join(lines)


def _campaign_list_text(campaigns: list[dict], status_filter: str = "") -> str:
    if not campaigns:
        if status_filter == "active":
            return "Hiện không có chiến dịch nào đang chạy trong tài khoản này."
        if status_filter == "paused":
            return "Hiện không có chiến dịch nào đang tạm dừng trong tài khoản này."
        return "Bạn chưa có chiến dịch nào trong tài khoản này."
    heading = "Các chiến dịch phù hợp:"
    if status_filter == "active":
        heading = "Các chiến dịch đang chạy:"
    elif status_filter == "paused":
        heading = "Các chiến dịch đang tạm dừng:"
    lines = [heading]
    for index, item in enumerate(campaigns[:8], 1):
        order = item["order"]
        lines.append(
            f"{index}. {order.get('brand') or item['campaign_id']} — "
            f"{order.get('status') or 'không rõ'} — {item['campaign_id']}"
        )
    return "\n".join(lines)


async def _select_campaign(thread: dict, campaign: dict) -> dict:
    return await _update_thread(thread, {
        "active_campaign_id": campaign["campaign_id"],
        "active_campaign_conversation_id": campaign["conversation_id"],
        "active_campaign_session_id": campaign["session_id"],
        "active_report_campaign_id": None,
        "active_report_view": None,
        "pending_report_request": None,
        "pending_action": None,
    })


def _workspace_link(campaign: dict | None) -> str:
    if not campaign:
        return config.ZALO_WEB_WORKSPACE_URL
    return (
        f"{config.ZALO_WEB_WORKSPACE_URL}/?conversation="
        f"{quote(str(campaign['conversation_id']), safe='')}"
    )


def _report_type(message: str) -> str:
    folded = _fold(message)
    for value in ("daily_ops", "awareness", "consideration", "conversion", "retention", "executive"):
        if value.replace("_", " ") in folded:
            return value
    if "hang ngay" in folded or "daily" in folded or "van hanh" in folded:
        return "daily_ops"
    if "nhan biet" in folded:
        return "awareness"
    if "can nhac" in folded:
        return "consideration"
    if "chuyen doi" in folded:
        return "conversion"
    if "giu chan" in folded:
        return "retention"
    if "dieu hanh" in folded or "tong quan" in folded:
        return "executive"
    return "daily_ops"


async def _answer_report(message: str, campaign: dict) -> str:
    from handlers.report import handle_report_chat, handle_report_entry
    from session import get_or_create_session

    session = await get_or_create_session(campaign["session_id"])
    context = session.get("form_state", {}).get("report_context", {})
    if str(context.get("campaignId") or "") != campaign["campaign_id"]:
        await handle_report_entry(campaign["session_id"])
    result = await handle_report_chat(
        message, campaign["session_id"], _report_type(message),
    )
    return result.text


def _status_text(campaign: dict) -> str:
    order = campaign["order"]
    return (
        f"Chiến dịch: {order.get('brand') or campaign['campaign_id']}\n"
        f"Mã: {campaign['campaign_id']}\n"
        f"Trạng thái: {order.get('status') or 'không rõ'}\n"
        f"Mục tiêu: {order.get('objective') or 'không rõ'}\n"
        f"Ngân sách: {order.get('budget') or 0:,.0f} VND\n"
        f"Thời gian: {order.get('startDate') or '?'} → {order.get('endDate') or '?'}"
    )


async def _setup_text(campaign: dict) -> str:
    from workspace.service import get_workspace
    order = campaign["order"]
    workspace = await get_workspace(campaign["session_id"])
    artifacts = workspace.get("artifacts", {})
    audience = (artifacts.get("audience", {}) or {}).get("value") or {}
    targeting = (artifacts.get("targeting", {}) or {}).get("value") or order.get("targeting") or {}
    placements = order.get("placements") or []
    creatives = order.get("creatives") or []
    attrs = audience.get("attrs") or audience.get("recommendations") or [] if isinstance(audience, dict) else []
    audience_names = [str(item.get("fullLabel") or item.get("name") or item.get("label")) for item in attrs[:6] if isinstance(item, dict)]
    return (
        f"Cấu hình — {order.get('brand') or campaign['campaign_id']}\n"
        f"• Objective: {order.get('objective') or 'không rõ'}\n"
        f"• Budget: {order.get('budget') or 0:,.0f} VND\n"
        f"• Audience: {', '.join(audience_names) if audience_names else 'chưa có dữ liệu'}\n"
        f"• Targeting: {json.dumps(targeting, ensure_ascii=False)[:500]}\n"
        f"• Placements: {', '.join(map(str, placements)) or 'chưa có'}\n"
        f"• Creative assets: {len(creatives) or (1 if order.get('creative') else 0)}\n"
        f"Mở workspace: {_workspace_link(campaign)}"
    )


def _live_text(campaign: dict) -> str:
    order = campaign["order"]
    sites = []
    for zone in order.get("placements") or []:
        folded = _fold(zone)
        if "zmp3" in folded or "zingmp3" in folded:
            sites.append("https://zingmp3-stg.pawgrammers.io.vn")
        elif "bm" in folded or "baomoi" in folded:
            sites.append("https://baomoi-stg.pawgrammers.io.vn")
        else:
            sites.append("https://znews-stg.pawgrammers.io.vn")
    sites = list(dict.fromkeys(sites))
    creative_urls = [
        str(item.get("url")) for item in order.get("creatives") or []
        if isinstance(item, dict) and item.get("url")
    ]
    lines = [f"Live view — {order.get('brand') or campaign['campaign_id']}"]
    lines.extend(f"• {url}" for url in sites)
    if creative_urls:
        lines.append(f"Creative preview: {creative_urls[0]}")
    if not sites:
        lines.append("Chưa có placement để tạo liên kết live.")
    return "\n".join(lines)


async def _store_channel_media(
    image_bytes: bytes, content_type: str = "image/png", *, filename: str | None = None,
) -> str:
    """Persist short-lived media bytes behind a hashed opaque URL token."""
    import hashlib
    import secrets
    from bson.binary import Binary

    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = _now()
    doc = {
        "_id": f"zmedia_{uuid.uuid4().hex}", "token_hash": digest,
        "content_type": content_type, "data": Binary(image_bytes),
        "created_at": now,
        "expires_at": now + timedelta(seconds=max(60, config.ZALO_MEDIA_TTL_SECONDS)),
    }
    if filename:
        safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip(".-")[:120]
        if safe_filename:
            doc["filename"] = safe_filename
    collections = await _collections()
    if collections is not None:
        await collections["media"].insert_one(doc)
    else:
        _mem_media[digest] = doc
    return f"{config.ZALO_PUBLIC_API_URL}/zalo/media/{token}"


async def _delivery_image_parts(
    image_bytes: bytes,
    content_type: str,
    *,
    label: str = "ảnh",
) -> list[str | dict]:
    """Store a <=1 MB OA image plus an expiring original-resolution fallback."""
    from zalo_media import prepare_zalo_image

    prepared = prepare_zalo_image(image_bytes, content_type)
    image_url = await _store_channel_media(prepared.data, prepared.content_type)
    parts: list[str | dict] = [{
        "kind": "image", "image_url": image_url,
        "byte_size": len(prepared.data),
    }]
    if prepared.changed:
        original_url = await _store_channel_media(image_bytes, content_type)
        ttl_minutes = max(1, config.ZALO_MEDIA_TTL_SECONDS // 60)
        parts.append(
            f"Ảnh {label} đã được tối ưu dưới 1 MB để gửi qua Zalo. "
            f"Xem bản đầy đủ trong {ttl_minutes} phút: {original_url}"
        )
    return parts


async def _get_channel_media_doc(token: str) -> dict | None:
    import hashlib
    digest = hashlib.sha256(str(token or "").encode()).hexdigest()
    collections = await _collections()
    if collections is not None:
        doc = await collections["media"].find_one({
            "token_hash": digest, "expires_at": {"$gt": _now()},
        })
    else:
        doc = _mem_media.get(digest)
        if doc and doc.get("expires_at") <= _now():
            doc = None
    if not doc:
        return None
    return doc


async def get_channel_media(token: str) -> tuple[bytes, str] | None:
    """Backward-compatible media lookup used by existing image callers/tests."""
    doc = await _get_channel_media_doc(token)
    if not doc:
        return None
    return bytes(doc["data"]), str(doc.get("content_type") or "image/png")


async def get_channel_media_download(token: str) -> tuple[bytes, str, str | None] | None:
    doc = await _get_channel_media_doc(token)
    if not doc:
        return None
    return (
        bytes(doc["data"]), str(doc.get("content_type") or "application/octet-stream"),
        str(doc.get("filename")) if doc.get("filename") else None,
    )


async def _live_response(
    campaign: dict,
    requested_site: str = "all",
) -> list[str | dict]:
    """Capture site groups in the order: heading, zone image(s), full site."""
    order = campaign["order"]
    placements = [str(item) for item in order.get("placements") or []]
    specs = {
        "baomoi": ("BaoMoi", "https://baomoi-stg.pawgrammers.io.vn"),
        "znews": ("Znews", "https://znews-stg.pawgrammers.io.vn"),
        "zingmp3": ("ZingMP3", "https://zingmp3-stg.pawgrammers.io.vn"),
    }
    placement_groups: dict[str, list[str]] = {key: [] for key in specs}
    for zone in placements:
        folded = _fold(zone).replace(" ", "")
        if "zingmp3" in folded or "zmp3" in folded:
            placement_groups["zingmp3"].append(zone)
        elif "baomoi" in folded or folded.startswith("bm"):
            placement_groups["baomoi"].append(zone)
        else:
            placement_groups["znews"].append(zone)

    if requested_site not in {*specs, "all"}:
        return ["Mình chưa hỗ trợ site live này."]
    selected = (
        [requested_site] if requested_site != "all"
        else [key for key in specs if placement_groups[key]]
    )
    if not selected:
        return ["Campaign này chưa có placement để chụp ảnh live."]
    if requested_site != "all" and not placement_groups[requested_site]:
        label = specs[requested_site][0]
        return [f"Campaign này không có placement trên {label}, nên mình không thể chụp ảnh live của site đó."]

    from handlers.screenshot import handle_screenshot
    parts: list[str | dict] = []
    for site_key in selected:
        label, url = specs[site_key]
        try:
            screenshot = await handle_screenshot(
                url=url, session_id=campaign["session_id"],
                zone_ids=placement_groups[site_key],
            )
        except Exception:
            screenshot = {"ok": False}
        if not screenshot.get("ok"):
            parts.append(f"Mình chưa chụp được ảnh live trên {label}. Bạn thử lại sau ít phút nhé.")
            continue

        parts.append(f"Đây là ảnh live quảng cáo trên {label}:")
        for zone in screenshot.get("zones") or []:
            crop_b64 = zone.get("crop_b64")
            if not crop_b64:
                continue
            parts.extend(await _delivery_image_parts(
                base64.b64decode(crop_b64), "image/png",
                label=f"zone {zone.get('label') or zone.get('id') or label}",
            ))
        if screenshot.get("full_b64"):
            parts.extend(await _delivery_image_parts(
                base64.b64decode(screenshot["full_b64"]), "image/jpeg",
                label=f"toàn trang {label}",
            ))
    return parts or ["Mình chưa chụp được ảnh live lúc này. Bạn thử lại sau ít phút nhé."]


async def _lifecycle_request(thread: dict, campaign: dict, action: str) -> str:
    order = campaign["order"]
    target = "paused" if action == "pause" else "active"
    if str(order.get("status") or "").lower() == target:
        verb = "tạm dừng" if action == "pause" else "hoạt động"
        return f"Chiến dịch {order.get('brand')} đã ở trạng thái {verb}."
    pending = {
        "kind": "campaign_lifecycle", "action": action,
        "campaign_id": campaign["campaign_id"],
        "conversation_id": campaign["conversation_id"],
        "session_id": campaign["session_id"],
        "nonce": uuid.uuid4().hex, "expires_at": _now() + timedelta(minutes=5),
    }
    await _update_thread(thread, {"pending_action": pending})
    verb = "TẠM DỪNG" if action == "pause" else "TIẾP TỤC"
    return (
        f"Xác nhận {verb} chiến dịch “{order.get('brand') or campaign['campaign_id']}” "
        f"({campaign['campaign_id']})?\nTrả lời “Xác nhận” để thực hiện hoặc “Hủy” để giữ nguyên."
    )


def _pending_expired(pending: dict) -> bool:
    expiry = pending.get("expires_at")
    if not isinstance(expiry, datetime):
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry <= _now()


async def _handle_pending(thread: dict, message: str, campaigns: list[dict]) -> tuple[str | None, dict]:
    pending = thread.get("pending_action") or {}
    if not pending:
        return None, thread
    if _pending_expired(pending):
        thread = await _update_thread(thread, {"pending_action": None})
        return "Yêu cầu trước đã hết hạn. Vui lòng gửi lại nếu bạn vẫn muốn thực hiện.", thread
    folded = _fold(message)
    if pending.get("kind") == "campaign_selection":
        pending_ids = [
            str(item) for item in (pending.get("campaign_ids") or []) if item
        ]
        eligible_campaigns = [
            item for campaign_id in pending_ids
            for item in campaigns
            if item["campaign_id"] == campaign_id
        ]
        if not eligible_campaigns:
            thread = await _update_thread(thread, {"pending_action": None})
            return (
                "Các chiến dịch trong lựa chọn trước không còn khả dụng hoặc bạn không còn quyền truy cập. "
                "Không có thao tác nào được thực hiện.",
                thread,
            )
        selected = None
        if folded.isdigit():
            index = int(folded) - 1
            if 0 <= index < len(eligible_campaigns):
                selected = eligible_campaigns[index]
        if not selected:
            selected, _ = resolve_campaign(
                message, eligible_campaigns, None,
                allow_context_fallback=False,
            )
        if not selected and config.ZALO_OPENAI_ENABLED:
            try:
                from session import get_history
                from zalo_openai import plan_zalo_turn
                plan = await plan_zalo_turn(
                    message=message,
                    history=await get_history(thread["session_id"]),
                    campaigns=eligible_campaigns,
                    thread=thread,
                )
                if 1 <= plan.selected_campaign_index <= len(eligible_campaigns):
                    selected = eligible_campaigns[plan.selected_campaign_index - 1]
                elif plan.campaign_reference:
                    selected, _ = resolve_campaign(
                        plan.campaign_reference, eligible_campaigns, None,
                        allow_context_fallback=False,
                    )
            except Exception:
                pass
        if not selected:
            return _campaign_choices(eligible_campaigns), thread
        thread = await _select_campaign(thread, selected)
        return f"Đã chọn chiến dịch “{selected['order'].get('brand')}” ({selected['campaign_id']}).", thread
    if folded in _REJECT:
        thread = await _update_thread(thread, {"pending_action": None})
        return "Đã hủy yêu cầu. Không có thay đổi nào được thực hiện.", thread
    if pending.get("kind") == "campaign_lifecycle":
        if folded not in _CONFIRM:
            return "Yêu cầu đang chờ xác nhận. Trả lời “Xác nhận” hoặc “Hủy” — hệ thống sẽ không tự suy đoán.", thread
        campaign = next((item for item in campaigns if item["campaign_id"] == pending.get("campaign_id") and item["session_id"] == pending.get("session_id")), None)
        if not campaign:
            thread = await _update_thread(thread, {"pending_action": None})
            return "Không còn quyền truy cập chiến dịch này. Không có thay đổi nào được thực hiện.", thread
        from tools.order_api import set_order_delivery_state
        try:
            result = await set_order_delivery_state(campaign["campaign_id"], pending["action"])
        except Exception as exc:
            thread = await _update_thread(thread, {"pending_action": None})
            return f"Không thể cập nhật trạng thái chiến dịch: {str(exc)[:240]}", thread
        thread = await _update_thread(thread, {"pending_action": None})
        state = "đã tạm dừng" if pending["action"] == "pause" else "đã tiếp tục hoạt động"
        suffix = " (trạng thái đã đúng từ trước)" if result.get("already_in_state") else ""
        return f"Chiến dịch “{campaign['order'].get('brand')}” {state}{suffix}.", thread
    if pending.get("kind") == "choose_autopilot_mode":
        if any(word in folded for word in ("tu dong", "fully", "automatic")):
            mode = "fully_automatic"
        elif any(word in folded for word in ("ban tu dong", "semi", "quan trong")):
            mode = "semi_automatic"
        else:
            mode = ""
            if config.ZALO_OPENAI_ENABLED:
                try:
                    from session import get_history
                    from zalo_openai import plan_zalo_turn
                    plan = await plan_zalo_turn(
                        message=message,
                        history=await get_history(thread["session_id"]),
                        campaigns=[],
                        thread=thread,
                    )
                    mode = plan.autopilot_mode
                except Exception:
                    pass
            if mode not in {"fully_automatic", "semi_automatic"}:
                return "Chọn 1) Tự động hoàn toàn hoặc 2) Bán tự động.", thread
        thread = await _update_thread(thread, {"pending_action": {
            "kind": "collect_autopilot_brief", "mode": mode,
            "expires_at": _now() + timedelta(minutes=30),
        }})
        return (
            "Hãy gửi brief gồm: thương hiệu, mục tiêu, ngân sách (triệu VND), "
            "ngày bắt đầu/kết thúc và thông điệp hoặc ghi chú."
        ), thread
    if pending.get("kind") == "collect_autopilot_brief":
        from session import get_history
        brief, errors = await _extract_brief(
            message,
            history=await get_history(thread["session_id"]),
            thread_id=thread["thread_id"],
        )
        if errors:
            return "Brief chưa đủ để chạy Autopilot:\n- " + "\n- ".join(errors), thread
        thread = await _update_thread(thread, {"pending_action": {
            "kind": "confirm_autopilot_brief", "mode": pending["mode"],
            "brief": brief, "expires_at": _now() + timedelta(minutes=15),
        }})
        return (
            f"Xác nhận brief Autopilot:\n• Brand: {brief['brand']}\n"
            f"• Objective: {brief['objective']}\n• Budget: {brief['budget']} triệu VND\n"
            f"• Dates: {brief['startDate']} → {brief['endDate']}\n"
            "Creative source: AI generation. Trả lời “Xác nhận” để bắt đầu hoặc “Hủy”."
        ), thread
    if pending.get("kind") == "confirm_autopilot_brief":
        if folded not in _CONFIRM:
            return "Brief đang chờ duyệt. Trả lời “Xác nhận” hoặc “Hủy”.", thread
        result = await _start_autopilot(thread, pending["brief"], pending["mode"])
        thread = result["thread"]
        return result["text"], thread
    return None, thread


async def _extract_brief(
    message: str, *, history: list[dict] | None = None, thread_id: str = "",
) -> tuple[dict | None, list[str]]:
    from autopilot.capabilities import validate_brief_value
    if config.ZALO_OPENAI_ENABLED:
        try:
            from zalo_openai import extract_zalo_brief
            value = await extract_zalo_brief(
                message=message,
                history=history or [],
                thread_id=thread_id,
            )
        except Exception:
            value = {}
    else:
        system = (
            "Trích xuất brief quảng cáo từ tin nhắn tiếng Việt. Chỉ trả về một JSON object với "
            "brand, advertiser, objective, kpi, budget, startDate, endDate, notes. "
            "objective phải là awareness, consideration, conversion hoặc retention. "
            "budget dùng đơn vị triệu VND. Ngày dùng YYYY-MM-DD. Không bịa trường còn thiếu; dùng chuỗi rỗng hoặc 0."
        )
        try:
            from llm import simple_generate
            raw = await asyncio.to_thread(simple_generate, system, message)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            value = json.loads(match.group(0) if match else raw)
        except Exception:
            value = {}
    brief, errors = validate_brief_value(value, today=date.today())
    return brief, errors


async def _start_autopilot(thread: dict, brief: dict, mode: str) -> dict:
    from autopilot.service import create_run
    from identity import create_conversation, set_conversation_title_for_session
    from workspace.service import apply_mutation, get_workspace

    actor = _thread_actor(thread)
    conversation = await create_conversation(
        actor, title=brief["brand"], experience_mode="autopilot",
    )
    workspace = await get_workspace(conversation["session_id"])
    await apply_mutation(
        conversation["session_id"], "brief", brief,
        base_revision=workspace["revision"], actor="zalo_campaign_operator",
        reason="explicit Zalo Autopilot brief confirmation",
        idempotency_key=f"zalo-brief:{thread['thread_id']}:{uuid.uuid4().hex}",
    )
    await set_conversation_title_for_session(conversation["session_id"], brief["brand"])
    policy = "auto_build_draft" if mode == "fully_automatic" else "critical_only"
    run = await create_run(
        conversation["session_id"], approval_policy=policy,
        creative_source="ai_generate", actor="zalo_campaign_operator",
        idempotency_key=f"zalo-run:{thread['thread_id']}:{uuid.uuid4().hex}",
    )
    thread = await _update_thread(thread, {
        "pending_action": None,
        "active_campaign_id": None,
        "active_campaign_conversation_id": conversation["conversation_id"],
        "active_campaign_session_id": conversation["session_id"],
    })
    await subscribe_run(thread, run["run_id"])
    mode_label = "Tự động hoàn toàn" if mode == "fully_automatic" else "Bán tự động"
    return {"thread": thread, "text": (
        f"Đã bắt đầu Campaign Autopilot cho “{brief['brand']}”.\n"
        f"Mode: {mode_label}\nRun: {run['run_id']}\n"
        "Tôi sẽ cập nhật ở các mốc quan trọng. Cả hai mode đều dừng để xác nhận trước khi launch."
    )}


async def subscribe_run(thread: dict, run_id: str) -> None:
    now = _now()
    doc = {
        "_id": f"zsub_{uuid.uuid4().hex}", "thread_id": thread["thread_id"],
        "run_id": run_id, "status": "active", "delivered_event_ids": [],
        "created_at": now, "updated_at": now,
    }
    collections = await _collections()
    if collections is not None:
        await collections["subscriptions"].update_one(
            {"thread_id": thread["thread_id"], "run_id": run_id},
            {"$setOnInsert": doc}, upsert=True,
        )
    else:
        _mem_subscriptions.setdefault((thread["thread_id"], run_id), doc)


async def _plan_openai_turn(
    *, message: str, history: list[dict], campaigns: list[dict], thread: dict,
):
    if not config.ZALO_OPENAI_ENABLED:
        return None
    from zalo_openai import plan_zalo_turn
    return await plan_zalo_turn(
        message=message, history=history, campaigns=campaigns, thread=thread,
    )


async def _render_openai_tool_result(
    *, message: str, history: list[dict], intent: str, tool_result: str,
    thread: dict,
) -> str:
    if not config.ZALO_OPENAI_ENABLED:
        return tool_result
    from zalo_openai import render_zalo_reply
    try:
        return await render_zalo_reply(
            message=message,
            history=history,
            intent=intent,
            tool_result=tool_result,
            thread_id=thread["thread_id"],
        )
    except Exception:
        # The server-grounded tool result is safe and more useful than losing a
        # successful read because only the natural-language renderer failed.
        return tool_result


async def handle_channel_event(event: dict) -> list[str | dict]:
    """Process a Zalo turn with bounded context and model-selected tools."""
    if not config.ZALO_OPENAI_ENABLED:
        return await _handle_channel_event_legacy(event)
    external_uid = event.get("external_uid")
    if not external_uid or event.get("event_name") not in {"user_send_text", "user_send_image"}:
        return []
    message = str(event.get("text") or "").strip()
    if not message and event.get("images"):
        return [
            "\u0110\u00e3 nh\u1eadn \u1ea3nh. Upload creative tr\u1ef1c ti\u1ebfp qua Zalo s\u1ebd \u0111\u01b0\u1ee3c n\u1ed1i v\u00e0o Autopilot \u1edf b\u1ea3n k\u1ebf ti\u1ebfp; "
            f"hi\u1ec7n t\u1ea1i vui l\u00f2ng m\u1edf workspace: {config.ZALO_WEB_WORKSPACE_URL}"
        ]
    if not message:
        return []

    from session import add_message
    from zalo_sessions import append_chat_message, build_context, get_or_roll_chat_session

    thread = await get_or_create_thread(external_uid)
    chat_session, rolled, _previous = await get_or_roll_chat_session(thread)
    if rolled and thread.get("pending_action"):
        # A confirmation cannot be carried into a different time-bounded chat.
        thread = await _update_thread(thread, {"pending_action": None})
    await add_message(thread["session_id"], "user", message)
    chat_session = await append_chat_message(chat_session["chat_session_id"], "user", message)

    # Only deterministic confirmation/rejection gates run ahead of the model.
    # Language understanding and normal workflow progression stay in the tool loop.
    pending_kind = (thread.get("pending_action") or {}).get("kind")
    explicit_decision = _fold(message) in _CONFIRM.union(_REJECT)
    if (pending_kind in {"campaign_lifecycle", "confirm_autopilot_brief"} and explicit_decision) or pending_kind == "campaign_selection":
        campaigns = await owned_campaigns(thread)
        pending_text, thread = await _handle_pending(thread, message, campaigns)
        if pending_text:
            await add_message(thread["session_id"], "assistant", pending_text)
            await append_chat_message(chat_session["chat_session_id"], "assistant", pending_text)
            return [pending_text]

    # Existing Autopilot review remains a server-side confirmation boundary.
    # It is only entered for an explicit confirmation/rejection phrase.
    active_session = thread.get("active_campaign_session_id")
    if active_session and _fold(message) in _CONFIRM.union(_REJECT):
        try:
            from autopilot.service import get_latest_run
            run = await get_latest_run(active_session)
            if run and run.get("status") == "waiting_review":
                from autopilot.chat import route_autopilot_chat
                response = await route_autopilot_chat(message, active_session, 0)
                if response is not None:
                    await add_message(thread["session_id"], "assistant", response.text)
                    await append_chat_message(chat_session["chat_session_id"], "assistant", response.text)
                    return [response.text]
        except Exception:
            pass

    context_messages, bridge_summary = await build_context(thread["thread_id"], chat_session)
    try:
        from zalo_openai import run_zalo_tool_turn
        result = await run_zalo_tool_turn(
            thread=thread, message=message, messages=context_messages,
            bridge_summary=bridge_summary,
        )
        text = result.text
        response_parts: list[str | dict] = [text, *result.media_parts]
    except Exception:
        text = (
            "Tr\u1ee3 l\u00fd h\u1ed9i tho\u1ea1i \u0111ang t\u1ea1m th\u1eddi kh\u00f4ng k\u1ebft n\u1ed1i \u0111\u01b0\u1ee3c v\u1edbi OpenAI. "
            "Kh\u00f4ng c\u00f3 thao t\u00e1c hay thay \u0111\u1ed5i chi\u1ebfn d\u1ecbch n\u00e0o \u0111\u01b0\u1ee3c th\u1ef1c hi\u1ec7n; vui l\u00f2ng th\u1eed l\u1ea1i sau \u00edt ph\u00fat."
        )
        response_parts = [text]
    await add_message(thread["session_id"], "assistant", text)
    await append_chat_message(chat_session["chat_session_id"], "assistant", text)
    return response_parts


async def _handle_channel_event_legacy(event: dict) -> list[str | dict]:
    """Process one durable normalized inbound event into concise text parts."""
    external_uid = event.get("external_uid")
    if not external_uid:
        return []
    if event.get("event_name") not in {"user_send_text", "user_send_image"}:
        return []
    thread = await get_or_create_thread(external_uid)
    message = str(event.get("text") or "").strip()
    response_parts: list[str | dict] | None = None
    if not message and event.get("images"):
        return [
            "Đã nhận ảnh. Upload creative trực tiếp qua Zalo sẽ được nối vào Autopilot ở bản kế tiếp; "
            f"hiện tại vui lòng mở workspace: {config.ZALO_WEB_WORKSPACE_URL}"
        ]
    if not message:
        return []

    from session import add_message, get_history
    await add_message(thread["session_id"], "user", message)
    campaigns = await owned_campaigns(thread)
    pending_text, thread = await _handle_pending(thread, message, campaigns)
    if pending_text:
        await add_message(thread["session_id"], "assistant", pending_text)
        return [pending_text]

    # Review decisions use the existing Autopilot review service and its
    # proposal/side-effect guards. The channel does not invent a second gate.
    active_session = thread.get("active_campaign_session_id")
    if active_session:
        try:
            from autopilot.service import get_latest_run
            run = await get_latest_run(active_session)
            if run and run.get("status") == "waiting_review":
                from autopilot.chat import route_autopilot_chat
                response = await route_autopilot_chat(message, active_session, 0)
                if response is not None:
                    await add_message(thread["session_id"], "assistant", response.text)
                    return [response.text]
        except Exception:
            pass

    history = await get_history(thread["session_id"])
    try:
        plan = await _plan_openai_turn(
            message=message, history=history, campaigns=campaigns, thread=thread,
        )
    except Exception:
        text = (
            "Trợ lý hội thoại đang tạm thời không kết nối được với OpenAI. "
            "Không có thao tác hay thay đổi chiến dịch nào được thực hiện; vui lòng thử lại sau ít phút."
        )
        await add_message(thread["session_id"], "assistant", text)
        return [text]

    folded = _fold(message)
    intent = plan.intent if plan else ""
    if plan and (plan.needs_clarification or intent == "clarify"):
        text = plan.clarification_question.strip() or (
            "Bạn muốn thao tác với chiến dịch nào? Hãy gửi tên hoặc mã chiến dịch."
        )
    elif intent in {"greet", "help", "smalltalk"} or (
        not plan and folded in _GREETING_OR_HELP
    ):
        text = (plan.conversational_reply.strip() if plan else "") or _help_text()
    elif intent == "unsupported":
        text = (plan.conversational_reply.strip() if plan else "") or (
            "Zalo chỉ hỗ trợ xem thông tin, báo cáo, live view và xác nhận tạm dừng/tiếp tục. "
            f"Các chỉnh sửa khác cần thực hiện trên workspace: {config.ZALO_WEB_WORKSPACE_URL}"
        )
    elif intent == "start_autopilot" or (
        not plan and any(phrase in folded for phrase in (
            "tao chien dich", "chien dich moi", "new campaign", "chay autopilot",
        ))
    ):
        thread = await _update_thread(thread, {"pending_action": {
            "kind": "choose_autopilot_mode",
            "expires_at": _now() + timedelta(minutes=15),
        }})
        text = (
            "Chọn mode Campaign Autopilot:\n"
            "1. Tự động hoàn toàn — chỉ dừng trước khi launch.\n"
            "2. Bán tự động — dừng ở các bước quan trọng và trước khi launch."
        )
    elif intent == "list_campaigns" or (
        not plan and any(phrase in folded for phrase in (
            "danh sach", "cac chien dich", "list campaign", "campaign list",
        ))
    ):
        status_filter = plan.campaign_status_filter if plan else ""
        listed = campaigns
        if status_filter == "active":
            listed = [item for item in campaigns if str(
                (item.get("order") or {}).get("status") or ""
            ).lower() in {"active", "running", "live"}]
        elif status_filter == "paused":
            listed = [item for item in campaigns if str(
                (item.get("order") or {}).get("status") or ""
            ).lower() == "paused"]
        raw_text = _campaign_list_text(listed, status_filter)
        text = await _render_openai_tool_result(
            message=message, history=history, intent="list_campaigns",
            tool_result=raw_text, thread=thread,
        )
        if len(listed) > 1:
            await _update_thread(thread, {"pending_action": {
                "kind": "campaign_selection",
                "campaign_ids": [item["campaign_id"] for item in listed[:8]],
                "expires_at": _now() + timedelta(minutes=10),
            }})
    else:
        planned_campaign_intents = {
            "select_campaign", "status", "setup", "report", "live_view",
            "pause", "resume",
        }
        has_campaign_intent = (
            intent in planned_campaign_intents
            if plan else _has_campaign_operation_intent(folded)
        )
        resolution_message = message
        if plan and plan.campaign_reference:
            resolution_message = f"{message} {plan.campaign_reference}"
        campaign = None
        ambiguous: list[dict] = []
        if plan and 1 <= plan.selected_campaign_index <= len(campaigns):
            campaign = campaigns[plan.selected_campaign_index - 1]
        else:
            campaign, ambiguous = resolve_campaign(
                resolution_message, campaigns, thread.get("active_campaign_id"),
                allow_context_fallback=has_campaign_intent,
            )
        if not campaign:
            if ambiguous:
                await _update_thread(thread, {"pending_action": {
                    "kind": "campaign_selection",
                    "campaign_ids": [item["campaign_id"] for item in ambiguous[:8]],
                    "expires_at": _now() + timedelta(minutes=10),
                }})
                text = _campaign_choices(ambiguous)
            elif has_campaign_intent:
                text = (plan.clarification_question.strip() if plan else "") or (
                    "Tôi chưa xác định được chiến dịch. Hãy gửi tên/mã chiến dịch hoặc hỏi “Danh sách chiến dịch”."
                )
            else:
                text = (plan.conversational_reply.strip() if plan else "") or _help_text()
        else:
            thread = await _select_campaign(thread, campaign)
            if intent == "select_campaign":
                text = (
                    f"Đã chọn chiến dịch “{campaign['order'].get('brand')}” "
                    f"({campaign['campaign_id']}). Bạn muốn xem trạng thái, cấu hình, báo cáo hay live view?"
                )
            elif intent == "pause" or (
                not plan and any(word in folded for word in ("tam dung", "pause"))
            ):
                text = await _lifecycle_request(thread, campaign, "pause")
            elif intent == "resume" or (
                not plan and any(word in folded for word in (
                    "tiep tuc lai", "resume", "kich hoat lai",
                ))
            ):
                text = await _lifecycle_request(thread, campaign, "resume")
            elif not plan and any(word in folded for word in ("sua", "thay doi", "cap nhat")) and any(
                word in folded for word in ("budget", "ngan sach", "ngay", "audience", "target", "placement", "creative")
            ):
                text = (
                    "Zalo chỉ cho phép tạm dừng/tiếp tục chiến dịch đã tạo; không sửa budget, lịch, "
                    f"audience, placement hoặc creative. Mở workspace: {_workspace_link(campaign)}"
                )
            elif intent == "report" or (
                not plan and any(word in folded for word in (
                    "bao cao", "report", "daily", "awareness", "consideration",
                    "conversion", "retention", "executive", "ctr", "impression",
                    "click", "reach",
                ))
            ):
                report_message = message
                if plan and plan.report_type:
                    report_message = f"{message} report_type={plan.report_type}"
                raw_text = await _answer_report(report_message, campaign)
                text = await _render_openai_tool_result(
                    message=message, history=history, intent="report",
                    tool_result=raw_text, thread=thread,
                )
            elif intent == "live_view" or (
                not plan and any(word in folded for word in (
                    "live", "screenshot", "anh quang cao", "xem quang cao",
                ))
            ):
                response_parts = await _live_response(campaign)
                text = await _render_openai_tool_result(
                    message=message, history=history, intent="live_view",
                    tool_result=str(response_parts[0]), thread=thread,
                )
                response_parts[0] = text
            elif intent == "setup" or (
                not plan and any(word in folded for word in (
                    "cau hinh", "setup", "audience", "placement", "creative",
                    "targeting", "ngan sach",
                ))
            ):
                raw_text = await _setup_text(campaign)
                text = await _render_openai_tool_result(
                    message=message, history=history, intent="setup",
                    tool_result=raw_text, thread=thread,
                )
            else:
                raw_text = _status_text(campaign)
                text = await _render_openai_tool_result(
                    message=message, history=history, intent="status",
                    tool_result=raw_text, thread=thread,
                )

    await add_message(thread["session_id"], "assistant", text)
    return response_parts if response_parts else [text]


def reset_channel_agent_for_test() -> None:
    _mem_threads.clear()
    _mem_subscriptions.clear()
    _mem_media.clear()
    try:
        from zalo_sessions import reset_zalo_sessions_for_test
        reset_zalo_sessions_for_test()
    except ImportError:
        pass
