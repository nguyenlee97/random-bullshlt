from types import SimpleNamespace
import threading

import pytest

from rag.index import _catalog_fingerprint
from rag.recommend import _catalog_segment_count
from rag.recommend import (
    _guard_reason,
    _hybrid_search,
    _rank_merged,
    _raw_query,
    recommend_rag,
)
from handlers.audience import _normalize_targeting
from tools.audience_provenance import catalog_source


def _segments():
    return [
        {
            "_id": "mongo-a",
            "segmentId": "INT001",
            "type": "Interest",
            "category": "Business",
            "subcategory": None,
            "fullLabel": "Advertising",
            "context": "marketing",
            "sizeMin": 10,
            "sizeMax": 20,
        },
        {
            "_id": "mongo-b",
            "segmentId": "BEH001",
            "type": "Behavior",
            "category": "Digital",
            "subcategory": None,
            "fullLabel": "Online shoppers",
            "context": None,
            "sizeMin": 30,
            "sizeMax": 40,
        },
    ]


def test_catalog_fingerprint_ignores_order_and_environment_mongo_ids():
    original = _segments()
    reseeded = [dict(original[1], _id="other-b"), dict(original[0], _id="other-a")]

    assert _catalog_fingerprint(original) == _catalog_fingerprint(reseeded)


def test_catalog_fingerprint_changes_when_searchable_content_changes():
    original = _segments()
    changed = [dict(item) for item in original]
    changed[0]["fullLabel"] = "Digital advertising"

    assert _catalog_fingerprint(original) != _catalog_fingerprint(changed)


def test_catalog_count_comes_from_index_metadata_not_retrieval_pool():
    candidates = [
        {"_id": "one", "_rag_index": {"segment_count": 310}},
        {"_id": "two", "_rag_index": {"segment_count": 310}},
    ]
    assert _catalog_segment_count(candidates) == 310
    assert _catalog_segment_count([{"_id": "legacy"}]) == 1


def test_raw_query_preserves_user_audience_notes():
    query = _raw_query({
        "brand": "Example",
        "objective": "conversion",
        "kpi": "100 orders",
        "notes": "urban runners, exclude children",
    })

    assert "urban runners" in query
    assert "exclude children" in query
    assert "conversion" in query


def test_targeting_normalization_rejects_invented_values_and_dimensions():
    options = {
        "geo": {"South": ["TP.HCM", "Đà Nẵng"]},
        "gender": ["Male", "Female"],
    }
    result = _normalize_targeting({
        "geo": ["TP.HCM", "Atlantis", "TP.HCM"],
        "gender": "Female",
        "secretDimension": ["anything"],
    }, options)

    assert result == {"geo": ["TP.HCM"], "gender": ["Female"]}


def test_catalog_source_cites_stable_segment_and_index_version():
    source = catalog_source(
        {"_id": "mongo-a", "segmentId": "INT001"},
        {"schema": 2, "catalog_fingerprint": "abc123"},
    )

    assert source == {
        "type": "dmp_catalog",
        "endpoint": "/api/dmp/attributes",
        "segmentId": "INT001",
        "recordId": "mongo-a",
        "catalogFingerprint": "abc123",
        "indexSchema": 2,
    }


def test_coverage_ranking_keeps_strong_single_aspect_match():
    merged = {
        "generic": {"name": "generic", "_rank": 5, "_query_hits": 3,
                    "_fusion_score": 0.05},
        "specific": {"name": "specific", "_rank": 0, "_query_hits": 1,
                     "_fusion_score": 0.016},
    }

    assert [item["name"] for item in _rank_merged(merged)] == ["specific", "generic"]


def test_coverage_ranking_uses_query_agreement_as_tiebreaker():
    merged = {
        "one": {"name": "one", "_rank": 0, "_query_hits": 1,
                "_fusion_score": 0.016},
        "two": {"name": "two", "_rank": 0, "_query_hits": 2,
                "_fusion_score": 0.032},
    }

    assert [item["name"] for item in _rank_merged(merged)] == ["two", "one"]


def test_b2b_leisure_guard_uses_catalog_taxonomy():
    brief = {"notes": "Industrial B2B MRO supplier, not leisure flyers."}
    consumer = {"category": "Hobbies and activities",
                "subcategory": "Travel (travel & tourism)",
                "fullLabel": "Air travel (transportation)"}
    industry = {"category": "Business and industry", "subcategory": None,
                "fullLabel": "Aviation (air travel)"}

    assert _guard_reason(brief, consumer) == "b2b_consumer_leisure"
    assert _guard_reason(brief, industry) is None


