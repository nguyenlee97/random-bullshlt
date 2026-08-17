from datetime import datetime, timezone

import pytest

import creative_assets


@pytest.fixture(autouse=True)
def clear_creative_assets(monkeypatch):
    creative_assets._mem_assets.clear()

    async def no_collection():
        return None

    monkeypatch.setattr(creative_assets, "_collection", no_collection)
    yield
    creative_assets._mem_assets.clear()


def _asset(asset_id: str, session_id: str, *, actor_key: str = "user:user-1") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "_id": asset_id,
        "asset_id": asset_id,
        "actor_key": actor_key,
        "linked_actor_keys": [],
        "session_id": session_id,
        "name": asset_id,
        "kind": "logo",
        "required": True,
        "url": f"https://example.test/{asset_id}.png",
        "lifecycle": "active",
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_reference_assets_are_scoped_to_the_current_conversation():
    creative_assets._mem_assets.update({
        "current": _asset("current", "session-current"),
        "other-chat": _asset("other-chat", "session-other"),
    })
    actor = {"user_id": "user-1"}

    listed = await creative_assets.list_assets(actor, "session-current")
    assert [item["asset_id"] for item in listed] == ["current"]

    assert [
        item["asset_id"]
        for item in await creative_assets.get_assets(
            actor, ["current", "other-chat"], "session-current",
        )
    ] == ["current"]


@pytest.mark.asyncio
async def test_reference_asset_cannot_be_deleted_from_another_conversation():
    creative_assets._mem_assets["other-chat"] = _asset(
        "other-chat", "session-other",
    )
    actor = {"user_id": "user-1"}

    assert not await creative_assets.delete_asset(
        actor, "other-chat", "session-current",
    )
    assert creative_assets._mem_assets["other-chat"]["lifecycle"] == "active"

    assert await creative_assets.delete_asset(
        actor, "other-chat", "session-other",
    )
    assert creative_assets._mem_assets["other-chat"]["lifecycle"] == "deleted"
