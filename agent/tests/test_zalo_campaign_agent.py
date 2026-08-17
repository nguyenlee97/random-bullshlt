from datetime import timedelta
from types import SimpleNamespace
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
    assert "trợ lý đồng hành" in greeting[0]
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
async def test_openai_tool_agent_understands_active_campaign_list_request(monkeypatch):
    import zalo_campaign_agent as agent
    from config import config
    from zalo_openai import ZaloToolTurnResult

    campaigns = [
        _campaign("ORD-RUNNING", "Doraemon", "active"),
        _campaign("ORD-PAUSED", "Summer", "paused"),
    ]
    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    monkeypatch.setattr(agent, "owned_campaigns", AsyncMock(return_value=campaigns))
    tool_agent = AsyncMock(return_value=ZaloToolTurnResult(
        text="Doraemon — active — ORD-RUNNING", thread={},
        media_parts=[], tool_calls=["list_campaigns"],
    ))
    monkeypatch.setattr("zalo_openai.run_zalo_tool_turn", tool_agent)

    response = await agent.handle_channel_event({
        "event_name": "user_send_text",
        "external_uid": "oa-user-natural-list",
        "text": "đang có chiến dịch gì đang chạy",
    })

    assert "Doraemon" in response[0]
    assert "ORD-RUNNING" in response[0]
    assert "Summer" not in response[0]
    assert "Tôi có thể giúp" not in response[0]
    tool_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_planner_resolves_natural_pending_selection_only_within_choices(monkeypatch):
    import zalo_campaign_agent as agent
    from config import config
    from zalo_openai import ZaloTurnPlan

    campaigns = [
        _campaign("ORD-ONE", "First"),
        _campaign("ORD-TWO", "Second"),
        _campaign("ORD-OTHER", "Not Offered"),
    ]
    thread = await agent.get_or_create_thread("oa-user-natural-select")
    thread = await agent._update_thread(thread, {"pending_action": {
        "kind": "campaign_selection",
        "campaign_ids": ["ORD-ONE", "ORD-TWO"],
        "expires_at": agent._now() + timedelta(minutes=5),
    }})
    planner = AsyncMock(return_value=ZaloTurnPlan(
        intent="select_campaign", selected_campaign_index=2,
    ))
    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    monkeypatch.setattr("zalo_openai.plan_zalo_turn", planner)

    text, updated = await agent._handle_pending(
        thread, "chọn cái thứ hai", campaigns,
    )

    assert "ORD-TWO" in text
    assert updated["active_campaign_id"] == "ORD-TWO"
    planner.assert_awaited_once()
    assert [
        item["campaign_id"] for item in planner.await_args.kwargs["campaigns"]
    ] == ["ORD-ONE", "ORD-TWO"]


@pytest.mark.asyncio
async def test_openai_planner_failure_fails_closed_without_campaign_mutation(monkeypatch):
    import zalo_campaign_agent as agent
    from config import config

    campaign = _campaign("ORD-SAFE", "Safe Campaign")
    mutation = AsyncMock()
    log_error = AsyncMock()
    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    monkeypatch.setattr(agent, "owned_campaigns", AsyncMock(return_value=[campaign]))
    monkeypatch.setattr(agent, "alog", log_error)
    monkeypatch.setattr(
        "zalo_openai.run_zalo_tool_turn",
        AsyncMock(side_effect=RuntimeError("provider down")),
    )
    monkeypatch.setattr("tools.order_api.set_order_delivery_state", mutation)

    response = await agent.handle_channel_event({
        "event_name": "user_send_text",
        "external_uid": "oa-user-provider-failure",
        "text": "tạm dừng chiến dịch này",
    })

    assert "đang tạm thời không phản hồi" in response[0]
    assert "Không có thao tác" in response[0]
    mutation.assert_not_awaited()
    log_error.assert_awaited_once()
    assert log_error.await_args.args[1] == "error"
    assert log_error.await_args.args[2] == {
        "handler": "zalo_tool_turn",
        "error_type": "RuntimeError",
        "error": "provider down",
    }


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
async def test_owned_campaign_survives_history_deletion(monkeypatch):
    from identity import bootstrap_anonymous, create_conversation, delete_conversation
    from session import update_order_ids
    from zalo_campaign_agent import owned_campaigns

    owner = await bootstrap_anonymous()
    conversation = await create_conversation(owner["identity_id"], title="Delete chat")
    await update_order_ids(conversation["session_id"], ["ORD-RETAINED"])
    result = await delete_conversation(
        owner["identity_id"], conversation["conversation_id"]
    )

    assert result["retained_campaign_ids"] == ["ORD-RETAINED"]
    monkeypatch.setattr("tools.order_api.fetch_order", AsyncMock(return_value={
        "id": "ORD-RETAINED", "brand": "Retained", "status": "active",
    }))
    campaigns = await owned_campaigns({
        "anonymous_id": owner["identity_id"], "user_id": None,
    })
    assert [item["campaign_id"] for item in campaigns] == ["ORD-RETAINED"]


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


