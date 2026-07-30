from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class _SchemaResponses:
    def __init__(self, values):
        self.values = values
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        schema_name = kwargs["text_format"].__name__
        value = self.values[schema_name]
        if isinstance(value, dict):
            value = kwargs["text_format"].model_validate(value)
        return SimpleNamespace(
            id=f"resp_{schema_name}",
            output_parsed=value,
            usage=SimpleNamespace(
                input_tokens=20, output_tokens=10, total_tokens=30,
            ),
        )


class _Client:
    def __init__(self, values):
        self.responses = _SchemaResponses(values)


def _update_brief_decision():
    from openai_campaign.schemas import TurnDecision

    return TurnDecision.model_validate({
        "turn_type": "workflow_action",
        "user_goal": "Cập nhật brief từ thông tin người dùng cung cấp",
        "subrequests": [{
            "kind": "mutation",
            "description": "Cập nhật brand, ngân sách và thời gian chạy",
            "requires_live_data": False,
            "requested_capability": "propose_workspace_change",
        }],
        "faq_scope": "none",
        "workflow_action": "update_brief",
        "entities": [],
        "would_mutate_workspace": True,
        "needs_clarification": False,
        "clarification_question": "",
        "confidence": 0.95,
    })


def _clarification_decision():
    from openai_campaign.schemas import TurnDecision

    return TurnDecision.model_validate({
        "turn_type": "clarification",
        "user_goal": "Nhắc lại mục tiêu đã cung cấp",
        "subrequests": [],
        "faq_scope": "none",
        "workflow_action": "none",
        "entities": [],
        "would_mutate_workspace": False,
        "needs_clarification": True,
        "clarification_question": "Mục tiêu campaign là gì?",
        "confidence": 0.9,
    })


def test_openai_explicit_history_union_does_not_change_greennode_default():
    from graph.nodes.brief_collector import _explicit_advisory_missing_fields

    messages = [{
        "role": "user",
        "content": (
            "Objective Awareness, KPI Reach, audience là nông dân "
            "tại miền Tây."
        ),
    }]

    assert _explicit_advisory_missing_fields(
        {"messages": messages}, provided_fields=[],
    ) == ["objective", "kpi", "notes"]
    assert _explicit_advisory_missing_fields(
        {"messages": messages, "merge_explicit_text_evidence": True},
        provided_fields=[],
    ) == []


@pytest.mark.asyncio
async def test_openai_brief_correction_classified_as_clarification_stays_in_collector(
    monkeypatch,
):
    import graph.nodes.brief_collector as collector
    import openai_campaign.engine as engine
    from graph.nodes.brief_collector import BriefDelegationDecision, BriefIntakeTurn
    from session import get_pending_proposal

    forbidden = AsyncMock(side_effect=AssertionError("GreenNode structured call"))
    monkeypatch.setattr(collector, "structured", forbidden)
    monkeypatch.setattr(
        engine, "decide_turn", AsyncMock(return_value=_clarification_decision()),
    )
    client = _Client({
        "BriefIntakeTurn": BriefIntakeTurn(
            action="ask_clarification",
            message="Cần bổ sung Brief.",
            missing_fields=["objective", "kpi", "notes"],
        ),
        "BriefDelegationDecision": BriefDelegationDecision(
            mode="none", provided_fields=[], delegated_fields=[],
        ),
    })

    result = await engine.handle_openai_freeform(
        "Mục tiêu tôi đã nói ở trên là Awareness rồi.",
        0,
        "openai-objective-correction",
        client=client,
    )

    assert result.meta.tool == "freeform_chat"
    assert "Mục tiêu campaign" not in result.text
    assert "KPI mong muốn" in result.text
    assert "Đối tượng mục tiêu" in result.text
    assert await get_pending_proposal("openai-objective-correction") is None
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_tool_rejects_nested_initial_brief_proposal():
    from openai_campaign.tools import execute_openai_tool
    from workspace.intent import InvalidWorkspaceIntent
    from workspace.service import get_workspace, list_pending_proposals

    session_id = "openai-nested-initial-brief"
    with pytest.raises(InvalidWorkspaceIntent, match="toàn bộ field `brief`"):
        await execute_openai_tool(
            "propose_workspace_change",
            {
                "field": "brief.notes",
                "value_json": '"TP.HCM và các tỉnh lân cận"',
                "reason": "Bổ sung địa lý",
            },
            session_id=session_id,
            message="Phạm vi địa lý là TP.HCM và các tỉnh lân cận",
            workspace=None,
            confirmed_steps=[],
        )

    workspace = await get_workspace(session_id)
    assert workspace["artifacts"]["brief"]["value"] is None
    assert await list_pending_proposals(session_id) == []


