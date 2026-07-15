from datetime import timedelta

import pytest

from autopilot import service
from autopilot.capabilities import (
    CapabilityResult, _analyze_creatives, _create_order, _generate_strategy,
    _rank_placements, _retrieve_audience,
)
from autopilot import worker
from workspace.service import (
    apply_mutation, get_task_context, get_workspace, set_preferences,
)


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
async def test_strategy_simulator_returns_three_directional_scenarios():
    workspace = {"artifacts": {"brief": {"revision": 3, "value": BRIEF}}}
    result = await _generate_strategy({"session_id": "simulator"}, workspace)
    value = result.value
    assert value["kind"] == "campaign_strategy_simulation"
    assert value["selected"] == "reach_first"
    assert [option["id"] for option in value["options"]] == [
        "balanced", "reach_first", "quality_first",
    ]
    reach = next(option for option in value["options"] if option["id"] == "reach_first")
    quality = next(option for option in value["options"] if option["id"] == "quality_first")
    assert reach["metrics"]["estimated_reach"] > quality["metrics"]["estimated_reach"]
    assert reach["metrics"]["average_cpm"] < quality["metrics"]["average_cpm"]
    assert all(option["metrics"]["is_estimate"] for option in value["options"])


@pytest.mark.asyncio
async def test_selected_strategy_is_grounded_into_audience_retrieval(monkeypatch):
    import handlers.audience as audience_handler

    captured = {}

    async def fake_recommend(session_id, brief_override=None):
        captured.update({"session_id": session_id, "brief": brief_override})
        return {
            "recommendations": [{"_id": "seg-1", "sizeMin": 100, "sizeMax": 300}],
            "total_segments": 20,
            "rag": {"candidates": 20, "rerank_enabled": True, "reranked": True},
        }

    monkeypatch.setattr(audience_handler, "handle_dmp_recommend", fake_recommend)
    workspace = {"artifacts": {
        "brief": {"value": {**BRIEF, "notes": "Người yêu công nghệ"}},
        "strategy": {"value": {"selected": "quality_first"}},
    }}
    result = await _retrieve_audience({"session_id": "strategy-audience"}, workspace)
    assert "inventory chất lượng" in captured["brief"]["notes"]
    assert result.value["attrs"][0]["_id"] == "seg-1"
    pipeline = next(item for item in result.evidence if item["type"] == "audience_pipeline")
    assert pipeline["strategy_id"] == "quality_first"
    assert pipeline["reranked"] is True


@pytest.mark.asyncio
async def test_operator_can_select_pending_strategy_before_review():
    await _seed("strategy-review")
    run = await service.create_run(
        "strategy-review", approval_policy="review_every_stage",
        idempotency_key="strategy-review",
    )
    workspace = await get_workspace("strategy-review")
    simulated = await _generate_strategy(run, workspace)
    context = await get_task_context("strategy-review", "strategy")
    task_id = f"{run['run_id']}:generate_strategy"
    service._mem_tasks[task_id].update(
        status="waiting_review",
        result=simulated.value,
        evidence=simulated.evidence,
        pending_artifact={
            "session_id": "strategy-review", "artifact": "strategy",
            "value": simulated.value,
            "input_revisions": context["input_revisions"],
            "base_artifact_revision": context["artifact_revision"],
        },
    )

    selected = await service.select_strategy(
        run["run_id"], "quality_first", reason="Ưu tiên inventory chất lượng"
    )
    selected_task = next(task for task in selected["tasks"] if task["key"] == "generate_strategy")
    assert selected_task["result"]["selected"] == "quality_first"
    assert selected_task["pending_artifact"]["value"]["selection"]["source"] == "operator"
    assert (await get_workspace("strategy-review"))["artifacts"]["strategy"]["status"] == "missing"

    await service.review_task(run["run_id"], task_id, approved=True, reason="selected")
    committed = await get_workspace("strategy-review")
    assert committed["artifacts"]["strategy"]["value"]["selected"] == "quality_first"


