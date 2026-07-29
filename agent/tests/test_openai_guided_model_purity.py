from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _ParsedResponses:
    def __init__(self, parsed):
        self.parsed = list(parsed)
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id=f"resp_{len(self.calls)}",
            output_parsed=self.parsed.pop(0),
            usage=SimpleNamespace(
                input_tokens=10, output_tokens=5, total_tokens=15,
            ),
        )


class _Client:
    def __init__(self, parsed):
        self.responses = _ParsedResponses(parsed)


def test_openai_component_has_no_greennode_model_imports():
    package = Path(__file__).parents[1] / "openai_campaign"
    source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
    forbidden = (
        "from llm import", "import llm", "graph.structured",
        "handlers.brief", "handlers.audience", "handlers.freeform",
    )
    assert not [token for token in forbidden if token in source]


@pytest.mark.asyncio
async def test_guided_dispatch_never_calls_other_provider():
    from campaign_engines.dispatcher import dispatch_guided
    from campaign_models import GREENNODE_MINIMAX, OPENAI_GPT_5_4_MINI

    calls = []

    async def green(**_kwargs):
        calls.append("green")
        return "green"

    async def openai(**_kwargs):
        calls.append("openai")
        return "openai"

    assert await dispatch_guided(
        OPENAI_GPT_5_4_MINI,
        greennode_handler=green,
        openai_handler=openai,
    ) == "openai"
    assert calls == ["openai"]

    calls.clear()
    assert await dispatch_guided(
        GREENNODE_MINIMAX,
        greennode_handler=green,
        openai_handler=openai,
    ) == "green"
    assert calls == ["green"]


