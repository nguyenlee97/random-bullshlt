from datetime import timedelta

import pytest

from autopilot import service
from autopilot.capabilities import (
    CapabilityResult, _analyze_creatives, _assign_creatives, _audience_attrs,
    _build_creatives, _build_order_draft, _create_order, _create_setup_report,
    _derive_targeting, _forecast, _generate_strategy, _launch_approval,
    _plan_placement_intent, _prepare_creatives, _rank_placements, _retrieve_audience,
)
from autopilot import worker
from campaign_models import LEGACY_CONVERSATION_MODEL, OPENAI_GPT_5_4_MINI
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
    assert first["quality_version_manifest"]["quality_schema_version"] == "quality-v1"
    assert (
        first["quality_version_manifest"]["approval_policy"]
        == "critical_only"
    )
    assert first["quality_version_manifest"] == second["quality_version_manifest"]
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


def test_openai_critical_policy_stops_at_three_operator_checkpoints():
    tasks = service._new_tasks("openai-review-plan", OPENAI_GPT_5_4_MINI)
    actual = {
        task["key"]
        for task in tasks
        if service._needs_review(task, "critical_only")
    }
    assert actual == {
        "plan_placement_intent",
        "assign_creatives",
        "launch_approval",
    }


def test_legacy_critical_policy_keeps_five_operator_checkpoints():
    tasks = service._new_tasks("legacy-review-plan", LEGACY_CONVERSATION_MODEL)
    actual = {
        task["key"]
        for task in tasks
        if service._needs_review(task, "critical_only")
    }
    assert actual == {
        "retrieve_audience",
        "derive_targeting",
        "plan_placement_intent",
        "assign_creatives",
        "launch_approval",
    }


def test_review_every_stage_still_reviews_audience_and_targeting():
    tasks = service._new_tasks("openai-stage-review", OPENAI_GPT_5_4_MINI)
    for key in ("retrieve_audience", "derive_targeting"):
        task = next(item for item in tasks if item["key"] == key)
        assert service._needs_review(task, "review_every_stage")
        assert not service._needs_review(task, "critical_only")


def test_creative_intel_commit_is_internal_autopilot_work():
    workspace = {
        "events": [{
            "revision": 2,
            "artifact": "creative_verdict",
            "actor": "creative_intel_worker",
        }],
        "artifacts": {
            "creative_verdict": {
                "revision": 2,
                "updated_by": "creative_intel_worker",
            },
        },
    }
    assert service._external_workspace_changes(workspace, 1) == []


@pytest.mark.asyncio
async def test_auto_build_has_no_routine_approval_checkpoints():
    assert not service._needs_review({"review": "launch"}, "auto_build_draft")
    assert not service._needs_review({"review": "critical"}, "auto_build_draft")
    assert not service._needs_review({"review": "stage"}, "auto_build_draft")
    assert service._needs_review({"review": "launch"}, "critical_only")


@pytest.mark.asyncio
async def test_launch_boundary_uses_fully_automatic_delegation():
    workspace = {"artifacts": {"order_draft": {
        "revision": 7,
        "value": {"payload": {
            "brand": "ZaloPay",
            "budget": 40_000_000,
            "placements": ["ZONE-1"],
        }},
    }}}
    automatic = await _launch_approval(
        {"approval_policy": "auto_build_draft"},
        workspace,
    )
    assert automatic.force_review is False
    assert automatic.value["requires_explicit_approval"] is False
    assert automatic.value["authorization"] == "fully_automatic_mode"
    assert automatic.evidence[0]["auto_approvable"] is True

    semi_automatic = await _launch_approval(
        {"approval_policy": "critical_only"},
        workspace,
    )
    assert semi_automatic.force_review is True
    assert semi_automatic.value["requires_explicit_approval"] is True


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