@pytest.mark.asyncio
async def test_openai_natural_brief_confirmation_uses_validated_semantic_decision(monkeypatch):
    import zalo_campaign_agent as agent
    from config import config
    from zalo_openai import ZaloPendingBriefDecision

    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    thread = await agent.get_or_create_thread("oa-natural-brief-confirm")
    thread = await agent._update_thread(thread, {"pending_action": {
        "kind": "confirm_autopilot_brief",
        "mode": "semi_automatic",
        "brief": {"brand": "GreenFarm"},
        "expires_at": agent._now() + timedelta(minutes=5),
    }})
    classifier = AsyncMock(return_value=ZaloPendingBriefDecision(
        intent="approve",
        explicit=True,
        evidence="làm luôn theo brief này",
    ))
    start = AsyncMock(return_value={"thread": thread, "text": "started"})
    tool_loop = AsyncMock(side_effect=AssertionError("tool loop must not run"))
    monkeypatch.setattr("zalo_openai.classify_pending_brief_decision", classifier)
    monkeypatch.setattr("zalo_openai.run_zalo_tool_turn", tool_loop)
    monkeypatch.setattr(agent, "_start_autopilot", start)
    monkeypatch.setattr(agent, "owned_campaigns", AsyncMock(return_value=[]))

    result = await agent.handle_channel_event({
        "event_name": "user_send_text",
        "external_uid": "oa-natural-brief-confirm",
        "text": "Được, làm luôn theo brief này nhé",
    })

    assert result == ["started"]
    start.assert_awaited_once()
    assert start.await_args.args[1:] == (
        {"brand": "GreenFarm"}, "semi_automatic",
    )
    tool_loop.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_brief_question_and_invalid_evidence_fail_closed(monkeypatch):
    import zalo_campaign_agent as agent
    from config import config
    from zalo_openai import ZaloPendingBriefDecision

    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    start = AsyncMock()
    tool_loop = AsyncMock(side_effect=AssertionError("tool loop must not run"))
    monkeypatch.setattr(agent, "_start_autopilot", start)
    monkeypatch.setattr("zalo_openai.run_zalo_tool_turn", tool_loop)

    for uid, decision in (
        (
            "oa-brief-question",
            ZaloPendingBriefDecision(
                intent="question",
                explicit=False,
                reply="Brief chưa chạy; bạn đang hỏi về lịch.",
            ),
        ),
        (
            "oa-brief-bad-evidence",
            ZaloPendingBriefDecision(
                intent="approve",
                explicit=True,
                evidence="xác nhận ngay",
            ),
        ),
    ):
        thread = await agent.get_or_create_thread(uid)
        await agent._update_thread(thread, {"pending_action": {
            "kind": "confirm_autopilot_brief",
            "mode": "semi_automatic",
            "brief": {"brand": "GreenFarm"},
            "expires_at": agent._now() + timedelta(minutes=5),
        }})
        monkeypatch.setattr(
            "zalo_openai.classify_pending_brief_decision",
            AsyncMock(return_value=decision),
        )
        result = await agent.handle_channel_event({
            "event_name": "user_send_text",
            "external_uid": uid,
            "text": "Lịch này ổn không?",
        })
        assert "chưa" in result[0].lower() or "chờ duyệt" in result[0].lower()
        updated = await agent.get_or_create_thread(uid)
        assert updated["pending_action"]["kind"] == "confirm_autopilot_brief"

    start.assert_not_awaited()
    tool_loop.assert_not_awaited()


