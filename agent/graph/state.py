"""AgentState — the single state object flowing through the LangGraph graph.

Design rules (see docs/production-plan/02 §2):
- `workspace_snapshot` is rebuilt fresh every request and NEVER persisted into
  message history (stale-snapshot bug the old freeform.py already avoids).
- `form_state` is NOT here: it stays owned by session.py (single writer =
  deterministic handlers). The graph reads it via the snapshot only.
- Budget fields make cost overrun impossible by construction: nodes check
  `tokens_spent < token_budget` before every LLM call.
"""
from typing import Any, Literal, TypedDict

from graph.schemas import Critique, Plan


class AgentState(TypedDict, total=False):
    # ── request identity ────────────────────────────────────────────────────
    session_id: str
    request_id: str
    step: int
    user_message: str

    # ── context (rebuilt per request, never checkpointed into history) ──────
    workspace: dict                  # live workspace from frontend
    workspace_revision: int | None
    workspace_snapshot: str
    workspace_events: list[str]
    confirmed_steps: list[int]
    pending_proposal: dict | None
    auto_approve_brief: bool
    workspace_intent_checked: bool
    canonical_brief_missing: bool

    # ── llm conversation (graph-managed) ────────────────────────────────────
    messages: list[dict]             # OpenAI-format dicts (system/user/assistant/tool)
    tool_rounds: int                 # max 3 per turn (ported limit)

    # ── agentic auto-mode ───────────────────────────────────────────────────
    mode: Literal["chat", "auto"]
    plan: Plan | None
    current_task_idx: int
    task_results: dict[str, Any]
    critique: Critique | None
    retry_counts: dict[str, int]     # per task id, max 2 (MAX_TASK_RETRIES)

    # ── budgets (cost engineering) ──────────────────────────────────────────
    tokens_spent: int
    token_budget: int

    # ── output (assembled by respond node) ──────────────────────────────────
    response_text: str
    response_blocks: list[dict]
    response_meta: dict
    workspace_update: dict | None
    suggestions: list
    fallback_level: int              # 0 = none, 1/2/3 per the 3-level fallback
    used_tool: str


MAX_TOOL_ROUNDS = 3
MAX_TASK_RETRIES = 2
