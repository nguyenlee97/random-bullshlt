from datetime import timedelta
from unittest.mock import AsyncMock

import pytest


def _campaign(order_id, brand, status="active", session_id=None):
    return {
        "campaign_id": order_id,
        "conversation_id": f"conv-{order_id}",
        "session_id": session_id or f"sess-{order_id}",
        "conversation_title": brand,
        "experience_mode": "autopilot",
        "order": {
            "id": order_id, "brand": brand, "status": status,
            "objective": "awareness", "budget": 10_000_000,
            "startDate": "2026-08-01", "endDate": "2026-08-31",
            "placements": ["ZN.Masthead.Desktop"],
        },
    }


def test_campaign_resolver_exact_partial_active_and_ambiguous():
    from zalo_campaign_agent import resolve_campaign

    summer = _campaign("ORD-2026-101", "Summer Awareness")
    school = _campaign("ORD-2026-102", "Back To School")
    campaigns = [summer, school]

    selected, ambiguous = resolve_campaign("status ORD-2026-102", campaigns)
    assert selected["campaign_id"] == "ORD-2026-102"
    assert ambiguous == []

    selected, _ = resolve_campaign("bao cao summer", campaigns)
    assert selected["campaign_id"] == "ORD-2026-101"

    selected, _ = resolve_campaign("campaign này đang sao?", campaigns, "ORD-2026-102")
    assert selected["campaign_id"] == "ORD-2026-102"

    selected, ambiguous = resolve_campaign("xem trạng thái", campaigns)
    assert selected is None
    assert {item["campaign_id"] for item in ambiguous} == {"ORD-2026-101", "ORD-2026-102"}

    selected, ambiguous = resolve_campaign(
        "chào", [summer], allow_context_fallback=False,
    )
    assert selected is None
    assert ambiguous == []


@pytest.mark.asyncio
async def test_greeting_does_not_implicitly_select_only_campaign(monkeypatch):
    import zalo_campaign_agent as agent

    campaign = _campaign("ORD-GREET", "Doraemon")
    monkeypatch.setattr(agent, "owned_campaigns", AsyncMock(return_value=[campaign]))

    greeting = await agent.handle_channel_event({
        "event_name": "user_send_text",
        "external_uid": "oa-user-greeting",
        "text": "chào",
    })
    assert "Tôi có thể giúp" in greeting[0]
    assert "ORD-GREET" not in greeting[0]
    assert "Ngân sách" not in greeting[0]

    thread = await agent.get_or_create_thread("oa-user-greeting")
    assert thread["active_campaign_id"] is None

    status = await agent.handle_channel_event({
        "event_name": "user_send_text",
        "external_uid": "oa-user-greeting",
        "text": "trạng thái chiến dịch",
    })
    assert "ORD-GREET" in status[0]


@pytest.mark.asyncio
async def test_owned_campaigns_fetches_only_order_ids_from_owned_conversations(monkeypatch):
    from identity import bootstrap_anonymous, create_conversation
    from session import update_order_ids
    from zalo_campaign_agent import owned_campaigns

    owner = await bootstrap_anonymous()
    foreign = await bootstrap_anonymous()
    mine = await create_conversation(owner["identity_id"], title="Mine")
    theirs = await create_conversation(foreign["identity_id"], title="Theirs")
    await update_order_ids(mine["session_id"], ["ORD-MINE"])
    await update_order_ids(theirs["session_id"], ["ORD-FOREIGN"])

    fetch = AsyncMock(side_effect=lambda order_id: {
        "id": order_id, "brand": order_id, "status": "active",
    })
    monkeypatch.setattr("tools.order_api.fetch_order", fetch)
    campaigns = await owned_campaigns({
        "anonymous_id": owner["identity_id"], "user_id": None,
    })

    assert [item["campaign_id"] for item in campaigns] == ["ORD-MINE"]
    fetch.assert_awaited_once_with("ORD-MINE")


