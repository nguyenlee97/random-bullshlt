"""
Graph assembly — the chat graph (strangler replacement for freeform.py's pipeline).

    entry → intercepts ─(hit)──────────────────────────► respond → END
               │(miss)
               ▼
            context → agent ◄──────────┐
                        │              │ (tool results appended, ≤ MAX_TOOL_ROUNDS)
                        ├─ tool_calls → tools ──┘   (update_workspace → respond directly)
                        ├─ text       → respond
                        └─ empty      → fallback → respond

Checkpointer: pass one in for multi-turn graph state (langgraph-checkpoint-mongodb,
thread_id = session_id). The chat graph works stateless too — history still lives
in session.py during the strangler phase.
"""
from langgraph.graph import END, StateGraph

from graph.state import MAX_TOOL_ROUNDS, AgentState
from graph.nodes.intercepts import intercepts_node
from graph.nodes.workspace_intent import workspace_intent_node
from graph.nodes.agent_node import (
    agent_node,
    context_node,
    fallback_node,
    respond_node,
    tools_node,
)


def _route_after_intercepts(state: AgentState) -> str:
    return "respond" if state.get("response_text") else "workspace_intent"


def _route_after_workspace_intent(state: AgentState) -> str:
    return "respond" if state.get("response_text") else "context"


def _route_after_agent(state: AgentState) -> str:
    msgs = state.get("messages") or []
    if msgs and msgs[-1].get("role") == "assistant" and msgs[-1].get("tool_calls"):
        if state.get("tool_rounds", 0) >= MAX_TOOL_ROUNDS:
            return "fallback"           # runaway tool loop → deterministic exit
        return "tools"
    if state.get("response_text"):
        return "respond"
    return "fallback"                   # empty reply → attempt 2/3


def _route_after_tools(state: AgentState) -> str:
    # update_workspace proposal flow already produced a response
    return "respond" if state.get("response_text") else "agent"


def build_chat_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("intercepts", intercepts_node)
    g.add_node("workspace_intent", workspace_intent_node)
    g.add_node("context", context_node)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.add_node("fallback", fallback_node)
    g.add_node("respond", respond_node)

    g.set_entry_point("intercepts")
    g.add_conditional_edges("intercepts", _route_after_intercepts,
                            {"respond": "respond", "workspace_intent": "workspace_intent"})
    g.add_conditional_edges("workspace_intent", _route_after_workspace_intent,
                            {"respond": "respond", "context": "context"})
    g.add_edge("context", "agent")
    g.add_conditional_edges("agent", _route_after_agent,
                            {"tools": "tools", "respond": "respond", "fallback": "fallback"})
    g.add_conditional_edges("tools", _route_after_tools,
                            {"respond": "respond", "agent": "agent"})
    g.add_edge("fallback", "respond")
    g.add_edge("respond", END)

    return g.compile(checkpointer=checkpointer)


def build_auto_graph(checkpointer=None):
    """Auto mode: planner → (executor → critic → advance)* → assemble.
    ⛔ Ends at a human-review summary; order creation stays behind the existing
    UI confirm → order_guard + idempotency path (ADR 017)."""
    from graph.auto.planner import planner_node
    from graph.auto.executor import executor_node
    from graph.auto.critic import critic_node
    from graph.auto.subgraph import advance_node, assemble_node, route_after_advance

    g = StateGraph(AgentState)
    g.add_node("planner", planner_node)
    g.add_node("executor", executor_node)
    g.add_node("critic", critic_node)
    g.add_node("advance", advance_node)
    g.add_node("assemble", assemble_node)

    g.set_entry_point("planner")
    # planner error path: response_text already set → skip straight to end
    g.add_conditional_edges(
        "planner",
        lambda s: "assemble_skip" if s.get("response_text") else "executor",
        {"assemble_skip": END, "executor": "executor"})
    g.add_edge("executor", "critic")
    g.add_edge("critic", "advance")
    g.add_conditional_edges("advance", route_after_advance,
                            {"executor": "executor", "assemble": "assemble"})
    g.add_edge("assemble", END)
    return g.compile(checkpointer=checkpointer)
