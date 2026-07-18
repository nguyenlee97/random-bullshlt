"""Zalo OA webhook verification and explicit account/channel linking.

Zalo Login subjects and OA-scoped sender IDs are intentionally treated as
different identifiers.  A signed OA message containing a short-lived one-time
link code is the proof that joins an OA sender to an existing internal user.
Normal events are stored idempotently for the later durable FE-3 worker.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
import uuid

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import config


class ZaloChannelError(Exception):
    """Base channel error safe to translate into an HTTP status."""


class ZaloSignatureError(ZaloChannelError):
    pass


class ZaloLinkConflict(ZaloChannelError):
    pass


_LINK_RE = re.compile(r"^\s*LINK\s+([A-Z2-9]{10,24})\s*$", re.IGNORECASE)
_LINK_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_mem_links: dict[str, dict] = {}
_mem_channel_identities: dict[tuple[str, str, str], dict] = {}
_mem_events: dict[str, dict] = {}
_mem_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_expired(value: datetime | None) -> bool:
    """Accept both legacy naive Mongo datetimes and timezone-aware values."""
    if value is None:
        return True
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= _now()


def _public(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    value = deepcopy(doc)
    value.pop("_id", None)
    value.pop("code_hash", None)
    return value


async def _collections() -> dict[str, object] | None:
    from session import _ensure_mongo

    if not await _ensure_mongo():
        return None
    import session as session_store

    db = session_store._client[config.MONGODB_DB]
    return {
        "links": db["channel_link_attempts"],
        "identities": db["channel_identities"],
        "events": db["channel_events"],
    }


async def ensure_zalo_channel_indexes() -> None:
    collections = await _collections()
    if collections is None:
        return
    await collections["links"].create_index(
        "code_hash", unique=True, name="channel_link_code_unique"
    )
    await collections["links"].create_index(
        "expires_at", expireAfterSeconds=0, name="channel_link_expiry_ttl"
    )
    await collections["links"].create_index(
        [("user_id", 1), ("created_at", -1)], name="channel_link_user_time"
    )
    await collections["identities"].create_index(
        [("channel", 1), ("oa_id", 1), ("external_uid", 1)],
        unique=True,
        name="channel_external_identity_unique",
    )
    await collections["identities"].create_index(
        [("user_id", 1), ("channel", 1), ("oa_id", 1)],
        name="channel_identity_user",
    )
    await collections["events"].create_index(
        "event_key", unique=True, name="channel_event_key_unique"
    )
    await collections["events"].create_index(
        [("status", 1), ("received_at", 1)], name="channel_event_queue"
    )


def channel_ready() -> bool:
    return bool(
        config.ZALO_OA_ENABLED
        and config.ZALO_APP_ID
        and config.ZALO_OA_ID
        and config.ZALO_OA_SECRET
    )


def verify_webhook(raw_body: bytes, body: dict, signature_header: str | None) -> None:
    """Fail-closed verification of Zalo's raw-body SHA-256 webhook MAC."""
    if not channel_ready():
        raise ZaloChannelError("zalo oa webhook is not configured")
    timestamp = str(body.get("timestamp") or "").strip()
    if not timestamp or not signature_header:
        raise ZaloSignatureError("invalid Zalo webhook signature")
    try:
        timestamp_value = float(timestamp)
        if timestamp_value > 10_000_000_000:
            timestamp_value /= 1000.0
    except ValueError as exc:
        raise ZaloSignatureError("invalid Zalo webhook timestamp") from exc
    if abs(_now().timestamp() - timestamp_value) > max(
        60, int(config.ZALO_WEBHOOK_MAX_SKEW_SECONDS)
    ):
        raise ZaloSignatureError("expired Zalo webhook timestamp")
    expected = hashlib.sha256(
        config.ZALO_APP_ID.encode("utf-8")
        + raw_body
        + timestamp.encode("utf-8")
        + config.ZALO_OA_SECRET.encode("utf-8")
    ).hexdigest()
    supplied = signature_header.strip()
    if supplied.lower().startswith("mac="):
        supplied = supplied[4:].strip()
    if not hmac.compare_digest(expected, supplied):
        raise ZaloSignatureError("invalid Zalo webhook signature")
    app_id = str(body.get("app_id") or "").strip()
    if app_id and app_id != config.ZALO_APP_ID:
        raise ZaloSignatureError("Zalo webhook app does not match")


