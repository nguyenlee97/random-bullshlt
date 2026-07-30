from unittest.mock import AsyncMock

import pytest

from campaign_models import GREENNODE_MINIMAX, OPENAI_GPT_5_4_MINI
from openai_campaign.zalo_review import (
    assignment_media_parts,
    creative_media_parts,
    render_openai_milestone_message,
    render_openai_review_message,
)
from zalo_worker import _progress_message


def _run(key: str, value: dict, *, model: str = OPENAI_GPT_5_4_MINI) -> tuple[dict, dict]:
    task = {
        "task_id": f"run-review:{key}",
        "key": key,
        "title": key,
        "status": "waiting_review",
        "result": {"stale": True},
        "pending_artifact": {"value": value},
    }
    return {
        "run_id": "run-review",
        "conversation_model": model,
        "tasks": [task],
    }, task


def _event(task: dict) -> dict:
    return {
        "type": "task_waiting_review",
        "payload": {"task_id": task["task_id"]},
    }


def _workspace() -> dict:
    return {
        "artifacts": {
            "brief": {"value": {
                "brand": "Mixigaming",
                "budget": 50,
                "startDate": "2026-08-01",
                "endDate": "2026-08-07",
            }},
            "audience": {"value": {"attrs": [{"_id": "INT001"}]}},
            "targeting": {"value": {
                "age": ["25-34"],
                "gender": ["Male", "Female"],
                "geo": ["TP.HCM"],
            }},
            "creative": {"value": {"files": [{
                "name": "mixi-banner.png",
                "url": "https://example.test/mixi-banner.png",
                "width": 1160,
                "height": 280,
            }]}},
            "creative_verdict": {"value": {"files": [{
                "name": "mixi-banner.png",
                "url": "https://example.test/mixi-banner.png",
                "status": "auto_approved",
                "effective_status": "auto_approved",
            }]}},
            "placement_intent": {"value": {
                "candidates": [{"id": "ZONE-1", "name": "Masthead"}],
            }},
            "placements": {"value": {
                "selectedZoneIds": ["ZONE-1"],
                "zones": [{"id": "ZONE-1", "name": "Masthead"}],
            }},
            "forecast": {"value": {
                "estimated_reach": 1_200_000,
                "estimated_impressions": 3_600_000,
            }},
        },
    }


def test_openai_audience_review_lists_public_segment_details_only():
    run, task = _run("retrieve_audience", {
        "attrs": [
            {
                "_id": "INT001",
                "fullLabel": "Tea (nonalcoholic beverage)",
                "sizeMin": 2_530_000,
                "sizeMax": 3_560_000,
                "reason": "Phù hợp trực tiếp với sản phẩm.",
            },
            {
                "_id": "INT002",
                "fullLabel": "Coffeehouses (coffee)",
                "sizeMin": 1_750_000,
                "sizeMax": 2_470_000,
                "reason": "Có hành vi quan tâm đồ uống.",
            },
        ],
        "size": 5_155_000,
    })

    text = _progress_message(
        run,
        _event(task),
        workspace=_workspace(),
        workspace_url="https://example.test/?conversation=conv-1",
    )

    assert "2 segment" in text
    assert "Tea (nonalcoholic beverage)" in text
    assert "2,53 triệu–3,56 triệu" in text
    assert "Phù hợp trực tiếp với sản phẩm." not in text
    assert "Xác nhận” để duyệt audience" in text
    assert "bằng số hoặc tên" in text
    assert "https://example.test/?conversation=conv-1" in text
    assert "stale" not in text


def test_openai_targeting_review_shows_values_before_confirmation():
    run, task = _run("derive_targeting", {
        "age": ["25-34", "35-44"],
        "gender": ["Male", "Female"],
        "geo": ["TP.HCM", "Hà Nội"],
    })

    text = _progress_message(run, _event(task), workspace=_workspace())

    assert "Độ tuổi: 25-34, 35-44" in text
    assert "Giới tính: Male, Female" in text
    assert "Khu vực: TP.HCM, Hà Nội" in text
    assert "Xác nhận” để duyệt targeting" in text


