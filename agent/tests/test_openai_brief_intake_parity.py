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