def test_order_audience_uses_direct_tier_without_silently_adding_related_rows():
    direct = {"_id": "INT001", "tier": "recommended"}
    related = {"_id": "INT002", "tier": "adjacent"}
    assert _audience_attrs({
        "attrs": [direct],
        "adjacent_attrs": [related],
        "recommendations": [direct, related],
    }) == [direct]


@pytest.mark.asyncio
async def test_openai_autopilot_vague_brief_requires_clarification(monkeypatch):
    import openai_campaign.autopilot as openai_autopilot
    from campaign_models import OPENAI_GPT_5_4_MINI

    captured = {}

    async def vague_recommendation(*_args, **kwargs):
        captured["brief"] = kwargs["brief_override"]
        return {
            "recommendations": [],
            "adjacent_recommendations": [],
            "rag": {
                "information_sufficient": False,
                "insufficient_reason": "brief_missing_product_or_audience_evidence",
            },
            "provenance": {"provider": "openai", "model": "gpt-5.4-mini"},
        }

    monkeypatch.setattr(
        openai_autopilot,
        "recommend_openai_autopilot_audience",
        vague_recommendation,
    )
    workspace = {"artifacts": {
        "brief": {"value": {
            "brand": "Nova",
            "objective": "awareness",
            "kpi": "Tăng nhận diện",
            "notes": "Muốn tìm thêm khách hàng phù hợp cho sản phẩm mới.",
        }},
        "strategy": {"value": {"selected": "balanced"}},
    }}

    result = await _retrieve_audience(
        {
            "session_id": "openai-vague-autopilot",
            "conversation_model": OPENAI_GPT_5_4_MINI,
        },
        workspace,
    )

    assert result.value["attrs"] == []
    assert result.value["adjacent_attrs"] == []
    assert result.value["clarification_required"] is True
    assert "Bổ sung sản phẩm" in result.value["clarification_prompt"]
    assert result.force_review is True
    assert "Chiến lược" not in captured["brief"]["notes"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy", "actor"),
    [
        ("critical_only", "semi_automatic"),
        ("auto_build_draft", "fully_automatic"),
    ],
)
async def test_delegated_openai_modes_select_ranked_related_audience_without_review(
    monkeypatch, policy, actor,
):
    import openai_campaign.autopilot as openai_autopilot

    related = [{
        "_id": f"INT00{index}",
        "segmentId": f"INT00{index}",
        "fullLabel": label,
        "tier": "adjacent",
        "sizeMin": index * 1_000_000,
        "sizeMax": index * 1_200_000,
    } for index, label in enumerate(
        ["Construction", "Management", "Science", "Engineering"],
        start=1,
    )]

    async def related_recommendation(*_args, **_kwargs):
        return {
            "recommendations": [],
            "adjacent_recommendations": related,
            "rag": {"information_sufficient": True},
            "provenance": {"provider": "openai", "model": "gpt-5.4-mini"},
        }

    monkeypatch.setattr(
        openai_autopilot,
        "recommend_openai_autopilot_audience",
        related_recommendation,
    )
    result = await _retrieve_audience(
        {
            "session_id": f"openai-{actor}-audience",
            "conversation_model": OPENAI_GPT_5_4_MINI,
            "approval_policy": policy,
        },
        {"artifacts": {
            "brief": {"value": BRIEF},
            "strategy": {"value": {"selected": "balanced"}},
        }},
    )

    assert [item["segmentId"] for item in result.value["attrs"]] == [
        "INT001", "INT002", "INT003",
    ]
    assert [item["segmentId"] for item in result.value["adjacent_attrs"]] == [
        "INT004",
    ]
    assert result.value["selection_required"] is False
    assert result.value["selection"]["source"] == "autopilot_policy"
    assert result.value["selection"]["actor"] == actor
    assert result.force_review is False