@pytest.mark.asyncio
async def test_changing_committed_strategy_replans_only_consumers():
    await _seed("strategy-replan")
    run = await service.create_run(
        "strategy-replan", approval_policy="auto_build_draft",
        idempotency_key="strategy-replan",
    )
    workspace = await get_workspace("strategy-replan")
    simulated = await _generate_strategy(run, workspace)
    await apply_mutation(
        "strategy-replan", "strategy", simulated.value,
        base_revision=workspace["revision"], actor="autopilot_worker",
        idempotency_key="initial-strategy",
    )
    _mark_tasks(run["run_id"], {
        "normalize_brief": "succeeded", "validate_brief": "succeeded",
        "generate_strategy": "succeeded", "retrieve_audience": "succeeded",
        "derive_targeting": "succeeded", "analyze_creatives": "succeeded",
        "rank_placements": "succeeded", "assign_creatives": "succeeded",
        "forecast": "queued",
    })
    service._mem_tasks[f"{run['run_id']}:generate_strategy"]["result"] = simulated.value

    replanned = await service.select_strategy(run["run_id"], "quality_first")
    by_key = {task["key"]: task for task in replanned["tasks"]}
    assert by_key["generate_strategy"]["status"] == "succeeded"
    assert by_key["generate_strategy"]["result"]["selected"] == "quality_first"
    assert by_key["retrieve_audience"]["status"] == "queued"
    assert by_key["analyze_creatives"]["status"] == "queued"
    assert by_key["rank_placements"]["status"] == "queued"
    assert by_key["derive_targeting"]["status"] == "pending"
    assert replanned["last_replan"]["changed_artifacts"] == ["strategy"]


@pytest.mark.asyncio
async def test_strategy_change_is_blocked_after_order_creation():
    await _seed("strategy-after-order")
    run = await service.create_run("strategy-after-order", idempotency_key="after-order")
    service._mem_tasks[f"{run['run_id']}:create_order"]["status"] = "succeeded"
    with pytest.raises(service.RunConflict, match="after order creation"):
        await service.select_strategy(run["run_id"], "balanced")


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


def _mark_tasks(run_id: str, statuses: dict[str, str]) -> None:
    for task in service._mem_tasks.values():
        if task["run_id"] == run_id and task["key"] in statuses:
            task.update(
                status=statuses[task["key"]], result={"old": task["key"]},
                evidence=[{"old": True}], attempts=1,
            )


@pytest.mark.asyncio
async def test_brief_edit_replans_entire_active_run_from_validation_boundary():
    await _seed("replan-brief")
    run = await service.create_run(
        "replan-brief", approval_policy="auto_build_draft", idempotency_key="replan"
    )
    _mark_tasks(run["run_id"], {
        "normalize_brief": "succeeded", "validate_brief": "succeeded",
        "generate_strategy": "succeeded", "retrieve_audience": "succeeded",
        "derive_targeting": "queued",
    })
    workspace = await get_workspace("replan-brief")
    changed = {**BRIEF, "budget": 55}
    await apply_mutation(
        "replan-brief", "brief", changed, base_revision=workspace["revision"],
        actor="campaign_operator", idempotency_key="edit-budget",
    )

    result = await service.reconcile_workspace_changes(run["run_id"])
    replanned = result["run"]
    by_key = {task["key"]: task for task in replanned["tasks"]}
    assert result["changed"] is True
    assert replanned["plan_revision"] == 2
    assert replanned["last_replan"]["changed_artifacts"] == ["brief"]
    assert by_key["normalize_brief"]["status"] == "queued"
    assert by_key["validate_brief"]["status"] == "pending"
    assert by_key["generate_strategy"]["status"] == "pending"
    assert by_key["retrieve_audience"]["result"] is None


