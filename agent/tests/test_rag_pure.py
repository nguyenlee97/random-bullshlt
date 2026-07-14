from rag.index import _catalog_fingerprint
from rag.recommend import _guard_reason, _rank_merged, _raw_query


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
