from types import SimpleNamespace
import threading

import pytest

from rag.index import _catalog_fingerprint
from rag.recommend import _catalog_segment_count
from rag.recommend import (
    _focused_query,
    _guard_reason,
    _hybrid_search,
    _rank_merged,
    _raw_query,
    recommend_rag,
)
from rag.nano_rerank import rerank_candidates
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


def test_focused_query_removes_creative_and_strategy_workflow_noise():
    query = _focused_query({
        "brand": "Phở Anh Hai",
        "objective": "conversion",
        "notes": (
            "Mục tiêu bán được nhiều phở. "
            "Creative notes: người dùng chưa biết creative, nhờ gợi ý giúp.\n"
            "Chiến lược: ưu tiên audience có ý định cao."
        ),
    })

    assert "Phở Anh Hai" in query
    assert "bán được nhiều phở" in query
    assert "Creative notes" not in query
    assert "Chiến lược" not in query


def test_focused_query_preserves_b2b_and_exclusions_before_creative_tail():
    query = _focused_query({
        "brand": "GreenFarm",
        "notes": (
            "B2B bán phân bón cho trang trại và đại lý nông nghiệp; "
            "loại trừ người chỉ thích làm vườn tại nhà. "
            "Creative: bò uống sữa trên cánh đồng xanh."
        ),
    })

    assert "B2B" in query
    assert "trang trại" in query
    assert "loại trừ" in query
    assert "bò uống sữa" not in query


@pytest.mark.asyncio
async def test_semantic_query_plan_adds_catalog_queries_without_raw_creative_noise(monkeypatch):
    import rag.recommend as recommend

    captured = {}
    candidate = {
        "_id": "mongo-agri",
        "segmentId": "INT002",
        "fullLabel": "Agriculture",
        "name": "Agriculture",
        "_text": "agriculture business",
        "_rank": 0,
        "_query_hits": 1,
        "_fusion_score": 1 / 61,
        "_rag_index": {"segment_count": 310},
    }

    async def ready(_session_id):
        return True

    async def search(queries, _limit, mode=None):
        captured["queries"] = queries
        return [candidate]

    async def planner(_brief):
        return {
            "queries": ["agriculture industry", "farm input dealers"],
            "industry_queries": ["agriculture industry"],
            "buyer_queries": ["farm input dealers"],
            "creative_only_concepts": ["cow drinking milk"],
            "applied": True,
        }

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(recommend.config, "RAG_TOP_RETRIEVE", 10)
    monkeypatch.setattr(recommend.config, "RAG_TOP_FINAL", 10)

    result = await recommend_rag(
        "semantic-query-plan",
        {
            "brand": "GreenFarm",
            "objective": "conversion",
            "kpi": "qualified dealer leads",
            "notes": (
                "B2B fertilizer for farms. "
                "Creative: cow drinking milk in a green field."
            ),
        },
        provider="openai",
        query_rewriter=planner,
        use_focused_query=True,
        enable_query_rewrite=True,
        include_raw_query=False,
        rerank_mode="off",
        select_from_rerank_scores=True,
        min_relevance_score=0.5,
    )

    assert captured["queries"] == [
        "GreenFarm | conversion | qualified dealer leads | B2B fertilizer for farms.",
        "agriculture industry",
        "farm input dealers",
    ]
    assert all("cow drinking milk" not in query for query in captured["queries"])
    assert result["rag"]["query_plan"]["creative_only_concepts"] == [
        "cow drinking milk",
    ]


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
async def test_bm25_only_does_not_initialize_dense_embedding(monkeypatch):
    import rag.embeddings as embeddings
    import rag.recommend as recommend

    class Values(list):
        def tolist(self):
            return list(self)

    class Client:
        def query_points(self, *_args, **_kwargs):
            return SimpleNamespace(points=[])

    def dense_must_not_run(_queries):
        raise AssertionError("dense embedding ran in bm25_only mode")

    monkeypatch.setattr(embeddings, "embed_dense", dense_must_not_run)
    monkeypatch.setattr(
        embeddings,
        "embed_sparse",
        lambda queries: [
            SimpleNamespace(indices=Values([1]), values=Values([1.0]))
            for _ in queries
        ],
    )
    monkeypatch.setattr(recommend, "get_qdrant", lambda: Client())

    assert await _hybrid_search(["food delivery"], 5, mode="bm25_only") == []