def test_openai_placement_review_shows_inventory_metrics_and_estimate_disclosure():
    run, task = _run("plan_placement_intent", {
        "candidate_zone_ids": ["ZONE-1"],
        "candidates": [{
            "id": "BaoMoi_FoodDining_Background",
            "channel": "BaoMoi",
            "cpm": 42_000,
            "reach": 2_500_000,
        }],
    })

    text = _progress_message(run, _event(task), workspace=_workspace())

    assert "BaoMoi_FoodDining_Background" in text
    assert "CPM 42.000đ" in text
    assert "reach 2,5 triệu" in text
    assert "khớp:" not in text
    assert "ước tính" in text
    assert "Ad zone đề xuất ban đầu" in text
    assert "Chọn zone 1,2,3" in text
    assert "lọc lại độ tương thích" in text
    assert "tối đa 6 zone cuối" not in text
    assert "mở workspace để thay đổi ad zone" in text


def test_openai_audience_review_hides_internal_retrieval_tiers_and_scores():
    run, task = _run("retrieve_audience", {
        "attrs": [],
        "adjacent_attrs": [{
            "_id": "INT006",
            "fullLabel": "Construction",
            "reason": "Liên quan để mở rộng. Hạn chế: proxy ngành rộng.",
            "relevance_score": 0.34,
        }],
        "recommendations": [{
            "_id": "INT006",
            "fullLabel": "Construction",
            "reason": "Liên quan để mở rộng. Hạn chế: proxy ngành rộng.",
            "relevance_score": 0.34,
        }],
        "selection_required": True,
    })

    text = _progress_message(run, _event(task), workspace=_workspace())

    assert "Danh sách audience đề xuất: 1 segment" in text
    assert "1. Construction" in text
    assert "proxy" not in text.lower()
    assert "adjacent" not in text.lower()
    assert "0.34" not in text
    assert "relevance" not in text.lower()
    assert "Liên quan/giới hạn" not in text


def test_openai_audience_review_blocks_confirmation_for_vague_brief():
    run, task = _run("retrieve_audience", {
        "attrs": [],
        "adjacent_attrs": [],
        "clarification_required": True,
        "clarification_prompt": (
            "Bổ sung sản phẩm/dịch vụ, ngành hoặc người mua cụ thể trước khi chọn audience."
        ),
    })

    text = _progress_message(run, _event(task), workspace=_workspace())

    assert "Agent chưa chọn audience" in text
    assert "Bổ sung sản phẩm/dịch vụ" in text
    assert "Chưa thể xác nhận bước này" in text
    assert "Chọn audience 1,2,3" not in text


def test_openai_placement_review_keeps_all_twelve_ordinals_visible():
    zones = [{
        "id": f"ZONE-{index}",
        "name": f"Category homepage ad zone number {index}",
        "channel": "BaoMoi",
        "cpm": 40_000 + index * 1_000,
        "reach": 2_500_000 - index * 10_000,
        "topic_relevance": {
            "matched_keywords": ["nông nghiệp", "đại lý phân bón"],
        },
    } for index in range(1, 13)]
    run, task = _run("plan_placement_intent", {
        "candidate_zone_ids": [zone["id"] for zone in zones],
        "candidates": zones,
    })

    text = _progress_message(run, _event(task), workspace=_workspace())
    numbered = {
        int(line.split(".", 1)[0])
        for line in text.splitlines()
        if line.split(".", 1)[0].isdigit()
    }

    assert numbered == set(range(1, 13))
    assert len(text) <= 1950
    assert "Chọn zone 1,2,3" in text


def test_openai_assignment_review_resolves_zone_and_creative_names():
    run, task = _run("assign_creatives", {
        "assignments": {"ZONE-1": 0},
        "warnings": [],
    })

    text = _progress_message(run, _event(task), workspace=_workspace())

    assert "Masthead → Creative A (1160×280)" in text
    assert "Creative A: mixi-banner.png · đạt kiểm tra" in text
    assert "Xác nhận” để duyệt phân bổ" in text
    assert assignment_media_parts(
        task["pending_artifact"]["value"], _workspace()
    ) == [{
        "kind": "image",
        "image_url": "https://example.test/mixi-banner.png",
    }]


