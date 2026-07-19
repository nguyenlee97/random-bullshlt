import asyncio
from datetime import date
from types import SimpleNamespace
import time

import pytest

from graph.nodes import brief_collector as collector
from graph.nodes.brief_collector import (
    BriefDraft,
    BriefIntakeTurn,
    BriefTurn,
    normalize_inferred_dates,
)
from graph.nodes.intercepts import intercepts_node
from session import get_history
from workspace.service import get_workspace, list_pending_proposals


MIXIFOOD_DRAFT = BriefDraft(
    brand="Mixifood",
    objective="conversion",
    kpi="CTR > 0.8%, CPA < 50.000 VND",
    budget=2,
    startDate="2025-07-15",
    endDate="2025-07-17",
    notes=(
        "Sản phẩm: khô gà\nAudience: Nam và Nữ 18-35\n"
        "Geo: TP.HCM và Hà Nội\nInterest: Food, Snack, Online Shopping"
    ),
)


def _mixifood_state(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "step": 0,
        "user_message": "gợi ý giúp mình luôn",
        "confirmed_steps": [],
        "tokens_spent": 0,
        "messages": [
            {"role": "user", "content": (
                "bán khô gà, brand mixifood, budget 2 triệu, chạy 3 ngày từ 15/7"
            )},
            {"role": "assistant", "content": "Anh/chị muốn objective và KPI nào?"},
            {"role": "user", "content": "chọn giúp mình luôn"},
            {"role": "assistant", "content": (
                "Em đề xuất Conversion, CTR > 0.8%, CPA < 50K. "
                "Anh/chị cho em biết audience."
            )},
            {"role": "user", "content": "gợi ý giúp mình luôn"},
        ],
    }


def test_yearless_dates_are_rolled_forward_from_stale_model_year():
    messages = [{"role": "user", "content": "chạy 3 ngày từ 15/7"}]
    repaired = normalize_inferred_dates(
        MIXIFOOD_DRAFT.model_dump(), messages, today=date(2026, 7, 15)
    )
    assert repaired["startDate"] == "2026-07-15"
    assert repaired["endDate"] == "2026-07-17"


def test_minimax_nested_json_string_is_coerced_then_strictly_validated():
    turn = BriefTurn.model_validate({
        "action": "propose_brief",
        "message": "Đề xuất",
        "brief": __import__("json").dumps(MIXIFOOD_DRAFT.model_dump()),
    })
    assert turn.brief.brand == "Mixifood"
    assert turn.brief.objective == "conversion"


def test_clarification_rejects_empty_missing_fields():
    with pytest.raises(ValueError, match="missing Brief field"):
        BriefTurn.model_validate({
            "action": "ask_clarification",
            "message": "Cần làm rõ thêm thông tin.",
            "missing_fields": [],
        })


@pytest.mark.parametrize("soft_field", ["objective", "kpi", "notes"])
def test_every_missing_brief_field_can_block_a_proposal(soft_field):
    turn = BriefTurn.model_validate({
        "action": "ask_clarification",
        "message": "Cần làm rõ thêm thông tin.",
        "missing_fields": [soft_field],
    })
    assert turn.missing_fields == [soft_field]


def test_all_brief_fields_can_trigger_clarification():
    turn = BriefTurn.model_validate({
        "action": "ask_clarification",
        "message": "Cần bổ sung dữ kiện bắt buộc.",
        "missing_fields": [
            "brand", "objective", "kpi", "budget",
            "startDate", "endDate", "notes",
        ],
    })
    assert turn.missing_fields == [
        "brand", "objective", "kpi", "budget",
        "startDate", "endDate", "notes",
    ]


@pytest.mark.asyncio
async def test_campaign_statement_cannot_autofill_missing_advisory_fields(monkeypatch):
    def generated(_messages, schema, schema_name, _role, _max_tokens):
        assert schema is BriefIntakeTurn
        assert schema_name == "brief_intake_turn"
        return schema.model_validate({
            "action": "propose_brief",
            "message": "Em đề xuất một Brief để duyệt.",
            "brief": MIXIFOOD_DRAFT.model_dump(),
        }), 33

    monkeypatch.setattr(collector, "structured", generated)
    turn, tokens = await collector.generate_brief_turn({
        "user_message": "campaign Mixifood, budget 2 triệu, chạy 3 ngày từ 15/7",
        "messages": [{
            "role": "user",
            "content": "campaign Mixifood, budget 2 triệu, chạy 3 ngày từ 15/7",
        }],
    })
    assert turn.action == "ask_clarification"
    assert turn.brief is None
    assert turn.missing_fields == ["objective", "kpi", "notes"]
    assert tokens == 33


