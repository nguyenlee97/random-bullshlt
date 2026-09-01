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
        "threads": db["channel_threads"],
        "outbound": db["channel_outbound_messages"],
        "subscriptions": db["channel_run_subscriptions"],
        "media": db["channel_media"],
        "chat_sessions": db["channel_chat_sessions"],
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
    await collections["events"].create_index(
        [("status", 1), ("next_attempt_at", 1), ("lease_expires_at", 1)],
        name="channel_event_worker_queue",
    )
    await collections["threads"].create_index(
        [("channel", 1), ("oa_id", 1), ("external_uid", 1)],
        unique=True,
        name="channel_thread_external_unique",
    )
    await collections["threads"].create_index(
        [("user_id", 1), ("updated_at", -1)], name="channel_thread_account_time"
    )
    await collections["outbound"].create_index(
        "idempotency_key", unique=True, name="channel_outbound_idempotency_unique"
    )
    await collections["outbound"].create_index(
        [("status", 1), ("next_attempt_at", 1), ("lease_expires_at", 1)],
        name="channel_outbound_worker_queue",
    )
    await collections["subscriptions"].create_index(
        [("thread_id", 1), ("run_id", 1)], unique=True,
        name="channel_run_subscription_unique",
    )
    await collections["subscriptions"].create_index(
        [("status", 1), ("updated_at", 1)], name="channel_run_subscription_queue"
    )
    await collections["media"].create_index(
        "token_hash", unique=True, name="channel_media_token_unique"
    )
    await collections["media"].create_index(
        "expires_at", expireAfterSeconds=0, name="channel_media_expiry_ttl"
    )
    await collections["chat_sessions"].create_index(
        [("thread_id", 1), ("sequence", 1)], unique=True,
        name="channel_chat_session_sequence_unique",
    )
    await collections["chat_sessions"].create_index(
        [("thread_id", 1), ("status", 1)], unique=True,
        partialFilterExpression={"status": "open"},
        name="channel_chat_session_one_open",
    )
    await collections["chat_sessions"].create_index(
        [("thread_id", 1), ("started_at", -1)],
        name="channel_chat_session_thread_time",
    )
    await collections["chat_sessions"].create_index(
        [("summary_status", 1), ("summary_lease_expires_at", 1), ("last_activity_at", 1)],
        name="channel_chat_summary_queue",
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


_REPLY_ID_KEYS = (
    "msg_id", "message_id", "id", "reply_msg_id", "quote_msg_id",
    "reply_to_message_id", "source_msg_id",
)
_REPLY_CONTAINERS = (
    "reply", "quote", "reply_to", "replyTo", "replied_message",
    "quoted_message",
)


def _reply_reference(body: dict, message: dict) -> tuple[str | None, dict]:
    """Extract a provider reply reference without retaining quoted content.

    Zalo has emitted more than one reply/quote envelope over time. We accept a
    bounded allow-list of known container and identifier names, and persist only
    the matched path plus field names. Quoted text, sender data and the raw
    provider payload never enter the durable event document.
    """
    candidates: list[tuple[str, object]] = []
    for key in _REPLY_CONTAINERS:
        if key in message:
            candidates.append((f"message.{key}", message.get(key)))
    for key in _REPLY_CONTAINERS:
        if key in body:
            candidates.append((key, body.get(key)))
    for key in _REPLY_ID_KEYS[3:]:
        if key in message:
            candidates.append((f"message.{key}", message.get(key)))
        if key in body:
            candidates.append((key, body.get(key)))

    observed_keys: set[str] = set()
    reference = None
    source = None
    for path, value in candidates:
        if isinstance(value, dict):
            observed_keys.update(str(key)[:80] for key in value.keys())
            for key in _REPLY_ID_KEYS:
                clean = str(value.get(key) or "").strip()[:300]
                if clean:
                    reference, source = clean, f"{path}.{key}"
                    break
        else:
            observed_keys.add(path.rsplit(".", 1)[-1][:80])
            clean = str(value or "").strip()[:300]
            if clean:
                reference, source = clean, path
        if reference:
            break

    return reference, {
        "present": bool(candidates),
        "reference_found": bool(reference),
        "source": source,
        "candidate_keys": sorted(observed_keys)[:24],
        "message_keys": sorted(str(key)[:80] for key in message.keys())[:32],
        "body_keys": sorted(str(key)[:80] for key in body.keys())[:32],
    }


def normalize_event(body: dict, raw_body: bytes) -> dict:
    event_name = str(body.get("event_name") or "").strip()[:100]
    sender = body.get("sender") if isinstance(body.get("sender"), dict) else {}
    follower = body.get("follower") if isinstance(body.get("follower"), dict) else {}
    recipient = body.get("recipient") if isinstance(body.get("recipient"), dict) else {}
    message = body.get("message") if isinstance(body.get("message"), dict) else {}
    reply_to_message_id, reply_context = _reply_reference(body, message)
    # Message webhooks identify the OA user as sender.id. Follow/unfollow
    # webhooks use a different provider schema and identify that user as
    # follower.id instead. Prefer the event-specific field but retain the
    # sender fallback for older webhook variants.
    external_uid = str(
        (follower.get("id") if event_name in {"follow", "unfollow"} else None)
        or sender.get("id")
        or ""
    ).strip()[:200]
    # Follow webhooks carry oa_id at the top level instead of recipient.id.
    # Validate either shape so an event for another OA cannot be normalized as
    # belonging to the configured account.
    received_oa_id = str(
        body.get("oa_id") or recipient.get("id") or config.ZALO_OA_ID
    ).strip()[:200]
    if received_oa_id and received_oa_id != config.ZALO_OA_ID:
        raise ZaloSignatureError("Zalo webhook OA does not match")
    message_id = str(
        message.get("msg_id") or body.get("event_id") or body.get("event_id_by_app") or ""
    ).strip()[:300]
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    external_event_id = message_id or payload_hash
    event_key = _hash(f"zalo_oa:{config.ZALO_OA_ID}:{external_event_id}")
    text = str(message.get("text") or "")[:12000] if event_name == "user_send_text" else ""
    attachments = message.get("attachments") if isinstance(message.get("attachments"), list) else []
    images = []
    for attachment in attachments[:6]:
        if not isinstance(attachment, dict) or attachment.get("type") not in {"image", "photo"}:
            continue
        payload = attachment.get("payload") if isinstance(attachment.get("payload"), dict) else {}
        url = str(payload.get("url") or payload.get("thumbnail") or "").strip()
        if url.startswith("https://"):
            images.append({"url": url[:2048], "attachment_id": str(payload.get("id") or "")[:300]})
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
        "reply_to_message_id": reply_to_message_id,
        "reply_context": reply_context,
        "images": images,
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
    from zalo_oa_api import oa_recovery_configured

    return {
        **_public(doc),
        "oa_name": config.ZALO_OA_NAME,
        "existing_follower_check_available": oa_recovery_configured(),
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


async def _consume_link_for_provider_recovery(
    user_id: str, attempt_id: str, external_uid: str,
) -> dict | None:
    """Atomically claim the caller-owned pending attempt after an OA API match."""
    now = _now()
    collections = await _collections()
    if collections is not None:
        return await collections["links"].find_one_and_update(
            {
                "_id": attempt_id,
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
                "link_method": "oa_user_api",
            }},
            return_document=ReturnDocument.AFTER,
        )
    async with _mem_lock:
        attempt = _mem_links.get(attempt_id)
        if not attempt or not (
            attempt.get("user_id") == user_id
            and attempt.get("channel") == "zalo_oa"
            and attempt.get("oa_id") == config.ZALO_OA_ID
            and attempt.get("status") == "pending"
            and attempt.get("expires_at") > now
        ):
            return None
        attempt.update({
            "status": "linking",
            "external_uid": external_uid,
            "linked_at": now,
            "link_method": "oa_user_api",
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
    # If this OA sender chatted before linking, atomically transfer its stable
    # channel-owned conversation(s) without changing any session or artifact ID.
    collections = await _collections()
    if collections is not None:
        thread = await collections["threads"].find_one({
            "channel": "zalo_oa", "oa_id": config.ZALO_OA_ID,
            "external_uid": event["external_uid"],
        })
        anonymous_id = (thread or {}).get("anonymous_id")
        if anonymous_id:
            from identity import claim_channel_anonymous_conversations
            await claim_channel_anonymous_conversations(
                user_id=attempt["user_id"], anonymous_id=anonymous_id,
            )
            await collections["threads"].update_one(
                {"_id": thread["_id"]},
                {"$set": {
                    "user_id": attempt["user_id"], "anonymous_id": None,
                    "linked_at": now, "updated_at": now,
                }},
            )

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
        if event.get("event_name") == "follow":
            return {"status": "not_linked", "reason": "missing_follower_id"}
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
    elif event.get("event_name") == "follow":
        if not event.get("app_scoped_uid"):
            return {
                "status": "not_linked",
                "reason": "missing_user_id_by_app",
            }
        from accounts import _find_provider_identity

        identity = await _find_provider_identity("zalo", event["app_scoped_uid"])
        if not identity or not identity.get("user_id"):
            return {
                "status": "not_linked",
                "reason": "zalo_login_identity_not_found",
            }
        attempt = await _consume_pending_link_for_user(identity["user_id"], external_uid)
        if not attempt:
            return {
                "status": "not_linked",
                "reason": "no_pending_link_attempt",
            }
    else:
        return None
    return await _complete_link_attempt(attempt, event)


async def recover_existing_follower_link(user_id: str, attempt_id: str) -> dict:
    """Link an already-following OA user using current V3 provider evidence."""
    from accounts import _find_provider_identity_for_user
    from zalo_oa_api import ZaloOAAPIError, find_existing_follower

    identity = await _find_provider_identity_for_user("zalo", user_id)
    if not identity or not identity.get("provider_subject"):
        return {"status": "not_linked", "reason": "zalo_login_identity_not_found"}
    try:
        follower = await find_existing_follower(identity["provider_subject"])
    except ZaloOAAPIError:
        return {"status": "not_linked", "reason": "oa_user_api_unavailable"}
    if not follower:
        return {"status": "not_linked", "reason": "existing_follower_not_found"}
    attempt = await _consume_link_for_provider_recovery(
        user_id, attempt_id, follower["external_uid"]
    )
    if not attempt:
        try:
            current = await get_channel_link(user_id, attempt_id)
        except KeyError:
            current = None
        if current and current.get("status") == "linked":
            return {"status": "linked", "user_id": user_id}
        return {"status": "not_linked", "reason": "link_attempt_not_pending"}
    return await _complete_link_attempt(attempt, {
        "external_uid": follower["external_uid"],
        "app_scoped_uid": follower["app_scoped_uid"],
        "event_name": "oa_user_api_recovery",
    })


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


async def resolve_linked_user(external_uid: str) -> str | None:
    """Resolve one signed OA-scoped sender to its internal account."""
    clean_uid = str(external_uid or "").strip()
    if not clean_uid:
        return None
    collections = await _collections()
    if collections is not None:
        doc = await collections["identities"].find_one({
            "channel": "zalo_oa", "oa_id": config.ZALO_OA_ID,
            "external_uid": clean_uid, "status": "linked",
        })
    else:
        doc = _mem_channel_identities.get(("zalo_oa", config.ZALO_OA_ID, clean_uid))
        if doc and doc.get("status") != "linked":
            doc = None
    return str(doc.get("user_id")) if doc and doc.get("user_id") else None


async def record_event(event: dict) -> dict:
    """Insert once, optionally consume a link code, and leave durable work queued."""
    now = _now()
    doc = {
        "_id": f"cev_{uuid.uuid4().hex}",
        **event,
        "status": "received",
        "received_at": now,
        "attempts": 0,
        "next_attempt_at": now,
        "lease_owner": None,
        "lease_expires_at": None,
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
