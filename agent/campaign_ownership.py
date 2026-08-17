"""Durable server-owned campaign ownership references.

Conversation transcripts and campaign orders intentionally have different
lifecycles. This additive registry keeps the ownership proof for an order when
an operator deletes a conversation, without retaining the deleted transcript or
workspace artifacts. Clients never write owner identifiers into this store;
the owner is copied only from the server-resolved conversation for a session.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from config import config


_mem_campaigns: dict[str, dict] = {}
_mem_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _collection():
    from session import _ensure_mongo

    if not await _ensure_mongo():
        return None
    import session as session_store

    return session_store._client[config.MONGODB_DB]["account_campaign_ownership"]


def _owner_query(actor: dict) -> dict:
    owners: list[dict] = []
    if actor.get("user_id"):
        owners.append({"owner_user_id": actor["user_id"]})
    if actor.get("anonymous_id"):
        owners.append({"owner_user_id": None, "anonymous_id": actor["anonymous_id"]})
    if not owners:
        return {"_id": {"$exists": False}}
    return owners[0] if len(owners) == 1 else {"$or": owners}


def _same_owner(record: dict, conversation: dict) -> bool:
    if record.get("owner_user_id") or conversation.get("owner_user_id"):
        return bool(
            record.get("owner_user_id")
            and record.get("owner_user_id") == conversation.get("owner_user_id")
        )
    return bool(
        record.get("anonymous_id")
        and record.get("anonymous_id")
        == (conversation.get("anonymous_id") or conversation.get("identity_id"))
    )


def _public(record: dict) -> dict:
    value = deepcopy(record)
    value.pop("_id", None)
    value.pop("owner_user_id", None)
    value.pop("anonymous_id", None)
    return value


async def ensure_campaign_ownership_indexes() -> None:
    collection = await _collection()
    if collection is None:
        return
    await collection.create_index(
        "order_id", unique=True, name="campaign_ownership_order_unique"
    )
    await collection.create_index(
        [("owner_user_id", 1), ("updated_at", -1)],
        name="campaign_ownership_account",
    )
    await collection.create_index(
        [("anonymous_id", 1), ("updated_at", -1)],
        name="campaign_ownership_anonymous",
    )
    await collection.create_index(
        [("session_id", 1), ("updated_at", -1)],
        name="campaign_ownership_session",
    )


async def register_campaign_for_session(
    session_id: str, order_id: str,
) -> dict | None:
    """Record one order using only the conversation owner resolved by server."""
    from identity import conversation_record_for_session

    clean_order_id = str(order_id or "").strip()
    if not clean_order_id:
        return None
    conversation = await conversation_record_for_session(session_id)
    # Preserve evaluator/legacy sessions that have no conversation authority.
    if not conversation:
        return None

    now = _now()
    record = {
        "_id": clean_order_id,
        "order_id": clean_order_id,
        "owner_user_id": conversation.get("owner_user_id"),
        "anonymous_id": None if conversation.get("owner_user_id") else (
            conversation.get("anonymous_id") or conversation.get("identity_id")
        ),
        "conversation_id": conversation.get("conversation_id") or conversation.get("_id"),
        "session_id": session_id,
        "experience_mode": conversation.get("experience_mode"),
        "conversation_title": conversation.get("title"),
        "created_at": now,
        "updated_at": now,
    }
    collection = await _collection()
    if collection is not None:
        existing = await collection.find_one({"_id": clean_order_id})
        if existing:
            if not _same_owner(existing, conversation):
                raise PermissionError("campaign ownership is already registered")
            await collection.update_one(
                {"_id": clean_order_id},
                {"$set": {
                    "conversation_id": record["conversation_id"],
                    "session_id": session_id,
                    "experience_mode": record["experience_mode"],
                    "conversation_title": record["conversation_title"],
                    "updated_at": now,
                }},
            )
            existing.update(record)
            existing["created_at"] = existing.get("created_at") or now
            return _public(existing)
        try:
            await collection.insert_one(record)
        except DuplicateKeyError:
            existing = await collection.find_one({"_id": clean_order_id})
            if not existing or not _same_owner(existing, conversation):
                raise PermissionError("campaign ownership is already registered")
            return _public(existing)
        return _public(record)

    async with _mem_lock:
        existing = _mem_campaigns.get(clean_order_id)
        if existing and not _same_owner(existing, conversation):
            raise PermissionError("campaign ownership is already registered")
        if existing:
            record["created_at"] = existing.get("created_at") or now
        _mem_campaigns[clean_order_id] = record
    return _public(record)


async def preserve_session_campaigns(session_id: str) -> list[str]:
    """Backfill every order reference before session artifacts can be deleted."""
    from session import get_or_create_session
    from workspace.service import get_workspace

    session = await get_or_create_session(session_id)
    order_ids = list(session.get("created_order_ids") or [])
    try:
        workspace = await get_workspace(session_id)
        value = ((workspace.get("artifacts") or {}).get("order") or {}).get("value") or {}
        if isinstance(value, dict):
            value = value.get("order", value)
            order_id = value.get("id") or value.get("_id")
            if order_id:
                order_ids.append(str(order_id))
    except Exception:
        pass

    preserved: list[str] = []
    for order_id in dict.fromkeys(str(item) for item in order_ids if item):
        if await register_campaign_for_session(session_id, order_id):
            preserved.append(order_id)
    return preserved


async def list_owned_campaign_references(actor: dict) -> list[dict]:
    collection = await _collection()
    query = _owner_query(actor)
    if collection is not None:
        records = await collection.find(query).sort("updated_at", -1).to_list(None)
    else:
        records = [
            item for item in _mem_campaigns.values()
            if (
                item.get("owner_user_id") == actor.get("user_id")
                and bool(item.get("owner_user_id"))
            ) or (
                not item.get("owner_user_id")
                and item.get("anonymous_id") == actor.get("anonymous_id")
                and bool(item.get("anonymous_id"))
            )
        ]
        records.sort(
            key=lambda item: item.get("updated_at") or item["created_at"],
            reverse=True,
        )
    return [_public(item) for item in records]


async def list_authorized_campaign_references_for_session(
    session_id: str,
) -> list[dict]:
    """Resolve campaign references from server-owned session identity.

    Owned conversations may read campaigns registered to the same account (or
    anonymous actor). Legacy evaluator sessions have no conversation owner, so
    they are restricted to order IDs already persisted in that exact session.
    Browser/model input never contributes an owner identifier.
    """
    from identity import conversation_record_for_session
    from session import get_or_create_session

    conversation = await conversation_record_for_session(session_id)
    references: list[dict] = []
    if conversation:
        actor = {
            "user_id": conversation.get("owner_user_id"),
            "anonymous_id": None if conversation.get("owner_user_id") else (
                conversation.get("anonymous_id") or conversation.get("identity_id")
            ),
        }
        references.extend(await list_owned_campaign_references(actor))

    # Current-session order IDs are server-persisted evidence and cover
    # pre-registry campaigns as well as ownerless evaluator sessions.
    session = await get_or_create_session(session_id)
    references.extend(
        {
            "order_id": str(order_id),
            "session_id": session_id,
            "source": "session",
        }
        for order_id in (session.get("created_order_ids") or [])
        if str(order_id or "").strip()
    )

    deduped: dict[str, dict] = {}
    for reference in references:
        order_id = str(reference.get("order_id") or "").strip()
        if order_id and order_id not in deduped:
            deduped[order_id] = reference
    return list(deduped.values())


async def session_can_access_campaign(session_id: str, order_id: str) -> bool:
    """Fail closed unless trusted session ownership proves campaign access."""
    clean_order_id = str(order_id or "").strip()
    if not clean_order_id or not session_id:
        return False

    from identity import conversation_record_for_session
    from session import get_or_create_session

    conversation = await conversation_record_for_session(session_id)
    if conversation:
        actor = {
            "user_id": conversation.get("owner_user_id"),
            "anonymous_id": None if conversation.get("owner_user_id") else (
                conversation.get("anonymous_id") or conversation.get("identity_id")
            ),
        }
        collection = await _collection()
        if collection is not None:
            record = await collection.find_one({
                "order_id": clean_order_id,
                **_owner_query(actor),
            })
        else:
            candidate = _mem_campaigns.get(clean_order_id)
            record = (
                candidate
                if candidate and _same_owner(candidate, conversation)
                else None
            )
        if record:
            return True

    # Pre-registry and evaluator compatibility remains restricted to trusted
    # server state for this exact session.
    session = await get_or_create_session(session_id)
    return clean_order_id in {
        str(item) for item in (session.get("created_order_ids") or [])
    }


async def claim_campaigns(
    *, user_id: str, anonymous_id: str, conversation_ids: list[str] | None = None,
) -> int:
    """Move registry ownership only after the identity service proves a claim."""
    if not user_id or not anonymous_id:
        raise ValueError("campaign claim requires verified owners")
    query: dict = {"owner_user_id": None, "anonymous_id": anonymous_id}
    if conversation_ids is not None:
        query["conversation_id"] = {"$in": conversation_ids}
    now = _now()
    updates = {"$set": {
        "owner_user_id": user_id,
        "anonymous_id": None,
        "claimed_from_anonymous_id": anonymous_id,
        "claimed_at": now,
        "updated_at": now,
    }}
    collection = await _collection()
    if collection is not None:
        result = await collection.update_many(query, updates)
        return int(result.modified_count)
    count = 0
    async with _mem_lock:
        for record in _mem_campaigns.values():
            if record.get("owner_user_id") or record.get("anonymous_id") != anonymous_id:
                continue
            if conversation_ids is not None and record.get("conversation_id") not in conversation_ids:
                continue
            record.update(updates["$set"])
            count += 1
    return count
