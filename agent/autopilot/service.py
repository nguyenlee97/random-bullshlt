"""Durable run/task state machine for Campaign Autopilot.

The engine owns orchestration state only. Capability implementations commit
typed artifacts through ``workspace.service`` and order creation remains behind
the explicit launch-review task.
"""
from __future__ import annotations

import asyncio
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from config import config
from request_context import get_request_id
from workspace.service import get_workspace, list_pending_proposals, set_preferences

APPROVAL_POLICIES = {
    "review_every_stage", "critical_only", "auto_build_draft"
}
RUN_TERMINAL = {"completed", "failed", "cancelled"}
TASK_TERMINAL = {"succeeded", "failed", "cancelled", "skipped"}
AUTOPILOT_WORKSPACE_ACTORS = {
    "autopilot_worker",
    "autopilot_review",
    # Creative Intel commits the canonical VLM verdict asynchronously on
    # behalf of the active Autopilot task. It is not an operator edit.
    "creative_intel_worker",
}

# Workspace artifacts do not map one-to-one to plan outputs. Brief and creative
# are user-owned inputs, while an externally corrected order must be verified
# rather than created again. These roots make replanning explicit and auditable.
ARTIFACT_REPLAN_ROOT = {
    "brief": ("normalize_brief",),
    # A strategy edit is the operator selecting one already-generated option.
    # Keep the simulator result and recompute only consumers of that choice.
    "strategy": ("retrieve_audience", "plan_placement_intent", "analyze_creatives"),
    "audience": ("retrieve_audience",),
    "targeting": ("derive_targeting",),
    "placement_intent": ("plan_placement_intent",),
    "creative_format_plan": ("plan_creative_formats",),
    "creative": ("analyze_creatives", "rank_placements"),
    "creative_verdict": ("analyze_creatives",),
    "placements": ("rank_placements",),
    "assignments": ("assign_creatives",),
    "forecast": ("forecast",),
    "order_draft": ("build_order_draft",),
    "order": ("verify_order",),
    "report": ("create_setup_report",),
}

# A fixed capability graph is safer than allowing a model to invent tools.
# The strategy planner may parameterize these tasks in a later slice.
STANDARD_PLAN: tuple[dict[str, Any], ...] = (
    {"key": "normalize_brief", "capability": "normalize_brief", "deps": [],
     "artifact": None, "review": "none"},
    {"key": "validate_brief", "capability": "validate_brief",
     "deps": ["normalize_brief"], "artifact": None, "review": "none"},
    {"key": "generate_strategy", "capability": "generate_strategy_options",
     "deps": ["validate_brief"], "artifact": "strategy", "review": "stage"},
    {"key": "retrieve_audience", "capability": "retrieve_and_rank_audience",
     "deps": ["generate_strategy"], "artifact": "audience", "review": "critical"},
    {"key": "derive_targeting", "capability": "derive_targeting_and_exclusions",
     "deps": ["retrieve_audience"], "artifact": "targeting", "review": "critical"},
    {"key": "plan_placement_intent", "capability": "plan_placement_intent",
     "deps": ["derive_targeting"], "artifact": "placement_intent", "review": "critical"},
    {"key": "plan_creative_formats", "capability": "plan_creative_formats",
     "deps": ["plan_placement_intent"], "artifact": "creative_format_plan",
     "review": "stage"},
    {"key": "prepare_creatives", "capability": "prepare_creatives",
     "deps": ["plan_creative_formats"], "artifact": "creative", "review": "none"},
    {"key": "analyze_creatives", "capability": "analyze_creatives",
     "deps": ["generate_strategy", "prepare_creatives"],
     "artifact": "creative_verdict", "review": "stage"},
    {"key": "rank_placements", "capability": "rank_available_placements",
     "deps": ["plan_placement_intent", "analyze_creatives"],
     "artifact": "placements", "review": "stage"},
    {"key": "assign_creatives", "capability": "assign_creatives_to_placements",
     "deps": ["analyze_creatives", "rank_placements"], "artifact": "assignments",
     "review": "critical"},
    {"key": "forecast", "capability": "forecast_reach_cost_and_risk",
     "deps": ["derive_targeting", "assign_creatives"], "artifact": "forecast",
     "review": "stage"},
    {"key": "build_order_draft", "capability": "build_order_draft",
     "deps": ["forecast"], "artifact": "order_draft", "review": "stage"},
    {"key": "run_order_guard", "capability": "run_order_guard",
     "deps": ["build_order_draft"], "artifact": None, "review": "stage"},
    {"key": "launch_approval", "capability": "request_launch_approval",
     "deps": ["run_order_guard"], "artifact": None, "review": "launch"},
    {"key": "create_order", "capability": "create_order_idempotently",
     "deps": ["launch_approval"], "artifact": "order", "review": "none"},
    {"key": "verify_order", "capability": "verify_order",
     "deps": ["create_order"], "artifact": "order", "review": "none"},
    {"key": "create_setup_report", "capability": "create_setup_report",
     "deps": ["verify_order"], "artifact": "report", "review": "none"},
)

PLAN_ORDER = {spec["key"]: index for index, spec in enumerate(STANDARD_PLAN)}

_mem_runs: dict[str, dict] = {}
_mem_tasks: dict[str, dict] = {}
_mem_events: list[dict] = []
_lock = asyncio.Lock()


class RunConflict(Exception):
    pass


def task_commit_id(task: dict) -> str:
    """Return an idempotency key scoped to one task execution generation.

    Task IDs stay stable so the UI and durable plan can follow a task across
    replans. Workspace result commits cannot use that stable ID alone: a task
    rerun after an operator edit must be allowed to replace its now-stale
    artifact. Retries inside the same generation intentionally keep the same
    key so a worker crash after commit remains idempotent.
    """
    replan_revision = task.get("replan_workspace_revision")
    generation = (
        f"workspace-{int(replan_revision)}"
        if isinstance(replan_revision, int)
        else "initial"
    )
    return f"{task['task_id']}:{generation}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    out = deepcopy(doc)
    out.pop("_id", None)
    return out


async def _collections():
    from session import _ensure_mongo
    if await _ensure_mongo():
        import session as session_store
        db = session_store._client[config.MONGODB_DB]
        return db["agent_runs"], db["agent_tasks"], db["agent_run_events"]
    return None, None, None


async def ensure_autopilot_indexes() -> None:
    """Create additive indexes used by resume and account history summaries."""
    runs, tasks, events = await _collections()
    if runs is None:
        return
    await runs.create_index(
        [("session_id", 1), ("created_at", -1)],
        name="autopilot_session_created",
    )
    await tasks.create_index(
        [("run_id", 1), ("plan_index", 1)],
        name="autopilot_task_run_plan",
    )
    await events.create_index(
        [("run_id", 1), ("created_at", 1)],
        name="autopilot_event_run_created",
    )


