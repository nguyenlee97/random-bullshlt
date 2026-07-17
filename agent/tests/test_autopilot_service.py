from datetime import timedelta

import pytest

from autopilot import service
from autopilot.capabilities import (
    CapabilityResult, _analyze_creatives, _assign_creatives, _build_creatives, _build_order_draft,
    _create_order, _create_setup_report, _forecast, _generate_strategy,
    _plan_placement_intent, _prepare_creatives, _rank_placements, _retrieve_audience,
)
from autopilot import worker
from workspace.service import (
    apply_mutation, create_proposal, get_task_context, get_workspace, set_preferences,
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
async def test_preferences_are_revisioned_without_invalidating_artifacts(monkeypatch):
    await _seed("prefs")
    before = await get_workspace("prefs")
    result = await set_preferences(
        "prefs", experience_mode="autopilot", approval_policy="critical_only",
        creative_source="ai_generate",
        base_revision=before["revision"], actor="test", idempotency_key="pref-1",
    )
    after = await get_workspace("prefs")
    assert result["workspace_revision"] == before["revision"] + 1
    assert after["experience_mode"] == "autopilot"
    assert after["approval_policy"] == "critical_only"
    assert after["creative_source"] == "ai_generate"
    assert after["artifacts"]["brief"]["status"] == "approved"
    async def homepage_mode(_session_id):
        return "autopilot"

    monkeypatch.setattr(
        "identity.get_conversation_mode_for_session", homepage_mode
    )
    with pytest.raises(ValueError, match="fixed for this campaign"):
        await set_preferences("prefs", experience_mode="guided")


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
    assert first["trace_id"] == second["trace_id"]
    assert first["creative_source"] == "upload"
    assert [task["plan_index"] for task in first["tasks"]] == list(
        range(len(service.STANDARD_PLAN))
    )


@pytest.mark.asyncio
async def test_get_run_keeps_plan_order_for_legacy_equal_timestamp_tasks():
    await _seed("legacy-task-order")
    run = await service.create_run(
        "legacy-task-order", idempotency_key="legacy-task-order"
    )
    run_id = run["run_id"]
    task_docs = [
        task for task in service._mem_tasks.values() if task["run_id"] == run_id
    ]
    for task in task_docs:
        task.pop("plan_index", None)
    service._mem_tasks = {
        task["task_id"]: task for task in reversed(task_docs)
    }

    ordered = await service.get_run(run_id)

    assert [task["key"] for task in ordered["tasks"]] == [
        spec["key"] for spec in service.STANDARD_PLAN
    ]


def test_order_creatives_preserve_skin_and_banner_formats():
    files = [
        {
            "name": "background.png", "url": "https://example.test/skin.png",
            "width": 1504, "height": 704, "intendedFormat": "skin",
        },
        {
            "name": "box.png", "url": "https://example.test/box.png",
            "width": 300, "height": 250, "intendedFormat": "banner",
        },
    ]

    creatives = _build_creatives(
        files, {"SKIN_ZONE": 0, "BOX_ZONE": 1}, ["SKIN_ZONE", "BOX_ZONE"]
    )

    assert creatives[0]["format"] == "skin"
    assert creatives[0]["size"] == "skin"
    assert creatives[1]["format"] == "banner"
    assert creatives[1]["size"] == "300x250"


@pytest.mark.asyncio
async def test_run_persists_explicit_ai_creative_source():
    await _seed("start-ai-creative")
    run = await service.create_run(
        "start-ai-creative", creative_source="ai_generate",
        idempotency_key="start-ai-creative",
    )
    workspace = await get_workspace("start-ai-creative")
    assert run["creative_source"] == "ai_generate"
    assert workspace["creative_source"] == "ai_generate"


@pytest.mark.asyncio
async def test_run_rejects_unknown_creative_source():
    await _seed("start-invalid-creative")
    with pytest.raises(ValueError, match="creative_source"):
        await service.create_run(
            "start-invalid-creative", creative_source="surprise-me",
            idempotency_key="start-invalid-creative",
        )


@pytest.mark.asyncio
async def test_run_cannot_start_while_workspace_proposal_is_pending():
    session_id = "pending-start"
    workspace = await get_workspace(session_id)
    await create_proposal(
        session_id,
        "brief",
        BRIEF,
        base_revision=workspace["revision"],
        actor="test",
        reason="await explicit approval",
    )

    with pytest.raises(service.RunConflict, match="duyệt hoặc hủy"):
        await service.create_run(session_id, idempotency_key="must-not-start")

    unchanged = await get_workspace(session_id)
    assert unchanged["revision"] == workspace["revision"]
    assert unchanged["artifacts"]["brief"]["value"] is None


@pytest.mark.asyncio
async def test_validate_brief_retry_requires_an_actual_canonical_fix():
    session_id = "invalid-retry"
    workspace = await get_workspace(session_id)
    invalid_brief = {**BRIEF, "endDate": "2025-08-15"}
    await apply_mutation(
        session_id, "brief", invalid_brief, base_revision=workspace["revision"],
        actor="test", idempotency_key="invalid-retry:brief",
    )
    run = await service.create_run(session_id, idempotency_key="invalid-retry:run")
    task_id = next(
        task["task_id"] for task in run["tasks"] if task["key"] == "validate_brief"
    )
    service._mem_tasks[task_id].update(
        status="waiting_review",
        result={"valid": False, "errors": ["past"], "review_action": "retry"},
    )

    with pytest.raises(service.RunConflict, match="Brief vẫn chưa hợp lệ"):
        await service.review_task(run["run_id"], task_id, approved=True)

    unchanged = await service.get_run(run["run_id"])
    assert next(task for task in unchanged["tasks"] if task["task_id"] == task_id)["status"] == "waiting_review"


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
    assert run["status"] == "queued"
    assert next(t for t in run["tasks"] if t["key"] == "generate_strategy")["status"] == "queued"


def test_valid_brief_is_not_a_redundant_strict_review_checkpoint():
    validate_spec = next(item for item in service.STANDARD_PLAN if item["key"] == "validate_brief")
    assert not service._needs_review(validate_spec, "review_every_stage")


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
    assert value["calculation"]["version"] == "brief_scenario_v2"
    assert value["calculation"]["inputs"]["duration_days"] > 0


@pytest.mark.asyncio
async def test_strategy_and_forecast_expose_campaign_specific_provenance():
    workspace = {"artifacts": {
        "brief": {"value": {**BRIEF, "budget": 9}},
        "placements": {"value": {"zones": [
            {"id": "z1", "name": "Premium", "cpm": 80_000, "reach": 200_000},
            {"id": "z2", "name": "Reach", "cpm": 40_000, "reach": 800_000},
        ]}},
    }}
    strategy = await _generate_strategy({"session_id": "provenance"}, workspace)
    workspace["artifacts"]["strategy"] = {"value": strategy.value}
    forecast = await _forecast({"session_id": "provenance"}, workspace)

    assert forecast.value["calculation"]["version"] == "catalog_forecast_v2"
    assert forecast.value["average_cpm"] == 48_000
    assert forecast.value["inventory_reach_cap"] == 1_000_000
    assert forecast.value["estimated_reach"] > 0


@pytest.mark.asyncio
async def test_autopilot_launch_is_active_and_enables_synthetic_showcase(monkeypatch):
    import creative_intel.service as intel_service

    async def no_intel(session_id):
        return []

    monkeypatch.setattr(intel_service, "get_intel", no_intel)
    workspace = {"artifacts": {
        "brief": {"value": BRIEF},
        "audience": {"value": {"attrs": []}},
        "targeting": {"value": {}},
        "creative": {"value": {"files": []}},
        "placements": {"value": {"selectedZoneIds": ["z1"]}},
        "assignments": {"value": {"assignments": {}}},
    }}
    draft = await _build_order_draft({"session_id": "active-order", "run_id": "run-active"}, workspace)
    assert draft.value["payload"]["status"] == "active"

    report = await _create_setup_report({}, {"artifacts": {
        "order": {"value": {"order": {"id": "ORD-1", "status": "active"}}},
        "forecast": {"value": {"estimated_reach": 1000}},
    }})
    assert report.value["performance_data_available"] is True
    assert report.value["performance_data_mode"] == "synthetic_showcase"


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
async def test_reach_first_placement_intent_prioritizes_reach(monkeypatch):
    async def fake_rank_zones(**_kwargs):
        return [
            {"id": "cheap-small", "reach": 100_000, "cpm": 10_000, "score": 90},
            {"id": "premium-large", "reach": 800_000, "cpm": 70_000, "score": 80},
            {"id": "mid", "reach": 400_000, "cpm": 35_000, "score": 85},
        ]

    async def fake_conflicts(_start, _end):
        return {}

    monkeypatch.setattr("tools.zone_ranker.rank_zones", fake_rank_zones)
    monkeypatch.setattr("tools.order_api.fetch_zone_conflicts", fake_conflicts)
    workspace = {"artifacts": {
        "brief": {"value": BRIEF},
        "strategy": {"value": {"selected": "reach_first"}},
    }}
    result = await _plan_placement_intent({"session_id": "reach-first"}, workspace)
    assert result.value["candidate_zone_ids"] == ["premium-large", "mid", "cheap-small"]


@pytest.mark.asyncio
async def test_operator_can_edit_pending_placement_shortlist_before_review():
    await _seed("placement-review")
    run = await service.create_run(
        "placement-review", approval_policy="review_every_stage",
        idempotency_key="placement-review",
    )
    context = await get_task_context("placement-review", "placement_intent")
    task_id = f"{run['run_id']}:plan_placement_intent"
    value = {
        "kind": "placement_intent",
        "candidate_zone_ids": ["zone-a", "zone-b", "zone-c"],
        "candidates": [
            {"id": "zone-a", "reach": 500_000, "cpm": 60_000},
            {"id": "zone-b", "reach": 300_000, "cpm": 35_000},
            {"id": "zone-c", "reach": 200_000, "cpm": 25_000},
        ],
    }
    service._mem_tasks[task_id].update(
        status="waiting_review",
        result=value,
        pending_artifact={
            "session_id": "placement-review", "artifact": "placement_intent",
            "value": value,
            "input_revisions": context["input_revisions"],
            "base_artifact_revision": context["artifact_revision"],
        },
    )

    selected = await service.select_placement_intent(
        run["run_id"], ["zone-b", "zone-a"], reason="Prefer these slots"
    )
    selected_task = next(
        task for task in selected["tasks"] if task["key"] == "plan_placement_intent"
    )
    assert selected_task["pending_artifact"]["value"]["candidate_zone_ids"] == [
        "zone-b", "zone-a",
    ]
    assert selected_task["pending_artifact"]["value"]["selection"]["source"] == "operator"
    with pytest.raises(ValueError, match="not in the reviewed shortlist"):
        await service.select_placement_intent(run["run_id"], ["unknown-zone"])

    await service.review_task(run["run_id"], task_id, approved=True)
    committed = await get_workspace("placement-review")
    assert committed["artifacts"]["placement_intent"]["value"]["candidate_zone_ids"] == [
        "zone-b", "zone-a",
    ]


@pytest.mark.asyncio
async def test_strategy_is_locked_after_its_review_stage_passes():
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
        "derive_targeting": "succeeded", "plan_placement_intent": "succeeded",
        "plan_creative_formats": "succeeded", "prepare_creatives": "succeeded",
        "analyze_creatives": "succeeded",
        "rank_placements": "succeeded", "assign_creatives": "succeeded",
        "forecast": "queued",
    })
    service._mem_tasks[f"{run['run_id']}:generate_strategy"]["result"] = simulated.value

    with pytest.raises(service.RunConflict, match="own review stage"):
        await service.select_strategy(run["run_id"], "quality_first")


