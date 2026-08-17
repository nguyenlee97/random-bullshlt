import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _Responses:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _Client:
    def __init__(self, outputs):
        self.responses = _Responses(outputs)


def _response(*, output=None, text="", response_id="resp_test"):
    return SimpleNamespace(
        id=response_id,
        output=list(output or []),
        output_text=text,
    )


def _decision(**overrides):
    from openai_campaign.schemas import TurnDecision

    payload = {
        "turn_type": "faq",
        "user_goal": "Answer an advertising question",
        "subrequests": [{
            "kind": "question",
            "description": "Explain the topic",
            "requires_live_data": False,
            "requested_capability": "",
        }],
        "faq_scope": "static_knowledge",
        "workflow_action": "none",
        "would_mutate_workspace": False,
        "confidence": 0.95,
    }
    payload.update(overrides)
    return TurnDecision.model_validate(payload)


@pytest.mark.asyncio
async def test_static_faq_is_grounded_without_live_or_mutation_tools(monkeypatch):
    import openai_campaign.engine as engine

    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=_decision()))
    client = _Client([
        _response(output=[{
            "type": "function_call", "call_id": "call-kb",
            "name": "search_ad_knowledge",
            "arguments": json.dumps({"query": "frequency cap"}),
        }]),
        _response(text="Frequency cap giúp tránh lặp quảng cáo quá mức [ad-operations-faq, 2026-07-21.1]."),
    ])

    result = await engine.handle_openai_freeform(
        "Frequency cap là gì?", 0, "openai-static-faq", client=client,
    )

    assert result.meta.model == "gpt-5.4-mini"
    assert result.meta.tool == "search_ad_knowledge"
    assert "Frequency cap" in result.text
    first, final = client.responses.calls
    assert first["store"] is False
    assert first["tool_choice"] == "required"
    assert final["tool_choice"] == "none"
    assert all(tool["name"] != "propose_workspace_change" for tool in first["tools"])


@pytest.mark.asyncio
async def test_live_faq_runs_function_call_round_trip(monkeypatch):
    import openai_campaign.engine as engine
    import openai_campaign.tools as openai_tools

    decision = _decision(
        faq_scope="live_system",
        subrequests=[{
            "kind": "read",
            "description": "Check zone availability",
            "requires_live_data": True,
            "requested_capability": "search_zones",
        }],
    )
    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=decision))
    executor = AsyncMock(return_value={
        "zones": [{"id": "ZN-001", "is_booked": False}], "total": 1,
    })
    monkeypatch.setattr(openai_tools, "execute_tool", executor)
    client = _Client([
        _response(output=[{
            "type": "function_call",
            "call_id": "call-zone",
            "name": "search_zones",
            "arguments": json.dumps({
                "query": "znews", "objective": None,
                "start_date": None, "end_date": None,
            }),
        }]),
        _response(text="ZN-001 đang trống trong thời gian campaign."),
    ])

    result = await engine.handle_openai_freeform(
        "Zone ZNews nào đang trống?",
        3,
        "openai-live-faq",
        workspace={"brief": {"startDate": "2026-07-22", "endDate": "2026-07-30"}},
        client=client,
    )

    assert result.meta.tool == "search_zones"
    assert len(client.responses.calls) == 2
    assert client.responses.calls[0]["tool_choice"] == "required"
    assert client.responses.calls[1]["tool_choice"] == "none"
    second_input = client.responses.calls[1]["input"]
    assert any(
        item.get("type") == "function_call_output"
        and item.get("call_id") == "call-zone"
        for item in second_input
    )
    called_args = executor.await_args.args[1]
    assert called_args["start_date"] == "2026-07-22"
    assert called_args["end_date"] == "2026-07-30"