async def _emit(run_id: str, event_type: str, payload: dict | None = None) -> dict:
    event = {
        "event_id": f"are_{uuid.uuid4().hex}", "run_id": run_id,
        "type": event_type, "payload": deepcopy(payload or {}), "created_at": _now(),
    }
    _, _, events = await _collections()
    if events is not None:
        await events.insert_one({"_id": event["event_id"], **event})
    else:
        _mem_events.append(event)
    return event


def _task_id(run_id: str, key: str) -> str:
    return f"{run_id}:{key}"


def _needs_review(task: dict, policy: str) -> bool:
    level = task.get("review_level", task.get("review", "none"))
    if level == "launch":
        return True
    if level == "critical":
        return policy in {"review_every_stage", "critical_only"}
    if level == "stage":
        return policy == "review_every_stage"
    return False


def _new_tasks(run_id: str) -> list[dict]:
    now = _now()
    return [{
        "_id": _task_id(run_id, spec["key"]),
        "task_id": _task_id(run_id, spec["key"]),
        "run_id": run_id,
        "key": spec["key"],
        "plan_index": plan_index,
        "capability": spec["capability"],
        "dependencies": [_task_id(run_id, dep) for dep in spec["deps"]],
        "artifact": spec["artifact"],
        "review_level": spec["review"],
        "status": "queued" if not spec["deps"] else "pending",
        "attempts": 0,
        "max_attempts": config.AUTOPILOT_TASK_MAX_ATTEMPTS,
        "lease_owner": None,
        "lease_expires_at": None,
        "input_revisions": {},
        "result": None,
        "evidence": [],
        "error": None,
        "created_at": now,
        "updated_at": now,
    } for plan_index, spec in enumerate(STANDARD_PLAN)]


def _task_order_key(task: dict) -> tuple[int, str]:
    """Keep plan display stable, including runs created before plan_index existed."""
    plan_index = task.get("plan_index")
    if not isinstance(plan_index, int):
        plan_index = PLAN_ORDER.get(task.get("key"), len(STANDARD_PLAN))
    return plan_index, str(task.get("created_at") or "")


async def create_run(
    session_id: str,
    *,
    approval_policy: str = "critical_only",
    creative_source: str = "upload",
    actor: str = "campaign_operator",
    idempotency_key: str = "",
    creative_direction: str = "",
    creative_asset_ids: list[str] | None = None,
) -> dict:
    if approval_policy not in APPROVAL_POLICIES:
        raise ValueError("unsupported approval_policy")
    if creative_source not in {"upload", "ai_generate"}:
        raise ValueError("creative_source must be upload or ai_generate")
    key = idempotency_key.strip() or f"autopilot:{session_id}:{uuid.uuid4().hex}"
    runs, tasks, _ = await _collections()
    if runs is not None:
        existing = await runs.find_one({"session_id": session_id, "idempotency_key": key})
    else:
        existing = next((r for r in _mem_runs.values()
                         if r["session_id"] == session_id and r["idempotency_key"] == key), None)
    if existing:
        return await get_run(existing["run_id"])

    pending_proposals = await list_pending_proposals(session_id)
    if pending_proposals:
        fields = sorted({item.get("field", "workspace") for item in pending_proposals})
        raise RunConflict(
            "Hãy duyệt hoặc hủy các đề xuất workspace đang chờ trước khi bắt đầu "
            f"Campaign Autopilot: {', '.join(fields)}"
        )
    workspace = await get_workspace(session_id)
    brief = workspace.get("artifacts", {}).get("brief", {})
    if not brief.get("value"):
        raise ValueError("brief is required before starting Campaign Autopilot")

    pref = await set_preferences(
        session_id, experience_mode="autopilot", approval_policy=approval_policy,
        creative_source=creative_source,
        base_revision=workspace["revision"], actor=actor,
        idempotency_key=f"{key}:preferences",
    )
    workspace = await get_workspace(session_id)
    from identity import get_conversation_model_for_session
    model_lock = await get_conversation_model_for_session(session_id)
    from quality.versioning import get_version_manifest
    quality_version_manifest = get_version_manifest(
        engine=(
            "openai"
            if model_lock["conversation_model"] == "openai"
            else "greennode"
        ),
        approval_policy=approval_policy,
    )
    run_id = f"run_{uuid.uuid4().hex}"
    request_id = get_request_id()
    trace_id = request_id if request_id != "-" else f"trace_{uuid.uuid4().hex[:16]}"
    now = _now()
    run = {
        "_id": run_id, "run_id": run_id, "session_id": session_id,
        "workspace_id": workspace["workspace_id"],
        "workspace_revision": workspace["revision"],
        "plan_revision": 1, "status": "queued",
        "approval_policy": approval_policy, "started_by": actor,
        "creative_source": creative_source,
        "creative_direction": " ".join(str(creative_direction or "").split())[:1200],
        "creative_asset_ids": list(dict.fromkeys(creative_asset_ids or []))[:8],
        "conversation_id": model_lock.get("conversation_id"),
        "conversation_model": model_lock["conversation_model"],
        "conversation_model_version": model_lock["conversation_model_version"],
        "quality_version_manifest": quality_version_manifest,
        "idempotency_key": key, "cancel_requested": False,
        "pause_requested": False, "current_task_id": None,
        "created_at": now, "updated_at": now,
        "preference_revision": pref["workspace_revision"],
        "trace_id": trace_id,
    }
    task_docs = _new_tasks(run_id)
    if runs is not None:
        try:
            await runs.insert_one(run)
            await tasks.insert_many(task_docs)
        except Exception:
            existing = await runs.find_one({"session_id": session_id, "idempotency_key": key})
            if existing:
                return await get_run(existing["run_id"])
            raise
    else:
        async with _lock:
            _mem_runs[run_id] = run
            _mem_tasks.update({task["task_id"]: task for task in task_docs})
    await _emit(run_id, "run_created", {
        "approval_policy": approval_policy, "creative_source": creative_source,
        "conversation_model": model_lock["conversation_model"],
    })
    return await get_run(run_id)


async def _ensure_run_model_lock(run: dict, runs) -> dict:
    """Persist the immutable model on runs created before model selection.

    A pre-migration run inherits its owning conversation once. If that
    conversation is also legacy, the identity boundary resolves the explicit
    GreenNode legacy value. Later retries and resumes read only this run lock.
    """
    from campaign_models import conversation_model_version, normalize_conversation_model

    updates: dict[str, Any] = {}
    stored_model = run.get("conversation_model")
    if stored_model:
        normalized = normalize_conversation_model(stored_model)
        if normalized != stored_model:
            updates["conversation_model"] = normalized
        if not run.get("conversation_model_version"):
            updates["conversation_model_version"] = conversation_model_version(normalized)
    else:
        from identity import get_conversation_model_for_session

        lock = await get_conversation_model_for_session(run["session_id"])
        updates.update({
            "conversation_id": run.get("conversation_id") or lock.get("conversation_id"),
            "conversation_model": lock["conversation_model"],
            "conversation_model_version": lock["conversation_model_version"],
            "conversation_model_migrated_at": _now(),
        })

    if not updates:
        return run
    if runs is not None:
        await runs.update_one({"_id": run["_id"]}, {"$set": updates})
    else:
        _mem_runs[run["run_id"]].update(updates)
    return {**run, **updates}