@pytest.mark.asyncio
async def test_router_dispatches_openai_guided_forms_before_legacy_handlers(monkeypatch):
    from starlette.requests import Request

    import identity
    import openai_campaign.guided as guided
    import router
    from campaign_models import OPENAI_GPT_5_4_MINI
    from models import AgentResponse, ChatRequest, ResponseMeta

    async def allow_access(_request, _session_id):
        return None

    async def model_lock(_session_id):
        return {"conversation_model": OPENAI_GPT_5_4_MINI}

    green_brief = AsyncMock(side_effect=AssertionError("legacy brief handler called"))
    green_audience = AsyncMock(side_effect=AssertionError("legacy audience handler called"))
    openai_brief = AsyncMock(return_value=AgentResponse(
        text="openai brief",
        meta=ResponseMeta(tool="openai_brief_handler", model="gpt-5.4-mini", step=0),
    ))
    openai_audience = AsyncMock(return_value=AgentResponse(
        text="openai audience",
        meta=ResponseMeta(tool="openai_audience_handler", model="gpt-5.4-mini", step=1),
    ))
    monkeypatch.setattr(router, "_assert_session_access", allow_access)
    monkeypatch.setattr(identity, "get_conversation_model_for_session", model_lock)
    monkeypatch.setattr(router, "handle_brief", green_brief)
    monkeypatch.setattr(router, "handle_audience", green_audience)
    monkeypatch.setattr(guided, "handle_openai_brief", openai_brief)
    monkeypatch.setattr(guided, "handle_openai_audience", openai_audience)
    request = Request({
        "type": "http", "method": "POST", "path": "/api/agent/chat",
        "headers": [], "query_string": b"", "scheme": "http",
        "client": ("test", 1), "server": ("test", 80),
    })

    brief_result = await router.chat.__wrapped__(request, ChatRequest(
        session_id="openai-router-guided", step=0,
        formData={"brief": {
            "brand": "Mixifood", "objective": "awareness", "budget": 10,
            "startDate": "2026-08-20", "endDate": "2026-08-22",
        }},
    ))
    audience_result = await router.chat.__wrapped__(request, ChatRequest(
        session_id="openai-router-guided", step=1,
        formData={"segment": {"attrs": [{"segmentId": "INT158"}]}},
    ))

    assert brief_result.meta.tool == "openai_brief_handler"
    assert audience_result.meta.tool == "openai_audience_handler"
    openai_brief.assert_awaited_once()
    openai_audience.assert_awaited_once()
    green_brief.assert_not_awaited()
    green_audience.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_brief_and_audience_use_only_openai_structured_calls(monkeypatch):
    import llm
    from models import BriefData, SegmentData
    from openai_campaign.guided import (
        _AudienceAnalysis,
        _BriefAnalysis,
        handle_openai_audience,
        handle_openai_brief,
    )

    forbidden = AsyncMock(side_effect=AssertionError("GreenNode must not be called"))
    monkeypatch.setattr(llm, "chat_completion", forbidden)
    monkeypatch.setattr(llm, "force_text_completion", forbidden)
    monkeypatch.setattr(llm, "simple_generate", forbidden)
    client = _Client([
        _BriefAnalysis(
            summary="Brief phù hợp cho chiến dịch awareness.",
            audience_hint=["Người yêu ẩm thực"],
            warnings=[],
            suggested_kpis=["Reach"],
        ),
        _AudienceAnalysis(
            reasoning="Segment phù hợp với sản phẩm.",
            match_quality="excellent",
            segment_notes=[],
            warnings=[],
        ),
    ])

    brief = BriefData(
        brand="Mixifood", objective="awareness", kpi="Reach",
        budget=10, startDate="2026-08-20", endDate="2026-08-22",
        notes="Đồ ăn vặt",
    )
    brief_result = await handle_openai_brief(
        brief, "openai-guided-pure", client=client,
    )
    audience_result = await handle_openai_audience(
        SegmentData(attrs=[{
            "segmentId": "INT158", "fullLabel": "Fast food",
            "type": "Interest", "sizeMin": 1000, "sizeMax": 2000,
        }]),
        "openai-guided-pure",
        client=client,
    )

    assert brief_result.meta.model == "gpt-5.4-mini"
    assert audience_result.meta.model == "gpt-5.4-mini"
    assert len(client.responses.calls) == 2
    assert all(call["store"] is False for call in client.responses.calls)
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_targeting_evaluates_advanced_catalog_dimensions():
    import json

    from openai_campaign.guided import (
        _TargetingReason,
        _TargetingSelection,
        _recommend_targeting,
    )

    client = _Client([_TargetingSelection(
        targeting={
            "geo": ["TP.HCM"],
            "age": ["25-34"],
            "gender": ["Male", "Female"],
            "deviceOS": ["Android"],
            "interest": ["Automotive"],
        },
        reasoning=[
            _TargetingReason(
                field="interest",
                picks=["Automotive"],
                reason="Sản phẩm dành cho xe ô tô.",
            ),
        ],
    )])
    options = {
        "geo": {"Miền Nam": ["TP.HCM"]},
        "age": ["25-34"],
        "gender": ["Male", "Female"],
        "deviceOS": ["Android", "iOS"],
        "interest": ["Automotive", "Travel"],
    }

    targeting, reasoning, model = await _recommend_targeting(
        "openai-targeting-structured",
        {
            "brand": "Zalo",
            "objective": "awareness",
            "notes": "AI Agent Kiki dành cho xe ô tô.",
            "strategy": "reach_first",
        },
        options,
        [{
            "fullLabel": "Automotive",
            "category": "Interest",
            "tier": "recommended",
            "reason": "Quan tâm xe ô tô.",
        }],
        client=client,
    )

    assert targeting["deviceOS"] == ["Android"]
    assert targeting["interest"] == ["Automotive"]
    assert reasoning[0]["field"] == "interest"
    assert model == "gpt-5.4-mini"
    call = client.responses.calls[0]
    payload = json.loads(call["input"])
    assert payload["brief"]["strategy"] == "reach_first"
    assert payload["selected_segments"][0] == {
        "label": "Automotive",
        "category": "Interest",
        "tier": "recommended",
        "reason": "Quan tâm xe ô tô.",
    }
    assert payload["catalog_options"]["interest"] == ["Automotive", "Travel"]
    assert "advanced dimensions" in call["instructions"]


