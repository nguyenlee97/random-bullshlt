import pytest

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