async def get_run(run_id: str) -> dict:
    runs, tasks, _ = await _collections()
    if runs is not None:
        run = await runs.find_one({"_id": run_id})
        task_docs = await tasks.find({"run_id": run_id}).to_list(None)
    else:
        run = _mem_runs.get(run_id)
        task_docs = [task for task in _mem_tasks.values() if task["run_id"] == run_id]
    task_docs.sort(key=_task_order_key)
    if not run:
        raise KeyError(f"run not found: {run_id}")
    run = await _ensure_run_model_lock(run, runs)
    public_run = _public(run)
    # Runs created before trace IDs were persisted still get a stable fallback.
    public_run.setdefault("trace_id", public_run["run_id"])
    return {**public_run, "tasks": [_public(task) for task in task_docs]}


async def get_latest_run(session_id: str) -> dict | None:
    """Return the newest durable run for refresh/resume, if one exists."""
    runs, _, _ = await _collections()
    if runs is not None:
        doc = await runs.find_one({"session_id": session_id}, sort=[("created_at", -1)])
    else:
        candidates = [
            item for item in _mem_runs.values() if item.get("session_id") == session_id
        ]
        candidates.sort(key=lambda item: item.get("created_at") or _now(), reverse=True)
        doc = candidates[0] if candidates else None
    return await get_run(doc["run_id"]) if doc else None


def _history_run_summary(run: dict, task_docs: list[dict]) -> dict:
    terminal_count = sum(
        1 for task in task_docs if task.get("status") in TASK_TERMINAL
    )
    waiting = next(
        (task for task in task_docs if task.get("status") == "waiting_review"),
        None,
    )
    running = next(
        (task for task in task_docs if task.get("status") == "running"),
        None,
    )
    return {
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "approval_policy": run.get("approval_policy"),
        "task_total": len(task_docs),
        "task_completed": terminal_count,
        "current_task": (waiting or running or {}).get("key"),
        "updated_at": run.get("updated_at"),
    }


async def get_latest_run_summaries(session_ids: list[str]) -> dict[str, dict]:
    """Return one bounded run summary per session without N+1 history reads."""
    wanted = list(dict.fromkeys(value for value in session_ids if value))
    if not wanted:
        return {}
    runs, tasks, _ = await _collections()
    if runs is not None:
        run_docs = await runs.find(
            {"session_id": {"$in": wanted}}
        ).sort("created_at", -1).to_list(None)
        latest: dict[str, dict] = {}
        for run in run_docs:
            latest.setdefault(run.get("session_id"), run)
        run_ids = [run.get("run_id") for run in latest.values() if run.get("run_id")]
        task_docs = await tasks.find(
            {"run_id": {"$in": run_ids}},
            {"run_id": 1, "key": 1, "status": 1, "plan_index": 1},
        ).to_list(None) if run_ids else []
    else:
        latest = {}
        for run in sorted(
            _mem_runs.values(), key=lambda item: item.get("created_at") or _now(),
            reverse=True,
        ):
            session_id = run.get("session_id")
            if session_id in wanted:
                latest.setdefault(session_id, run)
        run_ids = {run.get("run_id") for run in latest.values()}
        task_docs = [
            task for task in _mem_tasks.values() if task.get("run_id") in run_ids
        ]
    tasks_by_run: dict[str, list[dict]] = {}
    for task in task_docs:
        tasks_by_run.setdefault(task.get("run_id"), []).append(task)
    return {
        session_id: _history_run_summary(
            run, sorted(tasks_by_run.get(run.get("run_id"), []), key=_task_order_key),
        )
        for session_id, run in latest.items()
        if session_id
    }


async def list_events(run_id: str, after: datetime | None = None) -> list[dict]:
    _, _, events = await _collections()
    query: dict[str, Any] = {"run_id": run_id}
    if after is not None:
        query["created_at"] = {"$gt": after}
    if events is not None:
        docs = await events.find(query).sort("created_at", 1).to_list(None)
    else:
        docs = [event for event in _mem_events if event["run_id"] == run_id
                and (after is None or event["created_at"] > after)]
    return [_public(doc) for doc in docs]


async def _set_run(run_id: str, updates: dict) -> None:
    updates = {**updates, "updated_at": _now()}
    runs, _, _ = await _collections()
    if runs is not None:
        result = await runs.update_one({"_id": run_id}, {"$set": updates})
        if result.matched_count != 1:
            raise KeyError(f"run not found: {run_id}")
    else:
        if run_id not in _mem_runs:
            raise KeyError(f"run not found: {run_id}")
        _mem_runs[run_id].update(updates)
    # A Zalo-created run has no browser chat traffic to update conversation
    # recency. Touch only the canonical conversation activity timestamp so it
    # stays visible in account history while the worker advances it.
    run = await get_run(run_id)
    from identity import touch_conversation_activity_for_session
    await touch_conversation_activity_for_session(run["session_id"])


async def pause_run(run_id: str, actor: str = "campaign_operator") -> dict:
    run = await get_run(run_id)
    if run["status"] in RUN_TERMINAL:
        raise RunConflict("terminal run cannot be paused")
    await _set_run(run_id, {"status": "paused", "pause_requested": True,
                            "paused_by": actor})
    await _emit(run_id, "run_paused", {"actor": actor})
    return await get_run(run_id)


async def resume_run(run_id: str, actor: str = "campaign_operator") -> dict:
    run = await get_run(run_id)
    if run["status"] != "paused":
        raise RunConflict("only a paused run can be resumed")
    if run.get("replan_blocked"):
        raise RunConflict(
            "run crossed the order side-effect boundary; start a new run to apply edits"
        )
    reconciliation = await reconcile_workspace_changes(run_id)
    if (
        reconciliation.get("reason") == "side_effect_boundary"
        or reconciliation["run"].get("replan_blocked")
    ):
        raise RunConflict(
            "run crossed the order side-effect boundary; start a new run to apply edits"
        )
    await _set_run(run_id, {"status": "queued", "pause_requested": False,
                            "resumed_by": actor})
    await _emit(run_id, "run_resumed", {"actor": actor})
    return await get_run(run_id)


async def cancel_run(run_id: str, actor: str = "campaign_operator") -> dict:
    run = await get_run(run_id)
    if run["status"] in RUN_TERMINAL:
        return run
    now = _now()
    runs, tasks, _ = await _collections()
    if runs is not None:
        await runs.update_one({"_id": run_id}, {"$set": {
            "status": "cancelled", "cancel_requested": True,
            "cancelled_by": actor, "updated_at": now,
        }})
        await tasks.update_many(
            {"run_id": run_id, "status": {"$in": ["pending", "queued"]}},
            {"$set": {"status": "cancelled", "updated_at": now}},
        )
    else:
        _mem_runs[run_id].update(status="cancelled", cancel_requested=True,
                                 cancelled_by=actor, updated_at=now)
        for task in _mem_tasks.values():
            if task["run_id"] == run_id and task["status"] in {"pending", "queued"}:
                task.update(status="cancelled", updated_at=now)
    await _emit(run_id, "run_cancelled", {"actor": actor})
    return await get_run(run_id)