@pytest.mark.asyncio
async def test_operator_creative_assignments_override_failed_auto_match(monkeypatch):
    async def fake_intel(_session_id):
        return {}

    async def fake_zone_map():
        return {
            "BaoMoi_Background": {
                "id": "BaoMoi_Background", "name": "Bao Moi Background",
                "size": "1504x704", "format": "image",
            },
        }

    monkeypatch.setattr("creative_intel.service.get_intel", fake_intel)
    monkeypatch.setattr("tools.zone_catalog.get_zone_map", fake_zone_map)
    monkeypatch.setattr(
        "tools.creative_match.enrich_files_with_intel",
        lambda files, _intel: [
            {**file, "intel": {"effective_status": "approved_override"}}
            for file in files
        ],
    )
    workspace = {"artifacts": {
        "creative": {"value": {"files": [{
            "id": "creative-1", "name": "background.png",
        }]}},
        "placements": {"value": {
            "selectedZoneIds": ["BaoMoi_Background"],
            "zones": [{"id": "BaoMoi_Background"}],
        }},
        "assignments": {
            "status": "approved", "updated_by": "campaign_operator",
            "value": {
                "assignments": {"BaoMoi_Background": 0},
                "selection": {"source": "operator"},
            },
        },
    }}

    result = await _assign_creatives({"session_id": "manual-assign"}, workspace)

    assert result.force_review is False
    assert result.value["manual_override"] is True
    assert result.value["assignments"] == {"BaoMoi_Background": 0}
    assert result.evidence == [{
        "type": "manual_creative_assignment", "count": 1, "passed": True,
    }]


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
async def test_running_worker_can_renew_its_lease():
    await _seed("lease-renew")
    run = await service.create_run("lease-renew", idempotency_key="lease-renew")
    task = await service.claim_next_task("live-worker", lease_seconds=10)
    previous_expiry = task["lease_expires_at"]
    assert await service.renew_task_lease(task["task_id"], "live-worker", 30)
    renewed = await service.get_run(run["run_id"])
    renewed_task = next(item for item in renewed["tasks"] if item["task_id"] == task["task_id"])
    assert renewed_task["lease_expires_at"] > previous_expiry
    assert not await service.renew_task_lease(task["task_id"], "wrong-worker", 30)