@pytest.mark.asyncio
async def test_openai_autopilot_targeting_uses_basic_and_advanced_catalog_fields(
    monkeypatch,
):
    captured = {}
    options = {
        "geo": {"Miền Nam": ["TP.HCM"]},
        "age": ["25-34", "35-44"],
        "gender": ["Male", "Female"],
        "deviceOS": ["Android", "iOS"],
        "deviceBrand": ["Samsung", "Apple"],
        "marital": ["Single", "Married"],
        "parental": ["Have children", "No children"],
        "education": ["College & Bachelor"],
        "income": ["Top 10-25%"],
        "career": ["Office Worker"],
        "interest": ["Automotive"],
        "weather": ["Sunny", "Rain"],
    }

    async def get_options():
        return options

    async def recommend(**kwargs):
        captured.update(kwargs)
        return (
            {
                "geo": ["TP.HCM"],
                "age": ["25-34", "35-44"],
                "gender": ["Male", "Female"],
                "deviceOS": ["Android"],
                "career": ["Office Worker"],
                "interest": ["Automotive"],
            },
            [{
                "field": "interest",
                "picks": ["Automotive"],
                "reason": "Kiki là sản phẩm AI dành cho xe ô tô.",
            }],
            "gpt-5.4-mini",
        )

    monkeypatch.setattr(
        "tools.targeting_options.get_targeting_options",
        get_options,
    )
    monkeypatch.setattr(
        "openai_campaign.autopilot.recommend_openai_autopilot_targeting",
        recommend,
    )
    result = await _derive_targeting(
        {
            "session_id": "openai-targeting-advanced",
            "conversation_model": OPENAI_GPT_5_4_MINI,
            "conversation_model_version": "openai-gpt-5.4-mini-v1",
        },
        {"artifacts": {
            "brief": {"value": {
                **BRIEF,
                "brand": "Zalo",
                "notes": "Ứng dụng AI Agent Kiki dành cho xe ô tô.",
            }},
            "strategy": {"value": {"selected": "reach_first"}},
            "audience": {"value": {"attrs": [{
                "segmentId": "INT001",
                "fullLabel": "Automotive",
                "tier": "recommended",
                "reason": "Quan tâm xe ô tô.",
            }]}},
        }},
    )

    assert captured["brief"]["strategy"] == "reach_first"
    assert captured["segments"][0]["fullLabel"] == "Automotive"
    assert result.value["interest"] == ["Automotive"]
    assert result.value["career"] == ["Office Worker"]
    assert result.evidence[0]["selection_mode"] == "openai_catalog_grounded"
    assert result.evidence[0]["advanced_dimensions"] == [
        "deviceOS", "career", "interest",
    ]


@pytest.mark.asyncio
async def test_openai_targeting_failure_falls_back_to_broad_delivery(monkeypatch):
    async def get_options():
        return {"geo": {"Miền Nam": ["TP.HCM"]}, "age": ["25-34"]}

    async def fail_targeting(**_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "tools.targeting_options.get_targeting_options",
        get_options,
    )
    monkeypatch.setattr(
        "openai_campaign.autopilot.recommend_openai_autopilot_targeting",
        fail_targeting,
    )
    result = await _derive_targeting(
        {
            "session_id": "openai-targeting-fallback",
            "conversation_model": OPENAI_GPT_5_4_MINI,
        },
        {"artifacts": {
            "brief": {"value": BRIEF},
            "strategy": {"value": {"selected": "balanced"}},
            "audience": {"value": {"attrs": []}},
        }},
    )

    assert result.value == {}
    assert result.evidence[0]["selection_mode"] == "broad_fallback"
    assert "RuntimeError" in result.evidence[0]["fallback_error"]