async def _refresh_run_status(run_id: str) -> None:
    run = await get_run(run_id)
    if run["status"] in {"paused", "cancelled"}:
        return
    statuses = {task["status"] for task in run["tasks"]}
    if "waiting_review" in statuses:
        status = "waiting_review"
    elif "failed" in statuses:
        status = "failed"
    elif statuses and statuses.issubset(TASK_TERMINAL):
        status = "completed"
    elif "running" in statuses:
        status = "running"
    else:
        status = "queued"
    await _set_run(run_id, {"status": status})


async def _queue_ready_dependents(run_id: str) -> None:
    run = await get_run(run_id)
    statuses = {task["task_id"]: task["status"] for task in run["tasks"]}
    ready = [task["task_id"] for task in run["tasks"]
             if task["status"] == "pending" and task["dependencies"]
             and all(statuses.get(dep) == "succeeded" for dep in task["dependencies"])]
    if not ready:
        return
    _, tasks, _ = await _collections()
    now = _now()
    if tasks is not None:
        await tasks.update_many({"_id": {"$in": ready}},
                                {"$set": {"status": "queued", "updated_at": now}})
    else:
        for task_id in ready:
            _mem_tasks[task_id].update(status="queued", updated_at=now)


def _external_workspace_changes(workspace: dict, after_revision: int) -> list[str]:
    changed: set[str] = set()
    for event in workspace.get("events", []):
        if int(event.get("revision", 0)) <= after_revision:
            continue
        artifact = event.get("artifact")
        if artifact and event.get("actor") not in AUTOPILOT_WORKSPACE_ACTORS:
            changed.add(artifact)
    # The bounded event history is normally sufficient. Artifact metadata is a
    # safe fallback if a long-running workspace has already truncated events.
    for artifact, item in workspace.get("artifacts", {}).items():
        if (
            int((item or {}).get("revision", 0)) > after_revision
            and (item or {}).get("updated_by") not in AUTOPILOT_WORKSPACE_ACTORS
        ):
            changed.add(artifact)
    return [name for name in ARTIFACT_REPLAN_ROOT if name in changed]


def _task_descendants(root_keys: set[str]) -> set[str]:
    descendants = set(root_keys)
    changed = True
    while changed:
        changed = False
        for spec in STANDARD_PLAN:
            if spec["key"] in descendants:
                continue
            if any(dependency in descendants for dependency in spec["deps"]):
                descendants.add(spec["key"])
                changed = True
    return descendants


async def reconcile_workspace_changes(run_id: str) -> dict:
    """Replan an active run after external canonical-workspace edits.

    Only affected tasks are reset. A task that is currently running is allowed
    to reach its revision-checked commit boundary before reconciliation. Once
    order creation succeeded, edits block this run instead of replaying the
    external side effect.
    """
    run = await get_run(run_id)
    if run["status"] in RUN_TERMINAL:
        return {"changed": False, "reason": "terminal", "run": run}
    workspace = await get_workspace(run["session_id"])
    previous_revision = int(run.get("workspace_revision", 0))
    if workspace["revision"] <= previous_revision:
        return {"changed": False, "reason": "current", "run": run}
    changed_artifacts = _external_workspace_changes(workspace, previous_revision)
    if not changed_artifacts:
        await _set_run(run_id, {"workspace_revision": workspace["revision"]})
        return {"changed": False, "reason": "internal_only", "run": await get_run(run_id)}

    root_keys = {
        root
        for artifact in changed_artifacts
        for root in ARTIFACT_REPLAN_ROOT.get(artifact, ())
    }
    affected_keys = _task_descendants(root_keys)
    # When the operator edits the exact artifact currently waiting for review,
    # their canonical mutation supersedes the pending Autopilot proposal. The
    # producer is accepted as an operator override; only its consumers replan.
    # Input-gate tasks such as prepare_creatives are requeued instead so they
    # can validate the newly uploaded file set before downstream work starts.
    recheck = [
        task for task in run["tasks"]
        if task.get("status") == "waiting_review"
        and task.get("artifact") in changed_artifacts
        and task.get("key") == "prepare_creatives"
    ]
    recheck_ids = {task["task_id"] for task in recheck}
    superseded = [
        task for task in run["tasks"]
        if task.get("status") == "waiting_review"
        and task.get("artifact") in changed_artifacts
        and task["task_id"] not in recheck_ids
        and workspace.get("artifacts", {}).get(task.get("artifact"), {}).get("status") == "approved"
    ]
    superseded_ids = {task["task_id"] for task in superseded}
    affected = [
        task for task in run["tasks"]
        if (task["key"] in affected_keys or task["task_id"] in recheck_ids)
        and task["task_id"] not in superseded_ids
    ]
    running = [task["task_id"] for task in affected if task["status"] == "running"]
    if running:
        await _set_run(run_id, {"replan_pending": {
            "workspace_revision": workspace["revision"],
            "changed_artifacts": changed_artifacts,
            "running_tasks": running,
        }})
        return {"changed": False, "reason": "running_task", "run": await get_run(run_id)}

    created = next((task for task in run["tasks"] if task["key"] == "create_order"), None)
    if created and created["status"] == "succeeded" and "create_order" in affected_keys:
        blocked = {
            "reason": "order_already_created",
            "message": "Workspace changed after order creation; start a new run to apply edits.",
            "workspace_revision": workspace["revision"],
            "changed_artifacts": changed_artifacts,
        }
        await _set_run(run_id, {
            "status": "paused", "pause_requested": True,
            "replan_blocked": blocked, "workspace_revision": workspace["revision"],
        })
        await _emit(run_id, "run_replan_blocked", blocked)
        return {"changed": False, "reason": "side_effect_boundary",
                "run": await get_run(run_id)}

    statuses = {task["task_id"]: task["status"] for task in run["tasks"]}
    statuses.update({task_id: "succeeded" for task_id in superseded_ids})
    affected_ids = {task["task_id"] for task in affected}
    now = _now()
    superseded_docs: list[tuple[str, dict]] = []
    for task in superseded:
        artifact_value = deepcopy(
            workspace.get("artifacts", {}).get(task["artifact"], {}).get("value")
        )
        superseded_docs.append((task["task_id"], {
            "status": "succeeded", "result": artifact_value,
            "pending_artifact": None, "error": None,
            "review_decision": {
                "approved": True, "actor": "campaign_operator",
                "reason": "canonical artifact edited during review",
                "created_at": now, "source": "workspace_override",
            },
            "completed_at": now, "updated_at": now,
        }))
    reset_docs: list[tuple[str, dict]] = []
    for task in affected:
        external_dependencies_ready = all(
            dependency not in affected_ids and statuses.get(dependency) == "succeeded"
            for dependency in task["dependencies"]
        )
        status = "queued" if not task["dependencies"] or external_dependencies_ready else "pending"
        reset_docs.append((task["task_id"], {
            "status": status, "attempts": 0, "lease_owner": None,
            "lease_expires_at": None, "result": None, "evidence": [], "error": None,
            "pending_artifact": None, "review_decision": None,
            "replanned_from_status": task["status"],
            "replan_workspace_revision": workspace["revision"], "updated_at": now,
        }))

    _, tasks, _ = await _collections()
    if tasks is not None:
        for task_id, updates in superseded_docs:
            await tasks.update_one({"_id": task_id}, {"$set": updates})
        for task_id, updates in reset_docs:
            await tasks.update_one(
                {"_id": task_id},
                {"$set": updates, "$unset": {"completed_at": "", "started_at": ""}},
            )
    else:
        for task_id, updates in superseded_docs:
            _mem_tasks[task_id].update(updates)
        for task_id, updates in reset_docs:
            _mem_tasks[task_id].update(updates)
            _mem_tasks[task_id].pop("completed_at", None)
            _mem_tasks[task_id].pop("started_at", None)

    plan_revision = int(run.get("plan_revision", 1)) + 1
    unaffected_review = any(
        task["status"] == "waiting_review"
        and task["task_id"] not in affected_ids
        and task["task_id"] not in superseded_ids
        for task in run["tasks"]
    )
    next_status = (
        "paused" if run["status"] == "paused"
        else "waiting_review" if unaffected_review
        else "queued"
    )
    await _set_run(run_id, {
        "status": next_status, "current_task_id": None,
        "workspace_revision": workspace["revision"], "plan_revision": plan_revision,
        "replan_pending": None, "last_replan": {
            "from_workspace_revision": previous_revision,
            "to_workspace_revision": workspace["revision"],
            "changed_artifacts": changed_artifacts,
            "affected_tasks": [task["key"] for task in affected],
            "superseded_review_tasks": [task["key"] for task in superseded],
            "rechecked_input_tasks": [task["key"] for task in recheck],
            "created_at": now,
        },
    })
    await _emit(run_id, "run_replanned", {
        "plan_revision": plan_revision,
        "from_workspace_revision": previous_revision,
        "to_workspace_revision": workspace["revision"],
        "changed_artifacts": changed_artifacts,
        "affected_tasks": [task["key"] for task in affected],
        "superseded_review_tasks": [task["key"] for task in superseded],
        "rechecked_input_tasks": [task["key"] for task in recheck],
    })
    return {"changed": True, "reason": "workspace_changed", "run": await get_run(run_id)}