@pytest.mark.asyncio
async def test_upload_creative_source_waits_for_a_file():
    workspace = {"artifacts": {"creative": {"value": {"files": []}}}}
    result = await _prepare_creatives(
        {"run_id": "run-upload", "creative_source": "upload"}, workspace
    )
    assert result.force_review is True
    assert result.value["reason"] == "missing_creative"
    assert result.value["review_action"] == "retry"


@pytest.mark.asyncio
async def test_upload_creative_source_reuses_canonical_files():
    creative = {"files": [{"url": "https://cdn.example/creative.png"}]}
    workspace = {"artifacts": {"creative": {"value": creative}}}
    result = await _prepare_creatives(
        {"run_id": "run-upload", "creative_source": "upload"}, workspace
    )
    assert result.value == creative
    assert result.externally_committed is True
    assert result.force_review is False


@pytest.mark.asyncio
async def test_upload_creative_source_pauses_for_partial_format_coverage():
    workspace = {"artifacts": {
        "creative": {"value": {"files": [{
            "url": "https://cdn.example/square.png", "width": 300, "height": 250,
        }]}},
        "creative_format_plan": {"value": {"formats": [
            {"format_id": "box", "width": 300, "height": 250, "zone_ids": ["a"]},
            {"format_id": "wide", "width": 1200, "height": 300, "zone_ids": ["b"]},
        ]}},
    }}
    result = await _prepare_creatives(
        {"run_id": "run-upload", "creative_source": "upload"}, workspace
    )
    assert result.force_review is True
    assert result.externally_committed is True
    assert result.value["reason"] == "creative_format_coverage_gap"
    assert result.value["formatCoverage"]["covered"] == 1
    assert result.value["formatCoverage"]["missing"][0]["format_id"] == "wide"