def normalize_event(body: dict, raw_body: bytes) -> dict:
    event_name = str(body.get("event_name") or "").strip()[:100]
    sender = body.get("sender") if isinstance(body.get("sender"), dict) else {}
    recipient = body.get("recipient") if isinstance(body.get("recipient"), dict) else {}
    message = body.get("message") if isinstance(body.get("message"), dict) else {}
    external_uid = str(sender.get("id") or "").strip()[:200]
    received_oa_id = str(recipient.get("id") or config.ZALO_OA_ID).strip()[:200]
    if received_oa_id and received_oa_id != config.ZALO_OA_ID:
        raise ZaloSignatureError("Zalo webhook OA does not match")
    message_id = str(
        message.get("msg_id") or body.get("event_id") or body.get("event_id_by_app") or ""
    ).strip()[:300]
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    external_event_id = message_id or payload_hash
    event_key = _hash(f"zalo_oa:{config.ZALO_OA_ID}:{external_event_id}")
    text = str(message.get("text") or "")[:12000] if event_name == "user_send_text" else ""
    return {
        "event_key": event_key,
        "channel": "zalo_oa",
        "oa_id": config.ZALO_OA_ID,
        "event_name": event_name,
        "external_event_id": external_event_id,
        "external_uid": external_uid,
        # This signed app-scoped identifier may match a Zalo Login identity,
        # but only while that account has an explicit pending link attempt.
        "app_scoped_uid": str(body.get("user_id_by_app") or "").strip()[:200] or None,
        "text": text,
        "provider_timestamp": str(body.get("timestamp") or ""),
        "payload_hash": payload_hash,
    }


async def start_channel_link(user_id: str) -> dict:
    if not channel_ready():
        raise ZaloChannelError("zalo oa linking is not configured")
    if not user_id:
        raise PermissionError("account session is required")
    code = "".join(secrets.choice(_LINK_ALPHABET) for _ in range(12))
    now = _now()
    attempt_id = f"zcl_{uuid.uuid4().hex}"
    expires_at = now + timedelta(
        seconds=max(120, int(config.ZALO_CHANNEL_LINK_TTL_SECONDS))
    )
    doc = {
        "_id": attempt_id,
        "attempt_id": attempt_id,
        "user_id": user_id,
        "channel": "zalo_oa",
        "oa_id": config.ZALO_OA_ID,
        "code_hash": _hash(code.upper()),
        "status": "pending",
        "created_at": now,
        "expires_at": expires_at,
        "linked_at": None,
    }
    collections = await _collections()
    if collections is not None:
        await collections["links"].update_many(
            {
                "user_id": user_id,
                "channel": "zalo_oa",
                "oa_id": config.ZALO_OA_ID,
                "status": "pending",
            },
            {"$set": {"status": "superseded"}},
        )
        await collections["links"].insert_one(doc)
    else:
        async with _mem_lock:
            for item in _mem_links.values():
                if (
                    item.get("user_id") == user_id
                    and item.get("oa_id") == config.ZALO_OA_ID
                    and item.get("status") == "pending"
                ):
                    item["status"] = "superseded"
            _mem_links[attempt_id] = doc
    from accounts import _audit

    await _audit("channel_link_started", user_id=user_id, channel="zalo_oa", oa_id=config.ZALO_OA_ID)
    return {
        **_public(doc),
        "oa_name": config.ZALO_OA_NAME,
        "link_code": code,
        "instruction": f"Send LINK {code} to the Zalo OA within 10 minutes.",
    }


async def get_channel_link(user_id: str, attempt_id: str) -> dict:
    collections = await _collections()
    if collections is not None:
        doc = await collections["links"].find_one({
            "_id": attempt_id, "user_id": user_id, "channel": "zalo_oa",
        })
    else:
        doc = _mem_links.get(attempt_id)
        if doc and doc.get("user_id") != user_id:
            doc = None
    if not doc:
        raise KeyError("channel link not found")
    if doc.get("status") == "pending" and _is_expired(doc.get("expires_at")):
        doc["status"] = "expired"
    return _public(doc)


