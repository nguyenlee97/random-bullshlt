from types import SimpleNamespace

import pytest

from config import config
from tools.placement_reranker import (
    PlacementRerankItem,
    PlacementRerankResult,
    PlacementTopicRerankItem,
    PlacementTopicRerankResult,
    rerank_placements,
    rerank_topics,
)


class FakeResponses:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id="resp_np6_test",
            output_parsed=self.result,
        )


class FakeClient:
    def __init__(self, result):
        self.responses = FakeResponses(result)


@pytest.mark.asyncio
async def test_reranker_can_only_reorder_known_candidate_ids(monkeypatch):
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "PLACEMENT_RERANK_MODEL", "gpt-5.4-nano")
    candidates = [
        {"id": "A", "score": 10, "topicId": "technology_science"},
        {"id": "B", "score": 9, "topicId": "family_parenting"},
    ]
    result = PlacementRerankResult(items=[
        PlacementRerankItem(
            placement_id="B", relevance_score=0.95, rationale="Family match",
        ),
        PlacementRerankItem(
            placement_id="A", relevance_score=0.1, rationale="Weak match",
        ),
    ])
    client = FakeClient(result)

    ranked, meta = await rerank_placements(
        candidates, {"text": "mother and baby"}, client=client,
    )

    assert [item["id"] for item in ranked] == ["B", "A"]
    assert ranked[0]["llm_rerank"]["model"] == "gpt-5.4-nano"
    assert meta["applied"] is True
    assert client.responses.calls[0]["store"] is False


@pytest.mark.asyncio
async def test_invalid_reranker_output_fails_open_to_deterministic_order(monkeypatch):
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    candidates = [{"id": "A", "score": 10}, {"id": "B", "score": 9}]
    invalid = PlacementRerankResult(items=[
        PlacementRerankItem(
            placement_id="UNKNOWN", relevance_score=1, rationale="Invalid",
        ),
    ])

    ranked, meta = await rerank_placements(
        candidates, {"text": "sports"}, client=FakeClient(invalid),
    )

    assert ranked == candidates
    assert meta["applied"] is False
    assert meta["reason"] == "provider_or_validation_failure"


@pytest.mark.asyncio
async def test_disabled_reranker_does_not_call_provider(monkeypatch):
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", False)
    candidates = [{"id": "A", "score": 10}]

    ranked, meta = await rerank_placements(candidates, {"text": "sports"})

    assert ranked == candidates
    assert meta == {"applied": False, "reason": "disabled_or_no_context"}


@pytest.mark.asyncio
async def test_topic_reranker_reorders_unique_retrieved_topics(monkeypatch):
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "PLACEMENT_RERANK_MODEL", "gpt-5.4-nano")
    candidates = [
        {
            "topic_id": "technology_science",
            "document": "technology cloud software",
            "rank": 1,
            "dense_score": 0.7,
        },
        {
            "topic_id": "family_parenting",
            "document": "family parenting children mother baby",
            "rank": 2,
            "dense_score": 0.6,
        },
    ]
    result = PlacementTopicRerankResult(items=[
        PlacementTopicRerankItem(
            topic_id="family_parenting",
            relevance_score=0.96,
            rationale="Early childhood context",
        ),
        PlacementTopicRerankItem(
            topic_id="technology_science",
            relevance_score=0.08,
            rationale="Unrelated",
        ),
    ])

    ranked, meta = await rerank_topics(
        candidates,
        {"text": "newborn essentials"},
        client=FakeClient(result),
    )

    assert [item["topic_id"] for item in ranked] == [
        "family_parenting",
        "technology_science",
    ]
    assert ranked[0]["topic_rerank"]["score"] == 0.96
    assert meta["stage"] == "topic"
    assert meta["applied"] is True


@pytest.mark.asyncio
async def test_topic_reranker_rejects_changed_candidate_set(monkeypatch):
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    candidates = [{"topic_id": "sports_outdoors", "document": "sports"}]
    invalid = PlacementTopicRerankResult(items=[
        PlacementTopicRerankItem(
            topic_id="unknown_topic",
            relevance_score=1,
            rationale="Invented",
        ),
    ])

    ranked, meta = await rerank_topics(
        candidates,
        {"text": "running shoes"},
        client=FakeClient(invalid),
    )

    assert ranked == candidates
    assert meta["applied"] is False
    assert meta["reason"] == "provider_or_validation_failure"


@pytest.mark.asyncio
async def test_topic_reranker_safely_appends_omitted_known_topics(monkeypatch):
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    candidates = [
        {"topic_id": "music_live_events", "document": "music concerts", "rank": 1},
        {"topic_id": "business_finance", "document": "finance", "rank": 2},
    ]
    partial = PlacementTopicRerankResult(items=[
        PlacementTopicRerankItem(
            topic_id="music_live_events",
            relevance_score=0.95,
            rationale="Concert campaign",
        ),
    ])

    ranked, meta = await rerank_topics(
        candidates,
        {"text": "live artist stage experience"},
        client=FakeClient(partial),
    )

    assert [item["topic_id"] for item in ranked] == [
        "music_live_events",
        "business_finance",
    ]
    assert ranked[1]["topic_rerank"]["score"] == 0
    assert meta["omitted_count"] == 1
    assert meta["applied"] is True


@pytest.mark.asyncio
async def test_topic_reranker_deduplicates_known_topics(monkeypatch):
    monkeypatch.setattr(config, "PLACEMENT_RERANK_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    candidates = [
        {"topic_id": "automotive_mobility", "document": "electric vehicle"},
        {"topic_id": "technology_science", "document": "technology"},
    ]
    duplicate = PlacementTopicRerankResult(items=[
        PlacementTopicRerankItem(
            topic_id="automotive_mobility",
            relevance_score=0.9,
            rationale="Electric mobility",
        ),
        PlacementTopicRerankItem(
            topic_id="automotive_mobility",
            relevance_score=0.8,
            rationale="Duplicate known topic",
        ),
    ])

    ranked, meta = await rerank_topics(
        candidates,
        {"text": "zero-emission urban transport"},
        client=FakeClient(duplicate),
    )

    assert [item["topic_id"] for item in ranked] == [
        "automotive_mobility",
        "technology_science",
    ]
    assert meta["duplicate_count"] == 1
    assert meta["omitted_count"] == 1
    assert meta["applied"] is True