@pytest.mark.asyncio
async def test_upload_creative_source_accepts_same_ratio_at_different_pixels():
    workspace = {"artifacts": {
        "creative": {"value": {"files": [{
            "url": "https://cdn.example/mixifood-znews-masthead.png",
            "name": "mixifood-znews-masthead.png",
            "width": 928,
            "height": 200,
        }]}},
        "creative_format_plan": {"value": {"formats": [{
            "format_id": "znews-masthead-1160x250",
            "width": 1160,
            "height": 250,
            "intended_format": "banner",
            "zone_ids": ["znews-home"],
        }]}},
    }}
    result = await _prepare_creatives(
        {"run_id": "run-upload-ratio", "creative_source": "upload"}, workspace
    )
    assert result.force_review is False
    assert result.value["files"][0]["width"] == 928
    assert result.evidence[1]["covered"] == 1
    assert result.evidence[1]["matches"][0]["mode"] in {"strong_ratio", "same_ratio"}


@pytest.mark.asyncio
async def test_ai_creative_source_generates_without_manual_upload(monkeypatch):
    import autopilot.creative_generation as creative_generation

    generated = {
        "url": "http://localhost:3000/uploads/ai.png",
        "formatId": "zuma-box",
        "source": "ai_generated",
        "generation": {
            "model": "openai/gpt-image-1",
            "promptFingerprint": "abc",
            "idempotencyKey": "autopilot:run-ai:zuma-box:variant-0:plan-r2:brief-r1",
        },
    }

    async def fake_generate_many(run, workspace, format_plan, *, concurrency):
        assert [item["format_id"] for item in format_plan["formats"]] == ["zuma-box"]
        assert concurrency >= 1
        return [generated], []

    monkeypatch.setattr(creative_generation, "generate_creatives", fake_generate_many)
    workspace = {"artifacts": {
        "brief": {"revision": 1, "value": BRIEF},
        "creative_format_plan": {"revision": 2, "value": {
            "formats": [{"format_id": "zuma-box", "zone_ids": ["ZONE-A"]}],
        }},
        "creative": {"value": {"files": []}},
    }}
    result = await _prepare_creatives(
        {"run_id": "run-ai", "session_id": "ai", "creative_source": "ai_generate"},
        workspace,
    )
    assert result.force_review is False
    assert result.externally_committed is False
    assert result.value == {
        "files": [generated], "uploaded": True, "source": "ai_generate",
        "formatPlanRevision": 2,
    }
    assert result.evidence[0]["models"] == ["openai/gpt-image-1"]


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
        "derive_targeting": "succeeded", "plan_placement_intent": "succeeded",
        "plan_creative_formats": "succeeded", "prepare_creatives": "succeeded",
        "analyze_creatives": "succeeded",
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
    assert by_key["rank_placements"]["status"] == "pending"
    assert by_key["analyze_creatives"]["status"] == "queued"
    assert by_key["assign_creatives"]["status"] == "pending"
    assert by_key["forecast"]["status"] == "pending"


