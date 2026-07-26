from tools.placement_relevance import (
    build_placement_context,
    score_placement_relevance,
)


def _zone(topic, keywords, categories, subcategories=None, segments=None):
    return {
        "id": f"ZONE-{topic}",
        "audienceContext": {
            "primaryTopics": [topic],
            "keywordsVi": keywords,
            "keywordsEn": [],
            "dmpCategoryAffinities": categories,
            "dmpSubcategoryAffinities": subcategories or [],
            "dmpSegmentAffinities": segments or [],
            "confidence": 0.9,
        },
    }


def test_context_uses_only_approved_brief_and_audience_labels():
    context = build_placement_context(
        {
            "brand": "Bé Khỏe",
            "objective": "awareness",
            "notes": "Sản phẩm dinh dưỡng cho mẹ và bé",
        },
        {
            "attrs": [{
                "category": "Family and relationships",
                "fullLabel": "Parents with young children",
            }],
        },
    )

    assert "Sản phẩm dinh dưỡng cho mẹ và bé" in context["text"]
    assert context["audience_categories"] == ["Family and relationships"]
    assert "notes" in context["source_fields"]


def test_family_context_scores_family_above_unrelated_technology():
    context = build_placement_context(
        {"brand": "Bé Khỏe", "notes": "Chăm sóc gia đình, mẹ và bé"},
        {"attrs": [{"category": "Family and relationships", "name": "Parents"}]},
    )
    family = score_placement_relevance(
        _zone(
            "family_parenting",
            ["gia đình", "cha mẹ", "trẻ em", "mẹ và bé"],
            ["Family and relationships"],
        ),
        context,
    )
    technology = score_placement_relevance(
        _zone(
            "technology_science",
            ["công nghệ", "thiết bị", "AI"],
            ["Technology (computers & electronics)"],
        ),
        context,
    )

    assert family["score"] > technology["score"]
    assert family["signal"] == "topic_match"
    assert "mẹ và bé" in family["matched_keywords"]


def test_missing_campaign_context_is_neutral_not_invented():
    result = score_placement_relevance(
        _zone("sports_outdoors", ["thể thao"], ["Sports and outdoors"]),
        {},
    )
    assert result["score"] == 0
    assert result["signal"] == "no_topic_signal"


def test_segment_affinity_separates_gaming_from_movies_in_same_category():
    context = build_placement_context(
        {"brand": "Arena Pass", "notes": "Gói ưu đãi cho người chơi game"},
        {"attrs": [{
            "category": "Entertainment (leisure)",
            "subcategory": "Video games",
            "fullLabel": "Esports",
        }]},
    )
    gaming = score_placement_relevance(
        _zone(
            "gaming_esports",
            ["gaming", "esports"],
            ["Entertainment (leisure)"],
            ["Video games"],
            ["Esports"],
        ),
        context,
    )
    movies = score_placement_relevance(
        _zone(
            "movies_tv_streaming",
            ["movies", "streaming"],
            ["Entertainment (leisure)"],
            ["Movies"],
            ["Streaming television"],
        ),
        context,
    )

    assert gaming["score"] > movies["score"]
    assert gaming["matched_subcategories"] == ["Video games"]
    assert gaming["matched_segments"] == ["Esports"]


def test_subcategory_affinity_separates_food_from_fashion():
    context = build_placement_context(
        {"brand": "Bếp Việt", "notes": "Khám phá món ngon và nhà hàng"},
        {"attrs": [{
            "category": "Food and drink (consumables)",
            "subcategory": "Restaurants",
            "name": "Food",
        }]},
    )
    food = score_placement_relevance(
        _zone(
            "food_dining",
            ["food", "restaurants"],
            ["Food and drink (consumables)"],
            ["Restaurants"],
            ["Food"],
        ),
        context,
    )
    fashion = score_placement_relevance(
        _zone(
            "fashion_beauty",
            ["fashion", "beauty"],
            ["Shopping and fashion"],
            ["Beauty"],
            ["Fashion"],
        ),
        context,
    )

    assert food["score"] > fashion["score"]
    assert food["matched_subcategories"] == ["Restaurants"]
