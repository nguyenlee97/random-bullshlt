import pytest

from rag.taxonomy import (
    build_taxonomy_graph,
    expand_candidates_with_taxonomy,
)


def _segment(
    segment_id,
    name,
    *,
    category="Hobbies and activities",
    subcategory=None,
    context=None,
    rank=0,
):
    return {
        "_id": f"mongo-{segment_id}",
        "segmentId": segment_id,
        "type": "Interest",
        "category": category,
        "subcategory": subcategory,
        "context": context,
        "name": name,
        "fullLabel": name,
        "_text": name,
        "_rank": rank,
        "_fusion_score": 0.1,
        "_query_hits": 4,
        "_query_matches": [{"kind": "product", "query_rank": 1}],
        "_aspect_hits": ["brief", "product", "audience"],
        "_rag_index": {"segment_count": 310},
    }


def _vehicle_catalog():
    return [
        _segment("INT218", "Vehicles (transportation)"),
        _segment(
            "INT219",
            "Automobiles (vehicles)",
            subcategory="Vehicles (transportation)",
            context="vehicles",
        ),
        _segment(
            "INT221",
            "Electric vehicle (vehicle)",
            subcategory="Vehicles (transportation)",
            context="vehicle",
        ),
        _segment(
            "INT222",
            "Hybrids (vehicle)",
            subcategory="Vehicles (transportation)",
            context="vehicle",
        ),
        _segment(
            "INT224",
            "Motorcycles (vehicles)",
            subcategory="Vehicles (transportation)",
            context="vehicles",
        ),
        _segment(
            "INT226",
            "Scooters (vehicle)",
            subcategory="Vehicles (transportation)",
            context="vehicle",
        ),
    ]


def test_live_taxonomy_derives_structure_and_semantic_correction():
    graph = build_taxonomy_graph(_vehicle_catalog())

    electric = graph.metadata("INT221")
    assert electric["direct_parent_sources"] == {
        "INT218": "catalog_subcategory",
        "INT219": "semantic_override",
    }
    assert set(graph.descendant_ids("INT219")) == {"INT221", "INT222"}
    assert "INT224" not in graph.descendant_ids("INT219")


def test_taxonomy_expansion_injects_parents_but_not_siblings():
    catalog = _vehicle_catalog()
    retrieved = [
        {**next(row for row in catalog if row["segmentId"] == "INT221"), "_rank": 0},
        _segment("OTHER-1", "Artificial intelligence", category="Technology", rank=1),
        _segment("OTHER-2", "Software", category="Technology", rank=2),
    ]

    expanded, _graph, trace = expand_candidates_with_taxonomy(
        retrieved,
        catalog,
        candidate_limit=3,
    )

    bounded_ids = [row["segmentId"] for row in expanded[:3]]
    assert "INT219" in bounded_ids
    assert "INT218" in bounded_ids
    assert "INT224" not in bounded_ids
    assert trace["injected_count"] == 2
    assert all(
        row["parent_id"] in {"INT218", "INT219"}
        for row in trace["injected"]
    )


@pytest.mark.asyncio
async def test_openai_gate_promotes_closest_automobile_parent_only(monkeypatch):
    import rag.nano_rerank as nano
    import rag.recommend as recommend

    catalog = _vehicle_catalog()
    wanted_ids = ["INT221", "INT226"]
    candidates = [
        {
            **next(row for row in catalog if row["segmentId"] == segment_id),
            "_rank": rank,
        }
        for rank, segment_id in enumerate(wanted_ids)
    ]
    async def ready(_session_id):
        return True

    async def search(_query_specs, _limit):
        return candidates, {"query_results": []}

    async def live_catalog(limit=1000):
        return catalog[:limit]

    async def nano_order(_query, _candidates, **_kwargs):
        ids = [row["segmentId"] for row in _candidates]
        scores = {
            "INT221": 0.90,
            "INT219": 0.78,
            "INT218": 0.70,
            "INT226": 0.52,
        }
        assessments = {
            "INT221": {
                "match_tier": "recommended",
                "match_basis": "exact_product",
            },
            "INT219": {
                "match_tier": "adjacent",
                "match_basis": "broad_parent",
            },
            "INT218": {
                "match_tier": "adjacent",
                "match_basis": "broad_parent",
            },
            "INT226": {
                "match_tier": "adjacent",
                "match_basis": "exact_user_interest",
            },
        }
        return list(range(len(ids))), {
            "applied": True,
            "mode": "openai_nano",
            "candidate_count": len(ids),
            "scores": {segment_id: scores[segment_id] for segment_id in ids},
            "assessments": {
                segment_id: assessments[segment_id] for segment_id in ids
            },
        }

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_openai_hybrid_search", search)
    monkeypatch.setattr(
        "tools.audience_library.get_all_segments", live_catalog
    )
    monkeypatch.setattr(nano, "rerank_candidates", nano_order)

    result = await recommend.recommend_rag(
        "openai-kiki-taxonomy",
        {
            "brand": "Zalo",
            "objective": "Nhận biết và tải ứng dụng",
            "notes": "Ứng dụng AI Agent Kiki dành cho xe ô tô.",
        },
        provider="openai",
        rerank_mode="openai_nano",
        select_from_rerank_scores=True,
        min_relevance_score=0.45,
        enable_query_rewrite=False,
        detailed_retrieval=True,
        rerank_candidate_limit=4,
    )

    assert [row["segmentId"] for row in result["recommendations"]] == [
        "INT221",
        "INT219",
    ]
    adjacent_ids = [
        row["segmentId"] for row in result["adjacent_recommendations"]
    ]
    assert "INT218" in adjacent_ids
    assert "INT226" in adjacent_ids
    decisions = {
        row["segment_id"]: row
        for row in result["rag"]["quality_gate"]["decisions"]
    }
    assert decisions["INT219"]["gate_rule"] == (
        "coverage_anchor_semantic_override"
    )
    assert decisions["INT218"]["taxonomy_decision"] == (
        "parent_kept_adjacent_closer_parent_available"
    )
    assert decisions["INT226"]["taxonomy_decision"] == (
        "sibling_kept_adjacent"
    )
    taxonomy_trace = result["rag"]["taxonomy_trace"]
    assert taxonomy_trace["applied"] is True
    assert taxonomy_trace["injected_count"] == 2
    assert {
        row["parent_id"] for row in taxonomy_trace["injected"]
    } == {"INT218", "INT219"}


