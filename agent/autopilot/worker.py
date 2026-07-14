"""Lease-based background worker for durable Campaign Autopilot tasks."""
from __future__ import annotations

import asyncio
import os
import uuid

from agent_logger import alog
from autopilot.capabilities import execute
from autopilot.service import (
    _needs_review,
    claim_next_task,
    complete_task,
    fail_task,
    get_run,
)
from config import config
from workspace.service import commit_artifact_result, get_task_context

_worker_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


def worker_running() -> bool:
    return bool(_worker_task and not _worker_task.done())


async def _process(task: dict) -> None:
    run = await get_run(task["run_id"])
    context = None
    if task.get("artifact"):
        context = await get_task_context(run["session_id"], task["artifact"])
    try:
        output = await execute(task, run)
        needs_review = output.force_review or _needs_review(task, run["approval_policy"])
        pending_artifact = None
        if task.get("artifact") and not output.externally_committed:
            pending_artifact = {
                "session_id": run["session_id"], "artifact": task["artifact"],
                "value": output.value,
                "input_revisions": context["input_revisions"],
                "base_artifact_revision": context["artifact_revision"],
            }
            # A result that needs approval remains outside canonical workspace
            # until a human/policy review commits it.
            if not needs_review:
                await commit_artifact_result(
                    run["session_id"], task["artifact"], output.value,
                    task_id=task["task_id"],
                    input_revisions=context["input_revisions"],
                    base_artifact_revision=context["artifact_revision"],
                    actor="autopilot_worker",
                    reason=f"Autopilot capability {task['capability']} completed",
                )
                pending_artifact = None
        await complete_task(
            task["task_id"], result=output.value, evidence=output.evidence,
            force_review=output.force_review,
            pending_artifact=pending_artifact,
        )
    except Exception as exc:
        await alog(run["session_id"], "error", {
            "handler": "autopilot_worker", "run_id": run["run_id"],
            "task_id": task["task_id"], "error": str(exc)[:500],
        })
        await fail_task(task["task_id"], str(exc), retryable=True)


async def _loop() -> None:
    worker_id = f"apw_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    while _stop_event and not _stop_event.is_set():
        task = await claim_next_task(worker_id)
        if task is None:
            try:
                await asyncio.wait_for(
                    _stop_event.wait(), timeout=config.AUTOPILOT_WORKER_POLL_SECONDS
                )
            except asyncio.TimeoutError:
                pass
            continue
        await _process(task)


async def start_worker() -> None:
    global _worker_task, _stop_event
    if worker_running():
        return
    _stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(_loop(), name="campaign-autopilot-worker")


async def stop_worker() -> None:
    global _worker_task, _stop_event
    if _stop_event:
        _stop_event.set()
    if _worker_task:
        try:
            await asyncio.wait_for(_worker_task, timeout=5)
        except asyncio.TimeoutError:
            _worker_task.cancel()
    _worker_task = None
    _stop_event = None