@pytest.mark.asyncio
async def test_nano_reranker_rejects_unknown_segment_and_fails_open(monkeypatch):
    class Responses:
        async def parse(self, **_kwargs):
            return SimpleNamespace(
                output_parsed=SimpleNamespace(items=[
                    SimpleNamespace(candidate_index=29, relevance_score=1.0)
                ]),
                id="resp-test",
            )

    class Client:
        responses = Responses()

    monkeypatch.setattr(
        "rag.nano_rerank.config.OPENAI_API_KEY", "test-key"
    )
    order, meta = await rerank_candidates(
        "food shoppers",
        [
            {"segmentId": "SEG-1", "fullLabel": "Food"},
            {"segmentId": "SEG-2", "fullLabel": "Online shoppers"},
        ],
        client=Client(),
    )

    assert order is None
    assert meta["applied"] is False
    assert meta["reason"] == "provider_or_validation_failure"


@pytest.mark.asyncio
async def test_nano_reranker_normalizes_duplicates_and_appends_omissions(monkeypatch):
    class Responses:
        async def parse(self, **_kwargs):
            return SimpleNamespace(
                output_parsed=SimpleNamespace(items=[
                    SimpleNamespace(
                        candidate_index=1, segment_id="SEG-2",
                        relevance_score=0.9,
                    ),
                    SimpleNamespace(
                        candidate_index=1, segment_id="SEG-2",
                        relevance_score=0.8,
                    ),
                ]),
                id="resp-test",
            )

    class Client:
        responses = Responses()

    monkeypatch.setattr(
        "rag.nano_rerank.config.OPENAI_API_KEY", "test-key"
    )
    order, meta = await rerank_candidates(
        "food shoppers",
        [
            {"segmentId": "SEG-1", "fullLabel": "Food"},
            {"segmentId": "SEG-2", "fullLabel": "Online shoppers"},
            {"segmentId": "SEG-3", "fullLabel": "Coupons"},
        ],
        client=Client(),
    )

    assert order == [1, 0, 2]
    assert meta["applied"] is True
    assert meta["duplicate_count"] == 1
    assert meta["omitted_count"] == 2


@pytest.mark.asyncio
async def test_nano_reranker_retries_mismatched_index_and_segment_id(monkeypatch):
    class Responses:
        calls = 0

        async def parse(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    output_parsed=SimpleNamespace(items=[
                        SimpleNamespace(
                            candidate_index=0,
                            segment_id="WRONG-ID",
                            relevance_score=0.9,
                        ),
                    ]),
                    id="resp-mismatched-index",
                )
            return SimpleNamespace(
                output_parsed=SimpleNamespace(items=[
                    SimpleNamespace(
                        candidate_index=0,
                        segment_id="SEG-1",
                        relevance_score=0.9,
                        match_tier="recommended",
                        matched_signals=["food"],
                        missing_signals=[],
                        limitation="",
                    ),
                ]),
                id="resp-retry",
            )

    class Client:
        responses = Responses()

    monkeypatch.setattr(
        "rag.nano_rerank.config.OPENAI_API_KEY", "test-key"
    )
    order, meta = await rerank_candidates(
        "food shoppers",
        [{"segmentId": "SEG-1", "fullLabel": "Food"}],
        client=Client(),
    )

    assert order == [0]
    assert meta["applied"] is True
    assert Client.responses.calls == 2


