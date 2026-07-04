"""Planner node — brief → Plan (structured output, ADR 005 strategy C)."""
from graph.state import AgentState
from graph.schemas import Plan
from graph.structured import StructuredOutputError, structured
from session import get_or_create_session
from agent_logger import alog

_PLANNER_PROMPT = """Bạn là planner của agent thiết lập chiến dịch quảng cáo.
Nhiệm vụ: lập kế hoạch task để setup toàn bộ chiến dịch từ brief dưới đây.

Tool được phép (CHỈ 4 tool này):
- recommend_audience: gợi ý DMP segments từ brief
- rank_zones: xếp hạng ad zones theo objective/budget
- match_creatives: gán creative files vào zones (chỉ khi đã có creative upload)
- draft_order: tổng hợp thành order draft (LUÔN là task cuối, depends_on các task trước)

Brief:
{brief}

Creative đã upload: {has_creative}

Lập plan ngắn gọn, đúng thứ tự phụ thuộc. Goal viết tiếng Việt, hiển thị cho user."""


async def planner_node(state: AgentState) -> dict:
    session = await get_or_create_session(state["session_id"])
    form_state = session.get("form_state", {})
    brief = (state.get("workspace") or {}).get("brief") or form_state.get("brief", {})
    creative = (state.get("workspace") or {}).get("creative") or form_state.get("creative", {})

    if not brief.get("brand"):
        return {"response_text": (
            "Để em tự động setup, anh/chị điền **Brief** trước đã nhé "
            "(brand, objective, budget, thời gian ở panel phải)!"),
            "used_tool": "auto_mode"}

    import json
    prompt = _PLANNER_PROMPT.format(
        brief=json.dumps(brief, ensure_ascii=False),
        has_creative="có" if creative.get("files") else "chưa",
    )
    try:
        plan, tokens = structured(
            [{"role": "user", "content": prompt}], Plan, "plan", role="generator")
        plan.execution_order()  # validate deps/cycles now, fail fast
    except (StructuredOutputError, ValueError) as e:
        await alog(state["session_id"], "error", {"node": "planner", "error": str(e)[:200]})
        return {"response_text": (
            "Em chưa lập được kế hoạch tự động cho brief này. "
            "Anh/Chị thử lại hoặc đi theo từng bước ở panel phải nhé!"),
            "used_tool": "auto_mode"}

    await alog(state["session_id"], "info", {
        "node": "planner", "tasks": [t.id for t in plan.execution_order()]})
    return {"plan": plan, "current_task_idx": 0,
            "tokens_spent": state.get("tokens_spent", 0) + tokens}