@pytest.mark.parametrize("notes", [
    "Không nhắm nhà đầu tư cá nhân nhỏ lẻ, tập trung chủ doanh nghiệp SME.",
    "Loại trừ nhà đầu tư nhỏ lẻ; chỉ phục vụ doanh nghiệp đang vận hành.",
    "B2B capital advisory. Do not target retail investors.",
])
def test_retail_investor_guard_honors_explicit_negative_intent(notes):
    retail_investment = {
        "category": "Business and industry",
        "subcategory": "Personal finance (banking)",
        "name": "Investment",
        "fullLabel": "Investment (business & finance)",
    }

    assert _guard_reason({"notes": notes}, retail_investment) == \
        "retail_investor_excluded"


def test_retail_investor_guard_preserves_business_investment_segments():
    brief = {"notes": "Không nhắm nhà đầu tư cá nhân; tập trung chủ doanh nghiệp SME."}
    investment_banking = {
        "category": "Business and industry",
        "subcategory": "Banking (Finance)",
        "name": "Investment banking",
        "fullLabel": "Investment banking (banking)",
    }

    assert _guard_reason(brief, investment_banking) is None


def test_retail_investor_guard_requires_an_explicit_exclusion():
    brief = {"notes": "Ứng dụng đầu tư cho nhà đầu tư cá nhân mới bắt đầu."}
    retail_investment = {
        "category": "Business and industry",
        "subcategory": "Personal finance",
        "name": "Investment",
        "fullLabel": "Investment (business & finance)",
    }

    assert _guard_reason(brief, retail_investment) is None


@pytest.mark.asyncio
async def test_rewritten_qdrant_queries_execute_concurrently(monkeypatch):
    import rag.embeddings as embeddings
    import rag.recommend as recommend

    class Values(list):
        def tolist(self):
            return list(self)

    barrier = threading.Barrier(3, timeout=1)

    class Client:
        def query_points(self, *_args, **_kwargs):
            barrier.wait()
            return SimpleNamespace(points=[])

    monkeypatch.setattr(embeddings, "embed_dense", lambda queries: [[0.1] for _ in queries])
    monkeypatch.setattr(
        embeddings,
        "embed_sparse",
        lambda queries: [SimpleNamespace(indices=Values([1]), values=Values([1.0]))
                         for _ in queries],
    )
    monkeypatch.setattr(recommend, "get_qdrant", lambda: Client())

    assert await _hybrid_search(["raw", "rewrite one", "rewrite two"], 5) == []


@pytest.mark.asyncio
async def test_rag_selection_dedupes_stable_ids_and_backfills_ranked_candidates(monkeypatch):
    import rag.recommend as recommend

    candidates = [
        {
            "_id": f"mongo-{index}",
            "segmentId": f"INT{index:03d}",
            "fullLabel": f"Segment {index}",
            "name": f"Segment {index}",
            "category": "Food",
            "subcategory": "Snacks",
            "_text": f"snack audience {index}",
            "_rank": index,
            "_query_hits": 1,
            "_fusion_score": 1 / (61 + index),
            "_rag_index": {"segment_count": 310},
        }
        for index in range(1, 7)
    ]

    async def ready(_session_id):
        return True

    async def search(_queries, _limit):
        return candidates

    async def select(_prompt):
        # A valid provider response can still repeat one catalog label.
        return [
            {"fullLabel": "Segment 1", "reason": "first"},
            {"fullLabel": "Segment 1", "reason": "duplicate"},
            {"fullLabel": "Segment 3", "reason": "third"},
            {"fullLabel": "Segment 4", "reason": "fourth"},
            {"fullLabel": "Segment 5", "reason": "fifth"},
            {"fullLabel": "Segment 6", "reason": "sixth"},
        ], "fixture"

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(recommend, "_select", select)
    monkeypatch.setattr(recommend.config, "RAG_QUERY_REWRITE", False)
    monkeypatch.setattr(recommend.config, "RAG_USE_RERANK", False)
    monkeypatch.setattr(recommend.config, "RAG_TOP_RETRIEVE", 15)
    monkeypatch.setattr(recommend.config, "RAG_TOP_FINAL", 15)

    result = await recommend_rag("rag-dedupe", {
        "brand": "Mixifood",
        "objective": "awareness",
        "kpi": "Reach",
        "notes": "snack food",
    })

    ids = [item["segmentId"] for item in result["recommendations"]]
    assert len(ids) == 6
    assert len(set(ids)) == 6
    assert "INT002" in ids
    assert result["rag"]["dropped_duplicates"] == 1