@pytest.mark.asyncio
async def test_nano_reranker_prompt_preserves_taxonomy_boundaries(monkeypatch):
    captured = {}

    class Responses:
        async def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_parsed=SimpleNamespace(items=[
                    SimpleNamespace(
                        candidate_index=0,
                        segment_id="INT059",
                        relevance_score=0.95,
                        match_tier="recommended",
                        matched_signals=["video games"],
                        missing_signals=[],
                        limitation="",
                    ),
                    SimpleNamespace(
                        candidate_index=1,
                        segment_id="INT060",
                        relevance_score=0.05,
                        match_tier="unrelated",
                        matched_signals=[],
                        missing_signals=["real-world motorsport"],
                        limitation="Different taxonomy meaning.",
                    ),
                ]),
                id="resp-taxonomy",
            )

    class Client:
        responses = Responses()

    monkeypatch.setattr(
        "rag.nano_rerank.config.OPENAI_API_KEY", "test-key"
    )
    order, meta = await rerank_candidates(
        "Controller for video gamers across multiple game genres",
        [
            {
                "segmentId": "INT059",
                "fullLabel": "Video games (gaming)",
                "category": "Entertainment",
            },
            {
                "segmentId": "INT060",
                "fullLabel": "Auto racing (motor sports)",
                "category": "Sports",
            },
        ],
        client=Client(),
    )

    assert order == [0, 1]
    assert meta["applied"] is True
    assert "Respect taxonomy namespaces" in captured["instructions"]
    assert "game genre must not promote" in captured["instructions"]
    assert "broad video-game interest is a direct user category" in (
        captured["instructions"]
    )


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

    async def search(_queries, _limit, mode=None):
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


@pytest.mark.asyncio
async def test_recommend_rag_keeps_catalog_order_when_selector_fails(monkeypatch):
    import rag.recommend as recommend

    candidates = [
        {
            "_id": f"mongo-{index}",
            "segmentId": f"SEG-{index}",
            "fullLabel": f"Segment {index}",
            "name": f"Segment {index}",
            "_text": f"relevant audience {index}",
            "_rank": index,
            "_query_hits": 1,
            "_fusion_score": 1 / (61 + index),
            "_rag_index": {"segment_count": 310},
        }
        for index in range(1, 8)
    ]

    async def ready(_session_id):
        return True

    async def search(_queries, _limit, mode=None):
        return candidates

    async def unavailable_selector(_prompt):
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(recommend, "_select", unavailable_selector)
    monkeypatch.setattr(recommend.config, "RAG_QUERY_REWRITE", False)
    monkeypatch.setattr(recommend.config, "AUDIENCE_RERANK_MODE", "off")
    monkeypatch.setattr(recommend.config, "RAG_TOP_RETRIEVE", 7)
    monkeypatch.setattr(recommend.config, "RAG_TOP_FINAL", 7)

    result = await recommend_rag("selector-fail-open", {
        "brand": "Example",
        "objective": "awareness",
        "notes": "relevant audience",
    })

    assert [item["segmentId"] for item in result["recommendations"]] == [
        "SEG-1", "SEG-2", "SEG-3", "SEG-4", "SEG-5", "SEG-6",
    ]
    assert result["rag"]["applied"] is True
    assert result["rag"]["selector"] == "retrieval_order_fallback"
    assert result["rag"]["selector_fallback_reason"] == "provider_unavailable"
    assert "selector_error" not in result["rag"]


