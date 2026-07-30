import pytest

from autopilot import capabilities
from campaign_models import LEGACY_CONVERSATION_MODEL, OPENAI_GPT_5_4_MINI
from openai_campaign.placement_inventory import (
    filter_openai_recommendable_zones,
    filter_openai_zone_tool_result,
    is_openai_recommendable_zone,
)


def _zone(
    zone_id: str,
    *,
    family: str,
    lifecycle: str = "active",
) -> dict:
    return {
        "id": zone_id,
        "placementFamily": family,
        "lifecycleStatus": lifecycle,
        "siteId": (
            "znews" if zone_id.startswith("Znews_")
            else "baomoi" if zone_id.startswith("BaoMoi_")
            else None
        ),
    }


def test_openai_inventory_uses_znews_masthead_not_background_on_old_catalog():
    old_active_masthead = _zone(
        "Znews_FoodDining_Masthead",
        family="category_masthead",
    )
    category_background = _zone(
        "Znews_FoodDining_Background",
        family="category_background",
    )

    assert is_openai_recommendable_zone(old_active_masthead)
    assert not is_openai_recommendable_zone(category_background)
    assert filter_openai_recommendable_zones(
        [old_active_masthead, category_background]
    ) == [old_active_masthead]


def test_openai_inventory_uses_baomoi_background_not_masthead():
    masthead = _zone(
        "BaoMoi_FoodDining_Masthead",
        family="category_masthead",
    )
    background = _zone(
        "BaoMoi_FoodDining_Background",
        family="category_background",
    )

    assert not is_openai_recommendable_zone(masthead)
    assert is_openai_recommendable_zone(background)


def test_openai_inventory_excludes_any_retired_catalog_row():
    retired = _zone(
        "retired-zone",
        family="category_sidebar",
        lifecycle="retired",
    )
    assert not is_openai_recommendable_zone(retired)


def test_openai_zone_tool_result_recounts_filtered_inventory():
    result = filter_openai_zone_tool_result({
        "zones": [
            _zone("BaoMoi_FoodDining_Masthead", family="category_masthead"),
            _zone("BaoMoi_FoodDining_SidebarBox", family="category_sidebar"),
        ],
        "total": 2,
        "note": "Tìm thấy 2 zone.",
    })

    assert [zone["id"] for zone in result["zones"]] == [
        "BaoMoi_FoodDining_SidebarBox"
    ]
    assert result["total"] == 1
    assert result["retired_inventory_excluded"] == 1


@pytest.mark.asyncio
async def test_openai_autopilot_excludes_znews_background_without_changing_legacy(
    monkeypatch,
):
    ranked = [
        {
            **_zone(
                "Znews_FoodDining_Background",
                family="category_background",
            ),
            "topicId": "food_dining",
            "score": 100,
            "reach": 1000,
            "cpm": 100,
        },
        {
            **_zone(
                "Znews_FoodDining_SidebarBox",
                family="category_sidebar",
            ),
            "topicId": "food_dining",
            "score": 90,
            "reach": 900,
            "cpm": 90,
        },
    ]

    async def fake_rank_zones(**_kwargs):
        return list(ranked)

    async def fake_conflicts(*_args):
        return {}

    monkeypatch.setattr("tools.zone_ranker.rank_zones", fake_rank_zones)
    monkeypatch.setattr("tools.order_api.fetch_zone_conflicts", fake_conflicts)

    workspace = {
        "artifacts": {
            "brief": {"value": {"objective": "awareness"}},
            "audience": {"value": {}},
            "strategy": {"value": {"selected": "balanced"}},
        }
    }
    openai_result = await capabilities._plan_placement_intent(
        {"conversation_model": OPENAI_GPT_5_4_MINI},
        workspace,
    )
    legacy_result = await capabilities._plan_placement_intent(
        {"conversation_model": LEGACY_CONVERSATION_MODEL},
        workspace,
    )

    assert openai_result.value["candidate_zone_ids"] == [
        "Znews_FoodDining_SidebarBox"
    ]
    assert openai_result.evidence[0]["retired_inventory_excluded"] == 1
    assert legacy_result.value["candidate_zone_ids"] == [
        "Znews_FoodDining_Background",
        "Znews_FoodDining_SidebarBox",
    ]