@pytest.mark.asyncio
async def test_creative_edit_replans_only_creative_dependent_branch():
    await _seed("replan-creative")
    run = await service.create_run(
        "replan-creative", approval_policy="auto_build_draft",
        idempotency_key="replan-creative",
    )
    _mark_tasks(run["run_id"], {
        "normalize_brief": "succeeded", "validate_brief": "succeeded",
        "generate_strategy": "succeeded", "retrieve_audience": "succeeded",
        "derive_targeting": "succeeded", "analyze_creatives": "succeeded",
        "rank_placements": "succeeded", "assign_creatives": "succeeded",
        "forecast": "queued",
    })
    workspace = await get_workspace("replan-creative")
    await apply_mutation(
        "replan-creative", "creative", {"files": [{"url": "https://x/new.png"}]},
        base_revision=workspace["revision"], actor="campaign_operator",
        idempotency_key="new-creative",
    )

    result = await service.reconcile_workspace_changes(run["run_id"])
    by_key = {task["key"]: task for task in result["run"]["tasks"]}
    assert result["changed"] is True
    assert by_key["generate_strategy"]["status"] == "succeeded"
    assert by_key["retrieve_audience"]["status"] == "succeeded"
    assert by_key["derive_targeting"]["status"] == "succeeded"
    assert by_key["rank_placements"]["status"] == "queued"
    assert by_key["analyze_creatives"]["status"] == "queued"
    assert by_key["assign_creatives"]["status"] == "pending"
    assert by_key["forecast"]["status"] == "pending"


@pytest.mark.asyncio
async def test_workspace_edit_supersedes_stale_launch_review():
    await _seed("replan-launch")
    run = await service.create_run("replan-launch", idempotency_key="launch")
    statuses = {spec["key"]: "succeeded" for spec in service.STANDARD_PLAN}
    statuses.update({
        "launch_approval": "waiting_review", "create_order": "pending",
        "verify_order": "pending", "create_setup_report": "pending",
    })
    _mark_tasks(run["run_id"], statuses)
    workspace = await get_workspace("replan-launch")
    await apply_mutation(
        "replan-launch", "brief", {**BRIEF, "budget": 60},
        base_revision=workspace["revision"], actor="campaign_operator",
        idempotency_key="launch-edit",
    )

    launch_id = f"{run['run_id']}:launch_approval"
    with pytest.raises(service.RunConflict, match="no longer waiting"):
        await service.review_task(run["run_id"], launch_id, approved=True)
    latest = await service.get_run(run["run_id"])
    by_key = {task["key"]: task for task in latest["tasks"]}
    assert by_key["launch_approval"]["status"] == "pending"
    assert by_key["create_order"]["status"] == "pending"


@pytest.mark.asyncio
async def test_edit_after_order_creation_blocks_replay_of_side_effect():
    await _seed("replan-created")
    run = await service.create_run("replan-created", idempotency_key="created")
    statuses = {spec["key"]: "succeeded" for spec in service.STANDARD_PLAN}
    statuses.update({"verify_order": "queued", "create_setup_report": "pending"})
    _mark_tasks(run["run_id"], statuses)
    workspace = await get_workspace("replan-created")
    await apply_mutation(
        "replan-created", "brief", {**BRIEF, "budget": 70},
        base_revision=workspace["revision"], actor="campaign_operator",
        idempotency_key="post-create-edit",
    )

    result = await service.reconcile_workspace_changes(run["run_id"])
    assert result["reason"] == "side_effect_boundary"
    assert result["run"]["status"] == "paused"
    assert result["run"]["replan_blocked"]["reason"] == "order_already_created"
    created = next(task for task in result["run"]["tasks"] if task["key"] == "create_order")
    assert created["status"] == "succeeded"
    with pytest.raises(service.RunConflict, match="side-effect boundary"):
        await service.resume_run(run["run_id"])


@pytest.mark.asyncio
async def test_order_capability_rejects_stale_draft_before_external_call():
    run = {
        "tasks": [{
            "key": "launch_approval", "status": "succeeded",
            "result": {"order_draft_revision": 7},
        }],
    }
    workspace = {
        "artifacts": {
            "order_draft": {
                "status": "stale", "revision": 7,
                "value": {"payload": {"idempotencyKey": "never-called"}},
            },
        },
    }
    with pytest.raises(RuntimeError, match="stale or missing"):
        await _create_order(run, workspace)


@pytest.mark.asyncio
async def test_order_capability_rejects_approval_for_older_draft():
    run = {
        "tasks": [{
            "key": "launch_approval", "status": "succeeded",
            "result": {"order_draft_revision": 6},
        }],
    }
    workspace = {
        "artifacts": {
            "order_draft": {
                "status": "approved", "revision": 7,
                "value": {"payload": {"idempotencyKey": "never-called"}},
            },
        },
    }
    with pytest.raises(RuntimeError, match="does not match"):
        await _create_order(run, workspace)