@pytest.mark.asyncio
async def test_recommend_rag_applies_bounded_nano_order_and_keeps_tail(monkeypatch):
    import rag.nano_rerank as nano
    import rag.recommend as recommend

    candidates = [
        {
            "_id": f"mongo-{index}",
            "segmentId": f"SEG-{index}",
            "fullLabel": f"Segment {index}",
            "name": f"Segment {index}",
            "_text": f"segment {index}",
            "_rank": index,
            "_query_hits": 1,
            "_fusion_score": 1 / (61 + index),
            "_rag_index": {"segment_count": 310},
        }
        for index in range(1, 8)
    ]

    async def ready(_session_id):
        return True

    async def search(_queries, _limit, mode=None):
        return candidates

    async def nano_order(_query, _candidates, **_kwargs):
        return [2, 0, 1], {
            "applied": True,
            "mode": "openai_nano",
            "model": "gpt-5.4-nano",
            "candidate_count": 3,
        }

    async def select(_prompt):
        return [
            {"fullLabel": f"Segment {index}", "reason": "fixture"}
            for index in (3, 1, 2, 4, 5, 6)
        ], "fixture"

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(recommend, "_select", select)
    monkeypatch.setattr(nano, "rerank_candidates", nano_order)
    monkeypatch.setattr(recommend.config, "RAG_QUERY_REWRITE", False)
    monkeypatch.setattr(recommend.config, "AUDIENCE_RERANK_MODE", "openai_nano")
    monkeypatch.setattr(recommend.config, "RAG_TOP_RETRIEVE", 7)
    monkeypatch.setattr(recommend.config, "RAG_TOP_FINAL", 7)

    result = await recommend_rag("nano-order", {
        "brand": "Example",
        "notes": "relevant audience",
    })

    assert result["rag"]["reranked"] is True
    assert result["rag"]["rerank_mode"] == "openai_nano"
    assert result["rag"]["rerank_model"] == "gpt-5.4-nano"
    assert [item["segmentId"] for item in result["recommendations"]][:3] == [
        "SEG-3", "SEG-1", "SEG-2",
    ]


@pytest.mark.asyncio
async def test_openai_score_gate_reaches_beyond_old_window_and_rejects_fillers(monkeypatch):
    import rag.nano_rerank as nano
    import rag.recommend as recommend

    candidates = [
        {
            "_id": f"mongo-{index}",
            "segmentId": f"SEG-{index}",
            "fullLabel": f"Segment {index}",
            "name": f"Segment {index}",
            "category": "Unrelated",
            "_text": f"segment {index}",
            "_rank": index,
            "_query_hits": 1,
            "_fusion_score": 1 / (61 + index),
            "_rag_index": {"segment_count": 310},
        }
        for index in range(40)
    ]
    for index, label in (
        (31, "Diners (restaurant)"),
        (36, "Restaurants (dining)"),
        (37, "Vietnamese cuisine (food & drink)"),
    ):
        candidates[index].update({
            "fullLabel": label,
            "name": label,
            "category": "Food and drink (consumables)",
        })

    async def ready(_session_id):
        return True

    async def search(_queries, _limit, mode=None):
        return candidates

    async def nano_order(
        _query, _candidates, candidate_limit=None, **_kwargs
    ):
        assert candidate_limit == 50
        leading = [37, 31, 36]
        order = leading + [index for index in range(40) if index not in leading]
        scores = {f"SEG-{index}": 0.22 for index in range(40)}
        scores.update({"SEG-31": 0.91, "SEG-36": 0.88, "SEG-37": 0.94})
        return order, {
            "applied": True,
            "mode": "openai_nano",
            "model": "gpt-5.4-nano",
            "candidate_count": 40,
            "scores": scores,
        }

    async def selector_must_not_run(_prompt):
        raise AssertionError("second audience selector ran")

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(recommend, "_select", selector_must_not_run)
    monkeypatch.setattr(nano, "rerank_candidates", nano_order)
    monkeypatch.setattr(recommend.config, "RAG_QUERY_REWRITE", False)
    monkeypatch.setattr(recommend.config, "RAG_TOP_RETRIEVE", 50)
    monkeypatch.setattr(recommend.config, "RAG_TOP_FINAL", 25)

    result = await recommend_rag(
        "openai-quality-gate",
        {
            "brand": "Phở Anh Hai",
            "objective": "conversion",
            "notes": "Mục tiêu bán được nhiều phở. Creative notes: gợi ý creative.",
        },
        provider="openai",
        rerank_mode="openai_nano",
        use_focused_query=True,
        enable_query_rewrite=False,
        select_from_rerank_scores=True,
        min_relevance_score=0.45,
        rerank_candidate_limit=50,
    )

    assert [item["segmentId"] for item in result["recommendations"]] == [
        "SEG-37", "SEG-31", "SEG-36",
    ]
    assert all(item["category"] == "Food and drink (consumables)"
               for item in result["recommendations"])
    assert result["rag"]["selector"] == "openai_nano_scores"
    assert result["rag"]["quality_gate"]["eligible"] == 3
    assert result["rag"]["stage_ms"]["generate"] <= 2


