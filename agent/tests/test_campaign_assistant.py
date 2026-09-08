import json
from unittest.mock import AsyncMock

import pytest


def _entry():
    return {
        "campaign_id": "ORD-QA", "title": "ZPlay", "lifecycle": "active",
        "experience_mode": "autopilot",
        "order": {
            "objective": "awareness", "budget": 80_000_000,
            "daily_budget": 10_000_000, "daily_budget_source": "derived",
            "placement_count": 2, "creative_count": 1,
        },
    }


@pytest.mark.asyncio
async def test_campaign_assistant_answers_arbitrary_budget_wording_from_evidence():
    import campaign_assistant

    plan = campaign_assistant.CampaignAssistantPlan(
        intent="read", sources=["campaign_overview"], target_tab="setup",
    )
    answer = campaign_assistant.CampaignAssistantAnswer(
        answer="Tổng ngân sách của ZPlay là 80.000.000 đ.",
        source_ids=["campaign_overview"], suggestions=["Ngân sách ngày là bao nhiêu?"],
    )
    generator = AsyncMock(side_effect=[(plan, {}), (answer, {})])

    result = await campaign_assistant.answer_campaign_question(
        _entry(), "budget campaign là bao nhiêu", generator=generator,
    )

    assert result["answer"] == "Tổng ngân sách của ZPlay là 80.000.000 đ."
    assert result["target_tab"] == "setup"
    assert result["read_only"] is True
    answer_payload = json.loads(generator.await_args_list[1].kwargs["input_data"])
    assert answer_payload["evidence"]["campaign_overview"]["order"]["budget"] == 80_000_000


@pytest.mark.asyncio
async def test_campaign_assistant_refuses_mutation_without_loading_mutation_tools(monkeypatch):
    import campaign_assistant

    plan = campaign_assistant.CampaignAssistantPlan(
        intent="mutation", sources=[], target_tab="setup",
    )
    generator = AsyncMock(return_value=(plan, {}))
    loader = AsyncMock()
    monkeypatch.setattr(campaign_assistant, "_load_sources", loader)

    result = await campaign_assistant.answer_campaign_question(
        _entry(), "Đổi budget thành 50 triệu giúp tôi", generator=generator,
    )

    assert result["read_only"] is True
    assert result["intent"] == "mutation"
    assert result["target_tab"] == "setup"
    assert "không thực hiện thay đổi" in result["answer"]
    loader.assert_not_awaited()
    assert generator.await_count == 1


@pytest.mark.asyncio
async def test_campaign_assistant_uses_incident_source_and_conversation_history(monkeypatch):
    import campaign_assistant

    plan = campaign_assistant.CampaignAssistantPlan(
        intent="read", sources=["campaign_incidents"], target_tab="evaluation",
    )
    answer = campaign_assistant.CampaignAssistantAnswer(
        answer="INC-123 đang được điều tra ở mức high.",
        source_ids=["campaign_incidents"],
    )
    generator = AsyncMock(side_effect=[(plan, {}), (answer, {})])
    monkeypatch.setattr(campaign_assistant, "_load_sources", AsyncMock(return_value={
        "campaign_overview": {"source_id": "campaign_overview", "available": True},
        "campaign_features": {"source_id": "campaign_features", "available": True},
        "campaign_incidents": {
            "source_id": "campaign_incidents", "available": True,
            "incidents": [{"incident_id": "INC-123", "state": "investigating", "severity": "high"}],
        },
    }))

    result = await campaign_assistant.answer_campaign_question(
        _entry(), "Còn cái đó thì sao?",
        history=[{"role": "user", "text": "Cho tôi xem incident INC-123"}],
        generator=generator,
    )

    assert result["target_tab"] == "evaluation"
    assert "INC-123" in result["answer"]
    plan_payload = json.loads(generator.await_args_list[0].kwargs["input_data"])
    assert plan_payload["recent_conversation"][0]["content"] == "Cho tôi xem incident INC-123"


@pytest.mark.asyncio
async def test_campaign_assistant_rejects_unknown_model_citation():
    import campaign_assistant

    plan = campaign_assistant.CampaignAssistantPlan(
        intent="read", sources=["campaign_overview"], target_tab="overview",
    )
    answer = campaign_assistant.CampaignAssistantAnswer(
        answer="Invented.", source_ids=["imaginary_source"],
    )
    generator = AsyncMock(side_effect=[(plan, {}), (answer, {})])

    result = await campaign_assistant.answer_campaign_question(
        _entry(), "Campaign này làm về gì?", generator=generator,
    )

    assert result["degraded"] is True
    assert "tạm thời không sẵn sàng" in result["answer"]


@pytest.mark.asyncio
async def test_campaign_assistant_fallback_understands_english_budget():
    import campaign_assistant

    generator = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    result = await campaign_assistant.answer_campaign_question(
        _entry(), "budget campaign là bao nhiêu", generator=generator,
    )

    assert result["target_tab"] == "setup"
    assert "80,000,000" in result["answer"]
    assert result["degraded"] is True


@pytest.mark.asyncio
async def test_campaign_assistant_strips_markdown_from_plain_text_bubble():
    import campaign_assistant

    plan = campaign_assistant.CampaignAssistantPlan(
        intent="read", sources=["campaign_overview"], target_tab="setup",
    )
    answer = campaign_assistant.CampaignAssistantAnswer(
        answer="Ngân sách là **80 triệu** và trạng thái `active`.",
        source_ids=["campaign_overview"], suggestions=["**Thời gian** chạy là bao lâu?"],
    )
    result = await campaign_assistant.answer_campaign_question(
        _entry(), "Budget?", generator=AsyncMock(side_effect=[(plan, {}), (answer, {})]),
    )

    assert result["answer"] == "Ngân sách là 80 triệu và trạng thái active."
    assert result["suggestions"] == ["Thời gian chạy là bao lâu?"]
