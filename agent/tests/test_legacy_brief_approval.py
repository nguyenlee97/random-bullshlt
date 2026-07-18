from datetime import date

import pytest

from graph.nodes import brief_collector as collector
from graph.nodes.brief_collector import BriefDraft, BriefTurn
from workspace.service import get_workspace, list_pending_proposals


MIXIFOOD_DRAFT = BriefDraft(
    brand="Mixifood",
    objective="consideration",
    kpi="CTR >= 0.8%, VI% >= 70%, Click >= 800",
    budget=5,
    startDate="2025-07-15",
    endDate="2025-07-17",
    notes="Sản phẩm: khô gà\nAudience: Nam và Nữ 18-45\nInterest: Food & drink",
)


@pytest.mark.asyncio
async def test_legacy_initial_recommendation_is_a_durable_proposal(monkeypatch):
    from handlers.freeform import handle_freeform

    async def generated(_state):
        return BriefTurn(
            action="propose_brief",
            message="Em đề xuất một Brief hoàn chỉnh.",
            brief=MIXIFOOD_DRAFT,
            reason="Agent tổng hợp theo yêu cầu gợi ý",
        ), 80

    monkeypatch.setattr(collector, "generate_brief_turn", generated)
    monkeypatch.setattr(collector, "campaign_today", lambda: date(2026, 7, 15))
    sid = "legacy-typed-initial-proposal"

    response = await handle_freeform(
        "gợi ý giúp mình", 0, sid, workspace={"brief": {}}
    )

    assert response.meta.tool == "workspace_proposal"
    assert response.blocks[0]["type"] == "workspace_proposal"
    assert response.workspace_update is None
    assert len(await list_pending_proposals(sid)) == 1
    assert (await get_workspace(sid))["artifacts"]["brief"]["value"] is None


@pytest.mark.asyncio
async def test_legacy_approval_recovers_and_commits_model_only_brief(monkeypatch):
    from handlers.freeform import handle_freeform
    from session import add_message

    async def generated(_state):
        return BriefTurn(
            action="propose_brief",
            message="Em đã khôi phục Brief từ gợi ý trước đó.",
            brief=MIXIFOOD_DRAFT,
            reason="Khôi phục recommendation đang được người dùng duyệt",
        ), 90

    monkeypatch.setattr(collector, "generate_brief_turn", generated)
    monkeypatch.setattr(collector, "campaign_today", lambda: date(2026, 7, 15))
    sid = "legacy-model-only-approval-recovery"
    await add_message(
        sid,
        "user",
        "bán khô gà, brand mixifood, budget 5 triệu, chạy 3 ngày từ 15/7",
    )
    await add_message(
        sid,
        "assistant",
        "Em đề xuất Consideration, CTR >= 0.8%. Nếu ok em sẽ lưu Brief.",
    )

    response = await handle_freeform("oke nhé", 0, sid, workspace={"brief": {}})

    assert response.meta.tool == "workspace_confirmed"
    assert response.workspace_update["field"] == "brief"
    assert response.workspace_update["value"]["brand"] == "Mixifood"
    assert response.workspace_update["value"]["startDate"] == "2026-07-15"
    assert await list_pending_proposals(sid) == []
    workspace = await get_workspace(sid)
    assert workspace["artifacts"]["brief"]["value"]["brand"] == "Mixifood"
    assert workspace["revision"] == 1
