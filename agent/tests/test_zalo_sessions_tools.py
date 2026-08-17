from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_chat_session_rolls_on_idle_and_clears_no_history(monkeypatch):
    from config import config
    import zalo_sessions

    monkeypatch.setattr(config, "ZALO_CHAT_SESSION_IDLE_MINUTES", 20)
    monkeypatch.setattr(config, "ZALO_CHAT_SESSION_MAX_MINUTES", 60)
    started = datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc)
    thread = {"thread_id": "zth-session-test"}
    first, rolled, previous = await zalo_sessions.get_or_roll_chat_session(thread, now=started)
    assert rolled is False and previous is None
    await zalo_sessions.append_chat_message(
        first["chat_session_id"], "user", "Xin chào", now=started,
    )

    second, rolled, previous = await zalo_sessions.get_or_roll_chat_session(
        thread, now=started + timedelta(minutes=21),
    )
    assert rolled is True
    assert second["sequence"] == 2
    assert previous["status"] == "closed"
    assert previous["close_reason"] == "idle_timeout"
    assert previous["summary_status"] == "queued"


@pytest.mark.asyncio
async def test_chat_session_hard_limit_wins_during_continuous_chat(monkeypatch):
    from config import config
    import zalo_sessions

    monkeypatch.setattr(config, "ZALO_CHAT_SESSION_IDLE_MINUTES", 20)
    monkeypatch.setattr(config, "ZALO_CHAT_SESSION_MAX_MINUTES", 60)
    started = datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc)
    thread = {"thread_id": "zth-hard-limit"}
    first, _, _ = await zalo_sessions.get_or_roll_chat_session(thread, now=started)
    await zalo_sessions.append_chat_message(
        first["chat_session_id"], "user", "still here",
        now=started + timedelta(minutes=55),
    )
    second, rolled, previous = await zalo_sessions.get_or_roll_chat_session(
        thread, now=started + timedelta(minutes=61),
    )
    assert rolled is True
    assert second["sequence"] == 2
    assert previous["close_reason"] == "hard_limit"


@pytest.mark.asyncio
async def test_context_keeps_newest_30_and_respects_token_budget(monkeypatch):
    from config import config
    import zalo_sessions

    monkeypatch.setattr(config, "ZALO_CONTEXT_MAX_MESSAGES", 30)
    monkeypatch.setattr(config, "ZALO_CONTEXT_MAX_INPUT_TOKENS", 24000)
    session, _, _ = await zalo_sessions.get_or_roll_chat_session({"thread_id": "zth-context"})
    for index in range(35):
        await zalo_sessions.append_chat_message(
            session["chat_session_id"], "user" if index % 2 == 0 else "assistant",
            f"message-{index}",
        )
    stored = zalo_sessions._mem_sessions[session["chat_session_id"]]
    messages, _ = await zalo_sessions.build_context("zth-context", stored)
    assert len(messages) == 30
    assert messages[0]["content"] == "message-5"
    assert messages[-1]["content"] == "message-34"


@pytest.mark.asyncio
async def test_summary_worker_persists_structured_memory(monkeypatch):
    from config import config
    import zalo_sessions

    monkeypatch.setattr(config, "ZALO_SUMMARY_MESSAGE_INTERVAL", 1)
    session, _, _ = await zalo_sessions.get_or_roll_chat_session({"thread_id": "zth-summary"})
    await zalo_sessions.append_chat_message(session["chat_session_id"], "user", "Nhớ campaign Doraemon")
    summarizer = AsyncMock(return_value={
        "summary": "User discussed Doraemon", "user_goals": [],
        "campaigns_discussed": ["Doraemon"], "resolved_questions": [],
        "unresolved_questions": [], "decisions": [], "user_preferences": [],
        "last_topic": "Doraemon", "last_campaign_reference": "Doraemon",
    })
    monkeypatch.setattr("zalo_openai.summarize_zalo_session", summarizer)
    assert await zalo_sessions.process_summary_once() is True
    stored = zalo_sessions._mem_sessions[session["chat_session_id"]]
    assert stored["summary_status"] == "idle"
    assert stored["summary"]["campaigns_discussed"] == ["Doraemon"]
    assert stored["summary_up_to_seq"] == 1