async def reconcile_active_runs() -> int:
    runs, _, _ = await _collections()
    if runs is not None:
        docs = await runs.find({"status": {"$nin": list(RUN_TERMINAL)}}).to_list(None)
    else:
        docs = [run for run in _mem_runs.values() if run["status"] not in RUN_TERMINAL]
    count = 0
    for run in docs:
        result = await reconcile_workspace_changes(run["run_id"])
        count += int(bool(result.get("changed")))
    return count


async def claim_next_task(worker_id: str, lease_seconds: int | None = None) -> dict | None:
    """Claim one queued task. Expired leases are recovered before selection."""
    await recover_expired_leases()
    lease_seconds = lease_seconds or config.AUTOPILOT_TASK_LEASE_SECONDS
    runs, tasks, _ = await _collections()
    now = _now()
    candidates = []
    if tasks is not None:
        candidates = await tasks.find({"status": "queued"}).sort("created_at", 1).to_list(20)
    else:
        candidates = sorted(
            (task for task in _mem_tasks.values() if task["status"] == "queued"),
            key=lambda task: task["created_at"],
        )[:20]
    for candidate in candidates:
        reconciliation = await reconcile_workspace_changes(candidate["run_id"])
        if reconciliation.get("changed"):
            continue
        run = await get_run(candidate["run_id"])
        if run["status"] in RUN_TERMINAL | {"paused", "waiting_review"}:
            continue
        updates = {
            "status": "running", "lease_owner": worker_id,
            "lease_expires_at": now + timedelta(seconds=lease_seconds),
            "started_at": candidate.get("started_at") or now,
            "attempts": candidate.get("attempts", 0) + 1, "updated_at": now,
        }
        claimed = False
        if tasks is not None:
            result = await tasks.update_one(
                {"_id": candidate["_id"], "status": "queued"}, {"$set": updates}
            )
            claimed = result.modified_count == 1
        else:
            async with _lock:
                current = _mem_tasks.get(candidate["task_id"])
                if current and current["status"] == "queued":
                    current.update(updates)
                    claimed = True
        if claimed:
            await _set_run(candidate["run_id"], {
                "status": "running", "current_task_id": candidate["task_id"]
            })
            await _emit(candidate["run_id"], "task_started", {
                "task_id": candidate["task_id"], "worker_id": worker_id,
            })
            refreshed = await get_run(candidate["run_id"])
            return next(
                task for task in refreshed["tasks"]
                if task["task_id"] == candidate["task_id"]
            )
    return None


async def renew_task_lease(
    task_id: str, worker_id: str, lease_seconds: int | None = None,
) -> bool:
    """Extend a running task lease while a long provider call is in flight."""
    lease_seconds = lease_seconds or config.AUTOPILOT_TASK_LEASE_SECONDS
    _, tasks, _ = await _collections()
    now = _now()
    updates = {
        "lease_expires_at": now + timedelta(seconds=lease_seconds),
        "updated_at": now,
    }
    if tasks is not None:
        result = await tasks.update_one(
            {"_id": task_id, "status": "running", "lease_owner": worker_id},
            {"$set": updates},
        )
        return result.modified_count == 1
    async with _lock:
        task = _mem_tasks.get(task_id)
        if not task or task.get("status") != "running" or task.get("lease_owner") != worker_id:
            return False
        task.update(updates)
        return True


async def complete_task(
    task_id: str, *, result: Any = None, evidence: list | None = None,
    force_review: bool = False, pending_artifact: dict | None = None,
) -> dict:
    runs, tasks, _ = await _collections()
    if tasks is not None:
        task = await tasks.find_one({"_id": task_id})
    else:
        task = _mem_tasks.get(task_id)
    if not task:
        raise KeyError(f"task not found: {task_id}")
    if task["status"] != "running":
        raise RunConflict("only a running task can complete")
    run = await get_run(task["run_id"])
    waiting = force_review or _needs_review(task, run["approval_policy"])
    status = "waiting_review" if waiting else "succeeded"
    now = _now()
    updates = {
        "status": status, "result": deepcopy(result),
        "evidence": deepcopy(evidence or []), "completed_at": now,
        "pending_artifact": deepcopy(pending_artifact),
        "updated_at": now, "lease_owner": None, "lease_expires_at": None,
    }
    if tasks is not None:
        await tasks.update_one({"_id": task_id}, {"$set": updates})
    else:
        _mem_tasks[task_id].update(updates)
    await _emit(task["run_id"], "task_waiting_review" if waiting else "task_completed",
                {"task_id": task_id})
    if not waiting:
        await _queue_ready_dependents(task["run_id"])
    await _refresh_run_status(task["run_id"])
    return await get_run(task["run_id"])


