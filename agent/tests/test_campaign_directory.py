from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_directory_unifies_drafts_reviews_and_owned_orders(monkeypatch):
    import campaign_directory
    import campaign_ownership
    import identity
    import session
    from tools import order_api

    conversations = [
        {
            "conversation_id": "conv-draft",
            "session_id": "sess-draft",
            "title": "Generic unfinished chat",
            "experience_mode": "guided",
            "updated_at": "2026-08-20T09:00:00Z",
        },
        {
            "conversation_id": "conv-review",
            "session_id": "sess-review",
            "title": "Forecast waiting for review",
            "experience_mode": "autopilot",
            "updated_at": "2026-08-20T11:00:00Z",
            "latest_run_summary": {
                "run_id": "run-review",
                "status": "waiting_review",
                "current_task": "forecast_order",
                "updated_at": "2026-08-20T11:00:00Z",
                "task_total": 18,
                "task_completed": 11,
            },
        },
        {
            "conversation_id": "conv-order",
            "session_id": "sess-order",
            "title": "Created order",
            "experience_mode": "guided",
            "updated_at": "2026-08-20T10:00:00Z",
        },
    ]

    async def list_conversations(actor, *, include_archived=False):
        assert actor == {"user_id": "owner", "anonymous_id": None}
        assert include_archived is True
        return conversations

    async def preserve(session_id):
        assert session_id.startswith("sess-")
        return []

    async def list_references(actor):
        assert actor == {"user_id": "owner", "anonymous_id": None}
        return [{
            "order_id": "ORD-OWNED",
            "conversation_id": "conv-order",
            "experience_mode": "guided",
            "conversation_title": "Created order",
            "updated_at": "2026-08-20T10:00:00Z",
        }]

    async def progress(session_ids):
        assert set(session_ids) == {"sess-draft", "sess-review", "sess-order"}
        return {
            "sess-draft": {"current_step": 0, "confirmed_steps": [0]},
            "sess-order": {"current_step": 6, "confirmed_steps": list(range(7))},
        }

    fetch_order = AsyncMock(return_value={
        "id": "ORD-OWNED",
        "brand": "Owned Brand",
        "status": "active",
        "objective": "Awareness",
        "budget": 120000000,
        "placements": ["zone-a", "zone-b"],
        "creatives": [{"id": "creative-a"}],
        "warnings": [],
        "updatedAt": "2026-08-20T12:00:00Z",
    })
    monkeypatch.setattr(identity, "list_conversations", list_conversations)
    monkeypatch.setattr(campaign_ownership, "preserve_session_campaigns", preserve)
    monkeypatch.setattr(campaign_ownership, "list_owned_campaign_references", list_references)
    monkeypatch.setattr(session, "get_session_progress_summaries", progress)
    monkeypatch.setattr(order_api, "fetch_order", fetch_order)

    result = await campaign_directory.list_campaign_directory(
        {"user_id": "owner", "anonymous_id": None}, include_archived=True
    )

    assert [item["entry_id"] for item in result] == [
        "conversation:conv-review", "conversation:conv-draft", "conversation:conv-order",
    ]
    assert result[0]["action_required"] == {
        "kind": "workflow_review",
        "run_id": "run-review",
        "task_key": "forecast_order",
        "label": "Duyệt bước forecast order",
    }
    assert result[0]["phase"] == "draft"
    assert result[0]["routes"]["conversation"] == "/agent/autopilot/history/conv-review"
    assert result[0]["progress"] == {
        "kind": "tasks", "completed": 11, "total": 18, "percent": 61,
        "current_key": "forecast_order", "current_label": "Forecast Order",
    }
    assert result[1]["lifecycle"] == "draft"
    assert result[1]["progress"]["current_label"] == "Audience"
    assert result[1]["routes"]["conversation"] == "/agent/copilot/history/conv-draft"
    assert result[2]["phase"] == "operational"
    assert result[2]["order"] == {
        "id": "ORD-OWNED",
        "status": "active",
        "objective": "Awareness",
        "budget": 120000000,
        "daily_budget": None,
        "start_date": None,
        "end_date": None,
        "placement_count": 2,
        "creative_count": 1,
        "placement_preview": [
            {"id": "zone-a", "label": "zone-a", "detail": "", "kind": "placement"},
            {"id": "zone-b", "label": "zone-b", "detail": "", "kind": "placement"},
        ],
        "creative_preview": [
            {"id": "creative-a", "label": "creative-a", "detail": "", "kind": "creative"},
        ],
        "warning_count": 0,
        "order_count": 1,
    }
    assert result[2]["routes"]["manage"] == "/manage/campaigns/ORD-OWNED"
    assert result[2]["routes"]["conversation"] == "/agent/copilot/history/conv-order?readonly=1"
    fetch_order.assert_awaited_once_with("ORD-OWNED")