async def _consume_link_code(code: str, external_uid: str) -> dict | None:
    now = _now()
    code_hash = _hash(code.upper())
    collections = await _collections()
    if collections is not None:
        attempt = await collections["links"].find_one_and_update(
            {
                "code_hash": code_hash,
                "channel": "zalo_oa",
                "oa_id": config.ZALO_OA_ID,
                "status": "pending",
                "expires_at": {"$gt": now},
            },
            {"$set": {
                "status": "linking",
                "external_uid": external_uid,
                "linked_at": now,
            }},
            return_document=ReturnDocument.AFTER,
        )
    else:
        async with _mem_lock:
            attempt = next(
                (
                    item for item in _mem_links.values()
                    if item.get("code_hash") == code_hash
                    and item.get("status") == "pending"
                    and item.get("expires_at") > now
                ),
                None,
            )
            if attempt:
                attempt.update({"status": "linking", "external_uid": external_uid, "linked_at": now})
    return attempt


async def _consume_pending_link_for_user(user_id: str, external_uid: str) -> dict | None:
    """Atomically consume the newest explicit attempt for a signed follow event."""
    now = _now()
    collections = await _collections()
    if collections is not None:
        return await collections["links"].find_one_and_update(
            {
                "user_id": user_id,
                "channel": "zalo_oa",
                "oa_id": config.ZALO_OA_ID,
                "status": "pending",
                "expires_at": {"$gt": now},
            },
            {"$set": {
                "status": "linking",
                "external_uid": external_uid,
                "linked_at": now,
                "link_method": "signed_follow",
            }},
            sort=[("created_at", -1)],
            return_document=ReturnDocument.AFTER,
        )
    async with _mem_lock:
        candidates = [
            item for item in _mem_links.values()
            if item.get("user_id") == user_id
            and item.get("channel") == "zalo_oa"
            and item.get("oa_id") == config.ZALO_OA_ID
            and item.get("status") == "pending"
            and item.get("expires_at") > now
        ]
        attempt = max(candidates, key=lambda item: item["created_at"], default=None)
        if attempt:
            attempt.update({
                "status": "linking",
                "external_uid": external_uid,
                "linked_at": now,
                "link_method": "signed_follow",
            })
        return attempt


