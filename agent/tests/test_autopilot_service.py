from datetime import timedelta

import pytest

from autopilot import service
from autopilot.capabilities import CapabilityResult
from autopilot import worker
from workspace.service import apply_mutation, get_workspace, set_preferences


BRIEF = {
    "brand": "ZaloPay",
    "objective": "awareness",
    "budget": 40,
    "startDate": "2026-08-01",
    "endDate": "2026-08-15",
}


async def _seed(session_id: str = "auto-test"):
    workspace = await get_workspace(session_id)
    await apply_mutation(
        session_id, "brief", BRIEF, base_revision=workspace["revision"],
        actor="test", idempotency_key=f"{session_id}:brief",
    )


@pytest.mark.asyncio
async def test_preferences_are_revisioned_without_invalidating_artifacts():
    await _seed("prefs")
    before = await get_workspace("prefs")
    result = await set_preferences(
        "prefs", experience_mode="autopilot", approval_policy="critical_only",
        base_revision=before["revision"], actor="test", idempotency_key="pref-1",
    )
    after = await get_workspace("prefs")
    assert result["workspace_revision"] == before["revision"] + 1
    assert after["experience_mode"] == "autopilot"
    assert after["approval_policy"] == "critical_only"
    assert after["artifacts"]["brief"]["status"] == "approved"


@pytest.mark.asyncio
async def test_run_start_is_idempotent_and_has_fixed_plan():
    await _seed("start")
    first = await service.create_run(
        "start", approval_policy="critical_only", idempotency_key="same-start"
    )
    second = await service.create_run(
        "start", approval_policy="critical_only", idempotency_key="same-start"
    )
    assert first["run_id"] == second["run_id"]
    assert [task["key"] for task in first["tasks"]] == [
        spec["key"] for spec in service.STANDARD_PLAN
    ]
    assert first["tasks"][0]["status"] == "queued"
    assert all(task["status"] == "pending" for task in first["tasks"][1:])


@pytest.mark.asyncio
async def test_run_requires_brief():
    with pytest.raises(ValueError, match="brief is required"):
        await service.create_run("missing-brief")


@pytest.mark.asyncio
async def test_pause_resume_and_cancel_preserve_completed_work():
    await _seed("lifecycle")
    run = await service.create_run("lifecycle", idempotency_key="life")
    paused = await service.pause_run(run["run_id"])
    assert paused["status"] == "paused"
    resumed = await service.resume_run(run["run_id"])
    assert resumed["status"] == "queued"
    cancelled = await service.cancel_run(run["run_id"])
    assert cancelled["status"] == "cancelled"
    assert all(task["status"] == "cancelled" for task in cancelled["tasks"])


@pytest.mark.asyncio
async def test_review_policy_interrupts_and_resume_queues_dependency():
    await _seed("review")
    run = await service.create_run(
        "review", approval_policy="review_every_stage", idempotency_key="review"
    )
    first = await service.claim_next_task("worker")
    assert first["key"] == "normalize_brief"
    run = await service.complete_task(first["task_id"], result={"ok": True})
    assert next(t for t in run["tasks"] if t["key"] == "validate_brief")["status"] == "queued"

    second = await service.claim_next_task("worker")
    run = await service.complete_task(second["task_id"], result={"valid": True})
    assert run["status"] == "waiting_review"
    reviewed = await service.review_task(
        run["run_id"], second["task_id"], approved=True, reason="valid brief"
    )
    assert reviewed["status"] == "queued"
    assert next(t for t in reviewed["tasks"] if t["key"] == "generate_strategy")["status"] == "queued"


@pytest.mark.asyncio
async def test_auto_build_still_requires_launch_review():
    assert service._needs_review({"review": "launch"}, "auto_build_draft")
    assert not service._needs_review({"review": "stage"}, "auto_build_draft")


@pytest.mark.asyncio
async def test_expired_worker_lease_is_recovered():
    await _seed("lease")
    run = await service.create_run("lease", idempotency_key="lease")
    task = await service.claim_next_task("dead-worker", lease_seconds=10)
    service._mem_tasks[task["task_id"]]["lease_expires_at"] = (
        service._now() - timedelta(seconds=1)
    )
    assert await service.recover_expired_leases() == 1
    recovered = await service.get_run(run["run_id"])
    assert recovered["tasks"][0]["status"] == "queued"
    assert recovered["tasks"][0]["lease_owner"] is None


@pytest.mark.asyncio
async def test_worker_commits_auto_approved_artifact(monkeypatch):
    await _seed("worker-auto")
    run = await service.create_run(
        "worker-auto", approval_policy="critical_only", idempotency_key="worker-auto"
    )

    async def fake_execute(task, _run):
        if task["key"] == "generate_strategy":
            return CapabilityResult(value={"selected": "balanced"})
        return CapabilityResult(value={"ok": True})

    monkeypatch.setattr(worker, "execute", fake_execute)
    first = await service.claim_next_task("worker")
    await worker._process(first)
    second = await service.claim_next_task("worker")
    await worker._process(second)
    strategy = await service.claim_next_task("worker")
    await worker._process(strategy)

    workspace = await get_workspace("worker-auto")
    assert workspace["artifacts"]["strategy"]["status"] == "approved"
    assert workspace["artifacts"]["strategy"]["value"] == {"selected": "balanced"}


@pytest.mark.asyncio
async def test_reviewed_artifact_is_not_committed_before_approval(monkeypatch):
    await _seed("worker-review")
    run = await service.create_run(
        "worker-review", approval_policy="review_every_stage",
        idempotency_key="worker-review",
    )

    async def fake_execute(task, _run):
        if task["key"] == "generate_strategy":
            return CapabilityResult(value={"selected": "quality_first"})
        return CapabilityResult(value={"ok": True})

    monkeypatch.setattr(worker, "execute", fake_execute)
    first = await service.claim_next_task("worker")
    await worker._process(first)
    validate = await service.claim_next_task("worker")
    await worker._process(validate)
    await service.review_task(run["run_id"], validate["task_id"], approved=True)
    strategy = await service.claim_next_task("worker")
    await worker._process(strategy)

    before = await get_workspace("worker-review")
    assert before["artifacts"]["strategy"]["status"] == "missing"
    reviewed = await service.review_task(
        run["run_id"], strategy["task_id"], approved=True, reason="chosen"
    )
    after = await get_workspace("worker-review")
    assert reviewed["status"] == "queued"
    assert after["artifacts"]["strategy"]["status"] == "approved"
    assert after["artifacts"]["strategy"]["value"] == {"selected": "quality_first"}
