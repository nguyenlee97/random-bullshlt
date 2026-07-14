import pytest

from graph.nodes import workspace_intent as intent_node
from graph.nodes.intercepts import intercepts_node
from workspace.intent import (
    InvalidWorkspaceIntent,
    WorkspaceIntent,
    classify_workspace_intent,
    looks_like_brief_edit,
    validate_workspace_intent,
)
from workspace.service import get_workspace


def _change(**overrides) -> WorkspaceIntent:
    values = {
        "intent": "propose_change",
        "command": "set_brief_field",
        "field": "brief.brand",
        "value": "Thương Hiệu Mới",
        "reason": "Người dùng yêu cầu đổi brand",
        "confidence": 0.99,
        "requires_clarification": False,
        "clarification": "",
    }
    values.update(overrides)
    return WorkspaceIntent(**values)


def test_prefilter_targets_edits_but_not_normal_workspace_questions():
    assert looks_like_brief_edit(
        "Hãy đề xuất đổi brand trong workspace thành Thương Hiệu Mới"
    )
    assert not looks_like_brief_edit("Brand hiện tại trong workspace là gì?")
    assert not looks_like_brief_edit("Audience nào phù hợp với chiến dịch?")


@pytest.mark.asyncio
async def test_normal_question_bypasses_the_structured_model(monkeypatch):
    def should_not_run(*args, **kwargs):
        raise AssertionError("structured model should have been bypassed")

    monkeypatch.setattr("workspace.intent._classify_sync", should_not_run)
    result = await classify_workspace_intent("Brand hiện tại là gì?", {"brand": "A"})
    assert result is None


def test_validator_merges_partial_brief_without_dropping_existing_fields():
    command = validate_workspace_intent(
        _change(field="brief", value={"brand": "B", "budget": 25}),
        {"brand": "A", "objective": "awareness", "budget": 10},
    )
    assert command == (
        "brief",
        {"brand": "B", "objective": "awareness", "budget": 25},
        "Người dùng yêu cầu đổi brand",
    )


def test_validator_rejects_invalid_or_hallucinated_values():
    with pytest.raises(InvalidWorkspaceIntent):
        validate_workspace_intent(
            _change(field="brief.objective", value="make_everything_viral"), {}
        )
    with pytest.raises(InvalidWorkspaceIntent):
        validate_workspace_intent(
            _change(field="brief", value={"secretAdminFlag": True}), {}
        )


@pytest.mark.asyncio
async def test_explicit_edit_creates_durable_proposal_without_mutating(monkeypatch):
    async def classified(message, current_brief):
        return _change()

    monkeypatch.setattr(intent_node, "classify_workspace_intent", classified)
    result = await intent_node.workspace_intent_node({
        "session_id": "intent-proposal",
        "step": 0,
        "user_message": "đổi brand thành Thương Hiệu Mới",
        "workspace": {},
        "confirmed_steps": [],
    })

    assert result["used_tool"] == "workspace_proposal"
    block = result["response_blocks"][0]
    assert block["type"] == "workspace_proposal"
    assert block["changes"]["proposal_id"].startswith("wpr_")
    assert block["changes"]["field"] == "brief.brand"

    before_approval = await get_workspace("intent-proposal")
    assert before_approval["revision"] == 0
    assert before_approval["artifacts"]["brief"]["value"] is None

    confirmed = await intercepts_node({
        "session_id": "intent-proposal",
        "step": 0,
        "user_message": "đồng ý",
        "workspace": {},
    })
    assert confirmed["workspace_update"]["proposal_id"] == block["changes"]["proposal_id"]
    after_approval = await get_workspace("intent-proposal")
    assert after_approval["revision"] == 1
    assert after_approval["artifacts"]["brief"]["value"]["brand"] == "Thương Hiệu Mới"


@pytest.mark.asyncio
async def test_ambiguous_edit_asks_for_value_and_does_not_create_proposal(monkeypatch):
    async def classified(message, current_brief):
        return _change(
            field="none",
            value=None,
            requires_clarification=True,
            clarification="Anh/chị muốn đổi brand thành tên nào?",
        )

    monkeypatch.setattr(intent_node, "classify_workspace_intent", classified)
    result = await intent_node.workspace_intent_node({
        "session_id": "intent-clarify",
        "step": 0,
        "user_message": "đổi brand",
        "workspace": {},
        "confirmed_steps": [],
    })
    assert result["used_tool"] == "workspace_clarification"
    assert "tên nào" in result["response_text"]
    workspace = await get_workspace("intent-clarify")
    assert workspace["revision"] == 0
