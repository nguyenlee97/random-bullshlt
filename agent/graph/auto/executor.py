"""
Executor node — runs one plan task via EXISTING deterministic/tool code.
⛔ No new LLM prompts here except what the reused handlers already do.
"""
from graph.state import AgentState
from session import get_or_create_session
from agent_logger import alog


async def _recommend_audience(state: AgentState, feedback: str | None) -> dict:
    from handlers.audience import handle_dmp_recommend
    result = await handle_dmp_recommend(state["session_id"])
    recs = result.get("recommendations", [])
    if feedback:  # critic retry: drop segments the critic flagged by label match
        bad = [w.strip().lower() for w in feedback.split(";") if w.strip()]
        recs = [r for r in recs
                if not any(b in (r.get("fullLabel") or "").lower() for b in bad)] or recs
    return {"recommendations": recs}


async def _rank_zones(state: AgentState, feedback: str | None) -> dict:
    from tools.placement_relevance import build_placement_context
    from tools.zone_ranker import rank_zones
    from tools.order_api import fetch_zone_conflicts
    session = await get_or_create_session(state["session_id"])
    brief = session.get("form_state", {}).get("brief", {})
    creative = session.get("form_state", {}).get("creative", {})
    segment = session.get("form_state", {}).get("segment", {})
    ranked = await rank_zones(
        objective=brief.get("objective", "awareness"),
        budget=brief.get("budget", 0), kpi=brief.get("kpi", ""),
        creative_files=creative.get("files", []),
        placement_context=build_placement_context(brief, segment),
        limit=12)
    conflicts = await fetch_zone_conflicts(brief.get("startDate", ""), brief.get("endDate", ""))
    available = [z for z in ranked if not conflicts.get(z["id"])]
    return {"zones": available[:6], "conflicts_skipped": len(ranked) - len(available)}


async def _match_creatives(state: AgentState, feedback: str | None) -> dict:
    from tools.creative_match import auto_assign
    from tools.zone_catalog import get_zone_map
    session = await get_or_create_session(state["session_id"])
    files = session.get("form_state", {}).get("creative", {}).get("files", [])
    zones_result = state.get("task_results", {}).get("zones") or {}
    zone_ids = [z["id"] for z in zones_result.get("zones", [])]
    if not files or not zone_ids:
        return {"assignments": {}, "skipped": "no creative files or zones yet"}
    zone_map = await get_zone_map()
    selected = [zone_map[z] for z in zone_ids if z in zone_map]
    return auto_assign(selected, files)


async def _draft_order(state: AgentState, feedback: str | None) -> dict:
    """Build the order payload + order_guard DRY RUN. Never creates. ⛔"""
    from validation.order_guard import OrderValidationError, guard_order
    session = await get_or_create_session(state["session_id"])
    brief = session.get("form_state", {}).get("brief", {})
    results = state.get("task_results", {})
    zone_ids = [z["id"] for z in (results.get("zones") or {}).get("zones", [])]
    dmp_include = [r.get("_id") for r in (results.get("audience") or {}).get("recommendations", [])
                   if r.get("_id")]

    payload = {
        "brand": brief.get("brand", ""), "objective": brief.get("objective", "awareness"),
        "budget": brief.get("budget", 0) * 1_000_000,
        "startDate": brief.get("startDate", ""), "endDate": brief.get("endDate", ""),
        "placements": zone_ids,
        "dmp": {"include": dmp_include, "exclude": []},
        "creatives": [],
    }
    try:
        await guard_order(payload, session)
        return {"payload": payload, "guard": "pass"}
    except OrderValidationError as e:
        return {"payload": payload, "guard": "fail", "reasons": e.reasons}


_EXECUTORS = {
    "recommend_audience": _recommend_audience,
    "rank_zones": _rank_zones,
    "match_creatives": _match_creatives,
    "draft_order": _draft_order,
}


async def executor_node(state: AgentState) -> dict:
    plan = state["plan"]
    tasks = plan.execution_order()
    task = tasks[state["current_task_idx"]]
    feedback = None
    if state.get("critique") and not state["critique"].passed:
        feedback = state["critique"].feedback_for_retry

    await alog(state["session_id"], "info", {
        "node": "executor", "task": task.id, "tool": task.tool,
        "retry": state.get("retry_counts", {}).get(task.id, 0)})
    try:
        result = await _EXECUTORS[task.tool](state, feedback)
    except Exception as e:
        result = {"error": str(e)[:200]}

    task_results = dict(state.get("task_results", {}))
    task_results[task.id] = result
    return {"task_results": task_results, "critique": None}