@pytest.mark.asyncio
async def test_directory_never_fetches_a_foreign_order(monkeypatch):
    from campaign_directory import list_campaign_directory
    from campaign_ownership import register_campaign_for_session
    from identity import create_conversation
    from tools import order_api

    owner = {"user_id": "directory-owner", "anonymous_id": None}
    foreign = {"user_id": "directory-foreign", "anonymous_id": None}
    mine = await create_conversation(owner, title="Mine")
    theirs = await create_conversation(foreign, title="Theirs")
    await register_campaign_for_session(mine["session_id"], "ORD-MINE")
    await register_campaign_for_session(theirs["session_id"], "ORD-FOREIGN")

    async def fetch(order_id):
        assert order_id == "ORD-MINE"
        return {"id": order_id, "brand": "Mine", "status": "active"}

    monkeypatch.setattr(order_api, "fetch_order", fetch)
    result = await list_campaign_directory(owner, include_archived=True)

    assert [item["campaign_id"] for item in result] == ["ORD-MINE"]


@pytest.mark.asyncio
async def test_deep_link_lookup_is_independent_of_directory_limit(monkeypatch):
    import campaign_directory
    import campaign_ownership
    import identity
    from tools import order_api

    references = [
        {"order_id": f"ORD-{index:03d}", "conversation_id": None}
        for index in range(125)
    ]
    monkeypatch.setattr(identity, "list_conversations", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        campaign_ownership, "list_owned_campaign_references",
        AsyncMock(return_value=references),
    )
    fetch = AsyncMock(return_value={
        "id": "ORD-124", "brand": "Deep link QA", "status": "paused",
    })
    monkeypatch.setattr(order_api, "fetch_order", fetch)

    entry = await campaign_directory.get_campaign_directory_entry(
        {"user_id": "owner", "anonymous_id": None}, "ORD-124",
    )

    assert entry["campaign_id"] == "ORD-124"
    assert entry["routes"]["manage"] == "/manage/campaigns/ORD-124"
    fetch.assert_awaited_once_with("ORD-124")


@pytest.mark.asyncio
async def test_directory_retains_owned_campaign_after_conversation_deletion(monkeypatch):
    from campaign_directory import list_campaign_directory
    from identity import bootstrap_anonymous, create_conversation, delete_conversation
    from session import update_order_ids
    from tools import order_api

    identity = await bootstrap_anonymous()
    actor = {"user_id": None, "anonymous_id": identity["identity_id"]}
    conversation = await create_conversation(actor, title="Campaign retained")
    await update_order_ids(conversation["session_id"], ["ORD-RETAINED"])
    await delete_conversation(actor, conversation["conversation_id"])
    monkeypatch.setattr(order_api, "fetch_order", AsyncMock(return_value={
        "id": "ORD-RETAINED", "brand": "Retained", "status": "active",
    }))

    result = await list_campaign_directory(actor, include_archived=True)

    assert [item["campaign_id"] for item in result] == ["ORD-RETAINED"]
    assert result[0]["conversation_id"] is None
    assert result[0]["routes"]["conversation"] is None
    assert "anonymous_id" not in result[0]
    assert "owner_user_id" not in result[0]


def test_campaign_directory_http_endpoint_resolves_actor_server_side(monkeypatch):
    import campaign_directory
    from config import config
    from main import app

    received = []

    async def directory(actor, *, include_archived, limit):
        received.append((actor, include_archived, limit))
        return [{"entry_id": "campaign:ORD-HTTP", "campaign_id": "ORD-HTTP"}]

    monkeypatch.setattr(campaign_directory, "list_campaign_directory", directory)
    client = TestClient(app)
    api_headers = {"X-API-Key": config.AGENT_API_KEY} if config.AGENT_API_KEY else {}
    assert client.post("/api/agent/auth/anonymous", headers=api_headers).status_code == 200

    response = client.get(
        "/api/agent/campaigns?include_archived=true&limit=999", headers=api_headers
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"campaigns": [{"entry_id": "campaign:ORD-HTTP", "campaign_id": "ORD-HTTP"}]}
    actor, include_archived, limit = received[0]
    assert actor["anonymous_id"] and actor["user_id"] is None
    assert include_archived is True
    assert limit == 100


def test_campaign_directory_http_endpoint_requires_an_identity():
    from config import config
    from main import app

    client = TestClient(app)
    api_headers = {"X-API-Key": config.AGENT_API_KEY} if config.AGENT_API_KEY else {}
    response = client.get("/api/agent/campaigns", headers=api_headers)
    assert response.status_code == 401


def test_campaign_deep_link_http_endpoint_is_owner_scoped(monkeypatch):
    import campaign_directory
    from config import config
    from main import app

    lookup = AsyncMock(return_value={"campaign_id": "ORD-DEEP"})
    monkeypatch.setattr(campaign_directory, "get_campaign_directory_entry", lookup)
    client = TestClient(app)
    api_headers = {"X-API-Key": config.AGENT_API_KEY} if config.AGENT_API_KEY else {}
    assert client.post("/api/agent/auth/anonymous", headers=api_headers).status_code == 200
    response = client.get("/api/agent/campaigns/ORD-DEEP", headers=api_headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"campaign": {"campaign_id": "ORD-DEEP"}}
    assert lookup.await_count == 1
    assert lookup.call_args.args[1] == "ORD-DEEP"
