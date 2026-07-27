from unittest.mock import AsyncMock

import pytest

from campaign_models import GREENNODE_MINIMAX, OPENAI_GPT_5_4_MINI
from openai_campaign.zalo_review import render_openai_review_message
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
            "creative": {"value": {"files": [{"name": "mixi-banner.png"}]}},
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


def test_openai_audience_review_lists_exact_pending_segments_and_reasons():
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
    assert "Phù hợp trực tiếp với sản phẩm." in text
    assert "Xác nhận” để duyệt toàn bộ danh sách" in text
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
            "id": "ZONE-1",
            "name": "Masthead",
            "channel": "BaoMoi",
            "cpm": 42_000,
            "reach": 2_500_000,
        }],
    })

    text = _progress_message(run, _event(task), workspace=_workspace())

    assert "Masthead" in text
    assert "CPM 42.000đ" in text
    assert "reach 2,5 triệu" in text
    assert "ước tính" in text
    assert "mở workspace để thay đổi placement" in text


def test_openai_assignment_review_resolves_zone_and_creative_names():
    run, task = _run("assign_creatives", {
        "assignments": {"ZONE-1": 0},
        "warnings": [],
    })

    text = _progress_message(run, _event(task), workspace=_workspace())

    assert "Masthead → mixi-banner.png" in text
    assert "Xác nhận” để duyệt mapping" in text


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
    assert "Xác nhận” để duyệt toàn bộ danh sách" in text
    assert "https://example.test/workspace" in text


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