@pytest.mark.asyncio
async def test_legacy_targeting_keeps_existing_deterministic_template(monkeypatch):
    async def get_options():
        return {
            "geo": ["Hà Nội", "TP.HCM", "Đà Nẵng"],
            "age": ["18-24", "25-34", "35-44"],
            "gender": ["Male", "Female"],
        }

    monkeypatch.setattr(
        "tools.targeting_options.get_targeting_options",
        get_options,
    )
    result = await _derive_targeting(
        {
            "session_id": "legacy-targeting",
            "conversation_model": LEGACY_CONVERSATION_MODEL,
        },
        {"artifacts": {
            "strategy": {"value": {"selected": "reach_first"}},
        }},
    )

    assert result.value == {
        "geo": ["Hà Nội", "TP.HCM", "Đà Nẵng"],
        "age": ["18-24", "25-34", "35-44"],
        "gender": ["Male", "Female"],
    }


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
async def test_operator_can_rerun_unapproved_audience_review():
    await _seed("audience-rerun")
    run = await service.create_run(
        "audience-rerun",
        approval_policy="review_every_stage",
        idempotency_key="audience-rerun",
    )
    task_id = f"{run['run_id']}:retrieve_audience"
    service._mem_tasks[task_id].update(
        status="waiting_review",
        result={"attrs": [{"segmentId": "INT020", "fullLabel": "Books"}]},
        evidence=[{"type": "audience_pipeline"}],
        pending_artifact={
            "session_id": "audience-rerun",
            "artifact": "audience",
            "value": {"attrs": [{"segmentId": "INT020", "fullLabel": "Books"}]},
            "input_revisions": {},
            "base_artifact_revision": 0,
        },
    )

    rerun = await service.rerun_review_task(
        run["run_id"],
        task_id,
        actor="test",
        reason="recommend again",
    )

    task = next(item for item in rerun["tasks"] if item["task_id"] == task_id)
    assert task["status"] == "queued"
    assert task["result"] is None
    assert task["evidence"] == []
    assert task["pending_artifact"] is None
    assert (await get_workspace("audience-rerun"))["artifacts"]["audience"]["status"] == "missing"


@pytest.mark.asyncio
async def test_openai_audience_rerun_invalidates_query_plan_cache(monkeypatch):
    await _seed("openai-audience-rerun")

    async def openai_model(_session_id):
        return {
            "conversation_id": "conv-openai-rerun",
            "conversation_model": OPENAI_GPT_5_4_MINI,
            "conversation_model_version": "gpt-5.4-mini",
        }

    invalidated = []
    monkeypatch.setattr(
        "identity.get_conversation_model_for_session", openai_model
    )
    monkeypatch.setattr(
        "openai_campaign.audience_search.invalidate_audience_search_cache",
        lambda brief: invalidated.append(brief),
    )
    run = await service.create_run(
        "openai-audience-rerun",
        approval_policy="critical_only",
        idempotency_key="openai-audience-rerun",
    )
    task_id = f"{run['run_id']}:retrieve_audience"
    service._mem_tasks[task_id].update(
        status="waiting_review",
        result={"attrs": []},
        pending_artifact={
            "session_id": "openai-audience-rerun",
            "artifact": "audience",
            "value": {"attrs": []},
            "input_revisions": {},
            "base_artifact_revision": 0,
        },
    )

    await service.rerun_review_task(run["run_id"], task_id)

    assert invalidated == [BRIEF]