@pytest.mark.asyncio
async def test_operator_audience_edit_supersedes_pending_review_and_resumes_run():
    await _seed("review-edit-audience")
    run = await service.create_run(
        "review-edit-audience", approval_policy="review_every_stage",
        idempotency_key="review-edit-audience",
    )
    _mark_tasks(run["run_id"], {
        "normalize_brief": "succeeded", "validate_brief": "succeeded",
        "generate_strategy": "succeeded", "retrieve_audience": "waiting_review",
        "derive_targeting": "pending",
    })
    workspace = await get_workspace("review-edit-audience")
    manual = {"attrs": [{"_id": "manual", "fullLabel": "Manual segment"}], "size": 42}
    await apply_mutation(
        "review-edit-audience", "segment", manual,
        base_revision=workspace["revision"], actor="campaign_operator",
        idempotency_key="manual-audience",
    )

    result = await service.reconcile_workspace_changes(run["run_id"])
    by_key = {task["key"]: task for task in result["run"]["tasks"]}
    assert result["changed"] is True
    assert result["run"]["status"] == "queued"
    assert by_key["retrieve_audience"]["status"] == "succeeded"
    assert by_key["retrieve_audience"]["result"] == manual
    assert by_key["retrieve_audience"]["pending_artifact"] is None
    assert by_key["retrieve_audience"]["review_decision"]["source"] == "workspace_override"
    assert by_key["derive_targeting"]["status"] == "queued"


