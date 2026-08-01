"""Lease-based background worker for durable Campaign Autopilot tasks."""
from __future__ import annotations

import asyncio
import os
import uuid

import httpx

from agent_logger import alog
from autopilot.capabilities import execute
from autopilot.service import (
    _needs_review,
    _set_run,
    artifact_invalidation_exclusions,
    claim_next_task,
    complete_task,
    fail_task,
    get_run,
    record_milestone,
    reconcile_active_runs,
    renew_task_lease,
    task_commit_id,
)
from config import config
from metrics import record_tool_call
from workspace.service import commit_artifact_result, get_task_context

_worker_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


def worker_running() -> bool:
    return bool(_worker_task and not _worker_task.done())


async def _start_campaign_report(run: dict, task: dict, result: dict) -> str:
    """Start the performance report immediately after the order side effect."""
    from handlers.report import handle_report_entry

    response = await handle_report_entry(
        run["session_id"],
        suppress_message=True,
    )
    update = getattr(response, "workspace_update", None) or {}
    campaign_id = str(
        (update.get("value") or {}).get("campaignId")
        or ((result or {}).get("order") or {}).get("id")
        or ((result or {}).get("order") or {}).get("_id")
        or ""
    ).strip()
    if not campaign_id:
        raise RuntimeError("report generation returned no campaign id")
    await _set_run(run["run_id"], {"report_campaign_id": campaign_id})
    await record_milestone(
        run["run_id"],
        f"report_generating:{campaign_id}",
        "🔄 **Báo cáo đang được tạo tự động** sau khi campaign launch. "
        "Bạn có thể tiếp tục theo dõi Autopilot trong lúc hệ thống xử lý.",
        metadata={
            "kind": "report_generating",
            "campaign_id": campaign_id,
        },
    )
    return campaign_id


async def _wait_for_campaign_report(
    run: dict,
    *,
    timeout_seconds: float = 180.0,
    poll_seconds: float = 3.0,
) -> dict:
    """Wait for the already-started report without blocking task lease renewal."""
    campaign_id = str(run.get("report_campaign_id") or "").strip()
    if not campaign_id:
        return {"state": "not_started"}
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_status: dict = {}
    async with httpx.AsyncClient(timeout=8.0) as client:
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(
                f"{config.BACKEND_URL.rstrip('/')}/api/reports/status/{campaign_id}",
            )
            if response.status_code == 200:
                last_status = response.json()
                total = int(last_status.get("total") or 0)
                ready = int(last_status.get("ready") or 0)
                errors = int(last_status.get("errors") or 0)
                if total and ready >= total:
                    await record_milestone(
                        run["run_id"],
                        f"report_ready:{campaign_id}",
                        "✅ **Báo cáo đã được tạo thành công.** "
                        "Mở tab **Báo cáo phân tích** trong phần Kết quả để xem ngay.",
                        metadata={
                            "kind": "report_ready",
                            "campaign_id": campaign_id,
                            "action": "open_report",
                        },
                    )
                    return {"state": "ready", **last_status}
                if total and ready + errors >= total and errors:
                    return {"state": "error", **last_status}
            await asyncio.sleep(poll_seconds)
    return {"state": "generating", **last_status}


async def _lease_heartbeat(task: dict, stop: asyncio.Event) -> None:
    interval = max(5.0, config.AUTOPILOT_TASK_LEASE_SECONDS / 3)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            try:
                renewed = await renew_task_lease(task["task_id"], task["lease_owner"])
            except Exception:
                return
            if not renewed:
                return


async def _process(task: dict) -> None:
    run = await get_run(task["run_id"])
    context = None
    heartbeat_stop = asyncio.Event()
    heartbeat = asyncio.create_task(
        _lease_heartbeat(task, heartbeat_stop),
        name=f"autopilot-lease-{task['task_id']}",
    )
    try:
        if task.get("artifact"):
            context = await get_task_context(run["session_id"], task["artifact"])
        commit_task_id = task_commit_id(task)
        try:
            output = await execute(task, run)
        except BaseException as exc:
            record_tool_call(
                tool=task.get("capability") or task.get("key") or "autopilot",
                outcome="cancelled" if isinstance(exc, asyncio.CancelledError) else "error",
            )
            raise
        record_tool_call(
            tool=task.get("capability") or task.get("key") or "autopilot",
            outcome="ok",
        )
        if task.get("key") == "create_setup_report":
            report_status = await _wait_for_campaign_report(run)
            if isinstance(output.value, dict):
                output.value["performance_report"] = report_status
            output.evidence.append({
                "type": "performance_report",
                "status": report_status.get("state"),
                "campaign_id": run.get("report_campaign_id"),
            })
        needs_review = output.force_review or _needs_review(task, run["approval_policy"])
        pending_artifact = None
        if task.get("artifact") and not output.externally_committed:
            pending_artifact = {
                "session_id": run["session_id"], "artifact": task["artifact"],
                "value": output.value,
                "input_revisions": context["input_revisions"],
                "base_artifact_revision": context["artifact_revision"],
                "commit_task_id": commit_task_id,
            }
            # A result that needs approval remains outside canonical workspace
            # until a human/policy review commits it.
            if not needs_review:
                await commit_artifact_result(
                    run["session_id"], task["artifact"], output.value,
                    task_id=commit_task_id,
                    input_revisions=context["input_revisions"],
                    base_artifact_revision=context["artifact_revision"],
                    actor="autopilot_worker",
                    reason=f"Autopilot capability {task['capability']} completed",
                    affected_exclusions=artifact_invalidation_exclusions(
                        run, task["artifact"]
                    ),
                )
                pending_artifact = None
        completed = await complete_task(
            task["task_id"], result=output.value, evidence=output.evidence,
            force_review=output.force_review,
            pending_artifact=pending_artifact,
        )
        if task.get("key") == "create_order" and not needs_review:
            try:
                await _start_campaign_report(run, task, output.value or {})
            except Exception as report_error:
                await alog(run["session_id"], "error", {
                    "handler": "autopilot_report_start",
                    "run_id": run["run_id"],
                    "task_id": task["task_id"],
                    "error": str(report_error)[:500],
                })
                await record_milestone(
                    run["run_id"],
                    f"report_start_failed:{task['task_id']}:{task.get('attempts', 1)}",
                    "⚠️ Campaign đã launch nhưng báo cáo chưa thể bắt đầu tự động. "
                    "Hãy mở tab Báo cáo để thử lại.",
                    metadata={"kind": "report_start_failed"},
                )
    except Exception as exc:
        await alog(run["session_id"], "error", {
            "handler": "autopilot_worker", "run_id": run["run_id"],
            "task_id": task["task_id"], "error": str(exc)[:500],
        })
        await fail_task(task["task_id"], str(exc), retryable=True)
    finally:
        heartbeat_stop.set()
        await heartbeat


async def _loop() -> None:
    worker_id = f"apw_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    while _stop_event and not _stop_event.is_set():
        try:
            await reconcile_active_runs()
        except Exception as exc:
            await alog("autopilot", "error", {
                "handler": "autopilot_reconcile", "error": str(exc)[:500],
            })
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