def test_openai_yearless_in_progress_range_stays_in_current_year():
    from openai_campaign.brief import normalize_openai_yearless_dates

    result = normalize_openai_yearless_dates(
        {"startDate": "2027-07-20", "endDate": "2027-07-22"},
        [{"role": "user", "content": "ngày 20/7 chạy tới 22/7"}],
        today=date(2026, 7, 21),
    )

    assert result["startDate"] == "2026-07-20"
    assert result["endDate"] == "2026-07-22"


def test_openai_yearless_elapsed_range_rolls_to_next_year():
    from openai_campaign.brief import normalize_openai_yearless_dates

    result = normalize_openai_yearless_dates(
        {"startDate": "2026-07-20", "endDate": "2026-07-22"},
        [{"role": "user", "content": "ngày 20/7 chạy tới 22/7"}],
        today=date(2026, 7, 23),
    )

    assert result["startDate"] == "2027-07-20"
    assert result["endDate"] == "2027-07-22"


def test_openai_explicit_year_is_never_rewritten():
    from openai_campaign.brief import normalize_openai_yearless_dates

    result = normalize_openai_yearless_dates(
        {"startDate": "2027-07-20", "endDate": "2027-07-22"},
        [{"role": "user", "content": "chạy từ 20/7/2027 tới 22/7/2027"}],
        today=date(2026, 7, 21),
    )

    assert result["startDate"] == "2027-07-20"
    assert result["endDate"] == "2027-07-22"


@pytest.mark.asyncio
async def test_exact_bun_bo_message_asks_for_missing_fields_without_partial_proposal(
    monkeypatch,
):
    import graph.nodes.brief_collector as collector
    import openai_campaign.engine as engine
    from graph.nodes.brief_collector import (
        BriefDelegationDecision,
        BriefIntakeTurn,
    )
    from session import get_pending_proposal

    forbidden = AsyncMock(side_effect=AssertionError("GreenNode structured call"))
    monkeypatch.setattr(collector, "structured", forbidden)
    monkeypatch.setattr(
        engine, "decide_turn", AsyncMock(return_value=_update_brief_decision()),
    )
    client = _Client({
        "BriefIntakeTurn": BriefIntakeTurn(
            action="ask_clarification",
            message="Cần bổ sung Brief.",
            missing_fields=[
                "brand", "objective", "kpi", "budget",
                "startDate", "endDate", "notes",
            ],
        ),
        "BriefDelegationDecision": BriefDelegationDecision(
            mode="none", provided_fields=[], delegated_fields=[],
        ),
    })

    result = await engine.handle_openai_freeform(
        "bán bún bò, brand Bún Bò Hutao, budget 50 triệu, , ngày 20/7 chạy tới 22/7",
        0,
        "openai-bun-bo-partial",
        client=client,
    )

    assert result.meta.model == "gpt-5.4-mini"
    assert result.meta.tool == "freeform_chat"
    assert result.blocks == []
    assert "Mục tiêu campaign" in result.text
    assert "KPI mong muốn" in result.text
    assert "Đối tượng mục tiêu" in result.text
    assert "Thương hiệu" not in result.text
    assert "ngân sách" not in result.text.lower()
    assert await get_pending_proposal("openai-bun-bo-partial") is None
    forbidden.assert_not_awaited()
    assert {call["text_format"].__name__ for call in client.responses.calls} == {
        "BriefIntakeTurn", "BriefDelegationDecision",
    }
    assert all(call["store"] is False for call in client.responses.calls)