@pytest.mark.asyncio
async def test_adjacent_only_audience_requires_explicit_selection_before_review():
    await _seed("audience-adjacent-review")
    run = await service.create_run(
        "audience-adjacent-review",
        approval_policy="review_every_stage",
        idempotency_key="audience-adjacent-review",
    )
    context = await get_task_context("audience-adjacent-review", "audience")
    task_id = f"{run['run_id']}:retrieve_audience"
    related = [
        {
            "_id": "INT006", "segmentId": "INT006",
            "fullLabel": "Construction", "tier": "adjacent",
            "sizeMin": 1_000_000, "sizeMax": 2_000_000,
        },
        {
            "_id": "INT020", "segmentId": "INT020",
            "fullLabel": "Management", "tier": "adjacent",
            "sizeMin": 2_000_000, "sizeMax": 3_000_000,
        },
    ]
    value = {
        "attrs": [],
        "adjacent_attrs": related,
        "recommendations": related,
        "selection_required": True,
        "size": 0,
    }
    service._mem_tasks[task_id].update(
        status="waiting_review",
        result=value,
        pending_artifact={
            "session_id": "audience-adjacent-review",
            "artifact": "audience",
            "value": value,
            "input_revisions": context["input_revisions"],
            "base_artifact_revision": context["artifact_revision"],
        },
    )

    with pytest.raises(service.RunConflict, match="at least one selected"):
        await service.review_task(run["run_id"], task_id, approved=True)

    selected = await service.select_audience_recommendations(
        run["run_id"], ["INT020"], reason="Management is an acceptable proxy"
    )
    selected_task = next(
        item for item in selected["tasks"] if item["task_id"] == task_id
    )
    selected_value = selected_task["pending_artifact"]["value"]
    assert [item["segmentId"] for item in selected_value["attrs"]] == ["INT020"]
    assert selected_value["selection_required"] is False

    await service.review_task(run["run_id"], task_id, approved=True)
    committed = await get_workspace("audience-adjacent-review")
    assert [
        item["segmentId"]
        for item in committed["artifacts"]["audience"]["value"]["attrs"]
    ] == ["INT020"]


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
async def test_openai_placement_intent_limits_one_topic_without_changing_greennode(monkeypatch):
    from campaign_models import GREENNODE_MINIMAX, OPENAI_GPT_5_4_MINI

    zones = [
        {
            "id": f"home-{index}",
            "topicId": "home_garden_diy",
            "placementFamily": f"family-{index % 3}",
            "reach": 1_000_000 - index,
            "score": 100 - index,
        }
        for index in range(10)
    ] + [
        {
            "id": f"tech-{index}",
            "topicId": "technology_science",
            "placementFamily": f"tech-family-{index}",
            "reach": 500_000 - index,
            "score": 80 - index,
        }
        for index in range(2)
    ]

    async def fake_rank_zones(**_kwargs):
        return zones

    async def fake_conflicts(_start, _end):
        return {}

    monkeypatch.setattr("tools.zone_ranker.rank_zones", fake_rank_zones)
    monkeypatch.setattr("tools.order_api.fetch_zone_conflicts", fake_conflicts)
    workspace = {"artifacts": {
        "brief": {"value": BRIEF},
        "strategy": {"value": {"selected": "balanced"}},
    }}

    openai = await _plan_placement_intent(
        {"session_id": "openai-zones", "conversation_model": OPENAI_GPT_5_4_MINI},
        workspace,
    )
    greennode = await _plan_placement_intent(
        {"session_id": "greennode-zones", "conversation_model": GREENNODE_MINIMAX},
        workspace,
    )

    openai_topics = [zone["topicId"] for zone in openai.value["candidates"]]
    assert len(openai.value["candidates"]) == 8
    assert openai_topics.count("home_garden_diy") == 6
    assert openai_topics.count("technology_science") == 2
    assert len(greennode.value["candidates"]) == 12


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
async def test_ai_source_accepts_reviewed_operator_replacement(monkeypatch):
    import autopilot.creative_generation as creative_generation

    async def must_not_generate(*_args, **_kwargs):
        raise AssertionError("reviewed operator replacement must bypass image generation")

    monkeypatch.setattr(creative_generation, "generate_creatives", must_not_generate)
    uploaded = {
        "url": "https://cdn.example/operator.png",
        "name": "operator.png",
        "width": 300,
        "height": 250,
        "analysisStatus": "approved_override",
        "analysisId": "ci_operator",
    }
    workspace = {"artifacts": {
        "brief": {"revision": 1, "value": BRIEF},
        "creative_format_plan": {"revision": 2, "value": {
            "formats": [{
                "format_id": "zuma-box", "width": 300, "height": 250,
                "zone_ids": ["ZONE-A"],
            }],
        }},
        "creative": {"value": {"files": [uploaded], "uploaded": True}},
    }}

    result = await _prepare_creatives(
        {"run_id": "run-ai-repair", "session_id": "ai-repair",
         "creative_source": "ai_generate"},
        workspace,
    )

    assert result.force_review is False
    assert result.externally_committed is True
    assert result.value["files"] == [uploaded]
    assert result.value["source"] == "operator_upload_override"
    assert result.evidence[0]["source"] == "operator_upload_override"
    assert result.evidence[1]["covered"] == 1


