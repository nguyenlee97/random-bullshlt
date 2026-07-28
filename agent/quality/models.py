"""Typed contracts for quality events and user feedback."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FeedbackSentiment(str, Enum):
    positive = "positive"
    negative = "negative"


class FeedbackReason(str, Enum):
    wrong_recommendation = "wrong_recommendation"
    missing_context = "missing_context"
    did_not_follow_request = "did_not_follow_request"
    incorrect_facts = "incorrect_facts"
    unsafe_or_inappropriate = "unsafe_or_inappropriate"
    too_slow = "too_slow"
    too_many_steps = "too_many_steps"
    unclear_explanation = "unclear_explanation"
    review_or_approval_problem = "review_or_approval_problem"
    tool_or_system_error = "tool_or_system_error"
    other = "other"


class FeedbackRequest(BaseModel):
    submission_id: str = Field(
        min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    session_id: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    target_kind: Literal["conversation", "run"] = "conversation"
    run_id: str | None = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    task_id: str | None = Field(
        default=None, max_length=256, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    request_id: str | None = Field(
        default=None, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    sentiment: FeedbackSentiment
    reason_codes: list[FeedbackReason] = Field(default_factory=list, max_length=5)
    comment: str = Field(default="", max_length=2000)
    expected_behavior: str = Field(default="", max_length=2000)
    surface: Literal["guided_result", "autopilot_summary"]
    step: int = Field(default=4, ge=-1, le=6)
    workspace_revision: int | None = Field(default=None, ge=0)
    supersedes_id: str | None = Field(
        default=None, max_length=64, pattern=r"^afb_[A-Za-z0-9]+$"
    )

    @model_validator(mode="after")
    def validate_target_and_reason(self):
        if self.target_kind == "run" and not self.run_id:
            raise ValueError("run_id is required for run feedback")
        if self.target_kind == "conversation" and self.run_id:
            raise ValueError("run_id is allowed only for run feedback")
        if self.target_kind == "conversation" and self.task_id:
            raise ValueError("task_id is allowed only for run feedback")
        if (
            self.target_kind == "conversation"
            and self.surface != "guided_result"
        ):
            raise ValueError("conversation feedback requires guided_result")
        if self.target_kind == "run" and self.surface != "autopilot_summary":
            raise ValueError("run feedback requires autopilot_summary")
        if (
            self.sentiment == FeedbackSentiment.negative
            and not self.reason_codes
            and not self.comment.strip()
        ):
            raise ValueError("negative feedback requires a reason or comment")
        self.comment = self.comment.strip()
        self.expected_behavior = self.expected_behavior.strip()
        return self


class FeedbackResponse(BaseModel):
    feedback_id: str
    status: Literal["recorded"] = "recorded"
    request_id: str


QUALITY_EVENT_TYPES = {
    "guard_decision",
    "interaction_completed",
    "fallback_used",
    "review_requested",
    "review_decided",
    "feedback_recorded",
    "outcome_observed",
    "dataset_candidate_created",
    "adjudication_recorded",
}