class _Responses:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(output=[{
                "type": "function_call", "call_id": "call-1",
                "name": "list_campaigns", "arguments": '{"status":"active"}',
            }], output_text="")
        return SimpleNamespace(output=[], output_text="Bạn có một chiến dịch đang chạy.")


@pytest.mark.asyncio
async def test_tool_agent_runs_function_call_round_trip(monkeypatch):
    import zalo_openai
    import zalo_tools
    from config import config

    responses = _Responses()
    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(zalo_openai, "_client", SimpleNamespace(responses=responses))
    executor = AsyncMock(return_value={"ok": True, "campaigns": [{"brand": "Doraemon"}]})
    monkeypatch.setattr(zalo_tools, "execute_zalo_tool", executor)

    result = await zalo_openai.run_zalo_tool_turn(
        thread={"thread_id": "zth-tool", "pending_action": None},
        message="Có campaign nào đang chạy?",
        messages=[{"role": "user", "content": "Có campaign nào đang chạy?"}],
        bridge_summary=None,
    )
    assert result.tool_calls == ["list_campaigns"]
    assert "một chiến dịch" in result.text
    executor.assert_awaited_once()
    second_input = responses.calls[1]["input"]
    assert any(item.get("type") == "function_call_output" and item.get("call_id") == "call-1" for item in second_input)
    assert responses.calls[0]["store"] is False
    assert responses.calls[0]["parallel_tool_calls"] is False


@pytest.mark.asyncio
async def test_list_campaigns_exposes_owned_comparison_fields(monkeypatch):
    import zalo_campaign_agent
    from zalo_tools import ToolExecutionContext, execute_zalo_tool

    campaigns = [
        {
            "campaign_id": "ORD-LOW",
            "order": {
                "brand": "Low Budget",
                "status": "paused",
                "objective": "awareness",
                "budget": 10_000_000,
                "startDate": "2026-07-20",
                "endDate": "2026-07-22",
            },
        },
        {
            "campaign_id": "ORD-HIGH",
            "order": {
                "brand": "High Budget",
                "status": "active",
                "objective": "conversion",
                "budget": 120_000_000,
                "startDate": "2026-07-23",
                "endDate": "2026-07-30",
            },
        },
    ]
    owned = AsyncMock(return_value=campaigns)
    monkeypatch.setattr(zalo_campaign_agent, "owned_campaigns", owned)
    context = ToolExecutionContext(
        thread={"thread_id": "zth-comparison", "session_id": "sess-comparison"},
        current_message="Campaign nào budget cao nhất?",
        history=[],
    )

    result = await execute_zalo_tool(context, "list_campaigns", {"status": "all"})

    assert result["ok"] is True
    assert result["campaigns"] == [
        {
            "campaign_id": "ORD-LOW",
            "brand": "Low Budget",
            "status": "paused",
            "objective": "awareness",
            "budget": 10_000_000,
            "start_date": "2026-07-20",
            "end_date": "2026-07-22",
            "index": 1,
        },
        {
            "campaign_id": "ORD-HIGH",
            "brand": "High Budget",
            "status": "active",
            "objective": "conversion",
            "budget": 120_000_000,
            "start_date": "2026-07-23",
            "end_date": "2026-07-30",
            "index": 2,
        },
    ]
    owned.assert_awaited_once_with(context.thread)


def test_tool_schemas_never_accept_owner_identifiers():
    from zalo_tools import ZALO_TOOLS

    serialized = str(ZALO_TOOLS).lower()
    for forbidden in ("user_id", "owner_id", "anonymous_id", "account_session_id"):
        assert forbidden not in serialized
    assert all(tool["strict"] is True for tool in ZALO_TOOLS)
    assert all(tool["parameters"]["additionalProperties"] is False for tool in ZALO_TOOLS)


def test_oversized_tool_output_remains_valid_json(monkeypatch):
    from config import config
    from zalo_tools import tool_output_json

    monkeypatch.setattr(config, "ZALO_CONTEXT_MAX_TOOL_TOKENS", 100)
    parsed = json.loads(tool_output_json({"ok": True, "answer": "x" * 5000}))
    assert parsed["ok"] is True
    assert parsed["truncated"] is True
    assert "content_prefix" in parsed
