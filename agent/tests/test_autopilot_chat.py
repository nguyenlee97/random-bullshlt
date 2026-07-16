import pytest

from autopilot.chat import review_intent, route_autopilot_chat


def test_review_intent_requires_explicit_language_and_rejects_negation_first():
    assert review_intent("Đồng ý, tiếp tục") == "approve"
    assert review_intent("Tôi không đồng ý") == "reject"
    assert review_intent("Tại sao Agent chọn audience này?") == "question"


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

    monkeypatch.setattr(chat, "add_message", fake_add_message)
    monkeypatch.setattr(workspace_service, "get_workspace", fake_workspace)
    monkeypatch.setattr(service, "get_latest_run", fake_run)
    monkeypatch.setattr(service, "review_task", fake_review)

    question = await route_autopilot_chat("Order này gồm những gì?", "session-2", 3)
    assert question.meta.tool == "autopilot_review_explain"
    assert decisions == []

    approved = await route_autopilot_chat("Đồng ý, tiếp tục", "session-2", 3)
    assert approved.meta.tool == "autopilot_review_chat"
    assert decisions == [True]