@pytest.mark.asyncio
async def test_guided_audience_requests_brief_detail_instead_of_guessing(monkeypatch):
    import openai_campaign.guided as guided

    async def vague_recommendation(*_args, **_kwargs):
        return {
            "recommendations": [],
            "adjacent_recommendations": [],
            "rag": {
                "information_sufficient": False,
                "insufficient_reason": "brief_missing_product_or_audience_evidence",
            },
        }

    monkeypatch.setattr(
        guided, "handle_openai_dmp_recommend", vague_recommendation,
    )
    monkeypatch.setattr(guided, "log_event", AsyncMock())

    result = await guided._grounded_audience_entry(
        "guided-vague-brief",
        {
            "brand": "Nova",
            "objective": "awareness",
            "kpi": "Tăng nhận diện",
            "notes": "Muốn tìm thêm khách hàng phù hợp cho sản phẩm mới.",
        },
    )

    assert result["need_more_info"] is True
    assert result["meta"]["tool"] == "audience_entry_clarification"
    assert "chưa có đủ thông tin" in result["text"]
    assert "chưa chọn segment nào" in result["blocks"][0]["text"]


@pytest.mark.asyncio
async def test_openai_dmp_full_catalog_never_uses_legacy_selector(monkeypatch):
    import llm
    import openai_campaign.guided as guided
    from openai_campaign.guided import _DmpRecommendation, _DmpSelection

    forbidden = AsyncMock(side_effect=AssertionError("GreenNode must not be called"))
    monkeypatch.setattr(llm, "simple_generate", forbidden)
    monkeypatch.setattr(guided.config, "USE_RAG_AUDIENCE", False)
    monkeypatch.setattr(guided, "get_all_segments", AsyncMock(return_value=[
        {
            "segmentId": "INT158", "fullLabel": "Fast food",
            "type": "Interest", "sizeMin": 1000, "sizeMax": 2000,
        },
        {
            "segmentId": "INT202", "fullLabel": "Snack foods",
            "type": "Interest", "sizeMin": 800, "sizeMax": 1200,
        },
    ]))
    client = _Client([_DmpSelection(recommendations=[
        _DmpRecommendation(fullLabel="Fast food", reason="Khớp với sản phẩm"),
        _DmpRecommendation(fullLabel="Not in catalog", reason="Phải bị loại"),
    ])])

    result = await guided.handle_openai_dmp_recommend(
        "openai-dmp-pure",
        brief_override={"brand": "Mixifood", "objective": "awareness"},
        client=client,
    )

    assert [item["segmentId"] for item in result["recommendations"]] == ["INT158"]
    assert result["provenance"] == {
        "provider": "openai", "model": "gpt-5.4-mini",
    }
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_rag_uses_one_scored_specialist_without_selector(monkeypatch):
    import openai_campaign.guided as guided

    captured = {}

    async def fake_rag(session_id, brief, **kwargs):
        captured.update(kwargs)
        return {
            "recommendations": [{
                "segmentId": "INT158", "fullLabel": "Fast food",
                "reason": "Relevant",
            }],
            "total_segments": 310,
            "rag": {"queries": ["Mixifood"], "selector": "openai_nano_scores"},
        }

    import rag.recommend as rag_recommend
    monkeypatch.setattr(rag_recommend, "recommend_rag", fake_rag)
    monkeypatch.setattr(guided.config, "USE_RAG_AUDIENCE", True)
    monkeypatch.setattr(
        guided.config, "AUDIENCE_RERANK_MODE", "openai_nano"
    )
    result = await guided.handle_openai_dmp_recommend(
        "openai-rag-pure",
        brief_override={"brand": "Mixifood", "objective": "awareness"},
    )

    assert captured["provider"] == "openai"
    assert captured["rerank_mode"] == "openai_nano"
    assert captured["use_focused_query"] is True
    assert captured["enable_query_rewrite"] is True
    assert captured["include_raw_query"] is False
    assert captured["select_from_rerank_scores"] is True
    assert "selector" not in captured
    assert callable(captured["query_rewriter"])
    assert result["rag"]["queries"] == ["Mixifood"]