@pytest.mark.asyncio
async def test_openai_score_gate_returns_empty_instead_of_six_weak_segments(monkeypatch):
    import rag.nano_rerank as nano
    import rag.recommend as recommend

    candidates = [
        {
            "_id": f"mongo-{index}",
            "segmentId": f"WEAK-{index}",
            "fullLabel": f"Weak segment {index}",
            "name": f"Weak segment {index}",
            "_text": f"weak {index}",
            "_rank": index,
            "_query_hits": 1,
            "_fusion_score": 1 / (61 + index),
            "_rag_index": {"segment_count": 310},
        }
        for index in range(8)
    ]

    async def ready(_session_id):
        return True

    async def search(_queries, _limit, mode=None):
        return candidates

    async def nano_order(
        _query, _candidates, candidate_limit=None, **_kwargs
    ):
        return list(range(8)), {
            "applied": True,
            "mode": "openai_nano",
            "candidate_count": 8,
            "scores": {f"WEAK-{index}": 0.22 for index in range(8)},
        }

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(nano, "rerank_candidates", nano_order)
    monkeypatch.setattr(recommend.config, "RAG_TOP_RETRIEVE", 50)
    monkeypatch.setattr(recommend.config, "RAG_TOP_FINAL", 25)

    result = await recommend_rag(
        "openai-reject-weak",
        {"brand": "Example", "notes": "specific product"},
        provider="openai",
        rerank_mode="openai_nano",
        select_from_rerank_scores=True,
        min_relevance_score=0.45,
        rerank_candidate_limit=50,
    )

    assert result["recommendations"] == []
    assert result["rag"]["quality_gate"]["eligible"] == 0
    assert result["rag"]["quality_gate"]["rejected"] == 8


def test_openai_retrieval_merge_prioritizes_explicit_audience_identity():
    from rag.recommend import _merge_openai_retrieval

    def row(segment_id, label, score):
        return ({
            "_id": segment_id,
            "segmentId": segment_id,
            "fullLabel": label,
            "_text": label,
            "_rag_index": {"segment_count": 310},
        }, score)

    specs = [
        {"query": "Vietnamese expats", "kind": "audience"},
        {"query": "IoT leak sensor", "kind": "product"},
        {"query": "warehouse manager", "kind": "buyer"},
        {"query": "industrial facilities", "kind": "industry"},
    ]
    dense = [
        [row("AUDIENCE", "Expats", 0.95), row("GENERIC", "Shops admins", 0.8)],
        [row("PRODUCT", "Technology early adopters", 0.9), row("GENERIC", "Shops admins", 0.8)],
        [row("BUYER", "Management", 0.9), row("GENERIC", "Shops admins", 0.8)],
        [row("INDUSTRY", "Construction", 0.9), row("GENERIC", "Shops admins", 0.8)],
    ]
    sparse = [
        [row("AUDIENCE", "Expats", 13.0)],
        [row("PRODUCT", "Technology early adopters", 12.0)],
        [row("BUYER", "Management", 11.0)],
        [row("INDUSTRY", "Construction", 10.0)],
    ]

    candidates, trace = _merge_openai_retrieval(specs, dense, sparse)

    assert [item["segmentId"] for item in candidates[:4]] == [
        "AUDIENCE", "PRODUCT", "BUYER", "INDUSTRY",
    ]
    assert trace["query_results"][0]["dense_top"][0]["full_label"] == (
        "Expats"
    )
    assert trace["query_results"][1]["bm25_top"][0]["full_label"] == (
        "Technology early adopters"
    )
    assert trace["merged_pre_rerank"][0]["segment_id"] == "AUDIENCE"