async def fail_task(task_id: str, error: str, retryable: bool = True) -> dict:
    _, tasks, _ = await _collections()
    task = await tasks.find_one({"_id": task_id}) if tasks is not None else _mem_tasks.get(task_id)
    if not task:
        raise KeyError(f"task not found: {task_id}")
    if task["status"] != "running":
        raise RunConflict("only a running task can fail")
    retry = retryable and task.get("attempts", 0) < task.get("max_attempts", 1)
    updates = {
        "status": "queued" if retry else "failed", "error": error[:500],
        "lease_owner": None, "lease_expires_at": None, "updated_at": _now(),
    }
    if tasks is not None:
        await tasks.update_one({"_id": task_id}, {"$set": updates})
    else:
        _mem_tasks[task_id].update(updates)
    await _emit(task["run_id"], "task_retry_scheduled" if retry else "task_failed",
                {"task_id": task_id, "error": error[:200]})
    await _refresh_run_status(task["run_id"])
    return await get_run(task["run_id"])


async def review_task(
    run_id: str, task_id: str, *, approved: bool,
    actor: str = "campaign_operator", reason: str = "",
) -> dict:
    _, tasks, _ = await _collections()
    task = await tasks.find_one({"_id": task_id, "run_id": run_id}) if tasks is not None \
        else _mem_tasks.get(task_id)
    if not task or task.get("run_id") != run_id:
        raise KeyError(f"task not found: {task_id}")
    if task["status"] != "waiting_review":
        if (
            approved
            and task["status"] in {"queued", "running"}
            and task.get("replanned_from_status") == "waiting_review"
        ):
            return await get_run(run_id)
        raise RunConflict("task is not waiting for review")
    now = _now()
    retry_after_review = bool(
        approved and (task.get("result") or {}).get("review_action") == "retry"
    )
    if retry_after_review and task.get("key") == "validate_brief":
        run = await get_run(run_id)
        pending = await list_pending_proposals(run["session_id"])
        if any(item.get("field") == "brief" for item in pending):
            raise RunConflict(
                "Brief đang chờ duyệt trong Chat; hãy duyệt hoặc hủy đề xuất trước khi kiểm tra lại"
            )
        workspace = await get_workspace(run["session_id"])
        from autopilot.capabilities import validate_brief_value
        _, validation_errors = validate_brief_value(
            workspace.get("artifacts", {}).get("brief", {}).get("value")
        )
        if validation_errors:
            raise RunConflict(
                "Brief vẫn chưa hợp lệ: " + "; ".join(validation_errors)
            )
    if not retry_after_review:
        reconciliation = await reconcile_workspace_changes(run_id)
        if reconciliation.get("reason") == "side_effect_boundary":
            raise RunConflict(
                "workspace changed; this review was superseded by a replanned task"
            )
        task = await tasks.find_one({"_id": task_id, "run_id": run_id}) if tasks is not None \
            else _mem_tasks.get(task_id)
    if not task or task["status"] != "waiting_review":
        raise RunConflict("task is no longer waiting for review")
    if (
        approved
        and task.get("key") == "retrieve_audience"
        and (
            ((task.get("pending_artifact") or {}).get("value") or {}).get(
                "selection_required"
            )
        )
    ):
        raise RunConflict(
            "audience review requires at least one selected segment"
        )
    if approved and task.get("pending_artifact") and not retry_after_review:
        from workspace.service import commit_artifact_result
        pending = task["pending_artifact"]
        await commit_artifact_result(
            pending["session_id"], pending["artifact"], pending["value"],
            task_id=pending.get("commit_task_id") or task_id,
            input_revisions=pending["input_revisions"],
            base_artifact_revision=pending["base_artifact_revision"],
            actor="autopilot_review",
            reason=f"approved by {actor}: {reason}".strip(),
        )
    updates = {
        "status": "queued" if retry_after_review else (
            "succeeded" if approved else "failed"
        ),
        "review_decision": {"approved": approved, "actor": actor, "reason": reason,
                            "created_at": now},
        "pending_artifact": None if approved else task.get("pending_artifact"),
        "updated_at": now,
    }
    if tasks is not None:
        await tasks.update_one({"_id": task_id}, {"$set": updates})
    else:
        _mem_tasks[task_id].update(updates)
    await _emit(run_id, "task_approved" if approved else "task_rejected",
                {"task_id": task_id, "actor": actor, "reason": reason})
    if approved and not retry_after_review:
        await _queue_ready_dependents(run_id)
    await _refresh_run_status(run_id)
    if retry_after_review:
        await reconcile_workspace_changes(run_id)
    return await get_run(run_id)


async def rerun_review_task(
    run_id: str,
    task_id: str,
    *,
    actor: str = "campaign_operator",
    reason: str = "",
) -> dict:
    """Replace an unapproved audience proposal by rerunning its task."""
    _, tasks, _ = await _collections()
    task = (
        await tasks.find_one({"_id": task_id, "run_id": run_id})
        if tasks is not None
        else _mem_tasks.get(task_id)
    )
    if not task or task.get("run_id") != run_id:
        raise KeyError(f"task not found: {task_id}")
    if task.get("status") != "waiting_review":
        raise RunConflict("task is not waiting for review")
    if task.get("key") != "retrieve_audience":
        raise RunConflict("only the audience review can be recommended again")

    run = await get_run(run_id)
    if run.get("status") in RUN_TERMINAL:
        raise RunConflict("audience cannot be rerun after the run is terminal")
    if any(
        item.get("key") == "create_order" and item.get("status") == "succeeded"
        for item in run.get("tasks", [])
    ):
        raise RunConflict("audience cannot be rerun after order creation")

    now = _now()
    updates = {
        "status": "queued",
        "result": None,
        "evidence": [],
        "pending_artifact": None,
        "review_decision": {
            "approved": None,
            "actor": actor,
            "reason": reason.strip() or "Audience recommendation requested again",
            "created_at": now,
        },
        "completed_at": None,
        "lease_owner": None,
        "lease_expires_at": None,
        "updated_at": now,
    }
    if tasks is not None:
        await tasks.update_one({"_id": task_id}, {"$set": updates})
    else:
        _mem_tasks[task_id].update(updates)
    await _emit(run_id, "task_retry_scheduled", {
        "task_id": task_id,
        "actor": actor,
        "reason": updates["review_decision"]["reason"],
        "explicit_review_rerun": True,
    })
    await _refresh_run_status(run_id)
    return await get_run(run_id)


