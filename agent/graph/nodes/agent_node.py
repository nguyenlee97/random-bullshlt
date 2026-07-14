"""
Agent + tools + fallback nodes — the LLM heart of the chat graph.

Ports freeform.py's LLM pipeline 1:1:
  context_node   → build messages (snapshot fresh, diff, trimmed history)
  agent_node     → chat_completion with TOOL_DEFINITIONS (+ length-retry)
  tools_node     → execute tools (date-injection quirk preserved) + update_workspace proposal flow
  fallback path  → attempt-2 force_text, attempt-3 hardcoded (sets fallback_level)

Reuses freeform.py helpers (snapshot/diff/summary builders) — parity by import.
"""
import json
import time

from graph.state import MAX_TOOL_ROUNDS, AgentState
from handlers.freeform import (
    _WORKSPACE_SUGGESTIONS,
    _build_update_summary,
    _build_workspace_diff,
    _build_workspace_snapshot,
    _field_to_step_index,
    _is_confirm,
    _STEP_NAMES_VI,
)
from llm import chat_completion, force_text_completion, sanitize_response
from prompts.system import SYSTEM_PROMPT
from session import add_message, get_history, set_pending_proposal
from tools.registry import TOOL_DEFINITIONS, execute_tool
from agent_logger import alog
from workspace.service import approve_proposal, create_proposal, get_workspace, legacy_view

_TOOL_FALLBACKS = {
    "get_audience_list": "Đã tìm thấy các đối tượng phù hợp. Anh/Chị xem danh sách ở panel phải và chọn nhé!",
    "search_zones": "Đã tìm thấy các zone phù hợp. Anh/Chị xem danh sách ở panel phải và chọn nhé!",
    "update_workspace": "Workspace đã được cập nhật. Anh/Chị xem thông tin bên phải và xác nhận nhé!",
}


async def context_node(state: AgentState) -> dict:
    """Build the message array. Snapshot is fresh every request (never stored)."""
    client_workspace = state.get("workspace") or {}
    canonical = await get_workspace(state["session_id"])
    client_revision = state.get("workspace_revision")
    canonical_revision = canonical["revision"]
    stale_client = client_revision is not None and client_revision != canonical_revision
    workspace = legacy_view(canonical) if stale_client or not client_workspace else client_workspace
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": (
            f"WORKSPACE CANONICAL REVISION: {canonical_revision}. "
            f"Client revision: {client_revision if client_revision is not None else 'migration/unknown'}. "
            + ("Client snapshot is stale; canonical server artifacts are authoritative."
               if stale_client else "Client snapshot is current for this turn.")
        )},
        {"role": "system", "content": _build_workspace_snapshot(
            workspace, state.get("confirmed_steps") or [], current_step=state["step"])},
    ]
    diff = _build_workspace_diff(state.get("workspace_events") or [])
    if diff:
        messages.append({"role": "system", "content": diff})
    messages.extend(await get_history(state["session_id"]))  # CONTEXT_WINDOW-trimmed
    messages.append({"role": "user", "content": state["user_message"]})
    return {"messages": messages, "tool_rounds": 0, "fallback_level": 0,
            "workspace": workspace, "workspace_revision": canonical_revision}


async def agent_node(state: AgentState) -> dict:
    """One LLM call. Routing (build.py) decides: tools / respond / fallback."""
    session_id = state["session_id"]
    messages = state["messages"]

    if state.get("tokens_spent", 0) >= state.get("token_budget", 10**9):
        return {"response_text": (
            "Em đã dùng hết ngân sách xử lý cho lượt này. "
            "Anh/Chị gửi lại tin nhắn ngắn gọn hơn giúp em nhé!"),
            "used_tool": "budget_exceeded"}

    await alog(session_id, "llm_call_start", {"handler": "graph_agent", "messages_count": len(messages)})
    response = chat_completion(messages=messages, tools=TOOL_DEFINITIONS)
    msg = response.choices[0].message
    tokens = (response.usage.total_tokens or 0) if getattr(response, "usage", None) else 0

    # length-exhaustion retry (ported)
    if response.choices[0].finish_reason == "length" and not msg.tool_calls:
        await alog(session_id, "warn", {"event": "llm_length_truncated", "path": "graph"})
        short = [messages[0]] + messages[-6:]
        try:
            retry = force_text_completion(messages=short)
            text = sanitize_response(retry.choices[0].message.content or "") or (
                "Xin lỗi anh/chị, em bị quá tải ngữ cảnh ở tin nhắn này. "
                "Anh/chị có thể hỏi ngắn hơn hoặc bắt đầu lại không ạ?")
        except Exception:
            text = ("Xin lỗi anh/chị, em đang gặp giới hạn xử lý. "
                    "Anh/chị thử hỏi ngắn gọn hơn giúp em nhé!")
        return {"response_text": text, "used_tool": "freeform_chat",
                "tokens_spent": state.get("tokens_spent", 0) + tokens}

    if msg.tool_calls:
        # stash raw tool calls for tools_node via messages
        assistant_msg = {
            "role": "assistant",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        }
        return {"messages": messages + [assistant_msg],
                "tokens_spent": state.get("tokens_spent", 0) + tokens}

    text = sanitize_response(msg.content or "")
    return {"response_text": text,  # empty text → build.py routes to fallback
            "used_tool": "freeform_chat",
            "tokens_spent": state.get("tokens_spent", 0) + tokens}