@pytest.mark.asyncio
async def test_multi_topic_audience_lookup_is_read_only_and_uses_separate_queries(monkeypatch):
    import openai_campaign.engine as engine
    import openai_campaign.tools as openai_tools
    from session import get_pending_proposal

    decision = _decision(
        faq_scope="catalog_discovery",
        subrequests=[{
            "kind": "read",
            "description": "Find coffee, beverage and office-worker audiences",
            "requires_live_data": True,
            "requested_capability": "search_audience_catalog",
        }],
    )
    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=decision))

    async def catalog_search(query, *, type_filter, limit):
        rows = {
            "coffee": [{
                "segmentId": "INT131", "fullLabel": "Coffee (food & drink)",
                "type": "Interest", "sizeMin": 147_000_000, "sizeMax": 165_000_000,
                "sizeEstimatedAt": "2026-07-21T00:00:00Z",
            }],
            "beverages": [{
                "segmentId": "INT130", "fullLabel": "Beverages (food & drink)",
                "type": "Interest", "sizeMin": 120_000_000, "sizeMax": 140_000_000,
                "sizeEstimatedAt": "2026-07-21T00:00:00Z",
            }],
            "office workers": [],
        }
        return rows[query]

    monkeypatch.setattr(openai_tools, "search_audience", catalog_search)
    client = _Client([
        _response(output=[{
            "type": "function_call", "call_id": "call-audiences",
            "name": "search_audience_catalog",
            "arguments": json.dumps({
                "queries": ["coffee", "beverages", "office workers"],
                "type": None,
            }),
        }]),
        _response(text=(
            "Tìm thấy INT131 và INT130; catalog chưa có nhóm khớp trực tiếp "
            "với office workers. Em chưa chọn nhóm nào."
        )),
    ])

    result = await engine.handle_openai_freeform(
        "Bây giờ tìm giúp tôi các audience hiện có liên quan tới cà phê, đồ uống "
        "và dân văn phòng. Cho tôi ID, khoảng size và độ mới dữ liệu, nhưng vẫn "
        "chưa chọn nhóm nào.",
        1,
        "openai-multi-topic-audience",
        client=client,
    )

    assert result.meta.tool == "search_audience_catalog"
    assert "INT131" in result.text and "INT130" in result.text
    assert await get_pending_proposal("openai-multi-topic-audience") is None
    assert all(
        tool["name"] != "propose_workspace_change"
        for tool in client.responses.calls[0]["tools"]
    )
    final_input = client.responses.calls[1]["input"]
    tool_output = next(
        json.loads(item["output"])
        for item in final_input
        if item.get("type") == "function_call_output"
    )
    assert [item["query"] for item in tool_output["query_results"]] == [
        "coffee", "beverages", "office workers",
    ]
    assert tool_output["unmatched_queries"] == ["office workers"]


@pytest.mark.asyncio
async def test_mutation_creates_visible_proposal_without_applying(monkeypatch):
    import openai_campaign.engine as engine
    from session import get_pending_proposal
    from workspace.service import apply_mutation, get_workspace

    workspace = await get_workspace("openai-proposal")
    await apply_mutation(
        "openai-proposal",
        "brief",
        {
            "brand": "Original", "objective": "awareness", "kpi": "Reach",
            "budget": 10, "startDate": "2026-08-20", "endDate": "2026-08-22",
            "notes": "Food lovers",
        },
        base_revision=workspace["revision"],
        actor="test",
        idempotency_key="openai-existing-brief",
    )

    decision = _decision(
        turn_type="workflow_action",
        user_goal="Change the brand to Acme",
        subrequests=[{
            "kind": "mutation",
            "description": "Change the campaign brand",
            "requires_live_data": False,
            "requested_capability": "update_brief",
        }],
        faq_scope="none",
        workflow_action="update_brief",
        would_mutate_workspace=True,
    )
    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=decision))
    client = _Client([
        _response(output=[{
            "type": "function_call",
            "call_id": "call-proposal",
            "name": "propose_workspace_change",
            "arguments": json.dumps({
                "field": "brief.brand",
                "value_json": json.dumps("Acme"),
                "reason": "Use the requested brand",
            }),
        }]),
        _response(text="Em đã chuẩn bị đề xuất đổi brand sang Acme; chưa áp dụng."),
    ])

    result = await engine.handle_openai_freeform(
        "Đổi brand thành Acme", 0, "openai-proposal", client=client,
    )

    workspace = await get_workspace("openai-proposal")
    pending = await get_pending_proposal("openai-proposal")
    assert workspace["revision"] == 1
    assert workspace["artifacts"]["brief"]["value"]["brand"] == "Original"
    assert pending["field"] == "brief.brand"
    assert pending["value"] == "Acme"
    assert result.workspace_update is None
    assert result.blocks[0]["type"] == "workspace_proposal"
    assert result.blocks[0]["changes"]["proposal_id"]
    assert client.responses.calls[0]["tool_choice"] == "required"
    assert client.responses.calls[1]["tool_choice"] == "none"


