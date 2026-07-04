"""
Auto-mode flow control + final assembly.

    planner → executor → critic → advance ─┬→ executor   (next task / retry)
                                           └→ assemble   (all tasks done)

Bounds ⛔: retries ≤ MAX_TASK_RETRIES per task; token budget checked in critic
and agent nodes; a task that still fails after retries is marked DEGRADED and
surfaced to the user — never silently dropped.
"""
from graph.state import MAX_TASK_RETRIES, AgentState
from session import add_message
from agent_logger import alog


async def advance_node(state: AgentState) -> dict:
    """Decide retry vs next task; executed after every critic verdict."""
    plan = state["plan"]
    tasks = plan.execution_order()
    idx = state["current_task_idx"]
    task = tasks[idx]
    critique = state.get("critique")
    retries = dict(state.get("retry_counts", {}))
    task_results = dict(state.get("task_results", {}))

    if critique and not critique.passed:
        if retries.get(task.id, 0) < MAX_TASK_RETRIES:
            retries[task.id] = retries.get(task.id, 0) + 1
            await alog(state["session_id"], "info", {
                "node": "advance", "task": task.id, "action": "retry",
                "attempt": retries[task.id]})
            return {"retry_counts": retries}          # idx unchanged → re-execute
        task_results[task.id] = {**task_results.get(task.id, {}), "degraded": True}
        await alog(state["session_id"], "warn", {
            "node": "advance", "task": task.id, "action": "degraded"})

    return {"current_task_idx": idx + 1, "task_results": task_results,
            "critique": None, "retry_counts": retries}


def route_after_advance(state: AgentState) -> str:
    plan = state["plan"]
    if state.get("critique") and not state["critique"].passed:
        return "executor"                              # retry same task
    if state["current_task_idx"] >= len(plan.execution_order()):
        return "assemble"
    return "executor"


async def assemble_node(state: AgentState) -> dict:
    """Human-readable summary + proposal. ⛔ STOPS here — order creation only
    via the existing UI confirm → handle_setup phase 2 → guard + idempotency."""
    results = state.get("task_results", {})
    lines = ["🤖 **Auto-setup hoàn tất!** Kết quả từng bước:\n"]
    blocks: list[dict] = []

    aud = next((v for k, v in results.items() if "recommendations" in (v or {})), None)
    if aud:
        recs = aud["recommendations"][:8]
        deg = " ⚠️(cần review)" if aud.get("degraded") else ""
        lines.append(f"**1. Audience{deg}** — {len(recs)} segments đề xuất")
        blocks.append({"type": "table", "title": "🎯 Audience đề xuất",
                       "columns": ["Segment", "Size", "Lý do"],
                       "rows": [[r.get("fullLabel", "?"),
                                 f"{r.get('sizeMin', 0):,}–{r.get('sizeMax', 0):,}",
                                 (r.get("reason") or "")[:80]] for r in recs]})

    zones = next((v for k, v in results.items() if "zones" in (v or {})), None)
    if zones:
        zs = zones["zones"]
        deg = " ⚠️(cần review)" if zones.get("degraded") else ""
        lines.append(f"**2. Zones{deg}** — {len(zs)} zones khả dụng"
                     + (f" ({zones.get('conflicts_skipped', 0)} bị trùng lịch, đã loại)"
                        if zones.get("conflicts_skipped") else ""))
        blocks.append({"type": "table", "title": "📍 Zones đề xuất",
                       "columns": ["Zone", "Reach", "CTR", "CPM"],
                       "rows": [[z["id"], f"{z.get('reach', 0):,}",
                                 f"{z.get('ctr', 0)}%", f"{z.get('cpm', 0):,}đ"] for z in zs]})

    draft = next((v for k, v in results.items() if "guard" in (v or {})), None)
    if draft:
        if draft["guard"] == "pass":
            lines.append("**3. Order draft** — ✅ hợp lệ (đã qua kiểm tra server-side)")
        else:
            lines.append("**3. Order draft** — ⚠️ chưa hợp lệ:\n"
                         + "\n".join(f"   - {r}" for r in draft.get("reasons", [])[:4]))

    lines.append("\n👉 Anh/Chị review ở panel phải, chỉnh nếu cần, và **xác nhận từng"
                 " bước** — em không tự tạo chiến dịch khi chưa được duyệt.")
    text = "\n".join(lines)

    await add_message(state["session_id"], "user", state["user_message"])
    await add_message(state["session_id"], "assistant", text)
    return {"response_text": text, "response_blocks": blocks, "used_tool": "auto_mode",
            "suggestions": [
                {"label": "✅ Áp dụng audience", "action": "send",
                 "text": "đồng ý, áp dụng các segments này"},
                {"label": "✏️ Chỉnh zones", "action": "prefill", "text": "Bỏ zone "},
            ]}
