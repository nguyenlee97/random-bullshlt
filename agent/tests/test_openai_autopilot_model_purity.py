from unittest.mock import AsyncMock

import pytest


def test_openai_catalog_becomes_available_only_after_runtime_enablement(monkeypatch):
    from campaign_models import OPENAI_GPT_5_4_MINI, conversation_model_catalog
    from config import config

    monkeypatch.setattr(config, "OPENAI_CAMPAIGN_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    catalog = conversation_model_catalog()
    openai = next(
        item for item in catalog["models"]
        if item["id"] == OPENAI_GPT_5_4_MINI
    )

    assert openai["available"] is True
    assert openai["status"] == "available"


@pytest.mark.asyncio
async def test_openai_autopilot_audience_never_calls_greennode(monkeypatch):
    import handlers.audience as green_audience
    import openai_campaign.autopilot as openai_autopilot
    from autopilot.capabilities import _retrieve_audience
    from campaign_models import OPENAI_GPT_5_4_MINI

    green = AsyncMock(side_effect=AssertionError("GreenNode audience was called"))
    openai = AsyncMock(return_value={
        "recommendations": [{
            "segmentId": "INT158",
            "_id": "catalog-158",
            "fullLabel": "Fast food",
            "sizeMin": 1000,
            "sizeMax": 2000,
        }],
        "total_segments": 310,
        "provenance": {"provider": "openai", "model": "gpt-5.4-mini"},
    })
    monkeypatch.setattr(green_audience, "handle_dmp_recommend", green)
    monkeypatch.setattr(
        openai_autopilot, "recommend_openai_autopilot_audience", openai,
    )

    result = await _retrieve_audience(
        {
            "session_id": "openai-autopilot-audience",
            "conversation_model": OPENAI_GPT_5_4_MINI,
            "conversation_model_version": "gpt-5.4-mini",
        },
        {"artifacts": {
            "brief": {"value": {"brand": "Mixifood", "objective": "awareness"}},
            "strategy": {"value": {"selected": "balanced"}},
        }},
    )

    assert result.value["attrs"][0]["segmentId"] == "INT158"
    assert result.evidence[1]["conversation_model"] == OPENAI_GPT_5_4_MINI
    assert result.evidence[1]["provider"] == "openai"
    openai.assert_awaited_once()
    green.assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_openai_autopilot_qa_never_calls_greennode(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import workspace.service as workspace_service
    from campaign_models import OPENAI_GPT_5_4_MINI

    green = AsyncMock(side_effect=AssertionError("GreenNode Q&A was called"))
    openai = AsyncMock(return_value=(
        "Reach forecast is 1.2 million users.",
        {"provider": "openai", "model": "gpt-5.4-mini"},
    ))
    monkeypatch.setattr(chat, "_answer_greennode_autopilot_question", green)
    monkeypatch.setattr(chat, "_answer_openai_autopilot_question", openai)
    monkeypatch.setattr(chat, "add_message", AsyncMock())
    monkeypatch.setattr(workspace_service, "get_workspace", AsyncMock(return_value={
        "experience_mode": "autopilot",
        "artifacts": {"forecast": {"value": {"reach": 1_200_000}}},
    }))
    monkeypatch.setattr(service, "get_latest_run", AsyncMock(return_value={
        "run_id": "run-openai-qa",
        "status": "completed",
        "trace_id": "trace-openai-qa",
        "conversation_model": OPENAI_GPT_5_4_MINI,
        "conversation_model_version": "gpt-5.4-mini",
        "tasks": [],
    }))

    response = await chat.route_autopilot_chat(
        "What is the forecast reach?", "openai-autopilot-qa", 4,
    )

    assert response.text == "Reach forecast is 1.2 million users."
    assert response.meta.model == "gpt-5.4-mini"
    openai.assert_awaited_once()
    green.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_review_question_is_read_only_and_never_approves(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import workspace.service as workspace_service
    from campaign_models import OPENAI_GPT_5_4_MINI

    decisions = []
    openai = AsyncMock(return_value=(
        "Logo có xuất hiện; text đọc được; không thấy claim ngoài brief.",
        {"provider": "openai", "model": "gpt-5.4-mini"},
    ))

    async def fake_review(*args, **kwargs):
        decisions.append(kwargs)

    monkeypatch.setattr(chat, "_answer_openai_autopilot_question", openai)
    monkeypatch.setattr(chat, "_answer_greennode_autopilot_question", AsyncMock(
        side_effect=AssertionError("GreenNode Q&A was called"),
    ))
    monkeypatch.setattr(chat, "add_message", AsyncMock())
    monkeypatch.setattr(service, "review_task", fake_review)
    monkeypatch.setattr(workspace_service, "get_workspace", AsyncMock(return_value={
        "experience_mode": "autopilot",
        "artifacts": {
            "creative_verdict": {"value": {
                "files": [{"required_assets_present": True, "text_readable": True}],
            }},
        },
    }))
    monkeypatch.setattr(service, "get_latest_run", AsyncMock(return_value={
        "run_id": "run-openai-review",
        "status": "waiting_review",
        "conversation_model": OPENAI_GPT_5_4_MINI,
        "conversation_model_version": "gpt-5.4-mini",
        "tasks": [{
            "task_id": "run-openai-review:launch_approval",
            "key": "launch_approval",
            "title": "Duyệt launch",
            "status": "waiting_review",
            "result": {"message": "Kiểm tra order draft."},
        }],
    }))

    response = await chat.route_autopilot_chat(
        "Kiểm tra logo và text giúp tôi. Tôi đang hỏi để review, "
        "chưa phê duyệt creative.",
        "openai-review-question",
        4,
    )

    assert response.meta.tool == "autopilot_review_qa"
    assert "checkpoint vẫn đang chờ quyết định" in response.text
    assert decisions == []
    context = openai.await_args.kwargs["context"]
    assert context["review_checkpoint"]["key"] == "launch_approval"
    assert context["artifacts"]["creative_verdict"]["files"][0]["text_readable"] is True


@pytest.mark.asyncio
async def test_openai_autopilot_failure_does_not_cross_fallback(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import workspace.service as workspace_service
    from campaign_models import OPENAI_GPT_5_4_MINI

    green = AsyncMock(side_effect=AssertionError("cross-provider fallback"))
    openai = AsyncMock(side_effect=RuntimeError("OpenAI unavailable"))
    monkeypatch.setattr(chat, "_answer_greennode_autopilot_question", green)
    monkeypatch.setattr(chat, "_answer_openai_autopilot_question", openai)
    monkeypatch.setattr(chat, "add_message", AsyncMock())
    monkeypatch.setattr(workspace_service, "get_workspace", AsyncMock(return_value={
        "experience_mode": "autopilot",
        "artifacts": {
            "brief": {"value": {"brand": "Mixifood"}},
            "order": {"value": {"order": {"id": "ORD-1", "status": "active"}}},
        },
    }))
    monkeypatch.setattr(service, "get_latest_run", AsyncMock(return_value={
        "run_id": "run-openai-failure",
        "status": "completed",
        "conversation_model": OPENAI_GPT_5_4_MINI,
        "conversation_model_version": "gpt-5.4-mini",
        "tasks": [],
    }))

    response = await chat.route_autopilot_chat(
        "Summarize this run", "openai-autopilot-failure", 4,
    )

    assert "ORD-1" in response.text
    assert response.meta.model == "gpt-5.4-mini"
    openai.assert_awaited_once()
    green.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_run_model_is_backfilled_once_from_owning_conversation():
    import autopilot.service as service
    from campaign_models import OPENAI_GPT_5_4_MINI
    from identity import bootstrap_anonymous, create_conversation
    from workspace.service import apply_mutation, get_workspace

    owner = await bootstrap_anonymous()
    conversation = await create_conversation(
        owner["identity_id"],
        experience_mode="autopilot",
        conversation_model=OPENAI_GPT_5_4_MINI,
    )
    workspace = await get_workspace(conversation["session_id"])
    await apply_mutation(
        conversation["session_id"],
        "brief",
        {
            "brand": "Model migration",
            "objective": "awareness",
            "budget": 10,
            "startDate": "2026-08-01",
            "endDate": "2026-08-10",
        },
        base_revision=workspace["revision"],
        actor="test",
        idempotency_key="legacy-run-model-brief",
    )
    run = await service.create_run(
        conversation["session_id"], idempotency_key="legacy-run-model",
    )
    private = service._mem_runs[run["run_id"]]
    private.pop("conversation_model", None)
    private.pop("conversation_model_version", None)

    restored = await service.get_run(run["run_id"])

    assert restored["conversation_model"] == OPENAI_GPT_5_4_MINI
    assert restored["conversation_model_version"] == "gpt-5.4-mini"
    assert private["conversation_model"] == OPENAI_GPT_5_4_MINI
    assert private["conversation_model_migrated_at"] is not None


@pytest.mark.asyncio
async def test_autopilot_retry_keeps_persisted_model_when_defaults_change(monkeypatch):
    import autopilot.service as service
    from campaign_models import GREENNODE_MINIMAX, OPENAI_GPT_5_4_MINI
    from config import config
    from identity import bootstrap_anonymous, create_conversation
    from workspace.service import apply_mutation, get_workspace

    owner = await bootstrap_anonymous()
    conversation = await create_conversation(
        owner["identity_id"],
        experience_mode="autopilot",
        conversation_model=OPENAI_GPT_5_4_MINI,
    )
    workspace = await get_workspace(conversation["session_id"])
    await apply_mutation(
        conversation["session_id"],
        "brief",
        {
            "brand": "Retry model lock",
            "objective": "awareness",
            "budget": 10,
            "startDate": "2026-08-01",
            "endDate": "2026-08-10",
        },
        base_revision=workspace["revision"],
        actor="test",
        idempotency_key="retry-model-lock-brief",
    )
    run = await service.create_run(
        conversation["session_id"], idempotency_key="retry-model-lock",
    )
    first_attempt = await service.claim_next_task("worker-one")
    monkeypatch.setattr(config, "DEFAULT_CONVERSATION_MODEL", GREENNODE_MINIMAX)
    await service.fail_task(first_attempt["task_id"], "transient", retryable=True)
    second_attempt = await service.claim_next_task("worker-two")
    restored = await service.get_run(run["run_id"])

    assert second_attempt["task_id"] == first_attempt["task_id"]
    assert restored["conversation_model"] == OPENAI_GPT_5_4_MINI
    assert restored["conversation_model_version"] == "gpt-5.4-mini"


@pytest.mark.asyncio
async def test_zalo_autopilot_uses_explicit_channel_model_policy(monkeypatch):
    import autopilot.service as service
    import campaign_models
    import identity
    import workspace.service as workspace_service
    import zalo_campaign_agent as agent
    from campaign_models import OPENAI_GPT_5_4_MINI
    from config import config

    captured = {}

    async def create_conversation(actor, **kwargs):
        captured["conversation_model"] = kwargs["conversation_model"]
        return {"conversation_id": "conv-zalo", "session_id": "sess-zalo"}

    monkeypatch.setattr(config, "ZALO_AUTOPILOT_CONVERSATION_MODEL", OPENAI_GPT_5_4_MINI)
    monkeypatch.setattr(campaign_models, "conversation_model_is_available", lambda _model: True)
    monkeypatch.setattr(identity, "create_conversation", create_conversation)
    monkeypatch.setattr(identity, "set_conversation_title_for_session", AsyncMock())
    monkeypatch.setattr(workspace_service, "get_workspace", AsyncMock(return_value={
        "revision": 0,
    }))
    monkeypatch.setattr(workspace_service, "apply_mutation", AsyncMock())
    monkeypatch.setattr(service, "create_run", AsyncMock(return_value={
        "run_id": "run-zalo-openai",
    }))
    monkeypatch.setattr(agent, "_update_thread", AsyncMock(side_effect=lambda thread, updates: {
        **thread, **updates,
    }))
    monkeypatch.setattr(agent, "subscribe_run", AsyncMock())

    await agent._start_autopilot(
        {"thread_id": "thread-zalo", "anonymous_id": "anon-zalo"},
        {
            "brand": "Zalo campaign",
            "objective": "awareness",
            "budget": 10,
            "startDate": "2026-08-01",
            "endDate": "2026-08-10",
        },
        "fully_automatic",
    )

    assert captured["conversation_model"] == OPENAI_GPT_5_4_MINI