async def select_audience_recommendations(
    run_id: str,
    segment_ids: list[str],
    *,
    actor: str = "campaign_operator",
    reason: str = "",
) -> dict:
    """Select reviewed direct/adjacent catalog rows without approving the gate."""
    from audience_reach import audience_selection

    run = await get_run(run_id)
    if run["status"] in RUN_TERMINAL:
        raise RunConflict("audience selection cannot change after the run is terminal")
    task = next(
        (item for item in run["tasks"] if item["key"] == "retrieve_audience"),
        None,
    )
    if not task or task["status"] != "waiting_review":
        raise RunConflict("audience recommendation is not waiting for review")
    pending = deepcopy(task.get("pending_artifact") or {})
    if pending.get("artifact") != "audience":
        raise RunConflict("audience review has no pending artifact")

    value = deepcopy(pending.get("value") or {})
    candidates = (
        value.get("recommendations")
        or [*(value.get("attrs") or []), *(value.get("adjacent_attrs") or [])]
    )

    def identity(item: dict) -> str:
        return str(
            item.get("segmentId")
            or item.get("_id")
            or item.get("code")
            or item.get("fullLabel")
            or item.get("name")
            or ""
        ).strip()

    by_id = {
        identity(item): item
        for item in candidates
        if isinstance(item, dict) and identity(item)
    }
    selected_ids = list(dict.fromkeys(
        str(item).strip() for item in segment_ids if str(item).strip()
    ))
    if not selected_ids:
        raise ValueError("select at least one audience segment")
    if len(selected_ids) > 12:
        raise ValueError("select at most 12 audience segments")
    unknown = [segment_id for segment_id in selected_ids if segment_id not in by_id]
    if unknown:
        raise ValueError(
            "audience is not in the reviewed recommendation: "
            + ", ".join(unknown)
        )

    selected = [deepcopy(by_id[segment_id]) for segment_id in selected_ids]
    selection = audience_selection(selected)
    selection_reason = reason.strip() or "Operator adjusted the reviewed audience"
    value.update({
        **selection,
        "selection_required": False,
        "selection": {
            "source": "operator",
            "actor": actor,
            "reason": selection_reason,
            "selected_at": _now(),
            "selected_count": len(selected),
        },
    })
    pending["value"] = value
    evidence = deepcopy(task.get("evidence") or [])
    evidence.append({
        "type": "audience_selection_updated",
        "actor": actor,
        "selected_count": len(selected),
        "segment_ids": selected_ids,
        "reason": selection_reason,
    })
    updates = {
        "result": value,
        "pending_artifact": pending,
        "evidence": evidence,
        "updated_at": _now(),
    }
    _, tasks, _ = await _collections()
    if tasks is not None:
        await tasks.update_one({"_id": task["task_id"]}, {"$set": updates})
    else:
        _mem_tasks[task["task_id"]].update(updates)
    await _emit(run_id, "audience_selection_updated", {
        "task_id": task["task_id"],
        "actor": actor,
        "selected_count": len(selected),
    })
    return await get_run(run_id)


async def select_placement_intent(
    run_id: str,
    zone_ids: list[str],
    *,
    actor: str = "campaign_operator",
    reason: str = "",
) -> dict:
    """Update the shortlist inside its review gate without restarting the run."""
    run = await get_run(run_id)
    if run["status"] in RUN_TERMINAL:
        raise RunConflict("placement selection cannot change after the run is terminal")
    if any(
        task["key"] == "create_order" and task["status"] == "succeeded"
        for task in run["tasks"]
    ):
        raise RunConflict("placement selection cannot change after order creation")

    task = next(
        (item for item in run["tasks"] if item["key"] == "plan_placement_intent"),
        None,
    )
    if not task or task["status"] != "waiting_review":
        raise RunConflict("placement shortlist is not waiting for review")
    pending = deepcopy(task.get("pending_artifact") or {})
    if pending.get("artifact") != "placement_intent":
        raise RunConflict("placement review has no pending artifact")

    value = deepcopy(pending.get("value") or {})
    candidates = value.get("candidates") or []
    by_id = {
        str(item.get("id")): item
        for item in candidates
        if isinstance(item, dict) and item.get("id")
    }
    selected_ids = list(dict.fromkeys(str(item).strip() for item in zone_ids if str(item).strip()))
    if not selected_ids:
        raise ValueError("select at least one placement")
    if len(selected_ids) > 12:
        raise ValueError("select at most 12 placements")
    unknown = [zone_id for zone_id in selected_ids if zone_id not in by_id]
    if unknown:
        raise ValueError("placement is not in the reviewed shortlist: " + ", ".join(unknown))

    selection_reason = reason.strip() or "Operator adjusted the reviewed shortlist"
    value.update({
        "candidate_zone_ids": selected_ids,
        "candidates": [deepcopy(by_id[zone_id]) for zone_id in selected_ids],
        "selection": {
            "source": "operator",
            "actor": actor,
            "reason": selection_reason,
            "selected_at": _now(),
            "selected_count": len(selected_ids),
        },
    })
    pending["value"] = value
    evidence = deepcopy(task.get("evidence") or [])
    evidence.append({
        "type": "placement_selection_updated",
        "actor": actor,
        "selected_count": len(selected_ids),
        "candidate_zone_ids": selected_ids,
        "reason": selection_reason,
    })
    updates = {
        "result": value,
        "pending_artifact": pending,
        "evidence": evidence,
        "updated_at": _now(),
    }
    _, tasks, _ = await _collections()
    if tasks is not None:
        await tasks.update_one({"_id": task["task_id"]}, {"$set": updates})
    else:
        _mem_tasks[task["task_id"]].update(updates)
    await _emit(run_id, "placement_selection_updated", {
        "task_id": task["task_id"],
        "actor": actor,
        "selected_count": len(selected_ids),
    })
    return await get_run(run_id)


