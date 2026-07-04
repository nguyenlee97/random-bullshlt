"""
Critic node — LLM-as-judge over one task result.
⛔ Different model family+provider than the generator (CRITIC_MODEL=gpt-5.4-mini
@ OpenAI, per catalog probe + ADR). Single sample (cost); rubric thresholds come
from judge calibration (07 §4) — pass = all ≥3 AND mean ≥3.5 (Critique.passed).
"""
import json

from graph.state import AgentState
from graph.schemas import Critique
from graph.structured import StructuredOutputError, structured
from session import get_or_create_session
from agent_logger import alog

_RUBRICS = {
    "recommend_audience": """Chấm các tiêu chí (1-5):
1. brief_fit: segments có đúng brand/objective/ghi chú audience không?
2. size_sanity: tổng size có hợp lý so với KPI reach không?
3. no_contradiction: có segment nào mâu thuẫn rõ với ghi chú brief không? (có → 1)
feedback_for_retry: nếu FAIL, liệt kê các fullLabel cần loại, cách nhau dấu chấm phẩy.""",
    "rank_zones": """Chấm các tiêu chí (1-5):
1. objective_alignment: zones có hợp objective không (vd conversion cần CTR cao)?
2. budget_feasibility: tổng CPM×reach ước tính có khớp ngân sách không?
3. format_coverage: các format zone có đa dạng/hợp lý không?
feedback_for_retry: nếu FAIL, nêu zone ID cần loại và lý do, ngắn gọn.""",
    "match_creatives": """Chấm các tiêu chí (1-5):
1. assignment_valid: mỗi zone được gán creative có kích thước phù hợp không?
2. coverage: có zone nào bị bỏ trống không đáng không?
feedback_for_retry: nếu FAIL, nêu cặp zone↔creative sai.""",
    "draft_order": """Chấm các tiêu chí (1-5):
1. guard_pass: guard="pass" → 5, guard="fail" → 1.
2. consistency: budget/dates/placements khớp brief không?
feedback_for_retry: nếu FAIL, tóm tắt reasons.""",
}

_PROMPT = """Bạn là giám khảo khó tính đánh giá output của agent quảng cáo.
{rubric}

Brief: {brief}
Task: {task_id} ({tool})
Output cần chấm: {result}

Trả về scores (đúng tên tiêu chí trong rubric) và feedback_for_retry (null nếu đạt)."""


async def critic_node(state: AgentState) -> dict:
    plan = state["plan"]
    task = plan.execution_order()[state["current_task_idx"]]
    result = state["task_results"].get(task.id, {})
    session = await get_or_create_session(state["session_id"])
    brief = session.get("form_state", {}).get("brief", {})

    # Budget check before spending on the critic
    if state.get("tokens_spent", 0) >= state.get("token_budget", 10**9):
        crit = Critique(scores=[], feedback_for_retry=None)  # empty = not passed
        return {"critique": crit}

    prompt = _PROMPT.format(
        rubric=_RUBRICS.get(task.tool, _RUBRICS["draft_order"]),
        brief=json.dumps(brief, ensure_ascii=False),
        task_id=task.id, tool=task.tool,
        result=json.dumps(result, ensure_ascii=False)[:4000],
    )
    try:
        critique, tokens = structured(
            [{"role": "user", "content": prompt}], Critique, "critique",
            role="critic", max_tokens=800)
    except StructuredOutputError as e:
        # Critic unavailable → fail-open with a WARN (don't block the pipeline
        # on the judge; the human confirm gate still stands ⛔)
        await alog(state["session_id"], "warn", {"node": "critic", "fail_open": str(e)[:150]})
        from graph.schemas import CriterionScore
        critique = Critique(scores=[CriterionScore(
            criterion="critic_unavailable", score=3, justification="fail-open")])
        tokens = 0

    await alog(state["session_id"], "info", {
        "node": "critic", "task": task.id, "passed": critique.passed,
        "mean": round(critique.mean, 2)})
    return {"critique": critique,
            "tokens_spent": state.get("tokens_spent", 0) + tokens}