@pytest.mark.asyncio
async def test_workspace_link_tool_uses_owned_active_conversation(monkeypatch):
    import zalo_campaign_agent as agent
    from config import config
    from identity import create_conversation
    from zalo_tools import ToolExecutionContext, ZALO_TOOLS, execute_zalo_tool

    thread = await agent.get_or_create_thread("oa-user-workspace-link")
    campaign = await create_conversation(
        agent._thread_actor(thread), title="Workspace Link",
        experience_mode="autopilot",
    )
    thread = await agent._update_thread(thread, {
        "active_campaign_conversation_id": campaign["conversation_id"],
        "active_campaign_session_id": campaign["session_id"],
    })
    ctx = ToolExecutionContext(
        thread=thread, current_message="give me workspace link", history=[],
    )

    result = await execute_zalo_tool(
        ctx, "get_workspace_link", {"campaign_reference": None},
    )

    assert result["ok"] is True
    assert result["workspace_url"] == (
        f"{config.ZALO_WEB_WORKSPACE_URL}/?conversation={campaign['conversation_id']}"
    )
    assert campaign["session_id"] not in result["workspace_url"]
    schema = next(tool for tool in ZALO_TOOLS if tool["name"] == "get_workspace_link")
    assert schema["strict"] is True
    assert "user_id" not in str(schema["parameters"])


@pytest.mark.asyncio
async def test_workspace_link_tool_does_not_leak_foreign_conversation():
    import zalo_campaign_agent as agent
    from identity import bootstrap_anonymous, create_conversation
    from zalo_tools import ToolExecutionContext, execute_zalo_tool

    thread = await agent.get_or_create_thread("oa-user-workspace-owner")
    foreign = await bootstrap_anonymous()
    foreign_campaign = await create_conversation(
        foreign["identity_id"], title="Foreign", experience_mode="autopilot",
    )
    thread = await agent._update_thread(thread, {
        "active_campaign_conversation_id": foreign_campaign["conversation_id"],
        "active_campaign_session_id": foreign_campaign["session_id"],
    })
    ctx = ToolExecutionContext(
        thread=thread, current_message="give me workspace link", history=[],
    )

    result = await execute_zalo_tool(
        ctx, "get_workspace_link", {"campaign_reference": None},
    )

    assert result["ok"] is False
    assert result["error"] == "campaign_reference_required"
    assert foreign_campaign["conversation_id"] not in str(result)


