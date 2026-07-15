from types import SimpleNamespace
import threading

import pytest

from rag.index import _catalog_fingerprint
from rag.recommend import _guard_reason, _hybrid_search, _rank_merged, _raw_query
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