@pytest.mark.asyncio
async def test_ai_creative_source_generates_without_manual_upload(monkeypatch):
    import autopilot.creative_generation as creative_generation

    generated = {
        "url": "http://localhost:3000/uploads/ai.png",
        "formatId": "zuma-box",
        "source": "ai_generated",
        "generation": {
            "model": "gpt-image-2",
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
    assert result.evidence[0]["models"] == ["gpt-image-2"]


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
async def test_critical_policy_auto_commits_audience_and_targeting(monkeypatch):
    async def openai_model_lock(_session_id):
        return {
            "conversation_id": "conv-worker-streamlined-critical",
            "conversation_model": OPENAI_GPT_5_4_MINI,
            "conversation_model_version": "openai-gpt-5.4-mini-v1",
        }

    monkeypatch.setattr(
        "identity.get_conversation_model_for_session",
        openai_model_lock,
    )
    await _seed("worker-streamlined-critical")
    run = await service.create_run(
        "worker-streamlined-critical",
        approval_policy="critical_only",
        idempotency_key="worker-streamlined-critical",
    )
    direct = {
        "_id": "INT001",
        "segmentId": "INT001",
        "fullLabel": "Automotive",
        "tier": "recommended",
    }
    related = {
        "_id": "INT002",
        "segmentId": "INT002",
        "fullLabel": "Technology",
        "tier": "adjacent",
    }

    async def fake_execute(task, _run):
        if task["key"] == "generate_strategy":
            return CapabilityResult(value={"selected": "balanced"})
        if task["key"] == "retrieve_audience":
            return CapabilityResult(value={
                "attrs": [direct],
                "adjacent_attrs": [related],
                "recommendations": [direct, related],
                "selection_required": False,
            })
        if task["key"] == "derive_targeting":
            return CapabilityResult(value={
                "geo": ["TP.HCM"],
                "age": ["25-34"],
                "gender": ["Male", "Female"],
            })
        return CapabilityResult(value={"ok": True})

    monkeypatch.setattr(worker, "execute", fake_execute)
    for expected_key in (
        "normalize_brief",
        "validate_brief",
        "generate_strategy",
        "retrieve_audience",
        "derive_targeting",
    ):
        task = await service.claim_next_task("worker-streamlined")
        assert task["key"] == expected_key
        await worker._process(task)

    current = await service.get_run(run["run_id"])
    by_key = {task["key"]: task for task in current["tasks"]}
    workspace = await get_workspace("worker-streamlined-critical")
    assert by_key["retrieve_audience"]["status"] == "succeeded"
    assert by_key["derive_targeting"]["status"] == "succeeded"
    assert by_key["plan_placement_intent"]["status"] == "queued"
    assert workspace["artifacts"]["audience"]["value"]["attrs"] == [direct]
    assert workspace["artifacts"]["audience"]["value"]["adjacent_attrs"] == [related]
    assert workspace["artifacts"]["targeting"]["value"]["geo"] == ["TP.HCM"]


@pytest.mark.asyncio
async def test_replanned_worker_replaces_its_own_stale_artifact(monkeypatch):
    await _seed("worker-replan-generation")
    run = await service.create_run(
        "worker-replan-generation", approval_policy="auto_build_draft",
        idempotency_key="worker-replan-generation",
    )
    strategy_id = f"{run['run_id']}:generate_strategy"
    strategy_task = service._mem_tasks[strategy_id]
    strategy_task.update(status="running", lease_owner="worker", attempts=1)

    outputs = iter((
        CapabilityResult(value={"selected": "balanced"}),
        CapabilityResult(value={"selected": "quality_first"}),
    ))

    async def fake_execute(_task, _run):
        return next(outputs)

    monkeypatch.setattr(worker, "execute", fake_execute)
    await worker._process(dict(strategy_task))
    first = await get_workspace("worker-replan-generation")
    assert first["artifacts"]["strategy"]["value"] == {"selected": "balanced"}

    await apply_mutation(
        "worker-replan-generation", "brief", {**BRIEF, "budget": 75},
        base_revision=first["revision"], actor="campaign_operator",
        idempotency_key="worker-replan-generation:brief-edit",
    )
    replanned = await service.reconcile_workspace_changes(run["run_id"])
    reset_task = next(
        task for task in replanned["run"]["tasks"]
        if task["task_id"] == strategy_id
    )
    assert reset_task["replan_workspace_revision"] > 0
    service._mem_tasks[strategy_id].update(
        status="running", lease_owner="worker", attempts=1,
    )

    await worker._process(dict(service._mem_tasks[strategy_id]))
    second = await get_workspace("worker-replan-generation")
    assert second["artifacts"]["strategy"]["status"] == "approved"
    assert second["artifacts"]["strategy"]["value"] == {
        "selected": "quality_first"
    }
    assert second["artifacts"]["strategy"]["revision"] > first["revision"]


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
async def test_later_audience_edit_keeps_operator_selection_and_replans_consumers():
    session_id = "later-audience-edit"
    await _seed(session_id)
    run = await service.create_run(
        session_id,
        approval_policy="auto_build_draft",
        idempotency_key="later-audience-edit",
    )
    _mark_tasks(run["run_id"], {
        "normalize_brief": "succeeded",
        "validate_brief": "succeeded",
        "generate_strategy": "succeeded",
        "retrieve_audience": "succeeded",
        "derive_targeting": "succeeded",
        "plan_placement_intent": "succeeded",
        "plan_creative_formats": "succeeded",
        "prepare_creatives": "waiting_review",
        "analyze_creatives": "pending",
    })
    candidates = [
        {
            "segmentId": "INT159",
            "fullLabel": "Organic food",
            "sizeMin": 4_070_000,
            "sizeMax": 5_490_000,
            "tier": "recommended",
        },
        {
            "segmentId": "INT117",
            "fullLabel": "Motherhood",
            "sizeMin": 1_450_000,
            "sizeMax": 2_040_000,
            "tier": "recommended",
        },
        {
            "segmentId": "INT118",
            "fullLabel": "Parenting",
            "sizeMin": 2_290_000,
            "sizeMax": 2_870_000,
            "tier": "adjacent",
        },
    ]
    audience = {
        "attrs": candidates[:2],
        "adjacent_attrs": candidates[2:],
        "recommendations": candidates,
        "size": 6_525_000,
    }
    workspace = await get_workspace(session_id)
    await apply_mutation(
        session_id,
        "segment",
        audience,
        base_revision=workspace["revision"],
        actor="autopilot_worker",
        idempotency_key="initial-audience",
    )

    updated = await service.select_audience_recommendations(
        run["run_id"],
        ["INT159", "INT117", "INT118"],
        reason="Add Parenting to the two current primary audiences",
    )

    workspace = await get_workspace(session_id)
    by_key = {task["key"]: task for task in updated["tasks"]}
    selected = workspace["artifacts"]["audience"]["value"]
    assert [item["segmentId"] for item in selected["attrs"]] == [
        "INT159", "INT117", "INT118",
    ]
    assert selected["selection"]["source"] == "operator"
    assert by_key["retrieve_audience"]["status"] == "succeeded"
    assert [item["segmentId"] for item in by_key["retrieve_audience"]["result"]["attrs"]] == [
        "INT159", "INT117", "INT118",
    ]
    assert by_key["derive_targeting"]["status"] == "queued"
    assert by_key["prepare_creatives"]["status"] == "pending"
    assert updated["status"] == "queued"


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
async def test_placement_ranking_keeps_compatible_and_nearest_ratio_fallback(monkeypatch):
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
    assert result.value["selectedZoneIds"] == ["GOOD", "BAD"]


@pytest.mark.asyncio
async def test_nearest_ratio_placement_continues_without_recovery_review(monkeypatch):
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
        "creative": {"value": {"files": [{
            "name": "bad.png", "type": "image/png",
            "width": 700, "height": 700,
        }]}},
        "creative_format_plan": {"value": {"formats": [{
            "format_id": "znews-masthead-1160x250",
            "width": 1160, "height": 250, "zone_ids": ["BAD"],
        }]}},
    }}
    result = await _rank_placements({"session_id": "incompatible"}, workspace)
    assert result.force_review is False
    assert result.value["selectedZoneIds"] == ["BAD"]