def test_openai_launch_review_shows_material_order_facts_and_side_effect():
    run, task = _run("launch_approval", {
        "ready": True,
        "requires_explicit_approval": True,
        "summary": {
            "brand": "Mixigaming",
            "budget": 50_000_000,
            "placements": ["ZONE-1"],
        },
    })
    run["tasks"].insert(0, {
        "task_id": "run-review:run_order_guard",
        "key": "run_order_guard",
        "status": "succeeded",
        "result": {"passed": True},
    })

    text = _progress_message(run, _event(task), workspace=_workspace())

    assert "Thương hiệu: Mixigaming" in text
    assert "Ngân sách: 50 triệu VND" in text
    assert "2026-08-01 → 2026-08-07" in text
    assert "Forecast ước tính: reach 1,2 triệu" in text
    assert "Kiểm tra an toàn order: Đạt" in text
    assert "sẽ tạo và kích hoạt order" in text


def test_large_review_keeps_confirmation_instructions_within_zalo_limit():
    attrs = [{
        "_id": f"INT{index:03d}",
        "fullLabel": f"Audience segment {index} with a deliberately descriptive catalog label",
        "sizeMin": index * 1_000_000,
        "sizeMax": index * 1_200_000,
        "reason": "A long but grounded explanation that helps the operator understand relevance.",
    } for index in range(1, 16)]
    run, task = _run("retrieve_audience", {"attrs": attrs, "size": 100_000_000})

    text = render_openai_review_message(
        run,
        task,
        workspace=_workspace(),
        workspace_url="https://example.test/workspace",
    )

    assert len(text) <= 1950
    assert "Xác nhận” để duyệt audience đang được chọn" in text
    assert "Gợi ý lại audience" in text
    assert "https://example.test/workspace" in text


def test_openai_fully_automatic_milestones_are_informational_and_complete():
    workspace = _workspace()
    tasks = [
        {
            "task_id": "task-brief",
            "key": "validate_brief",
            "status": "succeeded",
            "result": {"valid": True, "brief": workspace["artifacts"]["brief"]["value"]},
        },
        {
            "task_id": "task-audience",
            "key": "retrieve_audience",
            "status": "succeeded",
            "result": {
                "attrs": [{
                    "segmentId": "INT006",
                    "fullLabel": "Construction",
                    "sizeMin": 5_000_000,
                    "sizeMax": 6_000_000,
                    "tier": "adjacent",
                    "relevance_score": 0.34,
                    "reason": "Proxy/adjacent audience with internal limitations.",
                }],
                "selection_required": False,
                "size": 5_500_000,
            },
        },
        {
            "task_id": "task-targeting",
            "key": "derive_targeting",
            "status": "succeeded",
            "result": {
                "age": ["25-34"],
                "gender": ["Male", "Female"],
                "geo": ["TP.HCM"],
            },
        },
        {
            "task_id": "task-creative",
            "key": "analyze_creatives",
            "status": "succeeded",
            "result": workspace["artifacts"]["creative_verdict"]["value"],
        },
        {
            "task_id": "task-placement",
            "key": "rank_placements",
            "status": "succeeded",
            "result": {
                "zones": [{
                    "id": "ZONE-1",
                    "name": "Masthead",
                    "channel": "BaoMoi",
                    "format": "masthead",
                    "cpm": 42_000,
                    "reach": 2_500_000,
                    "relevance_score": 0.91,
                    "topic_relevance": {"matched_keywords": ["internal-keyword"]},
                }],
            },
        },
    ]
    run = {
        "run_id": "run-auto-milestones",
        "conversation_model": OPENAI_GPT_5_4_MINI,
        "approval_policy": "auto_build_draft",
        "tasks": tasks,
    }

    rendered = {}
    for task in tasks:
        rendered[task["key"]] = _progress_message(
            run,
            {
                "type": "task_completed",
                "payload": {"task_id": task["task_id"]},
            },
            workspace=workspace,
        )

    assert "Brief đã xác nhận" in rendered["validate_brief"]
    assert "Mixigaming" in rendered["validate_brief"]
    assert "Audience đã chuẩn bị" in rendered["retrieve_audience"]
    assert "Construction" in rendered["retrieve_audience"]
    assert "Targeting đã chuẩn bị" in rendered["derive_targeting"]
    assert "Khu vực: TP.HCM" in rendered["derive_targeting"]
    assert "Creative đã kiểm tra" in rendered["analyze_creatives"]
    assert "đạt kiểm tra" in rendered["analyze_creatives"]
    assert "Ad placement đã chọn" in rendered["rank_placements"]
    assert "Masthead" in rendered["rank_placements"]
    for text in rendered.values():
        assert "Xác nhận" not in text
        assert "relevance" not in text.lower()
        assert "proxy" not in text.lower()
        assert "adjacent" not in text.lower()
        assert "internal-keyword" not in text

    assert creative_media_parts(workspace) == [{
        "kind": "image",
        "image_url": "https://example.test/mixi-banner.png",
    }]