@pytest.mark.asyncio
async def test_new_later_approval_request_creates_audience_proposal_when_none_pending(monkeypatch):
    import openai_campaign.engine as engine
    from session import get_pending_proposal
    from workspace.service import get_workspace

    session_id = "openai-create-later-audience"
    decision = _decision(
        turn_type="mixed",
        user_goal="Explain overlap and create a two-audience proposal for later approval",
        subrequests=[
            {
                "kind": "question", "description": "Explain audience overlap",
                "requires_live_data": False, "requested_capability": "",
            },
            {
                "kind": "mutation", "description": "Propose both audiences",
                "requires_live_data": False, "requested_capability": "select_audience",
            },
        ],
        faq_scope="none",
        workflow_action="select_audience",
        would_mutate_workspace=True,
    )
    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=decision))
    client = _Client([
        _response(output=[{
            "type": "function_call", "call_id": "call-audience-proposal",
            "name": "propose_workspace_change",
            "arguments": json.dumps({
                "field": "segment",
                "value_json": json.dumps({"attrs": ["INT131", "INT130"]}),
                "reason": "Create both audience selections for later confirmation",
            }),
        }]),
        _response(text=(
            "Hai nhóm có overlap vừa phải. Em đã tạo đề xuất chọn cả hai, "
            "nhưng chưa áp dụng và đang chờ xác nhận."
        )),
    ])

    result = await engine.handle_openai_freeform(
        "Hai nhóm đó có bị overlap nhiều không? Hãy giải thích ngắn gọn, đồng "
        "thời tạo đề xuất chọn cả hai cho campaign, nhưng chưa áp dụng cho tới "
        "khi tôi xác nhận.",
        1,
        session_id,
        client=client,
    )

    pending = await get_pending_proposal(session_id)
    unchanged = await get_workspace(session_id)
    assert pending["field"] == "segment"
    assert [item["segmentId"] for item in pending["value"]["attrs"]] == [
        "INT131", "INT130",
    ]
    assert unchanged["revision"] == 0
    assert unchanged["artifacts"]["audience"]["status"] == "missing"
    assert result.blocks[0]["type"] == "workspace_proposal"
    assert result.workspace_update is None


@pytest.mark.asyncio
async def test_created_proposal_stays_visible_when_final_summary_fails(monkeypatch):
    import openai_campaign.engine as engine
    from session import get_pending_proposal
    from workspace.service import apply_mutation, get_workspace

    workspace = await get_workspace("openai-proposal-fallback")
    await apply_mutation(
        "openai-proposal-fallback",
        "brief",
        {
            "brand": "Original", "objective": "awareness", "kpi": "Reach",
            "budget": 10, "startDate": "2026-08-20", "endDate": "2026-08-22",
            "notes": "Food lovers",
        },
        base_revision=workspace["revision"],
        actor="test",
        idempotency_key="openai-existing-brief-fallback",
    )

    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=_decision(
        turn_type="workflow_action",
        user_goal="Change the brand to Acme",
        subrequests=[{
            "kind": "mutation", "description": "Change brand",
            "requires_live_data": False, "requested_capability": "update_brief",
        }],
        faq_scope="none",
        workflow_action="update_brief",
        would_mutate_workspace=True,
    )))
    client = _Client([
        _response(output=[{
            "type": "function_call", "call_id": "call-proposal-fallback",
            "name": "propose_workspace_change",
            "arguments": json.dumps({
                "field": "brief.brand", "value_json": json.dumps("Acme"),
                "reason": "Requested brand",
            }),
        }]),
        RuntimeError("summary unavailable"),
    ])

    result = await engine.handle_openai_freeform(
        "Đổi brand thành Acme", 0, "openai-proposal-fallback", client=client,
    )

    assert result.blocks[0]["type"] == "workspace_proposal"
    assert "chưa áp dụng" in result.text
    assert (await get_pending_proposal("openai-proposal-fallback"))["value"] == "Acme"