async def tools_node(state: AgentState) -> dict:
    """Execute pending tool calls; update_workspace short-circuits to proposal flow."""
    session_id = state["session_id"]
    messages = state["messages"]
    tool_calls = messages[-1]["tool_calls"]
    used_tool = tool_calls[0]["function"]["name"]
    workspace = state.get("workspace") or {}

    # ── update_workspace: deterministic proposal flow, NO second LLM call ─────
    if used_tool == "update_workspace":
        first_args = json.loads(tool_calls[0]["function"]["arguments"])
        field = first_args.get("field", "")
        value = first_args.get("value")
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                pass
        reply = _build_update_summary(field, value, first_args.get("reason", ""))
        step_index = _field_to_step_index(field)
        is_locked = step_index in (state.get("confirmed_steps") or [])
        is_confirm = _is_confirm(state["user_message"].lower().strip())

        await add_message(session_id, "user", state["user_message"])
        await add_message(session_id, "assistant", reply)

        canonical = await get_workspace(session_id)
        proposal = await create_proposal(
            session_id,
            field,
            value,
            base_revision=canonical["revision"],
            actor="campaign_copilot",
            reason=first_args.get("reason", ""),
        )
        proposal_changes = {
            **first_args,
            "proposal_id": proposal["proposal_id"],
            "base_revision": proposal["base_revision"],
            "affected_artifacts": proposal["affected_artifacts"],
        }

        if is_confirm and not is_locked:
            mutation = await approve_proposal(
                proposal["proposal_id"], actor="campaign_operator"
            )
            return {"response_text": reply,
                    "response_blocks": [{"type": "info",
                        "text": f"Workspace đã được cập nhật: `{field}`."}],
                    "workspace_update": {"field": field, "value": value,
                                         "reason": first_args.get("reason", ""),
                                         "proposal_id": proposal["proposal_id"],
                                         "workspace_revision": mutation["workspace_revision"]},
                    "used_tool": "update_workspace"}

        warning = ""
        if is_locked and step_index >= 0:
            downstream = [_STEP_NAMES_VI[i] for i in range(step_index + 1, len(_STEP_NAMES_VI))]
            if downstream:
                warning = (f"⚠️ Bước {_STEP_NAMES_VI[step_index]} đã được xác nhận. Nếu thay đổi, "
                           f"các bước sau ({', '.join(downstream)}) sẽ bị reset.")
        await set_pending_proposal(session_id, proposal_changes)
        return {"response_text": reply,
                "response_blocks": [{"type": "workspace_proposal", "changes": proposal_changes,
                                     "is_locked": is_locked, "warning": warning,
                                     "affected_artifacts": proposal["affected_artifacts"]}],
                "suggestions": _WORKSPACE_SUGGESTIONS.get(field, []),
                "used_tool": "update_workspace"}

    # ── normal tools: execute all, append results, loop back to agent ─────────
    tool_results = []
    for tc in tool_calls:
        args = json.loads(tc["function"]["arguments"])
        name = tc["function"]["name"]
        # ported quirk: auto-inject brief dates into zone tools
        if name in ("get_zone_list", "search_zones"):
            brief = workspace.get("brief") or {}
            args.setdefault("start_date", brief.get("startDate") or args.get("start_date"))
            args.setdefault("end_date", brief.get("endDate") or args.get("end_date"))
            args = {k: v for k, v in args.items() if v}
        await alog(session_id, "tool_call", {"tool": name, "path": "graph",
                                             "args": {k: str(v)[:100] for k, v in args.items()}})
        t0 = time.time()
        result = await execute_tool(name, args)
        await alog(session_id, "tool_result", {"tool": name,
                   "duration_ms": int((time.time() - t0) * 1000)})
        tool_results.append({"tool_call_id": tc["id"], "role": "tool",
                             "content": json.dumps(result, ensure_ascii=False)})

    return {"messages": state["messages"] + tool_results,
            "tool_rounds": state.get("tool_rounds", 0) + 1,
            "used_tool": used_tool}


async def fallback_node(state: AgentState) -> dict:
    """Attempt 2 (force text, no tools) then attempt 3 (hardcoded per-tool)."""
    session_id = state["session_id"]
    used_tool = state.get("used_tool") or "freeform_chat"

    await alog(session_id, "fallback", {"attempt": 2, "tool": used_tool, "path": "graph"})
    try:
        forced = force_text_completion(messages=state["messages"])
        reply = sanitize_response(forced.choices[0].message.content or "")
    except Exception:
        reply = ""
    if reply:
        return {"response_text": reply, "fallback_level": 2}

    reply = _TOOL_FALLBACKS.get(used_tool,
        f"Em đã xử lý xong ({used_tool}). Anh/Chị hỏi thêm hoặc xem thông tin ở panel phải nhé!")
    await alog(session_id, "fallback", {"attempt": 3, "tool": used_tool, "using": "hardcoded"})
    return {"response_text": reply, "fallback_level": 3}


async def respond_node(state: AgentState) -> dict:
    """Persist the turn to history (chat paths that haven't already done so)."""
    if state.get("used_tool") in ("freeform_chat",) and state.get("response_text"):
        await add_message(state["session_id"], "user", state["user_message"])
        await add_message(state["session_id"], "assistant", state["response_text"])
    return {}
