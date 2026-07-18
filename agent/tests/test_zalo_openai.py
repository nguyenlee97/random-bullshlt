import json
from types import SimpleNamespace

import pytest


class _FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.parsed)


class _FakeClient:
    def __init__(self, parsed):
        self.responses = _FakeResponses(parsed)


@pytest.mark.asyncio
async def test_turn_planner_uses_gpt_54_mini_structured_responses_privately(monkeypatch):
    import zalo_openai
    from config import config

    parsed = zalo_openai.ZaloTurnPlan(
        intent="list_campaigns", campaign_status_filter="active",
    )
    client = _FakeClient(parsed)
    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(config, "ZALO_CHAT_MODEL", "gpt-5.4-mini")
    monkeypatch.setattr(zalo_openai, "_client", client)
    history = [
        {"role": "user", "content": f"message-{index}"}
        for index in range(15)
    ]
    thread = {
        "thread_id": "zth-private-raw-id",
        "external_uid": "must-never-reach-model",
        "user_id": "usr-must-never-reach-model",
        "active_campaign_id": "ORD-ONE",
        "pending_action": None,
    }

    result = await zalo_openai.plan_zalo_turn(
        message="đang có chiến dịch gì đang chạy",
        history=history,
        campaigns=[{
            "campaign_id": "ORD-ONE",
            "order": {"brand": "Doraemon", "status": "active", "objective": "awareness"},
        }],
        thread=thread,
    )

    assert result == parsed
    call = client.responses.calls[0]
    assert call["model"] == "gpt-5.4-mini"
    assert call["text_format"] is zalo_openai.ZaloTurnPlan
    assert call["store"] is False
    assert call["safety_identifier"].startswith("zalo_")
    assert "zth-private-raw-id" not in call["safety_identifier"]
    context = json.loads(call["input"])
    assert len(context["recent_messages"]) == 12
    serialized = call["input"]
    assert "must-never-reach-model" not in serialized
    assert "usr-must-never-reach-model" not in serialized
    assert context["owned_campaigns"][0]["campaign_id"] == "ORD-ONE"


@pytest.mark.asyncio
async def test_reply_renderer_is_grounded_in_server_tool_result(monkeypatch):
    import zalo_openai
    from config import config

    client = _FakeClient(zalo_openai.ZaloRenderedReply(
        text="Doraemon đang hoạt động.",
    ))
    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(zalo_openai, "_client", client)

    text = await zalo_openai.render_zalo_reply(
        message="nó đang chạy không?",
        history=[],
        intent="status",
        tool_result="Campaign Doraemon status=active",
        thread_id="zth-render",
    )

    assert text == "Doraemon đang hoạt động."
    context = json.loads(client.responses.calls[0]["input"])
    assert context["tool_result"] == "Campaign Doraemon status=active"
