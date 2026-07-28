import pytest

from config import config
from tools.placement_relevance import build_placement_context
from tools.zone_ranker import (
    rank_zones,
    sort_ranked_zones_for_strategy,
)


def _zone(zone_id, *, topic=None, reach=100_000, vi=60, ctr=0.4, cpm=30_000):
    zone = {
        "id": zone_id,
        "format": "banner",
        "size": "300x250",
        "reach": reach,
        "vi": vi,
        "ctr": ctr,
        "cpm": cpm,
        "obj": "awareness",
        "inventoryTier": "standard-box",
    }
    if topic:
        zone.update({
            "topicId": topic,
            "audienceContext": {
                "primaryTopics": [topic],
                "keywordsVi": ["mẹ và bé"],
                "keywordsEn": ["mother and baby", "parenting"],
                "dmpCategoryAffinities": ["Family and relationships"],
                "dmpSubcategoryAffinities": [],
                "dmpSegmentAffinities": ["Parents with young children"],
                "confidence": 0.9,
            },
        })
    return zone


@pytest.mark.asyncio
async def test_context_retrieval_beats_high_performance_generic_inventory(monkeypatch):
    zones = [
        _zone(
            "GENERIC-MASTHEAD",
            reach=2_000_000,
            vi=95,
            ctr=1.2,
            cpm=20_000,
        ),
        _zone("FAMILY-CATEGORY", topic="family_parenting"),
    ]

    async def fake_catalog():
        return zones

    monkeypatch.setattr("tools.zone_catalog.get_all_zones", fake_catalog)
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", False)
    context = build_placement_context(
        {"brand": "Baby Care", "notes": "Nutrition for mother and baby"},
        {"attrs": [{
            "category": "Family and relationships",
            "fullLabel": "Parents with young children",
        }]},
    )

    ranked = await rank_zones("awareness", placement_context=context, limit=2)

    assert [zone["id"] for zone in ranked] == [
        "FAMILY-CATEGORY",
        "GENERIC-MASTHEAD",
    ]
    assert ranked[0]["ranking_mode"] == "audience_context"
    assert ranked[0]["recommendation_basis"]["context_match"] is True
    assert ranked[1]["recommendation_basis"]["context_match"] is False


@pytest.mark.asyncio
async def test_missing_topic_signal_keeps_performance_fallback(monkeypatch):
    zones = [
        _zone("GENERIC-MASTHEAD", reach=2_000_000, vi=95, cpm=20_000),
        _zone("FAMILY-CATEGORY", topic="family_parenting"),
    ]

    async def fake_catalog():
        return zones

    monkeypatch.setattr("tools.zone_catalog.get_all_zones", fake_catalog)
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", False)

    ranked = await rank_zones("awareness", placement_context={}, limit=2)

    assert ranked[0]["id"] == "GENERIC-MASTHEAD"
    assert all(zone["ranking_mode"] == "performance_fallback" for zone in ranked)


def test_reach_and_quality_strategies_preserve_context_tier():
    relevant = {
        "id": "FAMILY",
        "ranking_mode": "audience_context",
        "topic_relevance": {"score": 0.45},
        "reach": 100_000,
        "vi": 60,
        "ctr": 0.4,
        "cpm": 30_000,
        "score": 30,
    }
    generic = {
        "id": "GENERIC",
        "ranking_mode": "audience_context",
        "topic_relevance": {"score": 0},
        "reach": 5_000_000,
        "vi": 99,
        "ctr": 2,
        "cpm": 10_000,
        "score": 90,
    }

    assert sort_ranked_zones_for_strategy(
        [relevant, generic], "reach_first",
    )[0]["id"] == "FAMILY"
    assert sort_ranked_zones_for_strategy(
        [relevant, generic], "quality_first",
    )[0]["id"] == "FAMILY"