def test_explicit_vng_budget_and_duration_are_not_reasked():
    message = (
        "quảng cáo chung kết thế giới liên minh huyền thoại, VNG, "
        "budget 100 triệu, 3 ngày từ 18/7/2026"
    )
    turn = BriefTurn(
        action="ask_clarification",
        message="Cần bổ sung Brief.",
        missing_fields=[
            "brand", "objective", "kpi", "budget",
            "startDate", "endDate", "notes",
        ],
    )
    enforced = collector._enforce_explicit_brief_fields(turn, {
        "messages": [{"role": "user", "content": message}],
    })
    assert enforced is not None
    assert enforced.missing_fields == ["objective", "kpi", "notes"]


@pytest.mark.asyncio
async def test_explicit_objective_kpi_and_audience_allow_proposal(monkeypatch):
    def generated(_messages, schema, schema_name, _role, _max_tokens):
        assert schema is BriefIntakeTurn
        assert schema_name == "brief_intake_turn"
        return schema.model_validate({
            "action": "propose_brief",
            "message": "Em đã chuẩn hóa Brief đầy đủ.",
            "brief": MIXIFOOD_DRAFT.model_dump(),
        }), 44

    monkeypatch.setattr(collector, "structured", generated)
    message = (
        "campaign Mixifood, objective conversion, KPI CTR > 0.8% và CPA < 50K, "
        "budget 2 triệu, chạy 3 ngày từ 15/7, audience nam nữ 18-35 tại Hà Nội "
        "và TP.HCM, sở thích đồ ăn vặt"
    )
    turn, tokens = await collector.generate_brief_turn({
        "user_message": message,
        "messages": [{"role": "user", "content": message}],
    })
    assert turn.action == "propose_brief"
    assert turn.brief is not None
    assert turn.missing_fields == []
    assert tokens == 44


@pytest.mark.asyncio
async def test_explanatory_question_keeps_answer_schema(monkeypatch):
    def generated(_messages, schema, schema_name, _role, _max_tokens):
        assert schema is BriefTurn
        assert schema_name == "brief_turn"
        return schema(
            action="answer",
            message="Awareness phù hợp khi mục tiêu chính là tăng nhận biết.",
        ), 21

    monkeypatch.setattr(collector, "structured", generated)
    turn, tokens = await collector.generate_brief_turn({
        "user_message": "Objective nào phù hợp với tôi?",
        "messages": [{"role": "user", "content": "Objective nào phù hợp với tôi?"}],
    })
    assert turn.action == "answer"
    assert tokens == 21


@pytest.mark.parametrize(
    ("provider_value", "workspace_millions"),
    [(2, 2), (2_000_000, 2), (2_000_000_000, 2000)],
)
def test_budget_is_normalized_from_raw_vnd(provider_value, workspace_millions):
    raw = MIXIFOOD_DRAFT.model_dump()
    raw["budget"] = provider_value
    assert BriefDraft.model_validate(raw).budget == workspace_millions


def test_ambiguous_over_limit_budget_is_not_silently_rescaled():
    raw = MIXIFOOD_DRAFT.model_dump()
    raw["budget"] = 6000
    with pytest.raises(ValueError):
        BriefDraft.model_validate(raw)


def test_explicit_past_year_is_never_silently_rewritten():
    messages = [{"role": "user", "content": "chạy từ 15/7/2025 đến 17/7/2025"}]
    unchanged = normalize_inferred_dates(
        MIXIFOOD_DRAFT.model_dump(), messages, today=date(2026, 7, 15)
    )
    assert unchanged["startDate"] == "2025-07-15"
    assert unchanged["endDate"] == "2025-07-17"


@pytest.mark.asyncio
async def test_recommended_brief_always_becomes_a_durable_reviewable_proposal(monkeypatch):
    async def generated(_state):
        return BriefTurn(
            action="propose_brief",
            message="Em đã tổng hợp một phương án.",
            brief=MIXIFOOD_DRAFT,
            reason="Agent chọn objective, KPI và audience theo yêu cầu",
        ), 123

    monkeypatch.setattr(collector, "generate_brief_turn", generated)
    monkeypatch.setattr(collector, "campaign_today", lambda: date(2026, 7, 15))
    sid = "brief-mixifood-regression"
    result = await collector.brief_collector_node(_mixifood_state(sid))

    assert result["used_tool"] == "workspace_proposal"
    assert result.get("workspace_update") is None
    assert result["response_blocks"][0]["type"] == "workspace_proposal"
    changes = result["response_blocks"][0]["changes"]
    assert changes["value"]["startDate"] == "2026-07-15"
    assert changes["value"]["endDate"] == "2026-07-17"
    assert changes["value"]["objective"] == "conversion"

    before = await get_workspace(sid)
    assert before["artifacts"]["brief"]["value"] is None
    assert len(await list_pending_proposals(sid)) == 1

    approved = await intercepts_node({
        "session_id": sid,
        "step": 0,
        "user_message": "xác nhận nhé",
        "workspace": {},
    })
    assert approved["used_tool"] == "workspace_confirmed"
    after = await get_workspace(sid)
    assert after["artifacts"]["brief"]["value"]["brand"] == "Mixifood"
    assert after["artifacts"]["brief"]["value"]["endDate"] == "2026-07-17"