@pytest.mark.asyncio
async def test_openai_understands_natural_autopilot_mode_without_starting_run(monkeypatch):
    import zalo_campaign_agent as agent
    from config import config
    from zalo_openai import ZaloTurnPlan

    thread = await agent.get_or_create_thread("oa-user-natural-mode")
    thread = await agent._update_thread(thread, {"pending_action": {
        "kind": "choose_autopilot_mode",
        "expires_at": agent._now() + timedelta(minutes=5),
    }})
    planner = AsyncMock(return_value=ZaloTurnPlan(
        intent="start_autopilot", autopilot_mode="fully_automatic",
    ))
    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    monkeypatch.setattr("zalo_openai.plan_zalo_turn", planner)

    text, updated = await agent._handle_pending(
        thread, "cứ tự làm hết, chỉ hỏi tôi lúc cuối", [],
    )

    assert "gửi brief" in text
    assert updated["pending_action"]["kind"] == "collect_autopilot_brief"
    assert updated["pending_action"]["mode"] == "fully_automatic"
    planner.assert_awaited_once()


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
async def test_openai_zalo_review_question_uses_exact_checkpoint_context(monkeypatch):
    import autopilot.chat as autopilot_chat
    import autopilot.service as autopilot_service
    import zalo_campaign_agent as agent
    from campaign_models import OPENAI_GPT_5_4_MINI
    from config import config

    thread = await agent.get_or_create_thread("oa-user-openai-review-question")
    await agent._update_thread(thread, {
        "active_campaign_session_id": "session-openai-review",
    })
    monkeypatch.setattr(config, "ZALO_OPENAI_ENABLED", True)
    monkeypatch.setattr(autopilot_service, "get_latest_run", AsyncMock(return_value={
        "run_id": "run-openai-review",
        "status": "waiting_review",
        "conversation_model": OPENAI_GPT_5_4_MINI,
        "tasks": [{
            "task_id": "run-openai-review:retrieve_audience",
            "key": "retrieve_audience",
            "status": "waiting_review",
        }],
    }))
    review = AsyncMock(return_value=SimpleNamespace(
        text="Segment Tea phù hợp trực tiếp với brief; checkpoint vẫn đang chờ duyệt.",
    ))
    monkeypatch.setattr(autopilot_chat, "route_autopilot_chat", review)
    tool_agent = AsyncMock(side_effect=AssertionError("generic Zalo tool loop was called"))
    monkeypatch.setattr("zalo_openai.run_zalo_tool_turn", tool_agent)

    response = await agent.handle_channel_event({
        "event_name": "user_send_text",
        "external_uid": "oa-user-openai-review-question",
        "text": "Tại sao agent đề xuất segment Tea?",
    })

    assert "Segment Tea" in response[0]
    review.assert_awaited_once_with(
        "Tại sao agent đề xuất segment Tea?",
        "session-openai-review",
        0,
    )
    tool_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_remote_creative_preview_reuses_zalo_image_optimizer(monkeypatch):
    import httpx
    import zalo_campaign_agent as agent

    class FakeResponse:
        content = b"large-generated-image"
        headers = {"content-type": "image/png"}

        def raise_for_status(self):
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _url):
            return FakeResponse()

    optimized = AsyncMock(return_value=[{
        "kind": "image",
        "image_url": "https://example.test/zalo-safe.png",
        "byte_size": 800_000,
    }])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    monkeypatch.setattr(agent, "_delivery_image_parts", optimized)

    parts = await agent._prepare_remote_review_media_parts([{
        "kind": "image",
        "image_url": "https://example.test/original.png",
    }])

    assert parts[0]["byte_size"] == 800_000
    optimized.assert_awaited_once_with(
        b"large-generated-image",
        "image/png",
        label="creative 1",
    )