def test_greennode_review_message_remains_legacy_and_does_not_render_payload():
    run, task = _run(
        "retrieve_audience",
        {"attrs": [{"fullLabel": "OpenAI-only segment detail"}]},
        model=GREENNODE_MINIMAX,
    )

    text = _progress_message(run, _event(task), workspace=_workspace())

    assert "đang chờ duyệt bước quan trọng" in text
    assert "OpenAI-only segment detail" not in text


@pytest.mark.asyncio
async def test_existing_waiting_run_receives_v2_summary_once_without_replaying_event(monkeypatch):
    import autopilot.service as autopilot_service
    import workspace.service as workspace_service
    import zalo_worker

    run, task = _run("retrieve_audience", {
        "attrs": [{
            "_id": "INT001",
            "fullLabel": "Tea (nonalcoholic beverage)",
            "sizeMin": 2_530_000,
            "sizeMax": 3_560_000,
            "reason": "Phù hợp trực tiếp với sản phẩm.",
        }],
        "size": 3_045_000,
    })
    event = {
        "event_id": "evt-already-delivered",
        "type": "task_waiting_review",
        "payload": {"task_id": task["task_id"]},
    }
    subscription = {
        "_id": "subscription-1",
        "run_id": run["run_id"],
        "thread_id": "thread-1",
        "status": "active",
        "delivered_event_ids": [event["event_id"]],
    }
    thread = {
        "_id": "thread-1",
        "thread_id": "thread-1",
        "external_uid": "zalo-user-1",
        "active_campaign_conversation_id": "conversation-1",
    }

    class FakeCollection:
        def __init__(self, document=None):
            self.document = document
            self.updates = []

        async def find_one(self, *_args, **_kwargs):
            return self.document

        async def update_one(self, query, update):
            self.updates.append((query, update))

    subscriptions = FakeCollection(subscription)
    collections = {
        "subscriptions": subscriptions,
        "threads": FakeCollection(thread),
    }
    enqueue = AsyncMock()
    monkeypatch.setattr(zalo_worker, "_collections", AsyncMock(return_value=collections))
    monkeypatch.setattr(zalo_worker, "enqueue_text", enqueue)
    monkeypatch.setattr(autopilot_service, "get_run", AsyncMock(return_value=run))
    monkeypatch.setattr(autopilot_service, "list_events", AsyncMock(return_value=[event]))
    monkeypatch.setattr(workspace_service, "get_workspace", AsyncMock(return_value=_workspace()))

    assert await zalo_worker._process_progress_once() is True

    enqueue.assert_awaited_once()
    kwargs = enqueue.await_args.kwargs
    assert "Tea (nonalcoholic beverage)" in kwargs["text"]
    assert kwargs["idempotency_key"] == (
        "run-review-summary:openai-review-v2:run-review:retrieve_audience"
    )
    update = subscriptions.updates[-1][1]["$set"]
    assert update["review_summary_markers"] == [
        "openai-review-v2:run-review:retrieve_audience"
    ]
    assert "delivered_event_ids" not in update
