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
from workspace.service import get_workspace, set_preferences

APPROVAL_POLICIES = {
    "review_every_stage", "critical_only", "auto_build_draft"
}
RUN_TERMINAL = {"completed", "failed", "cancelled"}
TASK_TERMINAL = {"succeeded", "failed", "cancelled", "skipped"}
AUTOPILOT_WORKSPACE_ACTORS = {"autopilot_worker", "autopilot_review"}

# Workspace artifacts do not map one-to-one to plan outputs. Brief and creative
# are user-owned inputs, while an externally corrected order must be verified
# rather than created again. These roots make replanning explicit and auditable.
ARTIFACT_REPLAN_ROOT = {
    "brief": "normalize_brief",
    "strategy": "generate_strategy",
    "audience": "retrieve_audience",
    "targeting": "derive_targeting",
    "creative": "analyze_creatives",
    "creative_verdict": "analyze_creatives",
    "placements": "rank_placements",
    "assignments": "assign_creatives",
    "forecast": "forecast",
    "order_draft": "build_order_draft",
    "order": "verify_order",
    "report": "create_setup_report",
}

# A fixed capability graph is safer than allowing a model to invent tools.
# The strategy planner may parameterize these tasks in a later slice.
STANDARD_PLAN: tuple[dict[str, Any], ...] = (
    {"key": "normalize_brief", "capability": "normalize_brief", "deps": [],
     "artifact": None, "review": "none"},
    {"key": "validate_brief", "capability": "validate_brief",
     "deps": ["normalize_brief"], "artifact": None, "review": "stage"},
    {"key": "generate_strategy", "capability": "generate_strategy_options",
     "deps": ["validate_brief"], "artifact": "strategy", "review": "stage"},
    {"key": "retrieve_audience", "capability": "retrieve_and_rank_audience",
     "deps": ["generate_strategy"], "artifact": "audience", "review": "stage"},
    {"key": "derive_targeting", "capability": "derive_targeting_and_exclusions",
     "deps": ["retrieve_audience"], "artifact": "targeting", "review": "stage"},
    {"key": "analyze_creatives", "capability": "analyze_creatives",
     "deps": ["generate_strategy"], "artifact": "creative_verdict", "review": "critical"},
    {"key": "rank_placements", "capability": "rank_available_placements",
     "deps": ["generate_strategy"], "artifact": "placements", "review": "stage"},
    {"key": "assign_creatives", "capability": "assign_creatives_to_placements",
     "deps": ["analyze_creatives", "rank_placements"], "artifact": "assignments",
     "review": "stage"},
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

_mem_runs: dict[str, dict] = {}
_mem_tasks: dict[str, dict] = {}
_mem_events: list[dict] = []
_lock = asyncio.Lock()


class RunConflict(Exception):
    pass


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
    } for spec in STANDARD_PLAN]


async def create_run(
    session_id: str,
    *,
    approval_policy: str = "critical_only",
    actor: str = "campaign_operator",
    idempotency_key: str = "",
) -> dict:
    if approval_policy not in APPROVAL_POLICIES:
        raise ValueError("unsupported approval_policy")
    workspace = await get_workspace(session_id)
    brief = workspace.get("artifacts", {}).get("brief", {})
    if not brief.get("value"):
        raise ValueError("brief is required before starting Campaign Autopilot")
    key = idempotency_key.strip() or f"autopilot:{session_id}:{uuid.uuid4().hex}"
    runs, tasks, _ = await _collections()
    if runs is not None:
        existing = await runs.find_one({"session_id": session_id, "idempotency_key": key})
    else:
        existing = next((r for r in _mem_runs.values()
                         if r["session_id"] == session_id and r["idempotency_key"] == key), None)
    if existing:
        return await get_run(existing["run_id"])

    pref = await set_preferences(
        session_id, experience_mode="autopilot", approval_policy=approval_policy,
        base_revision=workspace["revision"], actor=actor,
        idempotency_key=f"{key}:preferences",
    )
    workspace = await get_workspace(session_id)
    run_id = f"run_{uuid.uuid4().hex}"
    now = _now()
    run = {
        "_id": run_id, "run_id": run_id, "session_id": session_id,
        "workspace_id": workspace["workspace_id"],
        "workspace_revision": workspace["revision"],
        "plan_revision": 1, "status": "queued",
        "approval_policy": approval_policy, "started_by": actor,
        "idempotency_key": key, "cancel_requested": False,
        "pause_requested": False, "current_task_id": None,
        "created_at": now, "updated_at": now,
        "preference_revision": pref["workspace_revision"],
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
    await _emit(run_id, "run_created", {"approval_policy": approval_policy})
    return await get_run(run_id)


async def get_run(run_id: str) -> dict:
    runs, tasks, _ = await _collections()
    if runs is not None:
        run = await runs.find_one({"_id": run_id})
        task_docs = await tasks.find({"run_id": run_id}).sort("created_at", 1).to_list(None)
    else:
        run = _mem_runs.get(run_id)
        task_docs = [task for task in _mem_tasks.values() if task["run_id"] == run_id]
        task_docs.sort(key=lambda item: item["created_at"])
    if not run:
        raise KeyError(f"run not found: {run_id}")
    return {**_public(run), "tasks": [_public(task) for task in task_docs]}


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
        ARTIFACT_REPLAN_ROOT[artifact]
        for artifact in changed_artifacts
        if artifact in ARTIFACT_REPLAN_ROOT
    }
    affected_keys = _task_descendants(root_keys)
    affected = [task for task in run["tasks"] if task["key"] in affected_keys]
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
    affected_ids = {task["task_id"] for task in affected}
    now = _now()
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
        for task_id, updates in reset_docs:
            await tasks.update_one(
                {"_id": task_id},
                {"$set": updates, "$unset": {"completed_at": "", "started_at": ""}},
            )
    else:
        for task_id, updates in reset_docs:
            _mem_tasks[task_id].update(updates)
            _mem_tasks[task_id].pop("completed_at", None)
            _mem_tasks[task_id].pop("started_at", None)

    plan_revision = int(run.get("plan_revision", 1)) + 1
    unaffected_review = any(
        task["status"] == "waiting_review" and task["task_id"] not in affected_ids
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
            "created_at": now,
        },
    })
    await _emit(run_id, "run_replanned", {
        "plan_revision": plan_revision,
        "from_workspace_revision": previous_revision,
        "to_workspace_revision": workspace["revision"],
        "changed_artifacts": changed_artifacts,
        "affected_tasks": [task["key"] for task in affected],
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
    if approved and task.get("pending_artifact") and not retry_after_review:
        from workspace.service import commit_artifact_result
        pending = task["pending_artifact"]
        await commit_artifact_result(
            pending["session_id"], pending["artifact"], pending["value"],
            task_id=task_id,
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
