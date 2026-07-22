import json
from unittest.mock import AsyncMock

import pytest


def test_versioned_knowledge_search_returns_citable_grounding():
    from openai_campaign.knowledge import search_ad_knowledge

    result = search_ad_knowledge("How should I interpret CPM and CTR?")

    assert result["knowledge_version"] == "2026-07-21.1"
    assert result["sources"]
    assert all(item["source_id"] == "ad-operations-faq" for item in result["sources"])
    assert all(item["updated_at"] == "2026-07-21" for item in result["sources"])


@pytest.mark.asyncio
async def test_audience_reach_tool_resolves_ids_and_never_adds_segment_sizes(monkeypatch):
    import openai_campaign.tools as tools

    monkeypatch.setattr(tools, "get_all_segments", AsyncMock(return_value=[
        {"_id": "a", "sizeMin": 10_000_000, "sizeMax": 12_000_000},
        {"_id": "b", "sizeMin": 9_000_000, "sizeMax": 11_000_000},
    ]))
    result = await tools._execute_read_tool("get_audience_reach", {
        "segment_ids": ["a", "b", "a", "invented"],
    })

    assert result["selected_segment_ids"] == ["a", "b"]
    assert result["unique_reach"] < 23_000_000
    assert result["unresolved_segment_ids"] == ["invented"]


@pytest.mark.asyncio
async def test_audience_catalog_searches_topics_independently_and_merges_results(monkeypatch):
    import openai_campaign.tools as tools

    catalog = {
        "coffee": [
            {
                "segmentId": "INT131", "fullLabel": "Coffee (food & drink)",
                "type": "Interest", "sizeMin": 147_000_000,
                "sizeMax": 165_000_000, "sizeEstimatedAt": "2026-07-21T00:00:00Z",
            },
            {
                "segmentId": "INT165", "fullLabel": "Coffeehouses (coffee)",
                "type": "Interest", "sizeMin": 136_000_000,
                "sizeMax": 152_000_000, "sizeEstimatedAt": "2026-07-21T00:00:00Z",
            },
        ],
        "beverages": [
            {
                "segmentId": "INT130", "fullLabel": "Beverages (food & drink)",
                "type": "Interest", "sizeMin": 120_000_000,
                "sizeMax": 140_000_000, "sizeEstimatedAt": "2026-07-21T00:00:00Z",
            },
            {
                "segmentId": "INT131", "fullLabel": "Coffee (food & drink)",
                "type": "Interest", "sizeMin": 147_000_000,
                "sizeMax": 165_000_000, "sizeEstimatedAt": "2026-07-21T00:00:00Z",
            },
        ],
        "office workers": [],
    }

    async def search(query, *, type_filter, limit):
        assert type_filter is None
        assert limit == 10
        return catalog[query]

    monkeypatch.setattr(tools, "search_audience", search)
    result = await tools._execute_read_tool("search_audience_catalog", {
        "queries": ["coffee", "beverages", "office workers"],
        "type": None,
    })

    assert [item["segment_id"] for item in result["segments"]] == [
        "INT131", "INT165", "INT130",
    ]
    assert result["segments"][0]["matched_queries"] == ["coffee", "beverages"]
    assert result["unmatched_queries"] == ["office workers"]
    assert result["no_result"] is False
    assert result["segments"][0]["size_updated_at"] == "2026-07-21T00:00:00Z"


@pytest.mark.asyncio
async def test_audience_catalog_rejects_an_empty_topic_list():
    import openai_campaign.tools as tools

    with pytest.raises(ValueError, match="At least one audience catalog query"):
        await tools._execute_read_tool("search_audience_catalog", {
            "queries": [], "type": None,
        })


@pytest.mark.asyncio
async def test_zone_availability_requires_dates_before_claiming_free(monkeypatch):
    import openai_campaign.tools as tools

    monkeypatch.setattr(tools, "get_all_zones", AsyncMock(return_value=[
        {"id": "zone-a", "channel": "ZNews", "format": "Masthead"},
    ]))
    conflict_reader = AsyncMock(return_value={})
    monkeypatch.setattr(tools, "fetch_zone_conflicts", conflict_reader)

    result = await tools._execute_read_tool("compare_zones", {
        "zone_ids": ["zone-a"], "start_date": None, "end_date": None,
    })

    assert result["zones"][0]["availability"] == "unknown_dates_required"
    conflict_reader.assert_not_awaited()


def test_read_tool_definitions_never_expose_launch_or_arbitrary_database_access():
    from openai_campaign.tools import responses_tools

    tools = responses_tools(allow_mutation=False)
    names = {item["name"] for item in tools}
    assert "search_ad_knowledge" in names
    assert "get_zone_availability" in names
    assert "propose_workspace_change" not in names
    assert not ({"query_database", "launch_campaign", "execute_sql"} & names)
    audience_tool = next(item for item in tools if item["name"] == "search_audience_catalog")
    assert audience_tool["parameters"]["required"] == ["queries", "type"]
    assert audience_tool["parameters"]["properties"]["queries"]["maxItems"] == 6
    json.dumps(tools)