@pytest.mark.asyncio
async def test_creative_upload_supersedes_missing_input_review_and_resumes_analysis():
    await _seed("review-edit-creative")
    run = await service.create_run(
        "review-edit-creative", approval_policy="review_every_stage",
        idempotency_key="review-edit-creative",
    )
    _mark_tasks(run["run_id"], {
        "normalize_brief": "succeeded", "validate_brief": "succeeded",
        "generate_strategy": "succeeded", "retrieve_audience": "succeeded",
        "derive_targeting": "succeeded", "plan_placement_intent": "succeeded",
        "plan_creative_formats": "succeeded", "prepare_creatives": "waiting_review",
        "analyze_creatives": "pending",
    })
    workspace = await get_workspace("review-edit-creative")
    creative = {"files": [{"url": "https://x/upload.png", "width": 300, "height": 250}]}
    await apply_mutation(
        "review-edit-creative", "creative", creative,
        base_revision=workspace["revision"], actor="campaign_operator",
        idempotency_key="manual-creative",
    )

    result = await service.reconcile_workspace_changes(run["run_id"])
    by_key = {task["key"]: task for task in result["run"]["tasks"]}
    assert result["run"]["status"] == "queued"
    assert by_key["prepare_creatives"]["status"] == "queued"
    assert by_key["prepare_creatives"]["result"] is None
    assert by_key["analyze_creatives"]["status"] == "pending"
    assert result["run"]["last_replan"]["rechecked_input_tasks"] == ["prepare_creatives"]


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
        return [{"id": "BAD", "match_mode": "nearest_ratio"}]

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


@pytest.mark.asyncio
async def test_final_placement_ranking_keeps_ratio_compatible_candidate(monkeypatch):
    import creative_intel.service as creative_service
    import tools.order_api as order_api
    import tools.zone_ranker as zone_ranker

    async def fake_intel(_session_id):
        return []

    async def fake_rank(**_kwargs):
        return [{"id": "RATIO", "match_mode": "same_ratio", "score": 10}]

    async def no_conflicts(_start, _end):
        return {}

    monkeypatch.setattr(creative_service, "get_intel", fake_intel)
    monkeypatch.setattr(zone_ranker, "rank_zones", fake_rank)
    monkeypatch.setattr(order_api, "fetch_zone_conflicts", no_conflicts)
    workspace = {"artifacts": {
        "brief": {"value": BRIEF},
        "creative": {"value": {"files": [{"name": "ratio.png"}]}},
        "placement_intent": {"value": {"candidate_zone_ids": ["RATIO"]}},
    }}
    result = await _rank_placements({"session_id": "ratio-compatible"}, workspace)
    assert result.force_review is False
    assert result.value["selectedZoneIds"] == ["RATIO"]


@pytest.mark.asyncio
async def test_final_reach_first_order_matches_preliminary_strategy(monkeypatch):
    import creative_intel.service as creative_service
    import tools.order_api as order_api
    import tools.zone_ranker as zone_ranker

    async def fake_intel(_session_id):
        return []

    async def fake_rank(**_kwargs):
        return [
            {"id": "cheap", "match_mode": "exact_size", "reach": 100_000, "cpm": 10_000, "score": 90},
            {"id": "premium", "match_mode": "same_ratio", "reach": 800_000, "cpm": 70_000, "score": 80},
            {"id": "mid", "match_mode": "acceptable_ratio", "reach": 400_000, "cpm": 35_000, "score": 85},
        ]

    async def no_conflicts(_start, _end):
        return {}

    monkeypatch.setattr(creative_service, "get_intel", fake_intel)
    monkeypatch.setattr(zone_ranker, "rank_zones", fake_rank)
    monkeypatch.setattr(order_api, "fetch_zone_conflicts", no_conflicts)
    workspace = {"artifacts": {
        "brief": {"value": BRIEF},
        "creative": {"value": {"files": [{"name": "ratio.png"}]}},
        "strategy": {"value": {"selected": "reach_first"}},
        "placement_intent": {"value": {"candidate_zone_ids": ["cheap", "premium", "mid"]}},
    }}
    result = await _rank_placements({"session_id": "final-reach"}, workspace)
    assert result.value["selectedZoneIds"] == ["premium", "mid", "cheap"]
