import pytest

from config import config
from tools.placement_retrieval import reset_for_test, retrieve_placements


def _zone(zone_id, topic, *, keywords_vi=None, keywords_en=None):
    return {
        "id": zone_id,
        "name": topic.replace("_", " "),
        "publisher": "Publisher",
        "topicId": topic,
        "placementFamily": "category_masthead",
        "catalogVersion": "test",
        "audienceContext": {
            "primaryTopics": [topic],
            "secondaryTopics": [],
            "keywordsVi": keywords_vi or [],
            "keywordsEn": keywords_en or [],
            "dmpCategoryAffinities": [],
            "dmpSubcategoryAffinities": [],
            "dmpSegmentAffinities": [],
            "confidence": 1,
        },
    }


@pytest.mark.asyncio
async def test_dense_retrieval_recalls_semantic_synonym_without_catalog_keyword(
    monkeypatch,
):
    zones = [
        _zone("FAMILY", "family_parenting", keywords_en=["mother and baby"]),
        _zone("GAMING", "gaming_esports", keywords_en=["video games"]),
        _zone("MUSIC", "music_live_events", keywords_en=["concert"]),
    ]

    async def fake_embed(texts):
        vectors = []
        for text in texts:
            folded = text.lower()
            if "newborn essentials" in folded or "family_parenting" in folded:
                vectors.append([1.0, 0.0, 0.0])
            elif "gaming_esports" in folded:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors

    monkeypatch.setattr("tools.placement_retrieval._embed_dense", fake_embed)
    monkeypatch.setattr(config, "PLACEMENT_RAG_MAX_QUERIES", 1)
    monkeypatch.setattr(config, "PLACEMENT_RAG_CONTEXT_LIMIT", 2)
    monkeypatch.setattr(config, "PLACEMENT_RAG_SEMANTIC_THRESHOLD", 0.7)
    reset_for_test()

    evidence, meta = await retrieve_placements(
        zones,
        {"text": "newborn essentials", "content_text": "newborn essentials"},
        limit=3,
    )

    assert meta["applied"] is True
    assert evidence["FAMILY"]["rank"] == 1
    assert evidence["FAMILY"]["semantic_match"] is True
    assert evidence["FAMILY"]["dense_score"] == 1.0


@pytest.mark.asyncio
async def test_sparse_retrieval_preserves_exact_catalog_vocabulary(monkeypatch):
    zones = [
        _zone("FAMILY", "family_parenting", keywords_en=["parents"]),
        _zone("GAMING", "gaming_esports", keywords_en=["competitive esports"]),
        _zone("MUSIC", "music_live_events", keywords_en=["concert"]),
    ]

    async def fake_embed(texts):
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr("tools.placement_retrieval._embed_dense", fake_embed)
    monkeypatch.setattr(config, "PLACEMENT_RAG_MAX_QUERIES", 1)
    monkeypatch.setattr(config, "PLACEMENT_RAG_CONTEXT_LIMIT", 2)
    monkeypatch.setattr(config, "PLACEMENT_RAG_SEMANTIC_THRESHOLD", 1.1)
    reset_for_test()

    evidence, _ = await retrieve_placements(
        zones,
        {"text": "competitive esports", "content_text": "competitive esports"},
        limit=3,
    )

    assert evidence["GAMING"]["rank"] == 1
    assert evidence["GAMING"]["sparse_score"] == 1.0
