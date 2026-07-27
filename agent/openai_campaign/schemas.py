"""Structured semantic contracts for the OpenAI campaign engine."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TurnType = Literal["faq", "workflow_action", "mixed", "clarification"]
FAQScope = Literal[
    "static_knowledge", "catalog_discovery", "live_system", "none"
]
WorkflowAction = Literal[
    "approve",
    "reject",
    "defer",
    "update_brief",
    "select_audience",
    "rerun_audience",
    "generate_creative",
    "select_zone",
    "launch",
    "other",
    "none",
]


class TurnSubrequest(BaseModel):
    kind: Literal["question", "read", "mutation"]
    description: str = Field(min_length=1, max_length=500)
    requires_live_data: bool = False
    requested_capability: str = Field(default="", max_length=100)


class TurnEntity(BaseModel):
    type: Literal[
        "audience", "zone", "date_range", "campaign", "creative", "other"
    ]
    value: str = Field(default="", max_length=500)
    resolved_id: str = Field(default="", max_length=200)


class TurnDecision(BaseModel):
    turn_type: TurnType
    user_goal: str = Field(min_length=1, max_length=800)
    subrequests: list[TurnSubrequest] = Field(default_factory=list, max_length=8)
    faq_scope: FAQScope = "none"
    workflow_action: WorkflowAction = "none"
    entities: list[TurnEntity] = Field(default_factory=list, max_length=20)
    would_mutate_workspace: bool = False
    needs_clarification: bool = False
    clarification_question: str = Field(default="", max_length=500)
    confidence: float = Field(ge=0, le=1)


    def requires_clarification(self, threshold: float = 0.65) -> bool:
        return bool(
            self.turn_type == "clarification"
            or self.needs_clarification
            or self.confidence < threshold
        )