@pytest.mark.asyncio
async def test_incomplete_brief_asks_a_question_without_claiming_it_was_saved(monkeypatch):
    async def generated(_state):
        return BriefTurn(
            action="ask_clarification",
            message="Anh/chị muốn chạy ngân sách bao nhiêu và trong thời gian nào?",
            missing_fields=["budget", "startDate", "endDate"],
        ), 45

    monkeypatch.setattr(collector, "generate_brief_turn", generated)
    result = await collector.brief_collector_node({
        "session_id": "brief-incomplete",
        "step": 0,
        "user_message": "Tôi muốn quảng cáo Mixifood",
        "messages": [{"role": "user", "content": "Tôi muốn quảng cáo Mixifood"}],
        "tokens_spent": 0,
    })
    assert result["used_tool"] == "freeform_chat"
    assert "bao nhiêu" in result["response_text"]
    assert "đã lưu" not in result["response_text"].lower()
    assert await list_pending_proposals("brief-incomplete") == []


@pytest.mark.asyncio
async def test_vague_clarification_is_replaced_with_all_explicit_missing_questions(monkeypatch):
    async def generated(_state):
        return BriefTurn(
            action="ask_clarification",
            message="Tôi cần xác nhận thêm một số thông tin để hoàn thiện brief:",
            missing_fields=[
                "objective", "kpi", "notes", "budget",
                "startDate", "endDate", "budget",
            ],
        ), 38

    monkeypatch.setattr(collector, "generate_brief_turn", generated)
    result = await collector.brief_collector_node({
        "session_id": "brief-vague-clarification",
        "step": 0,
        "user_message": "Tạo campaign cho Mixifood",
        "messages": [{"role": "user", "content": "Tạo campaign cho Mixifood"}],
        "tokens_spent": 0,
    })

    response = result["response_text"]
    assert "Tổng ngân sách" in response
    assert "Campaign bắt đầu" in response
    assert "Campaign kết thúc" in response
    assert "Mục tiêu campaign" in response
    assert "KPI mong muốn" in response
    assert "Đối tượng mục tiêu" in response
    assert response.count("Tổng ngân sách") == 1
    assert not response.rstrip().endswith(":")


@pytest.mark.asyncio
async def test_explicit_past_campaign_is_rejected_before_proposal_creation(monkeypatch):
    async def generated(_state):
        return BriefTurn(
            action="propose_brief",
            message="Em đã tổng hợp.",
            brief=MIXIFOOD_DRAFT,
        ), 50

    monkeypatch.setattr(collector, "generate_brief_turn", generated)
    monkeypatch.setattr(collector, "campaign_today", lambda: date(2026, 7, 15))
    state = _mixifood_state("brief-explicit-past")
    state["messages"][0]["content"] = "chạy 3 ngày từ 15/7/2025"
    result = await collector.brief_collector_node(state)
    assert result["used_tool"] == "workspace_clarification"
    assert "quá khứ" in result["response_text"]
    assert await list_pending_proposals("brief-explicit-past") == []
    history = await get_history("brief-explicit-past")
    assert history[-2]["role"] == "user"
    assert history[-1]["content"] == result["response_text"]


@pytest.mark.asyncio
async def test_graph_llm_call_does_not_block_other_async_requests(monkeypatch):
    from graph.nodes import agent_node as node

    def blocking_completion(**_kwargs):
        time.sleep(0.12)
        message = SimpleNamespace(content="Phản hồi", tool_calls=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message, finish_reason="stop")],
            usage=SimpleNamespace(total_tokens=10),
        )

    monkeypatch.setattr(node, "chat_completion", blocking_completion)
    task = asyncio.create_task(node.agent_node({
        "session_id": "nonblocking-llm",
        "messages": [{"role": "user", "content": "hello"}],
        "tokens_spent": 0,
        "token_budget": 100,
    }))
    started = time.perf_counter()
    await asyncio.sleep(0.02)
    assert time.perf_counter() - started < 0.08
    result = await task
    assert result["response_text"] == "Phản hồi"
