import pytest
from unittest.mock import AsyncMock

from autopilot.chat import review_intent, route_autopilot_chat


def test_review_intent_requires_explicit_language_and_rejects_negation_first():
    assert review_intent("Đồng ý, tiếp tục") == "approve"
    assert review_intent("Tôi không đồng ý") == "reject"
    assert review_intent("Tại sao Agent chọn audience này?") == "question"
    assert review_intent(
        "Tôi đang hỏi để review, chưa phê duyệt creative."
    ) == "question"
    assert review_intent("Có nên phê duyệt bước này không?") == "question"
    assert review_intent("Gợi ý lại audience") == "retry"
    assert review_intent("Can you recommend audience again?") == "retry"


@pytest.mark.asyncio
async def test_running_autopilot_locks_chat(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import workspace.service as workspace_service

    messages = []

    async def fake_add_message(session_id, role, content):
        messages.append((role, content))

    async def fake_workspace(session_id):
        return {"experience_mode": "autopilot", "artifacts": {}}

    async def fake_run(session_id):
        return {"run_id": "run-1", "status": "running", "tasks": []}

    monkeypatch.setattr(chat, "add_message", fake_add_message)
    monkeypatch.setattr(workspace_service, "get_workspace", fake_workspace)
    monkeypatch.setattr(service, "get_latest_run", fake_run)

    response = await route_autopilot_chat("đổi budget", "session-1", 0)
    assert response.meta.tool == "autopilot_chat_locked"
    assert response.workspace_update is None
    assert [role for role, _ in messages] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_waiting_review_records_only_explicit_decision(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import workspace.service as workspace_service

    decisions = []

    async def fake_add_message(*args):
        return None

    async def fake_workspace(session_id):
        return {"experience_mode": "autopilot", "artifacts": {}}

    async def fake_run(session_id):
        return {
            "run_id": "run-2", "status": "waiting_review",
            "tasks": [{
                "task_id": "task-2", "key": "launch_approval",
                "title": "Duyệt launch", "status": "waiting_review",
                "result": {"message": "Kiểm tra order draft."},
            }],
        }

    async def fake_review(run_id, task_id, *, approved, actor, reason):
        decisions.append(approved)
        return {"run_id": run_id}

    async def fake_question(**kwargs):
        assert kwargs["context"]["review_checkpoint"]["key"] == "launch_approval"
        return "Order gồm audience, placement và creative hiện tại.", {
            "provider": "greennode",
            "model": "minimax-m2.5",
        }

    monkeypatch.setattr(chat, "add_message", fake_add_message)
    monkeypatch.setattr(chat, "_answer_greennode_autopilot_question", fake_question)
    monkeypatch.setattr(workspace_service, "get_workspace", fake_workspace)
    monkeypatch.setattr(service, "get_latest_run", fake_run)
    monkeypatch.setattr(service, "review_task", fake_review)

    question = await route_autopilot_chat("Order này gồm những gì?", "session-2", 3)
    assert question.meta.tool == "autopilot_review_qa"
    assert "chỉ là câu trả lời review" in question.text
    assert decisions == []

    deferred = await route_autopilot_chat(
        "Kiểm tra logo giúp tôi, tôi đang hỏi để review, chưa phê duyệt creative.",
        "session-2",
        3,
    )
    assert deferred.meta.tool == "autopilot_review_qa"
    assert decisions == []

    approved = await route_autopilot_chat("Đồng ý, tiếp tục", "session-2", 3)
    assert approved.meta.tool == "autopilot_review_chat"
    assert decisions == [True]


@pytest.mark.asyncio
async def test_waiting_audience_review_can_rerun_without_approval(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import workspace.service as workspace_service

    reruns = []
    approvals = []

    async def fake_add_message(*args):
        return None

    async def fake_workspace(_session_id):
        return {"experience_mode": "autopilot", "artifacts": {}}

    async def fake_run(_session_id):
        return {
            "run_id": "run-audience",
            "status": "waiting_review",
            "tasks": [{
                "task_id": "task-audience",
                "key": "retrieve_audience",
                "title": "Tìm audience",
                "status": "waiting_review",
                "result": {"attrs": [{"fullLabel": "Books"}]},
            }],
        }

    async def fake_rerun(run_id, task_id, *, actor, reason):
        reruns.append((run_id, task_id, actor, reason))
        return {"run_id": run_id, "status": "queued"}

    async def fake_review(*args, **kwargs):
        approvals.append((args, kwargs))

    monkeypatch.setattr(chat, "add_message", fake_add_message)
    monkeypatch.setattr(workspace_service, "get_workspace", fake_workspace)
    monkeypatch.setattr(service, "get_latest_run", fake_run)
    monkeypatch.setattr(service, "rerun_review_task", fake_rerun)
    monkeypatch.setattr(service, "review_task", fake_review)

    response = await route_autopilot_chat(
        "Gợi ý lại audience",
        "session-audience",
        1,
    )

    assert response.meta.tool == "autopilot_audience_rerun"
    assert "danh sách mới" in response.text
    assert len(reruns) == 1
    assert approvals == []


@pytest.mark.asyncio
async def test_openai_placement_ordinals_edit_then_require_separate_confirmation(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import workspace.service as workspace_service

    selections = []
    approvals = []
    candidates = [
        {"id": "ZONE-1", "name": "Masthead"},
        {"id": "ZONE-2", "name": "Article top"},
        {"id": "ZONE-3", "name": "Side box"},
        {"id": "ZONE-4", "name": "Footer"},
    ]

    async def fake_workspace(_session_id):
        return {"experience_mode": "autopilot", "artifacts": {}}

    async def fake_run(_session_id):
        value = {"candidate_zone_ids": [item["id"] for item in candidates],
                 "candidates": candidates}
        return {
            "run_id": "run-zones",
            "status": "waiting_review",
            "conversation_model": "openai_gpt_5_4_mini",
            "tasks": [{
                "task_id": "task-zones",
                "key": "plan_placement_intent",
                "title": "Ad zone đề xuất ban đầu",
                "status": "waiting_review",
                "result": value,
                "pending_artifact": {
                    "artifact": "placement_intent",
                    "value": value,
                },
            }],
        }

    async def fake_select(run_id, zone_ids, *, actor, reason):
        selections.append((run_id, zone_ids, actor, reason))
        return {"run_id": run_id}

    async def fake_review(run_id, task_id, *, approved, actor, reason):
        approvals.append((run_id, task_id, approved))
        return {"run_id": run_id}

    monkeypatch.setattr(chat, "add_message", AsyncMock())
    monkeypatch.setattr(workspace_service, "get_workspace", fake_workspace)
    monkeypatch.setattr(service, "get_latest_run", fake_run)
    monkeypatch.setattr(service, "select_placement_intent", fake_select)
    monkeypatch.setattr(service, "review_task", fake_review)

    edited = await route_autopilot_chat(
        "Tôi muốn chọn zone 1,2,3",
        "session-zones",
        3,
    )

    assert edited.meta.tool == "autopilot_placement_selection"
    assert selections[0][1] == ["ZONE-1", "ZONE-2", "ZONE-3"]
    assert approvals == []
    assert "vẫn đang chờ duyệt" in edited.text

    confirmed = await route_autopilot_chat("Xác nhận", "session-zones", 3)
    assert confirmed.meta.tool == "autopilot_review_chat"
    assert approvals == [("run-zones", "task-zones", True)]


@pytest.mark.asyncio
async def test_openai_audience_ordinals_can_select_adjacent_then_confirm(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import workspace.service as workspace_service

    selections = []
    approvals = []
    candidates = [
        {"segmentId": "INT006", "fullLabel": "Construction", "tier": "adjacent"},
        {"segmentId": "INT020", "fullLabel": "Management", "tier": "adjacent"},
    ]

    async def fake_workspace(_session_id):
        return {"experience_mode": "autopilot", "artifacts": {}}

    async def fake_run(_session_id):
        value = {
            "attrs": [],
            "adjacent_attrs": candidates,
            "recommendations": candidates,
            "selection_required": True,
        }
        return {
            "run_id": "run-audience",
            "status": "waiting_review",
            "conversation_model": "openai_gpt_5_4_mini",
            "tasks": [{
                "task_id": "task-audience",
                "key": "retrieve_audience",
                "title": "Audience",
                "status": "waiting_review",
                "result": value,
                "pending_artifact": {
                    "artifact": "audience",
                    "value": value,
                },
            }],
        }

    async def fake_select(run_id, segment_ids, *, actor, reason):
        selections.append((run_id, segment_ids, actor, reason))
        return {"run_id": run_id}

    async def fake_review(run_id, task_id, *, approved, actor, reason):
        approvals.append((run_id, task_id, approved))
        return {"run_id": run_id}

    monkeypatch.setattr(chat, "add_message", AsyncMock())
    monkeypatch.setattr(workspace_service, "get_workspace", fake_workspace)
    monkeypatch.setattr(service, "get_latest_run", fake_run)
    monkeypatch.setattr(service, "select_audience_recommendations", fake_select)
    monkeypatch.setattr(service, "review_task", fake_review)

    edited = await route_autopilot_chat(
        "Chọn audience 2",
        "session-audience",
        1,
    )

    assert edited.meta.tool == "autopilot_audience_selection"
    assert selections[0][1] == ["INT020"]
    assert approvals == []
    assert "Xác nhận” riêng" in edited.text


@pytest.mark.asyncio
async def test_openai_placement_ordinal_out_of_range_does_not_mutate(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import workspace.service as workspace_service

    async def fake_workspace(_session_id):
        return {"experience_mode": "autopilot", "artifacts": {}}

    async def fake_run(_session_id):
        value = {"candidates": [{"id": "ZONE-1"}, {"id": "ZONE-2"}]}
        return {
            "run_id": "run-zones-invalid",
            "status": "waiting_review",
            "conversation_model": "openai_gpt_5_4_mini",
            "tasks": [{
                "task_id": "task-zones-invalid",
                "key": "plan_placement_intent",
                "status": "waiting_review",
                "result": value,
                "pending_artifact": {
                    "artifact": "placement_intent",
                    "value": value,
                },
            }],
        }

    select = AsyncMock()
    review = AsyncMock()
    monkeypatch.setattr(chat, "add_message", AsyncMock())
    monkeypatch.setattr(workspace_service, "get_workspace", fake_workspace)
    monkeypatch.setattr(service, "get_latest_run", fake_run)
    monkeypatch.setattr(service, "select_placement_intent", select)
    monkeypatch.setattr(service, "review_task", review)

    response = await route_autopilot_chat(
        "Chọn zone 1,9",
        "session-zones-invalid",
        3,
    )

    assert response.meta.tool == "autopilot_placement_selection_invalid"
    assert "1–2" in response.text
    select.assert_not_awaited()
    review.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_creative_preview_returns_images_and_generic_confirm_is_blocked(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import creative_intel.service as creative_service
    import openai_campaign.autopilot as openai_autopilot
    import workspace.service as workspace_service
    from openai_campaign.autopilot import CreativeReviewAction

    workspace = {
        "experience_mode": "autopilot",
        "artifacts": {
            "creative": {"value": {"files": [{
                "name": "generated.png",
                "url": "https://example.test/generated.png",
                "width": 1160,
                "height": 280,
            }]}},
            "creative_verdict": {"value": {"files": []}},
        },
    }
    run = {
        "run_id": "run-creative-preview",
        "status": "waiting_review",
        "conversation_model": "openai_gpt_5_4_mini",
        "tasks": [{
            "task_id": "task-assign",
            "key": "assign_creatives",
            "status": "waiting_review",
            "result": {"assignments": {"ZONE-1": 0}},
        }],
    }
    intel = [{
        "analysis_id": "ci-1",
        "name": "generated.png",
        "url": "https://example.test/generated.png",
        "status": "needs_review",
        "effective_status": "needs_review",
        "review_reasons": ["Có chữ ngoài brief"],
    }]

    monkeypatch.setattr(chat, "add_message", AsyncMock())
    monkeypatch.setattr(workspace_service, "get_workspace", AsyncMock(return_value=workspace))
    monkeypatch.setattr(service, "get_latest_run", AsyncMock(return_value=run))
    monkeypatch.setattr(service, "review_task", AsyncMock())
    monkeypatch.setattr(
        creative_service,
        "sync_generation_vlm_reviews",
        AsyncMock(return_value=intel),
    )
    monkeypatch.setattr(
        openai_autopilot,
        "classify_openai_creative_review_action",
        AsyncMock(return_value=CreativeReviewAction(
            intent="show_creatives",
            explicit=True,
            evidence="Xem creative",
        )),
    )

    preview = await route_autopilot_chat(
        "Xem creative giúp tôi", "session-preview", 3,
    )
    assert preview.meta.tool == "autopilot_creative_preview"
    assert preview.media_parts == [{
        "kind": "image",
        "image_url": "https://example.test/generated.png",
    }]
    assert "Cảnh báo" in preview.text

    blocked = await route_autopilot_chat("Xác nhận", "session-preview", 3)
    assert blocked.meta.tool == "autopilot_creative_review_required"
    service.review_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_creative_preview_uses_canonical_approval_with_advisory(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import creative_intel.service as creative_service
    import workspace.service as workspace_service

    workspace = {
        "experience_mode": "autopilot",
        "artifacts": {
            "creative": {"value": {"files": [{
                "name": "generated.png",
                "url": "https://example.test/generated.png",
                "width": 1160,
                "height": 280,
                "generation": {"vlmVerdict": {
                    "acceptable": False,
                    "composition_safe": True,
                    "text_readable": True,
                    "unexpected_text": ["GENERIC SLOGAN"],
                }},
            }]}},
            "creative_verdict": {"value": {"files": []}},
        },
    }
    run = {
        "run_id": "run-creative-advisory",
        "status": "waiting_review",
        "conversation_model": "openai_gpt_5_4_mini",
        "tasks": [{
            "task_id": "task-assign",
            "key": "assign_creatives",
            "status": "waiting_review",
            "result": {"assignments": {"ZONE-1": 0}},
        }],
    }
    intel = [{
        "analysis_id": "ci-advisory",
        "name": "generated.png",
        "url": "https://example.test/generated.png",
        "status": "auto_approved",
        "effective_status": "auto_approved",
        "review_reasons": [],
        "generation_advisories": [
            "QA tạo ảnh có lưu ý nhưng không yêu cầu duyệt thủ công",
            "Chữ bổ sung: GENERIC SLOGAN",
        ],
    }]

    monkeypatch.setattr(chat, "add_message", AsyncMock())
    monkeypatch.setattr(workspace_service, "get_workspace", AsyncMock(return_value=workspace))
    monkeypatch.setattr(service, "get_latest_run", AsyncMock(return_value=run))
    monkeypatch.setattr(
        creative_service,
        "sync_generation_vlm_reviews",
        AsyncMock(return_value=intel),
    )

    preview = await route_autopilot_chat(
        "Xem creative giúp tôi", "session-advisory", 3,
    )

    assert preview.meta.tool == "autopilot_creative_preview"
    assert "Đạt kiểm tra" in preview.text
    assert "Lưu ý không chặn duyệt" in preview.text
    assert "Cần duyệt thủ công" not in preview.text


@pytest.mark.asyncio
async def test_openai_creative_override_requires_reason_and_replans(monkeypatch):
    import autopilot.chat as chat
    import autopilot.service as service
    import creative_intel.service as creative_service
    import openai_campaign.autopilot as openai_autopilot
    import workspace.service as workspace_service
    from openai_campaign.autopilot import CreativeReviewAction

    workspace = {
        "experience_mode": "autopilot",
        "artifacts": {
            "creative": {"value": {"files": [{
                "name": "generated.png",
                "url": "https://example.test/generated.png",
            }]}},
        },
    }
    run = {
        "run_id": "run-creative-override",
        "status": "waiting_review",
        "conversation_model": "openai_gpt_5_4_mini",
        "tasks": [{
            "task_id": "task-assign",
            "key": "assign_creatives",
            "status": "waiting_review",
            "result": {"assignments": {"ZONE-1": 0}},
        }],
    }
    intel = [{
        "analysis_id": "ci-override",
        "url": "https://example.test/generated.png",
        "status": "needs_review",
        "effective_status": "needs_review",
        "review_reasons": ["Có chữ ngoài brief"],
    }]
    approve = AsyncMock(return_value={"effective_status": "approved_override"})
    reconcile = AsyncMock(return_value={"changed": True})

    monkeypatch.setattr(chat, "add_message", AsyncMock())
    monkeypatch.setattr(workspace_service, "get_workspace", AsyncMock(return_value=workspace))
    monkeypatch.setattr(service, "get_latest_run", AsyncMock(return_value=run))
    monkeypatch.setattr(service, "reconcile_workspace_changes", reconcile)
    monkeypatch.setattr(
        creative_service,
        "sync_generation_vlm_reviews",
        AsyncMock(return_value=intel),
    )
    monkeypatch.setattr(creative_service, "approve_override", approve)
    monkeypatch.setattr(
        openai_autopilot,
        "classify_openai_creative_review_action",
        AsyncMock(return_value=CreativeReviewAction(
            intent="approve_override",
            creative_numbers=[1],
            reason="Đã kiểm tra chữ và thương hiệu",
            explicit=True,
            evidence="Chấp nhận creative 1",
        )),
    )

    response = await route_autopilot_chat(
        "Chấp nhận creative 1 vì đã kiểm tra chữ và thương hiệu",
        "session-override",
        3,
    )

    assert response.meta.tool == "autopilot_creative_override"
    approve.assert_awaited_once_with(
        "session-override",
        "ci-override",
        "Đã kiểm tra chữ và thương hiệu",
        actor="zalo_campaign_operator",
    )
    reconcile.assert_awaited_once_with("run-creative-override")
    assert "audit trail" in response.text


@pytest.mark.asyncio
async def test_completed_autopilot_uses_shared_report_chat_even_with_stale_step(monkeypatch):
    from unittest.mock import AsyncMock

    import autopilot.service as service
    import handlers.report as report_handler
    import workspace.service as workspace_service

    async def fake_workspace(session_id):
        return {
            "experience_mode": "autopilot",
            "artifacts": {"report": {"value": {"kind": "setup_report"}}},
        }

    async def fake_run(session_id):
        return {
            "run_id": "run-report",
            "status": "completed",
            "conversation_model": "openai_gpt_5_4_mini",
            "tasks": [],
        }

    monkeypatch.setattr(workspace_service, "get_workspace", fake_workspace)
    monkeypatch.setattr(service, "get_latest_run", fake_run)
    shared_report = AsyncMock(return_value="shared-report-response")
    monkeypatch.setattr(report_handler, "handle_report_chat", shared_report)

    result = await route_autopilot_chat(
        "Tóm tắt CTR", "session-report", 4, active_report_tab="conversion",
    )

    assert result == "shared-report-response"
    shared_report.assert_awaited_once_with(
        "Tóm tắt CTR",
        "session-report",
        "conversion",
        conversation_model="openai_gpt_5_4_mini",
    )
