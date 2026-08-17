import pytest
import time

from models import AgentResponse
from quality.feedback import record_feedback
from quality.models import FeedbackRequest


@pytest.mark.asyncio
async def test_feedback_is_idempotent_redacted_and_does_not_touch_workspace():
    from identity import bootstrap_anonymous, create_conversation
    from quality import store
    from workspace.service import get_workspace

    identity = await bootstrap_anonymous()
    conversation = await create_conversation(identity["identity_id"])
    session_id = conversation["session_id"]
    before = await get_workspace(session_id)
    body = FeedbackRequest(
        submission_id="feedback-test-001",
        session_id=session_id,
        sentiment="negative",
        reason_codes=["wrong_recommendation"],
        comment="Call me at 0912345678",
        surface="guided_result",
        workspace_revision=before["revision"],
    )
    actor = {
        "user_id": None,
        "anonymous_id": identity["identity_id"],
        "account_session_id": None,
    }

    first, created = await record_feedback(
        body,
        actor=actor,
        conversation=conversation,
        run=None,
        workspace_revision=before["revision"],
    )
    replay, replay_created = await record_feedback(
        body,
        actor=actor,
        conversation=conversation,
        run=None,
        workspace_revision=before["revision"],
    )
    from quality.events import drain_session_quality_tasks
    await drain_session_quality_tasks(session_id)
    after = await get_workspace(session_id)

    assert created is True
    assert replay_created is False
    assert replay["_id"] == first["_id"]
    assert "0912345678" not in first["comment_redacted"]
    assert first["owner"]["owner_ref"] != identity["identity_id"]
    assert after["revision"] == before["revision"]
    assert len(store._mem_feedback) == 1


@pytest.mark.asyncio
async def test_run_feedback_uses_manifest_locked_when_run_was_created():
    from identity import bootstrap_anonymous, create_conversation

    identity = await bootstrap_anonymous()
    conversation = await create_conversation(identity["identity_id"])
    locked_manifest = {
        "quality_schema_version": "quality-v1",
        "agent_build_version": "older-build",
        "guard_policy_version": "older-guard",
    }
    body = FeedbackRequest(
        submission_id="feedback-locked-manifest",
        session_id=conversation["session_id"],
        target_kind="run",
        run_id="run_locked_manifest",
        sentiment="positive",
        surface="autopilot_summary",
    )
    stored, _ = await record_feedback(
        body,
        actor={
            "user_id": None,
            "anonymous_id": identity["identity_id"],
            "account_session_id": None,
        },
        conversation=conversation,
        run={
            "run_id": "run_locked_manifest",
            "quality_version_manifest": locked_manifest,
        },
        workspace_revision=0,
    )
    from quality.events import drain_session_quality_tasks
    await drain_session_quality_tasks(conversation["session_id"])

    assert stored["version_manifest"] == locked_manifest


@pytest.mark.asyncio
async def test_feedback_idempotency_is_scoped_to_owner():
    from identity import bootstrap_anonymous, create_conversation
    from quality.events import drain_session_quality_tasks

    first_identity = await bootstrap_anonymous()
    second_identity = await bootstrap_anonymous()
    first_conversation = await create_conversation(first_identity["identity_id"])
    second_conversation = await create_conversation(second_identity["identity_id"])

    async def submit(identity, conversation):
        body = FeedbackRequest(
            submission_id="shared-client-submission-id",
            session_id=conversation["session_id"],
            sentiment="positive",
            surface="guided_result",
        )
        stored, created = await record_feedback(
            body,
            actor={
                "user_id": None,
                "anonymous_id": identity["identity_id"],
                "account_session_id": None,
            },
            conversation=conversation,
            run=None,
            workspace_revision=0,
        )
        await drain_session_quality_tasks(conversation["session_id"])
        return stored, created

    first, first_created = await submit(first_identity, first_conversation)
    second, second_created = await submit(second_identity, second_conversation)

    assert first_created is True
    assert second_created is True
    assert first["_id"] != second["_id"]


def test_negative_feedback_requires_reason_or_comment():
    with pytest.raises(ValueError):
        FeedbackRequest(
            submission_id="feedback-test-002",
            session_id="sess_test",
            sentiment="negative",
            surface="guided_result",
        )


def test_run_feedback_requires_run_id():
    with pytest.raises(ValueError):
        FeedbackRequest(
            submission_id="feedback-test-003",
            session_id="sess_test",
            target_kind="run",
            sentiment="positive",
            surface="autopilot_summary",
        )


def test_feedback_surface_must_match_target_kind():
    with pytest.raises(ValueError, match="guided_result"):
        FeedbackRequest(
            submission_id="feedback-test-004",
            session_id="sess_test",
            sentiment="positive",
            surface="autopilot_summary",
        )
    with pytest.raises(ValueError, match="autopilot_summary"):
        FeedbackRequest(
            submission_id="feedback-test-005",
            session_id="sess_test",
            target_kind="run",
            run_id="run_test",
            sentiment="positive",
            surface="guided_result",
        )


@pytest.mark.asyncio
async def test_interaction_capture_timeout_cannot_stall_chat(monkeypatch):
    import asyncio
    from quality import events

    async def slow_capture(**_kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(events, "_record_chat_interaction", slow_capture)
    monkeypatch.setattr(events.config, "QUALITY_EVENT_TIMEOUT_MS", 5)
    started = time.perf_counter()
    result = await events.record_chat_interaction(
        session_id="quality-timeout-session",
        step=0,
        response=AgentResponse(text="ok"),
        started_at=time.time(),
        workspace_revision_before=0,
        guard_summary=None,
    )

    assert result is None
    assert time.perf_counter() - started < 0.25


@pytest.mark.asyncio
async def test_feedback_fails_when_durable_store_is_unavailable(monkeypatch):
    from quality import store

    async def no_collections():
        return None, None, None

    monkeypatch.setattr(store, "_collections", no_collections)
    monkeypatch.setattr(
        store.config, "QUALITY_FEEDBACK_ALLOW_MEMORY_FALLBACK", False
    )
    with pytest.raises(RuntimeError, match="durable feedback storage"):
        await store.insert_feedback({
            "submission_id": "feedback-no-durable-store",
        })
