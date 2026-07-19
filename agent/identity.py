"""Server-resolved anonymous/account actors and owned campaign conversations.

Both browser credentials are opaque cookies. Only SHA-256 digests are stored
server-side, and clients never choose conversation owners or campaign session
IDs. Existing ``identity_id`` conversation documents remain readable while new
documents also carry the normalized additive ownership fields.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import secrets
import uuid

from pymongo import ReturnDocument

from config import config


_mem_identities: dict[str, dict] = {}
_mem_identity_by_hash: dict[str, str] = {}
_mem_conversations: dict[str, dict] = {}
_claim_lock = asyncio.Lock()


class ConversationRunActive(Exception):
    """Raised when deletion would race a non-terminal Autopilot run."""

    def __init__(self, conversations: list[dict]):
        self.conversations = conversations
        titles = ", ".join(
            str(item.get("title") or item.get("conversation_id"))
            for item in conversations[:3]
        )
        suffix = "…" if len(conversations) > 3 else ""
        super().__init__(
            f"Autopilot đang chạy trong: {titles}{suffix}. "
            "Hãy hủy run trước khi xóa cuộc trò chuyện."
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    value = deepcopy(doc)
    value.pop("_id", None)
    value.pop("token_hash", None)
    return value


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_session_id() -> str:
    namespace = "".join(
        char for char in config.DEMO_NAMESPACE.lower() if char.isalnum() or char in "-_"
    )[:32]
    prefix = f"{namespace}_" if namespace else ""
    return f"sess_{prefix}{uuid.uuid4().hex}"


async def _collections():
    from session import _ensure_mongo

    if not await _ensure_mongo():
        return None, None
    import session as session_store

    db = session_store._client[config.MONGODB_DB]
    return db["anonymous_identities"], db["agent_conversations"]


async def ensure_identity_indexes() -> None:
    """Create additive identity/conversation indexes without rewriting data."""
    identities, conversations = await _collections()
    if identities is None:
        return
    await identities.create_index(
        "token_hash", unique=True, name="anonymous_token_hash_unique"
    )
    await conversations.create_index(
        "session_id", unique=True, sparse=True, name="conversation_session_unique"
    )
    await conversations.create_index(
        [("owner_user_id", 1), ("updated_at", -1)], name="conversation_account_owner"
    )
    await conversations.create_index(
        [("anonymous_id", 1), ("updated_at", -1)], name="conversation_anonymous_owner"
    )
    await conversations.create_index(
        [("identity_id", 1), ("updated_at", -1)], name="conversation_legacy_owner"
    )


async def bootstrap_anonymous(token: str | None = None) -> dict:
    """Resolve a valid device token or issue a new anonymous identity."""
    identities, _ = await _collections()
    supplied = (token or "").strip()
    if supplied:
        digest = _token_hash(supplied)
        if identities is not None:
            identity = await identities.find_one({"token_hash": digest, "status": "active"})
            if identity:
                now = _now()
                await identities.update_one(
                    {"_id": identity["_id"]}, {"$set": {"last_seen_at": now}}
                )
                return {"identity_id": identity["identity_id"], "is_new": False}
        else:
            identity_id = _mem_identity_by_hash.get(digest)
            identity = _mem_identities.get(identity_id or "")
            if identity and identity.get("status") == "active":
                identity["last_seen_at"] = _now()
                return {"identity_id": identity["identity_id"], "is_new": False}

    raw_token = f"aa_anon_{secrets.token_urlsafe(32)}"
    digest = _token_hash(raw_token)
    identity_id = f"anon_{uuid.uuid4().hex}"
    now = _now()
    identity = {
        "_id": identity_id,
        "identity_id": identity_id,
        "token_hash": digest,
        "status": "active",
        "created_at": now,
        "last_seen_at": now,
    }
    if identities is not None:
        await identities.insert_one(identity)
    else:
        _mem_identities[identity_id] = identity
        _mem_identity_by_hash[digest] = identity_id
    return {"identity_id": identity_id, "token": raw_token, "is_new": True}


async def require_identity(token: str | None) -> dict:
    supplied = (token or "").strip()
    if not supplied:
        raise PermissionError("anonymous identity token is required")
    digest = _token_hash(supplied)
    identities, _ = await _collections()
    if identities is not None:
        identity = await identities.find_one({"token_hash": digest, "status": "active"})
    else:
        identity = _mem_identities.get(_mem_identity_by_hash.get(digest, ""))
        if identity and identity.get("status") != "active":
            identity = None
    if not identity:
        raise PermissionError("anonymous identity token is invalid")
    return _public(identity)


async def resolve_actor(
    account_token: str | None,
    anonymous_token: str | None,
    *,
    require_any: bool = True,
) -> dict:
    """Resolve both cookies server-side, preferring the account for ownership."""
    account = None
    anonymous = None
    if (account_token or "").strip():
        from accounts import require_account_session
        try:
            account = await require_account_session(account_token)
        except PermissionError:
            account = None
    if (anonymous_token or "").strip():
        try:
            anonymous = await require_identity(anonymous_token)
        except PermissionError:
            anonymous = None
    actor = {
        "user_id": (account or {}).get("user", {}).get("user_id"),
        "anonymous_id": (anonymous or {}).get("identity_id"),
        "account_session_id": (account or {}).get("session", {}).get("session_id"),
        "user": (account or {}).get("user"),
    }
    if require_any and not actor["user_id"] and not actor["anonymous_id"]:
        raise PermissionError("a valid account or anonymous identity is required")
    return actor


def _as_actor(actor: dict | str) -> dict:
    # String support is an internal migration convenience for older tests and
    # service callers. HTTP routes always pass resolve_actor() output.
    if isinstance(actor, str):
        return {"user_id": None, "anonymous_id": actor, "account_session_id": None}
    return actor


def _anonymous_owner(doc: dict) -> str | None:
    return doc.get("anonymous_id") or doc.get("identity_id")


def _actor_query(actor: dict | str) -> dict:
    actor = _as_actor(actor)
    owners: list[dict] = []
    if actor.get("user_id"):
        owners.append({"owner_user_id": actor["user_id"]})
    if actor.get("anonymous_id"):
        owners.append({
            "owner_user_id": None,
            "$or": [
                {"anonymous_id": actor["anonymous_id"]},
                {"identity_id": actor["anonymous_id"]},
            ],
        })
    if not owners:
        return {"_id": {"$exists": False}}
    return owners[0] if len(owners) == 1 else {"$or": owners}


def _actor_owns(doc: dict, actor: dict | str) -> bool:
    actor = _as_actor(actor)
    if doc.get("owner_user_id"):
        return doc.get("owner_user_id") == actor.get("user_id")
    return bool(
        actor.get("anonymous_id")
        and _anonymous_owner(doc) == actor.get("anonymous_id")
    )


def _public_conversation(doc: dict, actor: dict | str) -> dict:
    actor = _as_actor(actor)
    result = _public(doc)
    account_owned = bool(
        doc.get("owner_user_id")
        and doc.get("owner_user_id") == actor.get("user_id")
    )
    result["ownership"] = "account" if account_owned else "device"
    result["can_claim"] = bool(
        not account_owned and actor.get("user_id") and actor.get("anonymous_id")
    )
    result.pop("identity_id", None)
    result.pop("anonymous_id", None)
    result.pop("owner_user_id", None)
    result.pop("claimed_from_anonymous_id", None)
    return result


async def require_session_access(actor: dict | str | None, session_id: str) -> dict | None:
    """Authorize an owned session while preserving legacy evaluator sessions.

    Sessions that predate the conversation model have no owner record and keep
    working during migration. Once a session belongs to a conversation, its
    resolved account/anonymous actor is mandatory for reads and mutations.
    """
    _, conversations = await _collections()
    if conversations is not None:
        conversation = await conversations.find_one({"session_id": session_id})
    else:
        conversation = next(
            (item for item in _mem_conversations.values()
             if item.get("session_id") == session_id),
            None,
        )
    if not conversation:
        return None
    if not actor or not _actor_owns(conversation, actor):
        raise PermissionError("session is not owned by this actor")
    return _public_conversation(conversation, actor)


async def create_conversation(
    actor: dict | str, *, title: str = "", experience_mode: str | None = None
) -> dict:
    if experience_mode not in {None, "guided", "autopilot"}:
        raise ValueError("experience_mode must be guided or autopilot")
    _, conversations = await _collections()
    conversation_id = f"conv_{uuid.uuid4().hex}"
    now = _now()
    clean_title = " ".join((title or "").split())[:120]
    actor = _as_actor(actor)
    if not actor.get("user_id") and not actor.get("anonymous_id"):
        raise PermissionError("conversation owner is required")
    doc = {
        "_id": conversation_id,
        "conversation_id": conversation_id,
        "owner_user_id": actor.get("user_id"),
        "anonymous_id": None if actor.get("user_id") else actor.get("anonymous_id"),
        # Retain the old field on anonymous documents until all deployed builds
        # understand anonymous_id. Claimed/account documents clear it.
        "identity_id": None if actor.get("user_id") else actor.get("anonymous_id"),
        "session_id": _new_session_id(),
        "title": clean_title or "Chiến dịch mới",
        "title_source": "user" if clean_title else "default",
        "experience_mode": experience_mode,
        "created_at": now,
        "updated_at": now,
        "last_message_at": None,
        "archived_at": None,
    }
    if conversations is not None:
        await conversations.insert_one(doc)
    else:
        _mem_conversations[conversation_id] = doc
    return _public_conversation(doc, actor)


async def _owned_conversation(actor: dict | str, conversation_id: str) -> dict | None:
    _, conversations = await _collections()
    if conversations is not None:
        return await conversations.find_one({"_id": conversation_id, **_actor_query(actor)})
    doc = _mem_conversations.get(conversation_id)
    return doc if doc and _actor_owns(doc, actor) else None


async def conversation_record_for_session(session_id: str) -> dict | None:
    """Return the private owner record for internal campaign registration."""
    _, conversations = await _collections()
    if conversations is not None:
        return await conversations.find_one({"session_id": session_id})
    return next(
        (
            item for item in _mem_conversations.values()
            if item.get("session_id") == session_id
        ),
        None,
    )


async def list_conversations(actor: dict | str, *, include_archived: bool = False) -> list[dict]:
    _, conversations = await _collections()
    query = _actor_query(actor)
    if not include_archived:
        query["archived_at"] = None
    if conversations is not None:
        docs = await conversations.find(query).sort("updated_at", -1).to_list(length=100)
    else:
        docs = [
            item for item in _mem_conversations.values()
            if _actor_owns(item, actor)
            and (include_archived or item.get("archived_at") is None)
        ]
        docs.sort(key=lambda item: item.get("updated_at") or item["created_at"], reverse=True)
    from autopilot.service import get_latest_run_summaries
    run_summaries = await get_latest_run_summaries(
        [item.get("session_id") for item in docs]
    )
    result = []
    for item in docs:
        public = _public_conversation(item, actor)
        summary = run_summaries.get(item.get("session_id"))
        if summary:
            public["latest_run_summary"] = summary
        result.append(public)
    return result


async def get_conversation(actor: dict | str, conversation_id: str) -> dict:
    doc = await _owned_conversation(actor, conversation_id)
    if not doc:
        raise KeyError("conversation not found")

    from autopilot.service import get_latest_run
    from session import get_display_history, get_or_create_session
    from workspace.service import get_workspace, list_pending_proposals

    session_id = doc["session_id"]
    workspace = await get_workspace(session_id)
    session = await get_or_create_session(session_id)
    form_state = session.get("form_state") or {}
    report_context = form_state.get("report_context") or {}
    canonical_order = (
        (workspace.get("artifacts") or {}).get("order") or {}
    )
    canonical_report = (
        (workspace.get("artifacts") or {}).get("report") or {}
    )
    report_value = canonical_report.get("value") or {}
    if not isinstance(report_value, dict):
        report_value = {}
    report_campaign_id = str(
        report_context.get("campaignId")
        or report_value.get("campaignId")
        or ""
    )
    workflow_progress = {
        "order_created": bool(
            session.get("created_order_ids")
            or canonical_order.get("status") == "approved"
        ),
        "report_started": bool(
            report_campaign_id
            or canonical_report.get("status") == "approved"
        ),
        "report_campaign_id": report_campaign_id or None,
        "confirmed_steps": sorted(set(session.get("confirmed_steps") or [])),
        # Old Guided campaigns that already reached Setup/Result predate the
        # explicit review checkpoint and remain migration-compatible.
        "creative_review_confirmed": bool(
            2 in (session.get("confirmed_steps") or [])
            or session.get("created_order_ids")
            or any(
                ((workspace.get("artifacts") or {}).get(name) or {}).get("status")
                == "approved"
                for name in ("placements", "assignments", "order_draft", "order")
            )
        ),
    }
    workspace_mode = workspace.get("experience_mode")
    # An explicit homepage selection belongs to the conversation and is the
    # source of truth. Only legacy conversations with no selected mode inherit
    # the historical workspace default during migration.
    if not doc.get("experience_mode") and workspace_mode:
        await set_conversation_mode_for_session(session_id, workspace_mode)
        doc["experience_mode"] = workspace_mode
    return {
        **_public_conversation(doc, actor),
        "messages": await get_display_history(session_id),
        "workspace": workspace,
        "workflow_progress": workflow_progress,
        "pending_proposals": await list_pending_proposals(session_id),
        "latest_run": await get_latest_run(session_id),
    }


async def archive_conversation(actor: dict | str, conversation_id: str) -> dict:
    doc = await _owned_conversation(actor, conversation_id)
    if not doc:
        raise KeyError("conversation not found")
    now = _now()
    _, conversations = await _collections()
    if conversations is not None:
        await conversations.update_one(
            {"_id": conversation_id, **_actor_query(actor)},
            {"$set": {"archived_at": now, "updated_at": now}},
        )
    else:
        doc["archived_at"] = now
        doc["updated_at"] = now
    return {"ok": True, "conversation_id": conversation_id, "archived_at": now}


async def _assert_conversations_deletable(docs: list[dict]) -> None:
    """Reject deletion while any owned Autopilot run can still execute."""
    from autopilot.service import RUN_TERMINAL, get_latest_run

    active: list[dict] = []
    for doc in docs:
        run = await get_latest_run(doc["session_id"])
        if run and run.get("status") not in RUN_TERMINAL:
            active.append({
                "conversation_id": doc.get("conversation_id") or doc.get("_id"),
                "title": doc.get("title"),
                "run_id": run.get("run_id"),
                "run_status": run.get("status"),
            })
    if active:
        raise ConversationRunActive(active)


async def delete_conversation(actor: dict | str, conversation_id: str) -> dict:
    """Permanently delete one owned conversation and its agent artifacts.

    Campaign orders live in the Node backend and remain as business records.
    """
    doc = await _owned_conversation(actor, conversation_id)
    if not doc:
        raise KeyError("conversation not found")
    await _assert_conversations_deletable([doc])

    from campaign_ownership import preserve_session_campaigns
    from session import delete_session_data

    retained_campaign_ids = await preserve_session_campaigns(doc["session_id"])
    deleted_artifacts = await delete_session_data(doc["session_id"])
    _, conversations = await _collections()
    if conversations is not None:
        result = await conversations.delete_one({
            "_id": conversation_id, **_actor_query(actor),
        })
        if result.deleted_count != 1:
            raise KeyError("conversation not found")
    else:
        _mem_conversations.pop(conversation_id, None)
    return {
        "ok": True,
        "deleted_count": 1,
        "conversation_id": conversation_id,
        "session_id": doc["session_id"],
        "deleted_artifacts": deleted_artifacts,
        "orders_retained": True,
        "retained_campaign_ids": retained_campaign_ids,
    }


async def delete_all_conversations(actor: dict | str) -> dict:
    """Permanently delete every active or archived conversation for an owner."""
    _, conversations = await _collections()
    if conversations is not None:
        docs = await conversations.find(_actor_query(actor)).to_list(length=None)
    else:
        docs = [
            item for item in _mem_conversations.values()
            if _actor_owns(item, actor)
        ]
    await _assert_conversations_deletable(docs)

    from campaign_ownership import preserve_session_campaigns
    from session import delete_session_data

    artifact_counts: dict[str, int] = {}
    retained_campaign_ids: list[str] = []
    for doc in docs:
        retained_campaign_ids.extend(
            await preserve_session_campaigns(doc["session_id"])
        )
        deleted = await delete_session_data(doc["session_id"])
        for collection, count in deleted.items():
            artifact_counts[collection] = artifact_counts.get(collection, 0) + int(count)

    ids = [doc.get("conversation_id") or doc.get("_id") for doc in docs]
    if conversations is not None:
        result = await conversations.delete_many({
            "_id": {"$in": ids}, **_actor_query(actor),
        })
        deleted_count = result.deleted_count
    else:
        for conversation_id in ids:
            _mem_conversations.pop(conversation_id, None)
        deleted_count = len(ids)
    return {
        "ok": True,
        "deleted_count": deleted_count,
        "conversation_ids": ids,
        "deleted_artifacts": artifact_counts,
        "orders_retained": True,
        "retained_campaign_ids": list(dict.fromkeys(retained_campaign_ids)),
    }


async def has_claimable_conversations(actor: dict) -> bool:
    actor = _as_actor(actor)
    if not actor.get("user_id") or not actor.get("anonymous_id"):
        return False
    query = {
        "owner_user_id": None,
        "$or": [
            {"anonymous_id": actor["anonymous_id"]},
            {"identity_id": actor["anonymous_id"]},
        ],
    }
    _, conversations = await _collections()
    if conversations is not None:
        return bool(await conversations.count_documents(query, limit=1))
    return any(
        not doc.get("owner_user_id")
        and _anonymous_owner(doc) == actor["anonymous_id"]
        for doc in _mem_conversations.values()
    )


async def claim_conversation(actor: dict, conversation_id: str) -> dict:
    """Atomically transfer one unclaimed device conversation to an account."""
    actor = _as_actor(actor)
    user_id = actor.get("user_id")
    anonymous_id = actor.get("anonymous_id")
    if not user_id or not anonymous_id:
        raise PermissionError("claim requires account and anonymous credentials")
    from campaign_ownership import claim_campaigns, preserve_session_campaigns

    _, conversations = await _collections()
    now = _now()
    if conversations is not None:
        already = await conversations.find_one({
            "_id": conversation_id, "owner_user_id": user_id,
        })
        if already:
            return _public_conversation(already, actor)
        claimable = await conversations.find_one({
            "_id": conversation_id,
            "owner_user_id": None,
            "$or": [
                {"anonymous_id": anonymous_id},
                {"identity_id": anonymous_id},
            ],
        })
        if not claimable:
            raise KeyError("conversation not found")
        await preserve_session_campaigns(claimable["session_id"])
        doc = await conversations.find_one_and_update(
            {
                "_id": conversation_id,
                "owner_user_id": None,
                "$or": [
                    {"anonymous_id": anonymous_id},
                    {"identity_id": anonymous_id},
                ],
            },
            {"$set": {
                "owner_user_id": user_id,
                "anonymous_id": None,
                "identity_id": None,
                "claimed_from_anonymous_id": anonymous_id,
                "claimed_at": now,
                "updated_at": now,
            }},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise KeyError("conversation not found")
        identities, _ = await _collections()
        await identities.update_one(
            {"identity_id": anonymous_id},
            {"$set": {"claimed_by_user_id": user_id, "claimed_at": now}},
        )
    else:
        async with _claim_lock:
            doc = _mem_conversations.get(conversation_id)
            if doc and doc.get("owner_user_id") == user_id:
                return _public_conversation(doc, actor)
            if not doc or doc.get("owner_user_id") or _anonymous_owner(doc) != anonymous_id:
                raise KeyError("conversation not found")
            await preserve_session_campaigns(doc["session_id"])
            doc.update({
                "owner_user_id": user_id,
                "anonymous_id": None,
                "identity_id": None,
                "claimed_from_anonymous_id": anonymous_id,
                "claimed_at": now,
                "updated_at": now,
            })
            identity = _mem_identities.get(anonymous_id)
            if identity:
                identity["claimed_by_user_id"] = user_id
                identity["claimed_at"] = now
    await claim_campaigns(
        user_id=user_id,
        anonymous_id=anonymous_id,
        conversation_ids=[conversation_id],
    )
    from accounts import _audit
    await _audit(
        "conversation_claimed",
        user_id=user_id,
        conversation_id=conversation_id,
        anonymous_id=anonymous_id,
    )
    return _public_conversation(doc, actor)


async def claim_channel_anonymous_conversations(
    *, user_id: str, anonymous_id: str,
) -> int:
    """Transfer a verified channel actor's conversations to its linked account.

    This is an internal trust-boundary helper. It is called only after a signed
    OA identity has been attached to ``user_id``; no HTTP client can provide
    either owner identifier. Session/conversation IDs and every referenced
    campaign artifact remain unchanged.
    """
    if not user_id or not anonymous_id:
        raise ValueError("channel claim requires both verified owners")
    from campaign_ownership import claim_campaigns, preserve_session_campaigns

    _, conversations = await _collections()
    now = _now()
    query = {
        "owner_user_id": None,
        "$or": [
            {"anonymous_id": anonymous_id},
            {"identity_id": anonymous_id},
        ],
    }
    updates = {"$set": {
        "owner_user_id": user_id,
        "anonymous_id": None,
        "identity_id": None,
        "claimed_from_anonymous_id": anonymous_id,
        "claimed_at": now,
        "updated_at": now,
        "claim_source": "verified_zalo_channel_link",
    }}
    if conversations is not None:
        claimable = await conversations.find(query).to_list(None)
        for doc in claimable:
            await preserve_session_campaigns(doc["session_id"])
        result = await conversations.update_many(query, updates)
        await claim_campaigns(
            user_id=user_id,
            anonymous_id=anonymous_id,
            conversation_ids=[
                doc.get("conversation_id") or doc.get("_id") for doc in claimable
            ],
        )
        return int(result.modified_count)
    count = 0
    claimed_ids: list[str] = []
    async with _claim_lock:
        for doc in _mem_conversations.values():
            if doc.get("owner_user_id") or _anonymous_owner(doc) != anonymous_id:
                continue
            await preserve_session_campaigns(doc["session_id"])
            doc.update(updates["$set"])
            claimed_ids.append(doc.get("conversation_id") or doc.get("_id"))
            count += 1
    await claim_campaigns(
        user_id=user_id,
        anonymous_id=anonymous_id,
        conversation_ids=claimed_ids,
    )
    return count


async def touch_conversation_for_session(
    session_id: str, *, role: str | None = None, content: str = ""
) -> None:
    """Update recency and derive a useful title from the first user message."""
    _, conversations = await _collections()
    now = _now()
    title = " ".join(content.split())[:80] if role == "user" else ""
    if conversations is not None:
        await conversations.update_one(
            {"session_id": session_id},
            {"$set": {"updated_at": now, "last_message_at": now}},
        )
        if title:
            await conversations.update_one(
                {"session_id": session_id, "title_source": "default"},
                {"$set": {"title": title, "title_source": "first_message"}},
            )
        return
    for doc in _mem_conversations.values():
        if doc.get("session_id") != session_id:
            continue
        doc["updated_at"] = now
        doc["last_message_at"] = now
        if title and doc.get("title_source") == "default":
            doc["title"] = title
            doc["title_source"] = "first_message"
        return


async def touch_conversation_activity_for_session(session_id: str) -> None:
    """Refresh history ordering without pretending a browser message occurred."""
    _, conversations = await _collections()
    now = _now()
    if conversations is not None:
        await conversations.update_one(
            {"session_id": session_id}, {"$set": {"updated_at": now}}
        )
        return
    for doc in _mem_conversations.values():
        if doc.get("session_id") == session_id:
            doc["updated_at"] = now
            return


async def set_conversation_mode_for_session(session_id: str, mode: str) -> None:
    _, conversations = await _collections()
    now = _now()
    if conversations is not None:
        await conversations.update_one(
            {"session_id": session_id},
            {"$set": {"experience_mode": mode, "updated_at": now}},
        )
        return
    for doc in _mem_conversations.values():
        if doc.get("session_id") == session_id:
            doc["experience_mode"] = mode
            doc["updated_at"] = now
            return


async def get_conversation_mode_for_session(session_id: str) -> str | None:
    """Return the homepage-selected mode for an owned conversation.

    Legacy evaluator sessions and pre-conversation workspaces intentionally
    return ``None``. Their historical workspace default (``guided``) is not a
    user choice and therefore must not act as an immutable mode lock.
    """
    _, conversations = await _collections()
    if conversations is not None:
        doc = await conversations.find_one(
            {"session_id": session_id}, {"experience_mode": 1}
        )
    else:
        doc = next(
            (
                item for item in _mem_conversations.values()
                if item.get("session_id") == session_id
            ),
            None,
        )
    mode = (doc or {}).get("experience_mode")
    return mode if mode in {"guided", "autopilot"} else None


async def set_conversation_title_for_session(session_id: str, title: str) -> None:
    clean = " ".join((title or "").split())[:120]
    if not clean:
        return
    _, conversations = await _collections()
    now = _now()
    if conversations is not None:
        await conversations.update_one(
            {"session_id": session_id},
            {"$set": {
                "title": clean, "title_source": "workspace_brief", "updated_at": now,
            }},
        )
        return
    for doc in _mem_conversations.values():
        if doc.get("session_id") == session_id:
            doc["title"] = clean
            doc["title_source"] = "workspace_brief"
            doc["updated_at"] = now
            return