@pytest.mark.asyncio
async def test_openai_clarification_discards_provider_working_brief_without_failing(
    monkeypatch,
):
    """Regression for the exact invalid combination observed in production."""
    import graph.nodes.brief_collector as collector
    import openai_campaign.engine as engine
    from graph.nodes.brief_collector import BriefDelegationDecision
    from session import get_pending_proposal

    forbidden = AsyncMock(side_effect=AssertionError("GreenNode structured call"))
    monkeypatch.setattr(collector, "structured", forbidden)
    monkeypatch.setattr(
        engine, "decide_turn", AsyncMock(return_value=_update_brief_decision()),
    )
    client = _Client({
        "BriefIntakeTurn": {
            "action": "ask_clarification",
            "message": "Cần bổ sung Brief.",
            # GPT exposed a complete working draft even though it correctly
            # chose clarification. This must never become a proposal.
            "brief": {
                "brand": "Bún Bò Hutao",
                "objective": "awareness",
                "kpi": "Reach",
                "budget": 50,
                "startDate": "2026-07-20",
                "endDate": "2026-07-22",
                "notes": "Người yêu thích ẩm thực",
            },
            "missing_fields": ["objective", "kpi", "notes"],
        },
        "BriefDelegationDecision": BriefDelegationDecision(
            mode="none", provided_fields=[], delegated_fields=[],
        ),
    })

    result = await engine.handle_openai_freeform(
        "bán bún bò, brand Bún Bò Hutao, budget 50 triệu, "
        "ngày 20/7 chạy tới 22/7",
        0,
        "openai-autopilot-bun-bo-clarification",
        client=client,
    )

    assert result.meta.tool == "freeform_chat"
    assert "Mục tiêu campaign" in result.text
    assert "KPI mong muốn" in result.text
    assert "Đối tượng mục tiêu" in result.text
    assert "Thương hiệu" not in result.text
    assert "ngân sách" not in result.text.lower()
    assert await get_pending_proposal(
        "openai-autopilot-bun-bo-clarification"
    ) is None
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_zplay_intake_recovers_provider_working_draft_without_repair(
    monkeypatch,
):
    """Regression for production request 6345ecc1f5cc4b4e on 2026-07-29."""
    import graph.nodes.brief_collector as collector
    import openai_campaign.engine as engine
    from graph.nodes.brief_collector import BriefDelegationDecision
    from session import get_pending_proposal

    forbidden = AsyncMock(side_effect=AssertionError("GreenNode structured call"))
    monkeypatch.setattr(collector, "structured", forbidden)
    monkeypatch.setattr(
        engine, "decide_turn", AsyncMock(return_value=_update_brief_decision()),
    )
    client = _Client({
        "BriefIntakeTurn": {
            "action": "ask_clarification",
            "message": "Cần bổ sung Brief.",
            "brief": {
                "brand": "ZPlay",
                "objective": "awareness",
                "kpi": "Reach, VTR",
                "budget": 200,
                # Regression: the provider sometimes preserves the localized
                # walkthrough dates even though canonical state requires ISO.
                "startDate": "28/07/2026",
                "endDate": "04/08/2026",
                "notes": (
                    "Sản phẩm: Nền tảng game và giải đấu esports. "
                    "Đối tượng: Nam 15–28 tuổi, quan tâm gaming, esports và game online. "
                    "Thông điệp: Khám phá sân chơi dành cho cộng đồng game thủ."
                ),
            },
            "missing_fields": ["objective", "kpi", "notes"],
        },
        "BriefDelegationDecision": BriefDelegationDecision(
            mode="none",
            provided_fields=["objective", "kpi", "notes"],
            delegated_fields=[],
        ),
    })

    result = await engine.handle_openai_freeform(
        "\n".join([
            "Brand: ZPlay",
            "Sản phẩm / dịch vụ: Nền tảng game và giải đấu esports",
            "Objective: awareness",
            "KPI: Reach, VTR",
            "Budget: 200 triệu VND",
            "Thời gian: 28/07/2026 đến 04/08/2026",
            "Đối tượng mục tiêu: Nam 15–28 tuổi, quan tâm gaming, esports và game online",
            "Thông điệp chính: Khám phá sân chơi dành cho cộng đồng game thủ",
        ]),
        0,
        "openai-zplay-working-draft-recovery",
        client=client,
    )

    pending = await get_pending_proposal(
        "openai-zplay-working-draft-recovery"
    )
    assert result.meta.tool == "workspace_proposal"
    assert result.blocks[0]["type"] == "workspace_proposal"
    assert pending["value"]["brand"] == "ZPlay"
    assert pending["value"]["budget"] == 200.0
    assert pending["value"]["startDate"] == "2026-07-28"
    assert pending["value"]["endDate"] == "2026-08-04"
    assert {call["text_format"].__name__ for call in client.responses.calls} == {
        "BriefIntakeTurn", "BriefDelegationDecision",
    }
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_openai_intake_creates_one_atomic_whole_brief_proposal(
    monkeypatch,
):
    import graph.nodes.brief_collector as collector
    import openai_campaign.brief as openai_brief
    import openai_campaign.engine as engine
    from graph.nodes.brief_collector import (
        BriefDelegationDecision,
        BriefDraft,
        BriefIntakeTurn,
    )
    from session import get_pending_proposal
    from workspace.service import get_workspace, list_pending_proposals

    forbidden = AsyncMock(side_effect=AssertionError("GreenNode structured call"))
    monkeypatch.setattr(collector, "structured", forbidden)
    monkeypatch.setattr(
        engine, "decide_turn", AsyncMock(return_value=_update_brief_decision()),
    )
    monkeypatch.setattr(openai_brief, "campaign_today", lambda: date(2026, 7, 21))
    monkeypatch.setattr(collector, "campaign_today", lambda: date(2026, 7, 21))
    client = _Client({
        "BriefIntakeTurn": BriefIntakeTurn(
            action="propose_brief",
            message="Đã tổng hợp Brief.",
            reason="Tổng hợp đầy đủ thông tin người dùng cung cấp.",
            brief=BriefDraft(
                brand="Bún Bò Hutao",
                objective="awareness",
                kpi="Reach",
                budget=50,
                # The provider follows its generic "future occurrence" bias;
                # the OpenAI boundary must restore the still-running 2026 range.
                startDate="2027-07-20",
                endDate="2027-07-22",
                notes="Người yêu thích ẩm thực tại TP.HCM",
            ),
        ),
        "BriefDelegationDecision": BriefDelegationDecision(
            mode="none",
            provided_fields=["objective", "kpi", "notes"],
            delegated_fields=[],
        ),
    })

    result = await engine.handle_openai_freeform(
        "Bán bún bò, brand Bún Bò Hutao, objective awareness, KPI Reach, "
        "budget 50 triệu, chạy từ 20/7 tới 22/7, audience người yêu ẩm thực tại TP.HCM",
        0,
        "openai-bun-bo-complete",
        client=client,
    )

    pending = await get_pending_proposal("openai-bun-bo-complete")
    proposals = await list_pending_proposals("openai-bun-bo-complete")
    workspace = await get_workspace("openai-bun-bo-complete")
    assert pending["field"] == "brief"
    assert pending["value"] == {
        "brand": "Bún Bò Hutao",
        "objective": "awareness",
        "kpi": "Reach",
        "budget": 50.0,
        "startDate": "2026-07-20",
        "endDate": "2026-07-22",
        "notes": "Người yêu thích ẩm thực tại TP.HCM",
    }
    assert pending["proposal_id"] == proposals[0]["proposal_id"]
    assert len(proposals) == 1
    assert workspace["revision"] == 0
    assert workspace["artifacts"]["brief"]["value"] is None
    assert result.blocks[0]["type"] == "workspace_proposal"
    assert result.blocks[0]["changes"]["field"] == "brief"
    assert result.meta.model == "gpt-5.4-mini"
    forbidden.assert_not_awaited()