@pytest.mark.asyncio
async def test_semantic_approval_applies_only_existing_pending_proposal(monkeypatch):
    import openai_campaign.engine as engine
    from session import get_pending_proposal, set_pending_proposal
    from workspace.service import create_proposal, get_workspace

    workspace = await get_workspace("openai-approve")
    proposal = await create_proposal(
        "openai-approve", "brief.brand", "Acme",
        base_revision=workspace["revision"], actor="test", reason="Requested",
    )
    await set_pending_proposal("openai-approve", {
        "field": "brief.brand", "value": "Acme",
        "proposal_id": proposal["proposal_id"],
    })
    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=_decision(
        turn_type="workflow_action",
        user_goal="Approve the visible proposal",
        subrequests=[{
            "kind": "mutation", "description": "Approve proposal",
            "requires_live_data": False, "requested_capability": "approve",
        }],
        faq_scope="none",
        workflow_action="approve",
        would_mutate_workspace=True,
    )))
    client = _Client([])

    result = await engine.handle_openai_freeform(
        "Ừ, dùng đề xuất đó", 0, "openai-approve", client=client,
    )

    updated = await get_workspace("openai-approve")
    assert updated["revision"] == 1
    assert updated["artifacts"]["brief"]["value"]["brand"] == "Acme"
    assert await get_pending_proposal("openai-approve") is None
    assert result.workspace_update["field"] == "brief.brand"
    assert client.responses.calls == []


@pytest.mark.asyncio
async def test_negated_approval_defers_then_later_applies_same_audience_proposal(monkeypatch):
    import openai_campaign.engine as engine
    from session import get_pending_proposal, set_pending_proposal
    from workspace.service import create_proposal, get_workspace

    session_id = "openai-defer-audience"
    audience = {
        "attrs": [
            {
                "_id": "catalog-coffee", "segmentId": "INT131",
                "fullLabel": "Coffee (food & drink)",
            },
            {
                "_id": "catalog-beverages", "segmentId": "INT130",
                "fullLabel": "Beverages (food & drink)",
            },
        ],
        "reach": {
            "unique_reach": 6_900_219,
            "range": {"min": 6_057_100, "max": 7_739_889},
            "method": "calibrated_estimate",
        },
    }
    workspace = await get_workspace(session_id)
    proposal = await create_proposal(
        session_id,
        "segment",
        audience,
        base_revision=workspace["revision"],
        actor="test",
        reason="Select the two catalog-grounded audiences",
    )
    await set_pending_proposal(session_id, {
        "field": "segment",
        "value": audience,
        "proposal_id": proposal["proposal_id"],
    })
    defer = _decision(
        turn_type="workflow_action",
        user_goal="Keep the proposal pending; do not apply it yet",
        subrequests=[{
            "kind": "mutation", "description": "Defer the pending proposal",
            "requires_live_data": False, "requested_capability": "defer",
        }],
        faq_scope="none",
        workflow_action="defer",
        would_mutate_workspace=False,
    )
    approve = _decision(
        turn_type="workflow_action",
        user_goal="Apply the pending audience proposal now",
        subrequests=[{
            "kind": "mutation", "description": "Approve the pending proposal",
            "requires_live_data": False, "requested_capability": "approve",
        }],
        faq_scope="none",
        workflow_action="approve",
        would_mutate_workspace=True,
    )
    monkeypatch.setattr(
        engine, "decide_turn", AsyncMock(side_effect=[defer, approve]),
    )
    client = _Client([])

    deferred = await engine.handle_openai_freeform(
        "Tôi đồng ý với phần giải thích, nhưng chưa đồng ý áp dụng hai audience đó.",
        1,
        session_id,
        client=client,
    )

    pending = await get_pending_proposal(session_id)
    unchanged = await get_workspace(session_id)
    assert deferred.meta.tool == "workspace_deferred"
    assert "vẫn được giữ ở trạng thái chờ" in deferred.text
    assert pending["proposal_id"] == proposal["proposal_id"]
    assert unchanged["revision"] == 0
    assert unchanged["artifacts"]["audience"]["status"] == "missing"
    assert unchanged["artifacts"]["audience"]["value"] is None

    applied = await engine.handle_openai_freeform(
        "Xác nhận áp dụng đúng đề xuất audience đang chờ.",
        1,
        session_id,
        client=client,
    )

    updated = await get_workspace(session_id)
    selected = updated["artifacts"]["audience"]["value"]
    assert updated["revision"] == 1
    assert [item["segmentId"] for item in selected["attrs"]] == ["INT131", "INT130"]
    assert applied.meta.tool == "workspace_confirmed"
    assert applied.workspace_update["proposal_id"] == proposal["proposal_id"]
    assert await get_pending_proposal(session_id) is None
    assert client.responses.calls == []