@pytest.mark.asyncio
async def test_retry_review_is_idempotent_when_input_edit_already_replanned_task():
    await _seed("replan-review-race")
    run = await service.create_run("replan-review-race", idempotency_key="review-race")
    task_id = f"{run['run_id']}:analyze_creatives"
    service._mem_tasks[task_id].update(
        status="queued", replanned_from_status="waiting_review",
    )
    current = await service.review_task(run["run_id"], task_id, approved=True)
    task = next(item for item in current["tasks"] if item["task_id"] == task_id)
    assert task["status"] == "queued"


@pytest.mark.asyncio
async def test_stale_creative_verdict_is_recommitted_against_current_strategy(monkeypatch):
    import autopilot.capabilities as capabilities
    import creative_intel.service as creative_service

    docs = [{
        "analysis_id": "ci-1", "url": "http://localhost:3000/uploads/a.png",
        "effective_status": "auto_approved", "status": "auto_approved",
    }]
    workspace = {
        "artifacts": {
            "creative": {"value": {"files": [{"url": docs[0]["url"]}]}},
            "creative_verdict": {
                "status": "stale", "revision": 3,
                "value": {"batch_id": "batch-1", "files": [{"old": True}]},
            },
        },
    }

    async def fake_intel(_session_id):
        return docs

    async def fake_workspace(_session_id):
        return workspace

    monkeypatch.setattr(creative_service, "get_intel", fake_intel)
    monkeypatch.setattr(capabilities, "get_workspace", fake_workspace)
    result = await _analyze_creatives({"session_id": "stale-verdict"}, workspace)
    assert result.externally_committed is False
    assert result.value == {"batch_id": "batch-1", "files": docs}
    assert result.evidence[0]["revalidated"] is True


@pytest.mark.asyncio
async def test_placement_ranking_keeps_only_creative_compatible_zones(monkeypatch):
    import creative_intel.service as creative_service
    import tools.order_api as order_api
    import tools.zone_ranker as zone_ranker

    ranked = [
        {"id": "GOOD", "match_mode": "exact_size"},
        {"id": "BAD", "match_mode": "nearest_ratio"},
    ]

    async def fake_intel(_session_id):
        return []

    async def fake_rank(**_kwargs):
        return ranked

    async def no_conflicts(_start, _end):
        return {}

    monkeypatch.setattr(creative_service, "get_intel", fake_intel)
    monkeypatch.setattr(zone_ranker, "rank_zones", fake_rank)
    monkeypatch.setattr(order_api, "fetch_zone_conflicts", no_conflicts)
    workspace = {"artifacts": {
        "brief": {"value": BRIEF},
        "creative": {"value": {"files": [{"name": "good.png"}]}},
    }}
    result = await _rank_placements({"session_id": "compatible"}, workspace)
    assert result.force_review is False
    assert result.value["selectedZoneIds"] == ["GOOD"]


@pytest.mark.asyncio
async def test_no_compatible_placement_requests_new_creative(monkeypatch):
    import creative_intel.service as creative_service
    import tools.order_api as order_api
    import tools.zone_ranker as zone_ranker

    async def fake_intel(_session_id):
        return []

    async def fake_rank(**_kwargs):
        return [{"id": "BAD", "match_mode": "same_ratio"}]

    async def no_conflicts(_start, _end):
        return {}

    monkeypatch.setattr(creative_service, "get_intel", fake_intel)
    monkeypatch.setattr(zone_ranker, "rank_zones", fake_rank)
    monkeypatch.setattr(order_api, "fetch_zone_conflicts", no_conflicts)
    workspace = {"artifacts": {
        "brief": {"value": BRIEF},
        "creative": {"value": {"files": [{"name": "bad.png"}]}},
    }}
    result = await _rank_placements({"session_id": "incompatible"}, workspace)
    assert result.force_review is True
    assert result.value["reason"] == "no_compatible_placements"
    assert result.value["review_action"] == "retry"