@pytest.mark.asyncio
async def test_optional_reranker_cannot_cross_context_boundary(monkeypatch):
    zones = [
        _zone("GENERIC-MASTHEAD", reach=2_000_000, vi=95, cpm=20_000),
        _zone("FAMILY-CATEGORY", topic="family_parenting"),
    ]

    async def fake_catalog():
        return zones

    async def reverse_reranker(candidates, _context):
        return list(reversed(candidates)), {"applied": True, "model": "test"}

    monkeypatch.setattr("tools.zone_catalog.get_all_zones", fake_catalog)
    monkeypatch.setattr(
        "tools.placement_reranker.rerank_placements",
        reverse_reranker,
    )
    context = build_placement_context(
        {"notes": "mother and baby"},
        {"attrs": [{"category": "Family and relationships"}]},
    )

    ranked = await rank_zones("awareness", placement_context=context, limit=2)

    assert ranked[0]["id"] == "FAMILY-CATEGORY"
    assert ranked[1]["id"] == "GENERIC-MASTHEAD"


@pytest.mark.asyncio
async def test_semantic_retrieval_can_recall_unseen_synonym(monkeypatch):
    zones = [
        _zone(
            "GENERIC-MASTHEAD",
            reach=2_000_000,
            vi=95,
            ctr=1.2,
            cpm=20_000,
        ),
        _zone("FAMILY-CATEGORY", topic="family_parenting"),
    ]

    async def fake_catalog():
        return zones

    async def fake_retrieval(_zones, _context, *, limit):
        assert limit > 0
        return {
            "FAMILY-CATEGORY": {
                "applied": True,
                "mode": "hybrid_dense_bm25",
                "rank": 1,
                "dense_score": 0.82,
                "sparse_score": 0,
                "fusion_score": 1,
                "query_hits": 1,
                "semantic_match": True,
            },
        }, {
            "applied": True,
            "mode": "hybrid_dense_bm25",
            "candidate_count": 1,
        }

    monkeypatch.setattr("tools.zone_catalog.get_all_zones", fake_catalog)
    monkeypatch.setattr(
        "tools.placement_retrieval.retrieve_placements",
        fake_retrieval,
    )
    monkeypatch.setattr(config, "PLACEMENT_RAG_ENABLED", True)
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", False)
    context = build_placement_context(
        {"notes": "newborn essentials and early childhood care"},
        {},
    )

    ranked = await rank_zones("awareness", placement_context=context, limit=2)

    assert ranked[0]["id"] == "FAMILY-CATEGORY"
    assert ranked[0]["ranking_mode"] == "audience_context"
    assert ranked[0]["recommendation_basis"]["semantic_match"] is True
    assert ranked[0]["recommendation_basis"]["retrieval_mode"] == "hybrid_dense_bm25"
    assert ranked[0]["recommendation_relevance"] == 0.82


@pytest.mark.asyncio
async def test_semantic_retrieval_failure_keeps_performance_fallback(monkeypatch):
    zones = [
        _zone("GENERIC-MASTHEAD", reach=2_000_000, vi=95, cpm=20_000),
        _zone("FAMILY-CATEGORY", topic="family_parenting"),
    ]

    async def fake_catalog():
        return zones

    async def broken_retrieval(*_args, **_kwargs):
        raise RuntimeError("embedding unavailable")

    monkeypatch.setattr("tools.zone_catalog.get_all_zones", fake_catalog)
    monkeypatch.setattr(
        "tools.placement_retrieval.retrieve_placements",
        broken_retrieval,
    )
    monkeypatch.setattr(config, "PLACEMENT_RAG_ENABLED", True)
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", False)

    ranked = await rank_zones(
        "awareness",
        placement_context=build_placement_context(
            {"notes": "completely unseen campaign language"},
            {},
        ),
        limit=2,
    )

    assert ranked[0]["id"] == "GENERIC-MASTHEAD"
    assert all(zone["ranking_mode"] == "performance_fallback" for zone in ranked)
