"""Versioned canonical workspace with optimistic concurrency and audit events.

During migration every successful canonical mutation is mirrored to
``agent_sessions.form_state`` so existing handlers keep working. The canonical
write is revision-checked and idempotent; a stale client never overwrites it.
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from config import config
from session import get_or_create_session, update_form_state
from workspace.dependencies import ARTIFACTS, artifact_for_field, downstream


_client = None
_workspaces = None
_proposals = None
_events = None
_mongo_ok: bool | None = None
_mem_workspaces: dict[str, dict] = {}
_mem_proposals: dict[str, dict] = {}
_locks: dict[str, asyncio.Lock] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _workspace_id(session_id: str) -> str:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:20]
    return f"cw_{digest}"


def _artifact(status: str = "missing", revision: int = 0, value: Any = None) -> dict:
    return {"status": status, "revision": revision, "value": value}


def _legacy_artifacts(form_state: dict) -> dict:
    artifacts = {name: _artifact() for name in ARTIFACTS}
    legacy_map = {
        "brief": "brief",
        "segment": "audience",
        "targeting": "targeting",
        "creative": "creative",
        "setup": "placements",
        "assignments": "assignments",
        "report_context": "report",
    }
    for field, name in legacy_map.items():
        value = form_state.get(field)
        if value not in (None, {}, []):
            artifacts[name] = _artifact("approved", 0, deepcopy(value))
    return artifacts


def _default_workspace(session_id: str, form_state: dict | None = None) -> dict:
    now = _now()
    return {
        "_id": _workspace_id(session_id),
        "workspace_id": _workspace_id(session_id),
        "session_id": session_id,
        "revision": 0,
        "experience_mode": "guided",
        "approval_policy": "review_every_stage",
        "artifacts": _legacy_artifacts(form_state or {}),
        "events": [],
        "applied_mutations": [],
        "created_at": now,
        "updated_at": now,
    }


async def _ensure_store() -> bool:
    global _client, _workspaces, _proposals, _events, _mongo_ok
    if _mongo_ok is not None:
        return _mongo_ok
    try:
        _client = AsyncIOMotorClient(
            config.MONGODB_URI,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            socketTimeoutMS=5000,
        )
        await asyncio.wait_for(_client.admin.command("ping"), timeout=4)
        db = _client[config.MONGODB_DB]
        _workspaces = db["campaign_workspaces"]
        _proposals = db["workspace_proposals"]
        _events = db["workspace_events"]
        _mongo_ok = True
    except Exception:
        _mongo_ok = False
    return _mongo_ok


class WorkspaceConflict(Exception):
    def __init__(self, expected: int, actual: int, workspace: dict):
        super().__init__(f"workspace revision conflict: expected {expected}, actual {actual}")
        self.expected = expected
        self.actual = actual
        self.workspace = workspace


def _public(doc: dict) -> dict:
    result = deepcopy(doc)
    result.pop("applied_mutations", None)
    result["workspace_id"] = result.get("workspace_id") or result.get("_id")
    result.pop("_id", None)
    return result


def legacy_view(workspace: dict) -> dict:
    """Render canonical artifacts in the legacy React/handler field shape."""
    artifacts = workspace.get("artifacts", {})
    audience = deepcopy(artifacts.get("audience", {}).get("value") or {})
    targeting = deepcopy(artifacts.get("targeting", {}).get("value") or {})
    if targeting:
        audience["targeting"] = targeting
    setup = deepcopy(artifacts.get("placements", {}).get("value") or {})
    assignments = deepcopy(artifacts.get("assignments", {}).get("value") or {})
    if assignments:
        setup["assignments"] = assignments
    return {
        "brief": deepcopy(artifacts.get("brief", {}).get("value") or {}),
        "segment": audience,
        "creative": deepcopy(artifacts.get("creative", {}).get("value") or {}),
        "setup": setup,
    }


async def get_workspace(session_id: str) -> dict:
    if await _ensure_store():
        workspace_id = _workspace_id(session_id)
        doc = await _workspaces.find_one({"_id": workspace_id})
        if not doc:
            session = await get_or_create_session(session_id)
            candidate = _default_workspace(session_id, session.get("form_state", {}))
            await _workspaces.update_one(
                {"_id": workspace_id}, {"$setOnInsert": candidate}, upsert=True
            )
            doc = await _workspaces.find_one({"_id": workspace_id})
        return _public(doc)

    if session_id not in _mem_workspaces:
        session = await get_or_create_session(session_id)
        _mem_workspaces[session_id] = _default_workspace(
            session_id, session.get("form_state", {})
        )
    return _public(_mem_workspaces[session_id])


def _impact(doc: dict, artifact: str) -> list[str]:
    return [
        name
        for name in downstream(artifact)
        if doc.get("artifacts", {}).get(name, {}).get("status") != "missing"
    ]


def _merged_artifact_value(doc: dict, artifact: str, field: str, value: Any) -> Any:
    parts = field.split(".")
    if len(parts) == 1:
        return deepcopy(value)
    merged = deepcopy(doc.get("artifacts", {}).get(artifact, {}).get("value") or {})
    if not isinstance(merged, dict):
        merged = {}
    cursor = merged
    for part in parts[1:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = deepcopy(value)
    return merged


def _mutation_event(
    workspace_id: str,
    revision: int,
    field: str,
    artifact: str,
    actor: str,
    reason: str,
    idempotency_key: str,
    affected: list[str],
) -> dict:
    return {
        "event_id": f"wev_{uuid.uuid4().hex}",
        "workspace_id": workspace_id,
        "revision": revision,
        "type": "workspace_mutated",
        "field": field,
        "artifact": artifact,
        "actor": actor,
        "reason": reason,
        "idempotency_key": idempotency_key,
        "affected_artifacts": affected,
        "created_at": _now(),
    }


async def apply_mutation(
    session_id: str,
    field: str,
    value: Any,
    *,
    base_revision: int | None,
    actor: str,
    reason: str = "",
    idempotency_key: str = "",
) -> dict:
    artifact = artifact_for_field(field)
    root = field.split(".", 1)[0]
    key = idempotency_key or f"mut_{uuid.uuid4().hex}"
    current = await get_workspace(session_id)
    expected = current["revision"] if base_revision is None else base_revision
    workspace_id = current["workspace_id"]

    if await _ensure_store():
        raw = await _workspaces.find_one({"_id": workspace_id})
        duplicate = next(
            (item for item in raw.get("applied_mutations", []) if item.get("key") == key),
            None,
        )
        if duplicate:
            return {**duplicate["result"], "duplicate": True}
        if raw["revision"] != expected:
            raise WorkspaceConflict(expected, raw["revision"], _public(raw))

        new_revision = expected + 1
        affected = _impact(raw, artifact)
        committed_value = _merged_artifact_value(raw, artifact, field, value)
        event = _mutation_event(
            workspace_id, new_revision, field, artifact, actor, reason, key, affected
        )
        result = {
            "ok": True,
            "workspace_id": workspace_id,
            "workspace_revision": new_revision,
            "field": field,
            "artifact": artifact,
            "affected_artifacts": affected,
            "event_id": event["event_id"],
            "duplicate": False,
        }
        sets = {
            "revision": new_revision,
            "updated_at": event["created_at"],
            f"artifacts.{artifact}": {
                "status": "approved",
                "revision": new_revision,
                "value": committed_value,
                "updated_at": event["created_at"],
                "updated_by": actor,
            },
        }
        for name in affected:
            sets[f"artifacts.{name}.status"] = "stale"
            sets[f"artifacts.{name}.stale_at_revision"] = new_revision
            sets[f"artifacts.{name}.stale_reason"] = f"{artifact} changed"
        update = await _workspaces.update_one(
            {
                "_id": workspace_id,
                "revision": expected,
                "applied_mutations.key": {"$ne": key},
            },
            {
                "$set": sets,
                "$push": {
                    "events": {"$each": [event], "$slice": -200},
                    "applied_mutations": {
                        "$each": [{"key": key, "result": result}], "$slice": -200
                    },
                },
            },
        )
        if update.modified_count != 1:
            latest = await _workspaces.find_one({"_id": workspace_id})
            duplicate = next(
                (item for item in latest.get("applied_mutations", []) if item.get("key") == key),
                None,
            )
            if duplicate:
                return {**duplicate["result"], "duplicate": True}
            raise WorkspaceConflict(expected, latest["revision"], _public(latest))
        # The workspace document already contains the event in the same atomic
        # write as the revision. The append-only projection is useful for
        # querying, but its temporary failure must not make the caller retry a
        # mutation that has already committed.
        try:
            await _events.insert_one(event)
        except Exception:
            pass
    else:
        lock = _locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            raw = _mem_workspaces[session_id]
            duplicate = next(
                (item for item in raw["applied_mutations"] if item["key"] == key), None
            )
            if duplicate:
                return {**duplicate["result"], "duplicate": True}
            if raw["revision"] != expected:
                raise WorkspaceConflict(expected, raw["revision"], _public(raw))
            new_revision = expected + 1
            affected = _impact(raw, artifact)
            committed_value = _merged_artifact_value(raw, artifact, field, value)
            event = _mutation_event(
                workspace_id, new_revision, field, artifact, actor, reason, key, affected
            )
            raw["revision"] = new_revision
            raw["updated_at"] = event["created_at"]
            raw["artifacts"][artifact] = {
                "status": "approved",
                "revision": new_revision,
                "value": committed_value,
                "updated_at": event["created_at"],
                "updated_by": actor,
            }
            for name in affected:
                raw["artifacts"][name]["status"] = "stale"
                raw["artifacts"][name]["stale_at_revision"] = new_revision
                raw["artifacts"][name]["stale_reason"] = f"{artifact} changed"
            result = {
                "ok": True,
                "workspace_id": workspace_id,
                "workspace_revision": new_revision,
                "field": field,
                "artifact": artifact,
                "affected_artifacts": affected,
                "event_id": event["event_id"],
                "duplicate": False,
            }
            raw["events"] = (raw["events"] + [event])[-200:]
            raw["applied_mutations"] = (
                raw["applied_mutations"] + [{"key": key, "result": result}]
            )[-200:]

    # Any still-pending proposal based on an older revision can no longer be
    # approved safely. Remove it from normal confirmation routing while keeping
    # the record for audit and explicit stale-click errors.
    superseded_at = _now()
    if await _ensure_store():
        try:
            await _proposals.update_many(
                {
                    "session_id": session_id,
                    "status": "pending",
                    "base_revision": {"$lt": result["workspace_revision"]},
                },
                {"$set": {
                    "status": "superseded",
                    "superseded_by_revision": result["workspace_revision"],
                    "updated_at": superseded_at,
                }},
            )
        except Exception:
            pass
    else:
        for proposal in _mem_proposals.values():
            if (
                proposal.get("session_id") == session_id
                and proposal.get("status") == "pending"
                and proposal.get("base_revision", -1) < result["workspace_revision"]
            ):
                proposal.update(
                    status="superseded",
                    superseded_by_revision=result["workspace_revision"],
                    updated_at=superseded_at,
                )

    # Compatibility mirror. Canonical state has already committed atomically.
    await update_form_state(session_id, root, committed_value, sync_workspace=False)
    return result


async def sync_from_legacy(session_id: str, field: str, value: Any) -> dict | None:
    """Mirror deterministic-handler writes into the canonical workspace.

    Only authoritative campaign fields are mirrored. Internal recommendation
    caches remain in legacy form_state and do not create workspace revisions.
    """
    if field not in {"brief", "segment", "targeting", "creative", "setup", "assignments"}:
        return None
    for attempt in range(2):
        workspace = await get_workspace(session_id)
        try:
            return await apply_mutation(
                session_id,
                field,
                value,
                base_revision=workspace["revision"],
                actor="deterministic_handler",
                reason="legacy_form_state_mirror",
                idempotency_key=f"legacy:{field}:{uuid.uuid4().hex}",
            )
        except WorkspaceConflict:
            if attempt:
                raise
    return None


async def create_proposal(
    session_id: str,
    field: str,
    value: Any,
    *,
    base_revision: int,
    actor: str,
    reason: str,
) -> dict:
    workspace = await get_workspace(session_id)
    if workspace["revision"] != base_revision:
        raise WorkspaceConflict(base_revision, workspace["revision"], workspace)
    artifact = artifact_for_field(field)
    proposal = {
        "_id": f"wpr_{uuid.uuid4().hex}",
        "proposal_id": "",
        "workspace_id": workspace["workspace_id"],
        "session_id": session_id,
        "base_revision": base_revision,
        "field": field,
        "artifact": artifact,
        "value": deepcopy(value),
        "reason": reason,
        "actor": actor,
        "affected_artifacts": _impact(workspace, artifact),
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
    }
    proposal["proposal_id"] = proposal["_id"]
    if await _ensure_store():
        await _proposals.insert_one(proposal)
    else:
        _mem_proposals[proposal["proposal_id"]] = proposal
    result = deepcopy(proposal)
    result.pop("_id", None)
    return result


async def _get_proposal(proposal_id: str) -> dict | None:
    if await _ensure_store():
        return await _proposals.find_one({"_id": proposal_id})
    return _mem_proposals.get(proposal_id)


async def list_pending_proposals(session_id: str) -> list[dict]:
    """Return every durable pending proposal for explicit confirmation routing."""
    if await _ensure_store():
        cursor = _proposals.find(
            {"session_id": session_id, "status": "pending"}
        ).sort("created_at", 1)
        docs = await cursor.to_list(length=100)
    else:
        docs = sorted(
            (
                proposal for proposal in _mem_proposals.values()
                if proposal.get("session_id") == session_id
                and proposal.get("status") == "pending"
            ),
            key=lambda proposal: proposal.get("created_at") or _now(),
        )
    results = []
    for doc in docs:
        item = deepcopy(doc)
        item["proposal_id"] = item.get("proposal_id") or item.get("_id")
        item.pop("_id", None)
        results.append(item)
    return results


async def approve_proposal(proposal_id: str, *, actor: str) -> dict:
    proposal = await _get_proposal(proposal_id)
    if not proposal:
        raise KeyError("proposal not found")
    if proposal["status"] == "rejected":
        raise ValueError("proposal already rejected")
    result = await apply_mutation(
        proposal["session_id"],
        proposal["field"],
        proposal["value"],
        base_revision=proposal["base_revision"],
        actor=actor,
        reason=proposal.get("reason", ""),
        idempotency_key=f"proposal:{proposal_id}",
    )
    if await _ensure_store():
        await _proposals.update_one(
            {"_id": proposal_id},
            {"$set": {"status": "approved", "approved_by": actor,
                      "result": result, "updated_at": _now()}},
        )
    else:
        proposal.update(status="approved", approved_by=actor, result=result, updated_at=_now())
    return {
        **result,
        "proposal_id": proposal_id,
        "session_id": proposal["session_id"],
    }


async def reject_proposal(proposal_id: str, *, actor: str, reason: str) -> dict:
    proposal = await _get_proposal(proposal_id)
    if not proposal:
        raise KeyError("proposal not found")
    if proposal["status"] == "approved":
        raise ValueError("proposal already approved")
    update = {"status": "rejected", "rejected_by": actor,
              "rejection_reason": reason, "updated_at": _now()}
    if await _ensure_store():
        await _proposals.update_one({"_id": proposal_id}, {"$set": update})
    else:
        proposal.update(update)
    return {
        "ok": True,
        "proposal_id": proposal_id,
        "session_id": proposal["session_id"],
        "field": proposal["field"],
        **update,
    }