@pytest.mark.asyncio
async def test_creative_recovery_generates_missing_formats_and_replans(monkeypatch):
    import autopilot.creative_generation as creative_generation
    import workspace.service as workspace_service

    run = {
        "run_id": "run-repair",
        "session_id": "repair-session",
        "status": "waiting_review",
        "tasks": [
            {"key": "rank_placements", "status": "waiting_review"},
            {"key": "create_order", "status": "pending"},
        ],
    }
    workspace = {
        "revision": 7,
        "artifacts": {
            "creative": {"value": {"files": [{
                "id": "source", "name": "square.png", "type": "image/png",
                "width": 700, "height": 700,
            }]}},
            "creative_format_plan": {"value": {"formats": [{
                "format_id": "znews-masthead-1160x250",
                "width": 1160, "height": 250, "zone_ids": ["ZONE-A"],
            }]}},
        },
    }
    generated = {
        "id": "generated",
        "name": "masthead.png",
        "url": "https://example.test/masthead.png",
        "type": "image/png",
        "width": 1160,
        "height": 250,
        "formatId": "znews-masthead-1160x250",
        "generation": {"idempotencyKey": "repair-key"},
    }
    mutations = []
    events = []

    async def fake_get_run(_run_id):
        return run

    async def fake_get_workspace(_session_id):
        return workspace

    async def fake_generate(_run, _workspace, plan, **_kwargs):
        assert [item["format_id"] for item in plan["formats"]] == [
            "znews-masthead-1160x250"
        ]
        return [generated], []

    async def fake_apply_mutation(session_id, field, value, **kwargs):
        mutations.append((session_id, field, value, kwargs))
        return {"ok": True, "workspace_revision": 8}

    async def fake_reconcile(_run_id):
        return {"changed": True, "run": {**run, "workspace_revision": 8}}

    async def fake_emit(_run_id, event_type, data):
        events.append((event_type, data))

    monkeypatch.setattr(service, "get_run", fake_get_run)
    monkeypatch.setattr(service, "get_workspace", fake_get_workspace)
    monkeypatch.setattr(
        creative_generation, "generate_creatives", fake_generate
    )
    monkeypatch.setattr(workspace_service, "apply_mutation", fake_apply_mutation)
    monkeypatch.setattr(service, "reconcile_workspace_changes", fake_reconcile)
    monkeypatch.setattr(service, "_emit", fake_emit)

    result = await service.generate_missing_creative_formats(
        "run-repair", ["znews-masthead-1160x250"]
    )

    assert result["ok"] is True
    assert result["generated_count"] == 1
    assert mutations[0][0:2] == ("repair-session", "creative")
    assert [item["id"] for item in mutations[0][2]["files"]] == [
        "source", "generated"
    ]
    assert mutations[0][2]["source"] == "mixed_recovery"
    assert events[0][0] == "creative_recovery_generated"


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