async def generate_missing_creative_formats(
    run_id: str,
    format_ids: list[str] | None = None,
    *,
    actor: str = "campaign_operator",
    reason: str = "",
) -> dict:
    """Generate exact-size repair assets for a recoverable creative mismatch.

    This is an explicit operator recovery action. It does not change the run's
    original creative-source choice: generated assets are merged into the
    canonical creative artifact, then normal workspace reconciliation reruns
    Creative Intelligence and placement compatibility.
    """
    run = await get_run(run_id)
    if run["status"] in RUN_TERMINAL:
        raise RunConflict("creative recovery cannot change a terminal run")
    if any(
        task["key"] == "create_order" and task["status"] == "succeeded"
        for task in run["tasks"]
    ):
        raise RunConflict("creative recovery cannot run after order creation")

    waiting = next(
        (task for task in run["tasks"] if task["status"] == "waiting_review"),
        None,
    )
    allowed_waiting_tasks = {"prepare_creatives", "rank_placements"}
    if not waiting or waiting.get("key") not in allowed_waiting_tasks:
        raise RunConflict(
            "creative recovery is available only at a creative compatibility review"
        )

    workspace = await get_workspace(run["session_id"])
    artifacts = workspace.get("artifacts", {})
    format_plan = deepcopy(
        artifacts.get("creative_format_plan", {}).get("value") or {}
    )
    planned = list(format_plan.get("formats") or [])
    if not planned:
        raise RunConflict("creative recovery has no planned formats")

    creative = deepcopy(artifacts.get("creative", {}).get("value") or {})
    files = list(creative.get("files") or [])
    from tools.creative_match import match_file_to_format

    missing = [
        item for item in planned
        if not any(match_file_to_format(file, item).get("matched") for file in files)
    ]
    requested = list(dict.fromkeys(
        str(value).strip() for value in (format_ids or []) if str(value).strip()
    ))
    planned_by_id = {
        str(item.get("format_id")): item
        for item in planned if item.get("format_id")
    }
    unknown = [value for value in requested if value not in planned_by_id]
    if unknown:
        raise ValueError(
            "format is not in the current creative plan: " + ", ".join(unknown)
        )
    missing_ids = {str(item.get("format_id")) for item in missing}
    selected = [
        item for item in missing
        if not requested or str(item.get("format_id")) in requested
    ]
    if requested and not selected:
        return {
            "ok": True,
            "generated_count": 0,
            "failed_formats": [],
            "already_covered": requested,
            "run": run,
        }
    if len(selected) > config.AUTOPILOT_MAX_GENERATED_ASSETS:
        selected = selected[:config.AUTOPILOT_MAX_GENERATED_ASSETS]

    from autopilot.creative_generation import generate_creatives

    generated, failures = await generate_creatives(
        run,
        workspace,
        {**format_plan, "formats": selected},
        concurrency=config.AUTOPILOT_CREATIVE_GENERATION_CONCURRENCY,
    )
    if not generated:
        return {
            "ok": False,
            "generated_count": 0,
            "failed_formats": [
                item.get("format_id") for item in failures
            ],
            "message": (
                "Chưa thể tạo creative cho các format còn thiếu. "
                "Bạn có thể crop/scale ảnh hiện có hoặc thử lại."
            ),
            "run": await get_run(run_id),
        }

    merged_by_id = {
        str(file.get("id") or file.get("_id") or file.get("url") or index): file
        for index, file in enumerate(files)
    }
    for file in generated:
        key = str(file.get("id") or file.get("url"))
        merged_by_id[key] = file
    merged_files = list(merged_by_id.values())

    from workspace.service import apply_mutation

    generated_ids = sorted(
        str((file.get("generation") or {}).get("idempotencyKey") or file.get("id"))
        for file in generated
    )
    await apply_mutation(
        run["session_id"],
        "creative",
        {
            **creative,
            "files": merged_files,
            "uploaded": True,
            "source": "mixed_recovery",
        },
        base_revision=workspace["revision"],
        actor=actor,
        reason=reason.strip() or (
            "Operator requested exact-format creative generation during placement recovery"
        ),
        idempotency_key=(
            f"{run_id}:creative-recovery:r{workspace['revision']}:"
            + "|".join(generated_ids)
        ),
    )
    reconciliation = await reconcile_workspace_changes(run_id)
    await _emit(run_id, "creative_recovery_generated", {
        "actor": actor,
        "generated_count": len(generated),
        "format_ids": [file.get("formatId") for file in generated],
        "failed_formats": [item.get("format_id") for item in failures],
        "requested_missing_formats": sorted(missing_ids),
    })
    return {
        "ok": True,
        "generated_count": len(generated),
        "generated_format_ids": [file.get("formatId") for file in generated],
        "failed_formats": [item.get("format_id") for item in failures],
        "workspace_revision": reconciliation["run"].get("workspace_revision"),
        "run": await get_run(run_id),
    }


async def select_strategy(
    run_id: str,
    option_id: str,
    *,
    actor: str = "campaign_operator",
    reason: str = "",
) -> dict:
    """Record a simulator choice and safely replan its downstream consumers."""
    run = await get_run(run_id)
    if run["status"] in RUN_TERMINAL:
        raise RunConflict("strategy cannot change after the run is terminal")
    if any(
        task["key"] == "create_order" and task["status"] == "succeeded"
        for task in run["tasks"]
    ):
        raise RunConflict("strategy cannot change after order creation")

    task = next((item for item in run["tasks"] if item["key"] == "generate_strategy"), None)
    if not task or task["status"] != "waiting_review":
        raise RunConflict("strategy can only change during its own review stage")
    waiting_task = next(
        (item for item in run["tasks"] if item["status"] == "waiting_review"), None
    )
    if not waiting_task or waiting_task["task_id"] != task["task_id"]:
        raise RunConflict("strategy review stage has already passed")
    value = deepcopy(task.get("result") or {})
    options = value.get("options") if isinstance(value, dict) else None
    selected_option = next(
        (item for item in (options or []) if item.get("id") == option_id), None
    )
    if not selected_option:
        raise ValueError("unknown strategy option")

    selection_reason = reason.strip() or selected_option.get("rationale", "")
    value.update({
        "selected": option_id,
        "selected_reason": selection_reason,
        "selection": {
            "source": "operator",
            "actor": actor,
            "reason": selection_reason,
            "selected_at": _now(),
        },
    })
    evidence = deepcopy(task.get("evidence") or [])
    evidence.append({
        "type": "strategy_selected", "option_id": option_id,
        "actor": actor, "reason": selection_reason,
    })

    _, tasks, _ = await _collections()
    pending = deepcopy(task.get("pending_artifact") or {})
    if pending.get("artifact") != "strategy":
        raise RunConflict("strategy review has no pending artifact")
    pending["value"] = value
    updates = {
        "result": value,
        "evidence": evidence,
        "pending_artifact": pending,
        "updated_at": _now(),
    }
    if tasks is not None:
        await tasks.update_one({"_id": task["task_id"]}, {"$set": updates})
    else:
        _mem_tasks[task["task_id"]].update(updates)
    await _emit(run_id, "strategy_selected", {
        "task_id": task["task_id"], "option_id": option_id, "actor": actor,
    })
    return await get_run(run_id)


async def recover_expired_leases() -> int:
    now = _now()
    _, tasks, _ = await _collections()
    if tasks is not None:
        result = await tasks.update_many(
            {"status": "running", "lease_expires_at": {"$lt": now}},
            {"$set": {"status": "queued", "lease_owner": None,
                      "lease_expires_at": None, "updated_at": now,
                      "error": "worker lease expired; task recovered"}},
        )
        return result.modified_count
    count = 0
    for task in _mem_tasks.values():
        expiry = task.get("lease_expires_at")
        if task["status"] == "running" and expiry and expiry < now:
            task.update(status="queued", lease_owner=None, lease_expires_at=None,
                        updated_at=now, error="worker lease expired; task recovered")
            count += 1
    return count