@pytest.mark.asyncio
async def test_live_screenshot_uses_short_lived_opaque_media_url(monkeypatch):
    import base64
    import io
    from PIL import Image
    import zalo_campaign_agent as agent

    png_buffer = io.BytesIO()
    Image.new("RGB", (80, 60), "red").save(png_buffer, format="PNG")
    jpeg_buffer = io.BytesIO()
    Image.new("RGB", (120, 90), "blue").save(jpeg_buffer, format="JPEG")

    monkeypatch.setattr(
        agent.config,
        "LOCAL_BAOMOI_URL",
        "https://zah-4.123c.vn/baomoi/",
    )
    screenshot_capture = AsyncMock(return_value={
            "ok": True,
            "zones": [{
                "id": "BaoMoi_Masthead", "label": "Masthead",
                "crop_b64": base64.b64encode(png_buffer.getvalue()).decode(),
            }],
            "full_b64": base64.b64encode(jpeg_buffer.getvalue()).decode(),
        })
    monkeypatch.setattr(
        "handlers.screenshot.handle_screenshot",
        screenshot_capture,
    )
    campaign = _campaign("ORD-LIVE", "Live Demo")
    campaign["order"]["placements"] = ["BaoMoi_Masthead"]
    response = await agent._live_response(campaign, requested_site="baomoi")
    screenshot_capture.assert_awaited_once_with(
        url="https://zah-4.123c.vn/baomoi/",
        session_id=campaign["session_id"],
        zone_ids=["BaoMoi_Masthead"],
    )
    assert response[0] == "Đây là ảnh live quảng cáo trên BaoMoi:"
    assert response[1]["kind"] == "image"
    assert "/zalo/media/" in response[1]["image_url"]
    token = response[1]["image_url"].rsplit("/", 1)[-1]
    media = await agent.get_channel_media(token)
    assert media == (png_buffer.getvalue(), "image/png")
    assert response[2]["kind"] == "image"
    full_token = response[2]["image_url"].rsplit("/", 1)[-1]
    assert await agent.get_channel_media(full_token) == (
        jpeg_buffer.getvalue(), "image/jpeg",
    )
    assert token not in agent._mem_media


@pytest.mark.asyncio
async def test_live_screenshot_uses_exact_snapshot_category_pages(monkeypatch):
    import zalo_campaign_agent as agent

    monkeypatch.setattr(
        agent.config, "LOCAL_ZNEWS_URL", "https://zah-4.123c.vn/znews/",
    )
    monkeypatch.setattr(
        agent.config, "LOCAL_BAOMOI_URL", "https://zah-4.123c.vn/baomoi/",
    )
    screenshot_capture = AsyncMock(return_value={
        "ok": True, "zones": [], "full_b64": None,
    })
    monkeypatch.setattr(
        "handlers.screenshot.handle_screenshot", screenshot_capture,
    )

    campaign = _campaign("ORD-CATEGORY-LIVE", "Gaming Launch")
    campaign["order"]["placements"] = [
        "Znews_Gaming_Masthead",
        "Znews_Gaming_SidebarBox",
        "BaoMoi_Gaming_SidebarBox",
    ]
    campaign["order"]["placementSnapshots"] = [
        {
            "id": "Znews_Gaming_Masthead",
            "publisher": "ZNews",
            "siteUrl": "https://znews-stg.pawgrammers.io.vn/cong-nghe.html",
        },
        {
            "id": "Znews_Gaming_SidebarBox",
            "publisher": "ZNews",
            "siteUrl": "https://znews-stg.pawgrammers.io.vn/cong-nghe.html",
        },
        {
            "id": "BaoMoi_Gaming_SidebarBox",
            "publisher": "BaoMoi",
            "siteUrl": (
                "https://baomoi-stg.pawgrammers.io.vn/"
                "category.html?topic=gaming"
            ),
        },
    ]

    response = await agent._live_response(campaign)

    assert screenshot_capture.await_count == 2
    assert screenshot_capture.await_args_list[0].kwargs == {
        "url": "https://zah-4.123c.vn/znews/cong-nghe.html",
        "session_id": campaign["session_id"],
        "zone_ids": [
            "Znews_Gaming_Masthead",
            "Znews_Gaming_SidebarBox",
        ],
    }
    assert screenshot_capture.await_args_list[1].kwargs == {
        "url": "https://zah-4.123c.vn/baomoi/category.html?topic=gaming",
        "session_id": campaign["session_id"],
        "zone_ids": ["BaoMoi_Gaming_SidebarBox"],
    }
    assert response == [
        "Đây là ảnh live quảng cáo trên Znews:",
        "Đây là ảnh live quảng cáo trên BaoMoi:",
    ]
    live_text = agent._live_text(campaign)
    assert "https://zah-4.123c.vn/znews/cong-nghe.html" in live_text
    assert "https://zah-4.123c.vn/baomoi/category.html?topic=gaming" in live_text
    assert "https://zah-4.123c.vn/znews/\n" not in live_text