@pytest.mark.asyncio
async def test_openai_insufficient_plan_skips_catalog_retrieval(monkeypatch):
    import rag.recommend as recommend

    async def ready(_session_id):
        return True

    async def planner(_brief):
        return {
            "queries": [],
            "query_specs": [],
            "information_sufficient": False,
            "insufficient_reason": "brief_missing_product_or_audience_evidence",
            "applied": True,
        }

    async def forbidden_search(*_args, **_kwargs):
        raise AssertionError("catalog retrieval must not run for a vague brief")

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", forbidden_search)
    monkeypatch.setattr(recommend, "_openai_hybrid_search", forbidden_search)

    result = await recommend.recommend_rag(
        "openai-vague-brief",
        {
            "brand": "Nova",
            "objective": "awareness",
            "kpi": "Tăng nhận diện",
            "notes": "Muốn tìm thêm khách hàng phù hợp cho sản phẩm mới.",
        },
        provider="openai",
        query_rewriter=planner,
        enable_query_rewrite=True,
        detailed_retrieval=True,
    )

    assert result["recommendations"] == []
    assert result["adjacent_recommendations"] == []
    assert result["note"] == "audience_information_insufficient"
    assert result["rag"]["information_sufficient"] is False
    assert result["rag"]["quality_gate"]["reason"] == "insufficient_information"


@pytest.mark.asyncio
async def test_openai_quality_gate_separates_parent_proxy_and_cross_domain(monkeypatch):
    import rag.nano_rerank as nano
    import rag.recommend as recommend

    def candidate(
        segment_id, label, category, subcategory, rank, context=None
    ):
        return {
            "_id": segment_id,
            "segmentId": segment_id,
            "fullLabel": label,
            "name": label,
            "category": category,
            "subcategory": subcategory,
            "context": context,
            "_text": label,
            "_rank": rank,
            "_fusion_score": 0.1,
                "_query_hits": 4,
                "_query_matches": [{
                    "kind": "audience",
                    "query_rank": 1,
                }],
                "_rag_index": {"segment_count": 310},
        }

    candidates = [
        candidate(
            "CHILD-1", "Action games (video games)",
            "Entertainment", "Games", 0, "video games",
        ),
        candidate(
            "CHILD-2", "Sports games (video games)",
            "Entertainment", "Games", 1, "video games",
        ),
        candidate(
            "PARENT", "Video games (gaming)",
            "Entertainment", "Games", 2,
        ),
        candidate(
            "PROXY", "Construction (industry)",
            "Business and industry", None, 3,
        ),
        candidate(
            "CROSS", "Shops admins",
            "Digital Activities", None, 4,
        ),
    ]
    from rag.taxonomy import expand_candidates_with_taxonomy

    candidates, _graph, _trace = expand_candidates_with_taxonomy(
        candidates,
        candidates,
        candidate_limit=len(candidates),
    )

    async def ready(_session_id):
        return True

    async def search(_queries, _limit, mode=None):
        return candidates

    async def nano_order(_query, _candidates, **_kwargs):
        return list(range(len(candidates))), {
            "applied": True,
            "mode": "openai_nano",
            "candidate_count": len(candidates),
            "scores": {
                "CHILD-1": 0.90,
                "CHILD-2": 0.85,
                "PARENT": 0.55,
                "PROXY": 0.90,
                "CROSS": 0.40,
            },
            "assessments": {
                "CHILD-1": {
                    "match_tier": "recommended",
                    "match_basis": "exact_user_interest",
                },
                "CHILD-2": {
                    "match_tier": "recommended",
                    "match_basis": "exact_user_interest",
                },
                "PARENT": {
                    "match_tier": "adjacent",
                    "match_basis": "broad_parent",
                },
                "PROXY": {
                    "match_tier": "recommended",
                    "match_basis": "proxy",
                },
                "CROSS": {
                    "match_tier": "adjacent",
                    "match_basis": "proxy",
                },
            },
        }

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(nano, "rerank_candidates", nano_order)

    result = await recommend.recommend_rag(
        "openai-tier-confidence",
        {
            "brand": "Controller",
            "notes": "Gamepad for action and sports video game players.",
        },
        provider="openai",
        rerank_mode="openai_nano",
        select_from_rerank_scores=True,
        min_relevance_score=0.45,
    )

    assert [row["segmentId"] for row in result["recommendations"]] == [
        "CHILD-1", "CHILD-2", "PARENT",
    ]
    assert [row["segmentId"] for row in result["adjacent_recommendations"]] == [
        "PROXY",
    ]
    decisions = {
        row["segment_id"]: row
        for row in result["rag"]["quality_gate"]["decisions"]
    }
    assert decisions["PARENT"]["gate_rule"] == (
        "coverage_anchor_multiple_direct_children"
    )
    assert decisions["PROXY"]["gate_rule"] == "proxy_basis"
    assert decisions["CROSS"]["gate_rule"] == "generic_digital_proxy"


