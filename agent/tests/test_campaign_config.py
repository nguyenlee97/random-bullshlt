from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient


def _order(**updates):
    return {
        "id": "ORD-CONFIG", "brand": "Config QA", "status": "active",
        "objective": "awareness", "budget": 80_000_000, "daily": 0,
        "startDate": "2026-09-10", "endDate": "2026-09-17",
        "placements": ["ZN-1"], "creatives": [], **updates,
    }


@pytest.mark.asyncio
async def test_config_update_is_revisioned_and_idempotent(monkeypatch):
    import campaign_config
    from tools import order_api

    current = _order()
    fetch = AsyncMock(side_effect=lambda _campaign_id: dict(current))

    async def update(_campaign_id, patch):
        current.update(patch)
        return dict(current)

    monkeypatch.setattr(campaign_config, "_collection", AsyncMock(return_value=None))
    monkeypatch.setattr(order_api, "fetch_order", fetch)
    mutation = AsyncMock(side_effect=update)
    monkeypatch.setattr(order_api, "update_order", mutation)

    first = await campaign_config.update_campaign_config(
        "ORD-CONFIG", actor={"user_id": "owner"}, expected_revision=0,
        request_id="request-0001", patch={"budget": 96_000_000}, note="Tăng ngân sách",
    )
    duplicate = await campaign_config.update_campaign_config(
        "ORD-CONFIG", actor={"user_id": "owner"}, expected_revision=0,
        request_id="request-0001", patch={"budget": 96_000_000}, note="Tăng ngân sách",
    )

    assert first["revision"] == 1
    assert first["changes"] == {
        "budget": {"before": 80_000_000, "after": 96_000_000},
    }
    assert duplicate == first
    mutation.assert_awaited_once_with("ORD-CONFIG", {"budget": 96_000_000})


@pytest.mark.asyncio
async def test_config_update_rejects_stale_revision(monkeypatch):
    import campaign_config
    from tools import order_api

    monkeypatch.setattr(campaign_config, "_collection", AsyncMock(return_value=None))
    monkeypatch.setattr(order_api, "fetch_order", AsyncMock(return_value=_order()))
    monkeypatch.setattr(order_api, "update_order", AsyncMock(return_value=_order()))
    await campaign_config.update_campaign_config(
        "ORD-CONFIG", actor={"user_id": "owner"}, expected_revision=0,
        request_id="request-0001", patch={"budget": 90_000_000},
    )

    with pytest.raises(campaign_config.ConfigConflict):
        await campaign_config.update_campaign_config(
            "ORD-CONFIG", actor={"user_id": "owner"}, expected_revision=0,
            request_id="request-0002", patch={"daily": 10_000_000},
        )


@pytest.mark.asyncio
async def test_config_validation_blocks_unknown_fields_and_invalid_dates(monkeypatch):
    import campaign_config
    from tools import order_api

    monkeypatch.setattr(campaign_config, "_collection", AsyncMock(return_value=None))
    monkeypatch.setattr(order_api, "fetch_order", AsyncMock(return_value=_order()))
    mutation = AsyncMock()
    monkeypatch.setattr(order_api, "update_order", mutation)

    with pytest.raises(campaign_config.ConfigValidationError):
        await campaign_config.update_campaign_config(
            "ORD-CONFIG", actor={"user_id": "owner"}, expected_revision=0,
            request_id="request-unknown", patch={"status": "archived"},
        )
    with pytest.raises(campaign_config.ConfigValidationError):
        await campaign_config.update_campaign_config(
            "ORD-CONFIG", actor={"user_id": "owner"}, expected_revision=0,
            request_id="request-dates", patch={"startDate": "2026-10-01"},
        )
    mutation.assert_not_awaited()


@pytest.mark.asyncio
async def test_backend_rejection_does_not_consume_the_next_revision(monkeypatch):
    import campaign_config
    from tools import order_api

    monkeypatch.setattr(campaign_config, "_collection", AsyncMock(return_value=None))
    monkeypatch.setattr(order_api, "fetch_order", AsyncMock(return_value=_order()))
    response = httpx.Response(
        409, json={"error": "Zone conflict"},
        request=httpx.Request("PUT", "https://backend.test/api/orders/ORD-CONFIG"),
    )
    monkeypatch.setattr(
        order_api, "update_order",
        AsyncMock(side_effect=httpx.HTTPStatusError("conflict", request=response.request, response=response)),
    )

    with pytest.raises(campaign_config.ConfigValidationError, match="Zone conflict"):
        await campaign_config.update_campaign_config(
            "ORD-CONFIG", actor={"user_id": "owner"}, expected_revision=0,
            request_id="request-rejected", patch={"budget": 90_000_000},
        )

    assert campaign_config._mem_revisions["ORD-CONFIG"] == []
    assert ("ORD-CONFIG", "request-rejected") not in campaign_config._mem_requests


def test_config_http_endpoint_resolves_owner_and_csrf_server_side(monkeypatch):
    import campaign_config
    import campaign_directory
    from config import config
    from main import app

    owned = AsyncMock(return_value={"campaign_id": "ORD-CONFIG"})
    update = AsyncMock(return_value={"revision": 1, "changes": {"budget": {}}})
    monkeypatch.setattr(campaign_directory, "get_campaign_directory_entry", owned)
    monkeypatch.setattr(campaign_config, "update_campaign_config", update)
    client = TestClient(app)
    api_headers = {"X-API-Key": config.AGENT_API_KEY} if config.AGENT_API_KEY else {}
    assert client.post("/api/agent/auth/anonymous", headers=api_headers).status_code == 200
    headers = {**api_headers, "X-CSRF-Token": client.cookies.get("aa_csrf")}

    response = client.put("/api/agent/campaigns/ORD-CONFIG/config", headers=headers, json={
        "expected_revision": 0, "request_id": "browser-request-0001",
        "patch": {"budget": 90_000_000}, "note": "QA",
    })

    assert response.status_code == 200
    assert response.json()["revision"]["revision"] == 1
    assert update.await_count == 1
    assert update.call_args.kwargs["actor"]["anonymous_id"]
    assert update.call_args.kwargs["patch"] == {"budget": 90_000_000}


def test_config_http_endpoint_hides_foreign_campaign(monkeypatch):
    import campaign_config
    import campaign_directory
    from config import config
    from main import app

    monkeypatch.setattr(
        campaign_directory, "get_campaign_directory_entry", AsyncMock(return_value=None),
    )
    update = AsyncMock()
    monkeypatch.setattr(campaign_config, "update_campaign_config", update)
    client = TestClient(app)
    api_headers = {"X-API-Key": config.AGENT_API_KEY} if config.AGENT_API_KEY else {}
    assert client.post("/api/agent/auth/anonymous", headers=api_headers).status_code == 200
    headers = {**api_headers, "X-CSRF-Token": client.cookies.get("aa_csrf")}

    response = client.put("/api/agent/campaigns/ORD-FOREIGN/config", headers=headers, json={
        "expected_revision": 0, "request_id": "browser-request-0002",
        "patch": {"budget": 90_000_000},
    })

    assert response.status_code == 404
    update.assert_not_awaited()
