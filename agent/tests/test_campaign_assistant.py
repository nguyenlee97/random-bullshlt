import pytest


@pytest.mark.asyncio
async def test_campaign_assistant_is_read_only_and_routes_config_questions(monkeypatch):
    import campaign_assistant
    from evaluation import store

    monkeypatch.setattr(store, "list_incidents", lambda _campaign_id: _async_value([]))
    result = await campaign_assistant.answer_campaign_question({
        "campaign_id": "ORD-QA", "title": "ZPlay", "lifecycle": "completed",
        "order": {
            "objective": "awareness", "budget": 80_000_000,
            "daily_budget": 10_000_000, "daily_budget_source": "derived",
            "placement_count": 2, "creative_count": 1,
        },
    }, "Ngân sách và creative đang thế nào?")

    assert result["read_only"] is True
    assert result["target_tab"] == "setup"
    assert "ước tính" in result["answer"]
    assert "không" not in result or "mutation" not in result


@pytest.mark.asyncio
async def test_campaign_assistant_reports_open_incident_without_mutation(monkeypatch):
    import campaign_assistant
    from evaluation import store

    incidents = [{
        "incident_id": "INC-123", "issue_type": "ctr_regression",
        "severity": "high", "state": "investigating",
    }]
    monkeypatch.setattr(store, "list_incidents", lambda _campaign_id: _async_value(incidents))
    result = await campaign_assistant.answer_campaign_question({
        "campaign_id": "ORD-QA", "title": "ZPlay", "lifecycle": "active",
        "order": {},
    }, "Có incident nào không?")

    assert result["target_tab"] == "evaluation"
    assert "INC-123" in result["answer"]
    assert result["read_only"] is True


async def _async_value(value):
    return value
