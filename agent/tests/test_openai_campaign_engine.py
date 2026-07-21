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
async def test_static_faq_answers_without_live_or_mutation_tools(monkeypatch):
    import openai_campaign.engine as engine

    monkeypatch.setattr(engine, "decide_turn", AsyncMock(return_value=_decision()))
    client = _Client([_response(text="Frequency cap giúp tránh lặp quảng cáo quá mức.")])

    result = await engine.handle_openai_freeform(
        "Frequency cap là gì?", 0, "openai-static-faq", client=client,
    )

    assert result.meta.model == "gpt-5.4-mini"
    assert result.meta.tool == "openai_freeform_chat"
    assert "Frequency cap" in result.text
    call = client.responses.calls[0]
    assert call["store"] is False
    assert call["tool_choice"] == "none"
    assert all(tool["name"] != "propose_workspace_change" for tool in call["tools"])


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