async def _complete_link_attempt(attempt: dict, event: dict) -> dict:
    key = ("zalo_oa", config.ZALO_OA_ID, event["external_uid"])
    now = _now()
    identity_doc = {
        "channel": "zalo_oa",
        "oa_id": config.ZALO_OA_ID,
        "external_uid": event["external_uid"],
        "app_scoped_uid": event.get("app_scoped_uid"),
        "user_id": attempt["user_id"],
        "status": "linked",
        "linked_at": now,
        "updated_at": now,
    }
    collections = await _collections()
    try:
        if collections is not None:
            existing = await collections["identities"].find_one({
                "channel": "zalo_oa",
                "oa_id": config.ZALO_OA_ID,
                "external_uid": event["external_uid"],
            })
            if existing and existing.get("user_id") not in {None, attempt["user_id"]}:
                raise ZaloLinkConflict("OA identity is already linked to another account")
            await collections["identities"].update_one(
                {
                    "channel": "zalo_oa",
                    "oa_id": config.ZALO_OA_ID,
                    "external_uid": event["external_uid"],
                },
                {"$set": identity_doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            await collections["links"].update_one(
                {"_id": attempt["_id"], "status": "linking"},
                {"$set": {"status": "linked", "linked_at": now}},
            )
        else:
            existing = _mem_channel_identities.get(key)
            if existing and existing.get("user_id") not in {None, attempt["user_id"]}:
                raise ZaloLinkConflict("OA identity is already linked to another account")
            identity_doc["created_at"] = (existing or {}).get("created_at", now)
            _mem_channel_identities[key] = identity_doc
            attempt["status"] = "linked"
    except (DuplicateKeyError, ZaloLinkConflict):
        if collections is not None:
            await collections["links"].update_one(
                {"_id": attempt["_id"]}, {"$set": {"status": "conflict"}}
            )
        else:
            attempt["status"] = "conflict"
        raise
    from accounts import _audit

    await _audit(
        "channel_identity_linked",
        user_id=attempt["user_id"],
        channel="zalo_oa",
        oa_id=config.ZALO_OA_ID,
        link_method=attempt.get("link_method", "link_code"),
    )
    return {"status": "linked", "user_id": attempt["user_id"]}


async def confirm_link_from_event(event: dict) -> dict | None:
    """Complete only an explicit link attempt using signed provider evidence."""
    external_uid = event.get("external_uid")
    if not external_uid:
        return None
    attempt = None
    if event.get("event_name") == "user_send_text":
        match = _LINK_RE.fullmatch(event.get("text") or "")
        if not match:
            return None
        attempt = await _consume_link_code(match.group(1), external_uid)
        if not attempt:
            return {"status": "invalid_or_expired"}
        attempt["link_method"] = "link_code"
    elif event.get("event_name") == "follow" and event.get("app_scoped_uid"):
        from accounts import _find_provider_identity

        identity = await _find_provider_identity("zalo", event["app_scoped_uid"])
        if not identity or not identity.get("user_id"):
            return None
        attempt = await _consume_pending_link_for_user(identity["user_id"], external_uid)
        if not attempt:
            return None
    else:
        return None
    return await _complete_link_attempt(attempt, event)


async def unlink_channel(user_id: str) -> bool:
    now = _now()
    collections = await _collections()
    if collections is not None:
        result = await collections["identities"].update_many(
            {
                "channel": "zalo_oa",
                "oa_id": config.ZALO_OA_ID,
                "user_id": user_id,
                "status": "linked",
            },
            {"$set": {"status": "revoked", "user_id": None, "revoked_at": now, "updated_at": now}},
        )
        changed = result.modified_count > 0
    else:
        changed = False
        for doc in _mem_channel_identities.values():
            if doc.get("user_id") == user_id and doc.get("oa_id") == config.ZALO_OA_ID:
                doc.update({"status": "revoked", "user_id": None, "revoked_at": now, "updated_at": now})
                changed = True
    if changed:
        from accounts import _audit

        await _audit("channel_identity_unlinked", user_id=user_id, channel="zalo_oa", oa_id=config.ZALO_OA_ID)
    return changed


async def get_linked_channel_for_user(user_id: str) -> dict | None:
    if not user_id or not config.ZALO_OA_ID:
        return None
    collections = await _collections()
    if collections is not None:
        doc = await collections["identities"].find_one({
            "channel": "zalo_oa",
            "oa_id": config.ZALO_OA_ID,
            "user_id": user_id,
            "status": "linked",
        })
    else:
        doc = next(
            (
                item for item in _mem_channel_identities.values()
                if item.get("user_id") == user_id
                and item.get("oa_id") == config.ZALO_OA_ID
                and item.get("status") == "linked"
            ),
            None,
        )
    if not doc:
        return None
    return {
        "channel": "zalo_oa",
        "oa_id": doc.get("oa_id"),
        "status": "linked",
        "linked_at": doc.get("linked_at"),
    }


async def record_event(event: dict) -> dict:
    """Insert once, optionally consume a link code, and leave durable work queued."""
    now = _now()
    doc = {
        "_id": f"cev_{uuid.uuid4().hex}",
        **event,
        "status": "received",
        "received_at": now,
        "attempts": 0,
    }
    collections = await _collections()
    inserted = True
    if collections is not None:
        try:
            await collections["events"].insert_one(doc)
        except DuplicateKeyError:
            inserted = False
    else:
        async with _mem_lock:
            if event["event_key"] in _mem_events:
                inserted = False
            else:
                _mem_events[event["event_key"]] = doc
    if not inserted:
        return {"accepted": True, "duplicate": True, "link": None}
    try:
        link_result = await confirm_link_from_event(event)
    except ZaloLinkConflict:
        link_result = {"status": "conflict"}
    if link_result and link_result.get("status") == "linked":
        doc["status"] = "link_completed"
    elif link_result:
        doc["status"] = "link_rejected"
    if collections is not None and link_result:
        await collections["events"].update_one(
            {"event_key": event["event_key"]}, {"$set": {"status": doc["status"]}}
        )
    return {"accepted": True, "duplicate": False, "link": link_result}


async def get_channel_storage_for_test() -> dict:
    collections = await _collections()
    if collections is not None:
        return {
            "links": await collections["links"].find({}).to_list(length=None),
            "identities": await collections["identities"].find({}).to_list(length=None),
            "events": await collections["events"].find({}).to_list(length=None),
        }
    return {
        "links": list(_mem_links.values()),
        "identities": list(_mem_channel_identities.values()),
        "events": list(_mem_events.values()),
    }
