"""Owned, idempotent user feedback command."""

from __future__ import annotations

from copy import deepcopy
import hashlib

from config import config
from metrics import FEEDBACK, FEEDBACK_REASONS, FEEDBACK_WRITES
from quality.events import enqueue_quality_event
from quality.models import FeedbackRequest
from quality.store import expires, insert_feedback, now
from quality.versioning import get_version_manifest
from request_context import get_request_id
from security import redact_pii


def _owner(actor: dict) -> dict:
    kind = "account" if actor.get("user_id") else "anonymous"
    value = actor.get("user_id") or actor.get("anonymous_id") or "legacy"
    digest = hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()
    return {"kind": kind, "owner_ref": digest}


async def record_feedback(
    body: FeedbackRequest,
    *,
    actor: dict,
    conversation: dict | None,
    run: dict | None,
    workspace_revision: int | None,
) -> tuple[dict, bool]:
    safe_text = redact_pii({
        "comment": body.comment,
        "expected_behavior": body.expected_behavior,
    })
    conversation_id = (conversation or {}).get("conversation_id")
    approval_policy = (run or {}).get("approval_policy")
    model = (run or {}).get("model")
    conversation_model = (run or {}).get("conversation_model")
    engine = (
        "openai" if str(conversation_model or "").startswith("openai")
        else "greennode" if conversation_model
        else None
    )
    version_manifest = deepcopy((run or {}).get("quality_version_manifest"))
    if not version_manifest:
        version_manifest = get_version_manifest(
            model=model, engine=engine, approval_policy=approval_policy
        )
    doc = {
        "schema_version": "feedback-v1",
        "submission_id": body.submission_id,
        "target": {
            "kind": body.target_kind,
            "conversation_id": conversation_id,
            "session_id": body.session_id,
            "run_id": body.run_id,
            "task_id": body.task_id,
            "request_id": body.request_id,
        },
        "owner": _owner(actor),
        "sentiment": body.sentiment.value,
        "reason_codes": [value.value for value in body.reason_codes],
        "comment_redacted": safe_text["comment"],
        "expected_behavior_redacted": safe_text["expected_behavior"],
        "surface": body.surface,
        "step": body.step,
        "workspace_revision": workspace_revision,
        "version_manifest": version_manifest,
        "status": "recorded",
        "supersedes_id": body.supersedes_id,
        "created_at": now(),
        "expires_at": expires(config.QUALITY_FEEDBACK_RETENTION_DAYS),
    }
    stored, created = await insert_feedback(doc)
    if created:
        FEEDBACK.labels(sentiment=body.sentiment.value, surface=body.surface).inc()
        for reason in body.reason_codes:
            FEEDBACK_REASONS.labels(
                reason_code=reason.value, surface=body.surface
            ).inc()
        FEEDBACK_WRITES.labels(outcome="ok").inc()
        enqueue_quality_event(
            "feedback_recorded",
            session_id=body.session_id,
            conversation_id=conversation_id,
            run_id=body.run_id,
            surface=body.surface,
            payload={
                "feedback_id": stored["_id"],
                "sentiment": body.sentiment.value,
                "reason_codes": [value.value for value in body.reason_codes],
            },
            approval_policy=approval_policy,
        )
    return stored, created