@pytest.mark.asyncio
async def test_openai_tiers_keep_broad_b2b_proxies_optional(monkeypatch):
    import rag.nano_rerank as nano
    import rag.recommend as recommend

    candidates = [
        {
            "_id": "BEH011", "segmentId": "BEH011",
            "fullLabel": "Shops admins", "name": "Shops admins",
            "category": "Digital Activities", "_text": "shops admins",
            "_rank": 0, "_query_hits": 2, "_fusion_score": 0.03,
            "_rag_index": {"segment_count": 310},
        },
        {
            "_id": "INT006", "segmentId": "INT006",
            "fullLabel": "Construction", "name": "Construction",
            "category": "Business and industry", "_text": "construction",
            "_rank": 1, "_query_hits": 1, "_fusion_score": 0.02,
            "_rag_index": {"segment_count": 310},
        },
        {
            "_id": "INT020", "segmentId": "INT020",
            "fullLabel": "Management", "name": "Management",
            "category": "Business and industry", "_text": "management",
            "_rank": 2, "_query_hits": 1, "_fusion_score": 0.01,
            "_rag_index": {"segment_count": 310},
        },
    ]

    async def ready(_session_id):
        return True

    async def search(_queries, _limit, mode=None):
        return candidates

    async def nano_order(
        _query, _candidates, candidate_limit=None, **_kwargs
    ):
        return [0, 1, 2], {
            "applied": True,
            "mode": "openai_nano",
            "candidate_count": 3,
            "scores": {"BEH011": 0.72, "INT006": 0.50, "INT020": 0.45},
            "assessments": {
                "BEH011": {
                    "match_tier": "unrelated",
                    "matched_signals": [],
                    "missing_signals": ["facility role", "industrial IoT"],
                    "limitation": "Digital activity, not a warehouse buyer role.",
                },
                "INT006": {
                    "match_tier": "adjacent",
                    "matched_signals": ["industrial facilities"],
                    "missing_signals": ["warehouse operations", "IoT procurement"],
                    "limitation": "Broad industry proxy.",
                },
                "INT020": {
                    "match_tier": "adjacent",
                    "matched_signals": ["management role"],
                    "missing_signals": ["facility specialization"],
                    "limitation": "Broad role proxy.",
                },
            },
        }

    monkeypatch.setattr(recommend, "ensure_index", ready)
    monkeypatch.setattr(recommend, "_hybrid_search", search)
    monkeypatch.setattr(nano, "rerank_candidates", nano_order)
    monkeypatch.setattr(recommend.config, "RAG_TOP_FINAL", 25)

    result = await recommend_rag(
        "aquaguard-tier-test",
        {
            "brand": "AquaGuard Pro",
            "notes": "IoT leak sensors for warehouses and factories; B2B facility managers.",
        },
        provider="openai",
        rerank_mode="openai_nano",
        select_from_rerank_scores=True,
        min_relevance_score=0.50,
    )

    assert result["recommendations"] == []
    assert [
        item["segmentId"] for item in result["adjacent_recommendations"]
    ] == ["INT006", "INT020"]
    assert all(
        item["tier"] == "adjacent"
        for item in result["adjacent_recommendations"]
    )
    assert result["rag"]["tier_counts"] == {
        "recommended": 0,
        "adjacent": 2,
        "rejected": 1,
    }