@pytest.mark.asyncio
async def test_empty_direct_tier_rescues_only_exact_product_or_user_match(
    monkeypatch,
):
    import rag.nano_rerank as nano
    import rag.recommend as recommend

    candidates = [
        _segment(
            "INT158",
            "Fast food (food & drink)",
            category="Food and drink",
            subcategory="Food",
            rank=0,
        ),
        _segment(
            "INT008",
            "Engineering (science)",
            category="Business and industry",
            rank=1,
        ),
    ]
    candidates[0]["_query_matches"] = [{
        "kind": "industry",
        "query_rank": 1,
    }]
    candidates[1]["_query_matches"] = [{
        "kind": "industry",
        "query_rank": 1,
    }]

    async def ready(_session_id):
        return True

    async def search(_queries, _limit, mode=None):
        return candidates

    async def nano_order(_query, _candidates, **_kwargs):
        return [0, 1], {
            "applied": True,
            "mode": "openai_nano",
            "candidate_count": 2,
            "scores": {"INT158": 0.62, "INT008": 0.64},
            "assessments": {
                "INT158": {
                    "match_tier": "recommended",
                    "match_basis": "exact_product",
                },
                "INT008": {
                    "match_tier": "recommended",
                    "match_basis": "exact_industry",
                },
            },
        }

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(nano, "rerank_candidates", nano_order)

    result = await recommend.recommend_rag(
        "openai-minimum-viable-direct",
        {
            "brand": "Bánh Mì Ô Tô",
            "notes": "Bánh mì đóng hộp tiện lợi dùng cho tài xế.",
        },
        provider="openai",
        rerank_mode="openai_nano",
        select_from_rerank_scores=True,
        min_relevance_score=0.45,
        enable_query_rewrite=False,
    )

    assert [row["segmentId"] for row in result["recommendations"]] == [
        "INT158",
    ]
    assert [row["segmentId"] for row in result["adjacent_recommendations"]] == [
        "INT008",
    ]
    decisions = {
        row["segment_id"]: row
        for row in result["rag"]["quality_gate"]["decisions"]
    }
    assert decisions["INT158"]["gate_rule"] == (
        "minimum_viable_direct_exact_match"
    )
    assert decisions["INT008"]["gate_rule"] == (
        "recommended_below_direct_threshold"
    )


@pytest.mark.asyncio
async def test_product_domain_beats_ungrounded_buyer_context_parent(
    monkeypatch,
):
    import rag.nano_rerank as nano
    import rag.recommend as recommend

    fast_food = _segment(
        "INT158",
        "Fast food",
        category="Food and drink",
        subcategory="Food",
        rank=1,
    )
    fast_food["_query_matches"] = [{
        "query": "Fast food",
        "kind": "industry",
        "query_rank": 1,
    }]
    vehicles = _segment(
        "INT218",
        "Vehicles",
        category="Hobbies and activities",
        rank=0,
    )
    vehicles["_query_matches"] = [{
        "query": "Drivers",
        "kind": "buyer",
        "query_rank": 1,
    }]
    candidates = [vehicles, fast_food]

    async def ready(_session_id):
        return True

    async def search(_queries, _limit, mode=None):
        return candidates

    async def nano_order(_query, _candidates, **_kwargs):
        return [0, 1], {
            "applied": True,
            "mode": "openai_nano",
            "candidate_count": 2,
            "scores": {"INT218": 0.72, "INT158": 0.44},
            "assessments": {
                "INT218": {
                    "match_tier": "recommended",
                    "match_basis": "broad_parent",
                },
                "INT158": {
                    "match_tier": "adjacent",
                    "match_basis": "proxy",
                },
            },
        }

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(nano, "rerank_candidates", nano_order)

    result = await recommend.recommend_rag(
        "openai-product-over-buyer-proxy",
        {
            "brand": "Bánh Mì Ô Tô",
            "notes": "Bánh mì đóng hộp tiện lợi dùng cho tài xế.",
        },
        provider="openai",
        rerank_mode="openai_nano",
        select_from_rerank_scores=True,
        min_relevance_score=0.45,
        enable_query_rewrite=False,
    )

    assert [row["segmentId"] for row in result["recommendations"]] == [
        "INT158",
    ]
    assert [row["segmentId"] for row in result["adjacent_recommendations"]] == [
        "INT218",
    ]
    decisions = {
        row["segment_id"]: row
        for row in result["rag"]["quality_gate"]["decisions"]
    }
    assert decisions["INT218"]["gate_rule"] == (
        "broad_parent_without_product_domain_evidence"
    )
    assert decisions["INT158"]["gate_rule"] == (
        "minimum_viable_direct_exact_catalog_query"
    )
