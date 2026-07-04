"""Structured-output schemas for the agentic loop (Phase 1).

⛔ The planner may ONLY use the four whitelisted tools below. Schema validation
rejects anything else — an LLM-invented tool name can never execute.
"""
from typing import Literal

from pydantic import BaseModel, Field

ExecutorTool = Literal["recommend_audience", "rank_zones", "match_creatives", "draft_order"]


class PlanTask(BaseModel):
    id: str                                   # "audience", "zones", "creative_check", "order_draft"
    goal: str                                 # Vietnamese, shown to the user
    tool: ExecutorTool
    inputs: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    tasks: list[PlanTask] = Field(min_length=1, max_length=8)
    rationale: str = ""

    def execution_order(self) -> list[PlanTask]:
        """Topological order; raises ValueError on cycles/unknown deps."""
        by_id = {t.id: t for t in self.tasks}
        done: list[str] = []
        remaining = dict(by_id)
        while remaining:
            progressed = False
            for tid, task in list(remaining.items()):
                unknown = [d for d in task.depends_on if d not in by_id]
                if unknown:
                    raise ValueError(f"task {tid} depends on unknown task(s): {unknown}")
                if all(d in done for d in task.depends_on):
                    done.append(tid)
                    del remaining[tid]
                    progressed = True
            if not progressed:
                raise ValueError(f"dependency cycle among: {list(remaining)}")
        return [by_id[t] for t in done]


class CriterionScore(BaseModel):
    criterion: str
    score: int = Field(ge=1, le=5)
    justification: str = ""


class Critique(BaseModel):
    scores: list[CriterionScore]
    feedback_for_retry: str | None = None     # concrete + actionable, Vietnamese

    @property
    def mean(self) -> float:
        return sum(s.score for s in self.scores) / max(len(self.scores), 1)

    @property
    def passed(self) -> bool:
        # Threshold from judge calibration (07-eval-framework §4). Do not tune ad hoc.
        return bool(self.scores) and all(s.score >= 3 for s in self.scores) and self.mean >= 3.5


# ── JSON Schemas (for response_format / function-call strategies) ────────────
def to_json_schema(model: type[BaseModel], name: str) -> dict:
    """Pydantic model → strict json_schema block for response_format."""
    schema = model.model_json_schema()
    return {"name": name, "strict": True, "schema": schema}
