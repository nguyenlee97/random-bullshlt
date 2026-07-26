from unittest.mock import AsyncMock

import pytest


async def _conversation(user_id: str) -> dict:
    from identity import create_conversation

    return await create_conversation(
        {"user_id": user_id, "anonymous_id": None},
        title=f"Conversation for {user_id}",
    )


@pytest.mark.asyncio
async def test_order_status_allows_same_account_campaign_across_conversations(
    monkeypatch,
):
    from campaign_ownership import register_campaign_for_session
    from config import config
    from tools import registry

    monkeypatch.setattr(config, "QUALITY_DATA_ENABLED", False)
    creator = await _conversation("account-owner")
    reader = await _conversation("account-owner")
    await register_campaign_for_session(creator["session_id"], "ORD-OWNED")

    fetch_order = AsyncMock(return_value={
        "id": "ORD-OWNED",
        "status": "active",
        "brand": "Owned brand",
        "placements": ["ZN-001"],
    })
    monkeypatch.setattr(registry, "fetch_order", fetch_order)

    result = await registry.execute_tool(
        "get_order_status",
        {"order_id": "ORD-OWNED"},
        session_id=reader["session_id"],
    )

    assert result == {
        "ok": True,
        "order": {
            "id": "ORD-OWNED",
            "status": "active",
            "brand": "Owned brand",
            "placements": ["ZN-001"],
        },
    }
    fetch_order.assert_awaited_once_with("ORD-OWNED")


@pytest.mark.asyncio
async def test_order_status_denies_foreign_campaign_without_fetching_it(
    monkeypatch,
):
    from campaign_ownership import register_campaign_for_session
    from config import config
    from tools import registry

    monkeypatch.setattr(config, "QUALITY_DATA_ENABLED", False)
    foreign = await _conversation("foreign-owner")
    requester = await _conversation("requester")
    await register_campaign_for_session(foreign["session_id"], "ORD-FOREIGN")

    fetch_order = AsyncMock()
    monkeypatch.setattr(registry, "fetch_order", fetch_order)

    result = await registry.execute_tool(
        "get_order_status",
        {"order_id": "ORD-FOREIGN"},
        session_id=requester["session_id"],
    )

    assert result["ok"] is False
    assert result["error"] == "not_found_or_forbidden"
    assert "ORD-FOREIGN" not in result["message"]
    fetch_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_recent_order_status_lists_only_owned_campaigns(monkeypatch):
    from campaign_ownership import register_campaign_for_session
    from config import config
    from tools import registry

    monkeypatch.setattr(config, "QUALITY_DATA_ENABLED", False)
    owner_creator = await _conversation("list-owner")
    owner_reader = await _conversation("list-owner")
    foreign = await _conversation("list-foreign")
    await register_campaign_for_session(owner_creator["session_id"], "ORD-MINE")
    await register_campaign_for_session(foreign["session_id"], "ORD-NOT-MINE")

    async def fetch_order(order_id: str) -> dict:
        assert order_id != "ORD-NOT-MINE"
        return {
            "id": order_id,
            "status": "active",
            "brand": "owner@example.com",
        }

    monkeypatch.setattr(registry, "fetch_order", fetch_order)

    result = await registry.execute_tool(
        "get_order_status",
        {},
        session_id=owner_reader["session_id"],
    )

    assert result == {
        "ok": True,
        "orders": [{
            "id": "ORD-MINE",
            "status": "active",
            "brand": "[REDACTED_EMAIL]",
        }],
    }


@pytest.mark.asyncio
async def test_legacy_session_is_limited_to_its_persisted_order_ids(monkeypatch):
    from config import config
    import session
    from tools import registry

    monkeypatch.setattr(config, "QUALITY_DATA_ENABLED", False)
    sid = "legacy-owned-session"
    session._mem[sid] = session._default_session(sid)
    session._mem[sid]["created_order_ids"] = ["ORD-LEGACY"]

    fetch_order = AsyncMock(return_value={
        "id": "ORD-LEGACY",
        "status": "pending",
        "brand": "Legacy",
        "placements": [],
    })
    monkeypatch.setattr(registry, "fetch_order", fetch_order)

    allowed = await registry.execute_tool(
        "get_order_status",
        {"order_id": "ORD-LEGACY"},
        session_id=sid,
    )
    denied = await registry.execute_tool(
        "get_order_status",
        {"order_id": "ORD-OTHER"},
        session_id=sid,
    )

    assert allowed["ok"] is True
    assert denied["error"] == "not_found_or_forbidden"
    fetch_order.assert_awaited_once_with("ORD-LEGACY")


@pytest.mark.asyncio
async def test_order_status_without_trusted_session_fails_closed(monkeypatch):
    from config import config
    from tools import registry

    monkeypatch.setattr(config, "QUALITY_DATA_ENABLED", False)
    fetch_order = AsyncMock()
    monkeypatch.setattr(registry, "fetch_order", fetch_order)

    result = await registry.execute_tool(
        "get_order_status",
        {"order_id": "ORD-UNSCOPED"},
    )

    assert result["error"] == "not_found_or_forbidden"
    fetch_order.assert_not_awaited()


def test_public_conflict_details_remove_campaign_identity():
    from tools.order_api import public_conflict_details

    result = public_conflict_details({
        "orderId": "ORD-FOREIGN",
        "campaignName": "Secret launch",
        "idempotencyKey": "secret-retry-key",
        "startDate": "2026-08-01",
        "endDate": "2026-08-10",
    })

    assert result == {
        "booked": True,
        "startDate": "2026-08-01",
        "endDate": "2026-08-10",
    }
