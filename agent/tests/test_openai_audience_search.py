import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        outcome = (
            self.parsed[len(self.calls) - 1]
            if isinstance(self.parsed, list)
            else self.parsed
        )
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(id="resp-plan", output_parsed=outcome)


class _FakeClient:
    def __init__(self, parsed):
        self.responses = _FakeResponses(parsed)


@pytest.mark.asyncio
async def test_audience_search_plan_is_semantic_bounded_and_id_free(monkeypatch):
    import openai_campaign.audience_search as search
    from config import config

    parsed = search.AudienceSearchPlan(
        industry_queries=["agriculture industry", "fertilizer distribution"],
        buyer_queries=["farm owners", "agricultural input dealers"],
        product_queries=["crop nutrition"],
        audience_queries=["commercial farmers"],
        excluded_concepts=["home gardening hobbyists"],
        creative_only_concepts=["cow drinking milk"],
    )
    client = _FakeClient(parsed)
    log = AsyncMock()
    monkeypatch.setattr(search, "alog", log)
    monkeypatch.setattr(
        config, "AUDIENCE_QUERY_PLANNER_MODEL", "gpt-5.4-mini"
    )

    result = await search.plan_audience_search(
        "session-private",
        {
            "brand": "GreenFarm",
            "objective": "conversion",
            "notes": (
                "B2B fertilizer for farms and dealers; exclude home gardeners. "
                "Creative: cow drinking milk."
            ),
        },
        client=client,
    )

    assert result["queries"] == [
        "crop nutrition",
        "commercial farmers",
        "farm owners",
        "agriculture industry",
        "agricultural input dealers",
        "fertilizer distribution",
    ]
    assert result["query_specs"][0] == {
        "query": "crop nutrition", "kind": "product",
    }
    assert result["query_specs"][1] == {
        "query": "commercial farmers", "kind": "audience",
    }
    assert result["creative_only_concepts"] == ["cow drinking milk"]
    call = client.responses.calls[0]
    assert call["text_format"] is search.AudienceSearchPlan
    assert call["model"] == "gpt-5.4-mini"
    assert call["store"] is False
    assert "audience IDs" in call["instructions"]
    payload = json.loads(call["input"])
    assert payload["brief"]["brand"] == "GreenFarm"
    assert "session-private" not in call["input"]
    assert "session-private" not in call["safety_identifier"]
    log.assert_awaited_once()


@pytest.mark.asyncio
async def test_audience_search_plan_fails_closed_to_deterministic_focused_query(monkeypatch):
    import openai_campaign.audience_search as search

    client = _FakeClient(None)
    monkeypatch.setattr(search, "alog", AsyncMock())

    result = await search.plan_audience_search(
        "session-failure",
        {"brand": "GreenFarm", "notes": "B2B fertilizer"},
        client=client,
    )

    assert result["applied"] is False
    assert result["queries"] == []
    assert result["reason"] == "provider_or_validation_failure"
    assert len(client.responses.calls) == 2


@pytest.mark.asyncio
async def test_audience_search_plan_cache_avoids_repeating_same_model_call(monkeypatch):
    import openai_campaign.audience_search as search
    from config import config

    search.reset_audience_search_for_test()
    client = _FakeClient(search.AudienceSearchPlan(
        industry_queries=["agriculture industry"],
    ))
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(search, "_get_client", lambda: client)
    monkeypatch.setattr(search, "alog", AsyncMock())
    brief = {"brand": "GreenFarm", "notes": "B2B fertilizer for farms"}

    first = await search.plan_audience_search("session-one", brief)
    second = await search.plan_audience_search("session-two", brief)

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert len(client.responses.calls) == 1


def test_audience_search_query_budget_preserves_all_four_signal_groups():
    import openai_campaign.audience_search as search

    plan = search.AudienceSearchPlan(
        industry_queries=["industry 1", "industry 2", "industry 3"],
        buyer_queries=["buyer 1", "buyer 2", "buyer 3"],
        product_queries=["product 1", "product 2", "product 3"],
        audience_queries=["audience 1", "audience 2", "audience 3"],
    )

    assert search._queries(plan) == [
        "product 1", "audience 1", "buyer 1", "industry 1",
        "product 2", "audience 2", "buyer 2", "industry 2",
        "product 3", "audience 3", "buyer 3", "industry 3",
    ]


@pytest.mark.asyncio
async def test_audience_search_rejects_obviously_vague_brief_without_model_call(
    monkeypatch,
):
    import openai_campaign.audience_search as search

    client = _FakeClient(search.AudienceSearchPlan())
    log = AsyncMock()
    monkeypatch.setattr(search, "alog", log)

    result = await search.plan_audience_search(
        "session-vague",
        {
            "brand": "Nova",
            "objective": "awareness",
            "kpi": "Tăng nhận diện",
            "notes": "Muốn tìm thêm khách hàng phù hợp cho sản phẩm mới.",
        },
        client=client,
    )

    assert result["information_sufficient"] is False
    assert result["queries"] == []
    assert result["insufficient_reason"] == (
        "brief_missing_product_or_audience_evidence"
    )
    assert client.responses.calls == []
    log.assert_awaited_once()


@pytest.mark.asyncio
async def test_audience_search_retries_once_after_malformed_structured_output(
    monkeypatch,
):
    import openai_campaign.audience_search as search

    parsed = search.AudienceSearchPlan(
        product_queries=["SUV"],
        audience_queries=["large families"],
    )
    client = _FakeClient([ValueError("invalid JSON"), parsed])
    log = AsyncMock()
    monkeypatch.setattr(search, "alog", log)

    result = await search.plan_audience_search(
        "session-retry",
        {
            "brand": "TerraDrive Auto",
            "notes": "Large SUV and pickup dealer for large families.",
        },
        client=client,
    )

    assert result["queries"] == ["SUV", "large families"]
    assert len(client.responses.calls) == 2
    assert "Retry: keep the JSON" in client.responses.calls[1]["instructions"]


@pytest.mark.asyncio
async def test_vietnamese_travel_evidence_cannot_be_suppressed_by_planner(
    monkeypatch,
):
    import openai_campaign.audience_search as search

    client = _FakeClient(search.AudienceSearchPlan(
        information_sufficient=False,
        insufficient_reason=(
            "Brand and awareness metrics do not identify a category."
        ),
    ))
    monkeypatch.setattr(search, "alog", AsyncMock())

    result = await search.plan_audience_search(
        "session-vietjet-regression",
        {
            "brand": "Vietjet Air",
            "objective": "awareness",
            "kpi": "Reach, VTR",
            "notes": (
                "Đối tượng 20–45 tuổi, thích du lịch và săn vé máy bay giá rẻ"
            ),
        },
        client=client,
    )

    assert result["information_sufficient"] is True
    assert result["planner_information_sufficient"] is False
    assert result["sufficiency_overridden"] is True
    assert result["queries"] == []