@pytest.mark.asyncio
async def test_low_confidence_turn_never_calls_answer_or_tools(monkeypatch):
    import openai_campaign.engine as engine

    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=_decision(
        turn_type="workflow_action",
        user_goal="Unclear change",
        workflow_action="other",
        would_mutate_workspace=True,
        needs_clarification=True,
        clarification_question="Anh/chị muốn đổi phần nào?",
        confidence=0.4,
    )))
    client = _Client([])

    result = await engine.handle_openai_freeform(
        "Đổi cái đó", 0, "openai-clarify", client=client,
    )

    assert result.meta.tool == "semantic_clarification"
    assert result.text == "Anh/chị muốn đổi phần nào?"
    assert client.responses.calls == []


@pytest.mark.asyncio
async def test_openai_provider_failure_does_not_call_greennode_or_mutate(monkeypatch):
    import llm
    import openai_campaign.engine as engine
    from workspace.service import get_workspace

    green = AsyncMock(side_effect=AssertionError("GreenNode must not be called"))
    monkeypatch.setattr(llm, "chat_completion", green)
    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=_decision()))
    client = _Client([RuntimeError("OpenAI unavailable")])

    result = await engine.handle_openai_freeform(
        "Giải thích KPI", 0, "openai-failure", client=client,
    )

    workspace = await get_workspace("openai-failure")
    assert result.meta.tool == "openai_provider_unavailable"
    assert workspace["revision"] == 0
    green.assert_not_called()


def test_openai_tool_schemas_are_strict_and_do_not_accept_owner_identity():
    from openai_campaign.tools import OPENAI_TOOL_DEFINITIONS

    serialized = json.dumps(OPENAI_TOOL_DEFINITIONS).lower()
    for forbidden in ("owner_id", "user_id", "identity_id", "account_session_id"):
        assert forbidden not in serialized
    for tool in OPENAI_TOOL_DEFINITIONS:
        assert tool["strict"] is True
        schema = tool["parameters"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_complete_campaign_engine_requires_explicit_runtime_configuration(monkeypatch):
    import openai_campaign.engine as engine
    from config import config

    monkeypatch.setattr(config, "OPENAI_CAMPAIGN_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    assert engine.OPENAI_GUIDED_FREEFORM_IMPLEMENTED is True
    assert engine.OPENAI_GUIDED_SPECIALISTS_IMPLEMENTED is True
    assert engine.OPENAI_AUTOPILOT_IMPLEMENTED is True
    assert engine.OPENAI_CAMPAIGN_ENGINE_IMPLEMENTED is True
    assert engine.openai_campaign_ready() is True