@pytest.mark.asyncio
async def test_pause_requires_confirmation_and_rechecks_selected_campaign(monkeypatch):
    import zalo_campaign_agent as agent

    thread = await agent.get_or_create_thread("oa-user-lifecycle")
    campaign = _campaign("ORD-PAUSE", "Pause Me")
    prompt = await agent._lifecycle_request(thread, campaign, "pause")
    assert "Xác nhận" in prompt
    stored = agent._mem_threads[thread["thread_id"]]
    assert stored["pending_action"]["campaign_id"] == "ORD-PAUSE"

    mutation = AsyncMock(return_value={
        "ok": True, "newStatus": "paused", "already_in_state": False,
    })
    monkeypatch.setattr("tools.order_api.set_order_delivery_state", mutation)
    text, _ = await agent._handle_pending(
        agent._public(stored), "Xác nhận", [campaign],
    )
    assert "đã tạm dừng" in text
    mutation.assert_awaited_once_with("ORD-PAUSE", "pause")
    assert agent._mem_threads[thread["thread_id"]]["pending_action"] is None


@pytest.mark.asyncio
async def test_pause_confirmation_fails_closed_when_ownership_disappears(monkeypatch):
    import zalo_campaign_agent as agent

    thread = await agent.get_or_create_thread("oa-user-ownership-loss")
    campaign = _campaign("ORD-LOST", "No Longer Mine")
    await agent._lifecycle_request(thread, campaign, "pause")
    mutation = AsyncMock()
    monkeypatch.setattr("tools.order_api.set_order_delivery_state", mutation)
    text, _ = await agent._handle_pending(
        agent._public(agent._mem_threads[thread["thread_id"]]), "Xác nhận", [],
    )
    assert "Không còn quyền" in text
    mutation.assert_not_awaited()


@pytest.mark.asyncio
async def test_zalo_autopilot_modes_map_to_existing_policies(monkeypatch):
    import zalo_campaign_agent as agent

    thread = await agent.get_or_create_thread("oa-user-autopilot")
    pending = {
        "kind": "choose_autopilot_mode",
        "expires_at": agent._now() + timedelta(minutes=5),
    }
    thread = await agent._update_thread(thread, {"pending_action": pending})

    text, updated = await agent._handle_pending(thread, "Tự động hoàn toàn", [])
    assert "gửi brief" in text
    assert updated["pending_action"]["mode"] == "fully_automatic"

    monkeypatch.setattr(agent, "_start_autopilot", AsyncMock(return_value={
        "thread": updated, "text": "started",
    }))
    updated = await agent._update_thread(updated, {"pending_action": {
        "kind": "confirm_autopilot_brief", "mode": "fully_automatic",
        "brief": {"brand": "Demo"},
        "expires_at": agent._now() + timedelta(minutes=5),
    }})
    text, _ = await agent._handle_pending(updated, "Xác nhận", [])
    assert text == "started"
    agent._start_autopilot.assert_awaited_once_with(updated, {"brand": "Demo"}, "fully_automatic")


def test_progress_messages_are_milestone_scoped_and_launch_is_explicit():
    from zalo_worker import _progress_message

    run = {
        "run_id": "run-1",
        "tasks": [
            {"task_id": "task-a", "key": "retrieve_audience"},
            {"task_id": "task-launch", "key": "launch_approval", "title": "Launch"},
            {"task_id": "task-noise", "key": "normalize_brief"},
        ],
    }
    assert "audience" in _progress_message(run, {
        "type": "task_completed", "payload": {"task_id": "task-a"},
    })
    assert _progress_message(run, {
        "type": "task_completed", "payload": {"task_id": "task-noise"},
    }) is None
    assert "XÁC NHẬN LAUNCH" in _progress_message(run, {
        "type": "task_waiting_review", "payload": {"task_id": "task-launch"},
    })


@pytest.mark.asyncio
async def test_live_screenshot_uses_short_lived_opaque_media_url(monkeypatch):
    import base64
    import zalo_campaign_agent as agent

    monkeypatch.setattr(
        "handlers.screenshot.handle_screenshot",
        AsyncMock(return_value={
            "ok": True,
            "full_b64": base64.b64encode(b"fake-png").decode(),
        }),
    )
    response = await agent._live_response(_campaign("ORD-LIVE", "Live Demo"))
    assert response[1]["kind"] == "image"
    assert "/zalo/media/" in response[1]["image_url"]
    token = response[1]["image_url"].rsplit("/", 1)[-1]
    media = await agent.get_channel_media(token)
    assert media == (b"fake-png", "image/png")
    assert token not in agent._mem_media
