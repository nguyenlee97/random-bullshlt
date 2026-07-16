"""Anonymous device identities and owned campaign conversations.

The browser keeps one high-entropy token in localStorage.  Only its SHA-256
digest is stored server-side, so a database read does not expose credentials.
Conversations own opaque session IDs; clients never choose a session when they
create or resume a campaign.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import secrets
import uuid

from config import config


_mem_identities: dict[str, dict] = {}
_mem_identity_by_hash: dict[str, str] = {}
_mem_conversations: dict[str, dict] = {}


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


async def require_session_access(token: str | None, session_id: str) -> dict | None:
    """Authorize an owned session while preserving legacy evaluator sessions.

    Sessions that predate the conversation model have no owner record and keep
    working during migration. Once a session belongs to a conversation, its
    anonymous identity cookie is mandatory for reads and mutations.
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
    identity = await require_identity(token)
    if conversation.get("identity_id") != identity.get("identity_id"):
        raise PermissionError("session is not owned by this identity")
    return _public(conversation)


async def create_conversation(
    identity_id: str, *, title: str = "", experience_mode: str | None = None
) -> dict:
    if experience_mode not in {None, "guided", "autopilot"}:
        raise ValueError("experience_mode must be guided or autopilot")
    _, conversations = await _collections()
    conversation_id = f"conv_{uuid.uuid4().hex}"
    now = _now()
    clean_title = " ".join((title or "").split())[:120]
    doc = {
        "_id": conversation_id,
        "conversation_id": conversation_id,
        "identity_id": identity_id,
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
    return _public(doc)


async def _owned_conversation(identity_id: str, conversation_id: str) -> dict | None:
    _, conversations = await _collections()
    if conversations is not None:
        return await conversations.find_one({
            "_id": conversation_id, "identity_id": identity_id,
        })
    doc = _mem_conversations.get(conversation_id)
    return doc if doc and doc.get("identity_id") == identity_id else None


async def list_conversations(identity_id: str, *, include_archived: bool = False) -> list[dict]:
    _, conversations = await _collections()
    query = {"identity_id": identity_id}
    if not include_archived:
        query["archived_at"] = None
    if conversations is not None:
        docs = await conversations.find(query).sort("updated_at", -1).to_list(length=100)
    else:
        docs = [
            item for item in _mem_conversations.values()
            if item.get("identity_id") == identity_id
            and (include_archived or item.get("archived_at") is None)
        ]
        docs.sort(key=lambda item: item.get("updated_at") or item["created_at"], reverse=True)
    return [_public(item) for item in docs]


async def get_conversation(identity_id: str, conversation_id: str) -> dict:
    doc = await _owned_conversation(identity_id, conversation_id)
    if not doc:
        raise KeyError("conversation not found")

    from autopilot.service import get_latest_run
    from session import get_display_history
    from workspace.service import get_workspace, list_pending_proposals

    session_id = doc["session_id"]
    workspace = await get_workspace(session_id)
    workspace_mode = workspace.get("experience_mode")
    if workspace_mode and doc.get("experience_mode") != workspace_mode:
        await set_conversation_mode_for_session(session_id, workspace_mode)
        doc["experience_mode"] = workspace_mode
    return {
        **_public(doc),
        "messages": await get_display_history(session_id),
        "workspace": workspace,
        "pending_proposals": await list_pending_proposals(session_id),
        "latest_run": await get_latest_run(session_id),
    }


async def archive_conversation(identity_id: str, conversation_id: str) -> dict:
    doc = await _owned_conversation(identity_id, conversation_id)
    if not doc:
        raise KeyError("conversation not found")
    now = _now()
    _, conversations = await _collections()
    if conversations is not None:
        await conversations.update_one(
            {"_id": conversation_id, "identity_id": identity_id},
            {"$set": {"archived_at": now, "updated_at": now}},
        )
    else:
        doc["archived_at"] = now
        doc["updated_at"] = now
    return {"ok": True, "conversation_id": conversation_id, "archived_at": now}


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
