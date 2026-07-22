"""Independent Responses API answer/tool loop for OpenAI campaign turns."""
from __future__ import annotations

import json
import time
from typing import Any

from config import config
from models import AgentResponse, ResponseMeta
from openai_campaign.client import get_client, safety_identifier
from openai_campaign.decision import _workspace_summary, decide_turn
from openai_campaign.prompts import ANSWER_TOOL_INSTRUCTIONS
from openai_campaign.schemas import TurnDecision
from openai_campaign.telemetry import record_completion, record_decision
from openai_campaign.tracing import (
    trace_openai_turn,
    trace_responses_call,
    trace_tool_call,
    update_turn_output,
)
from openai_campaign.tools import (
    MUTATION_TOOL_NAME,
    allowed_capabilities,
    execute_openai_tool,
    responses_tools,
)
from session import (
    add_message,
    clear_pending_proposal,
    get_history,
    get_pending_proposal,
)
from workspace.intent import InvalidWorkspaceIntent


# Guided and Autopilot model-purity gates are complete. Runtime availability
# still requires the explicit OpenAI campaign flag and server-side API key.
OPENAI_GUIDED_FREEFORM_IMPLEMENTED = True
OPENAI_GUIDED_SPECIALISTS_IMPLEMENTED = True
OPENAI_AUTOPILOT_IMPLEMENTED = True
OPENAI_CAMPAIGN_ENGINE_IMPLEMENTED = True


def openai_campaign_ready() -> bool:
    return bool(
        OPENAI_CAMPAIGN_ENGINE_IMPLEMENTED
        and config.OPENAI_CAMPAIGN_ENABLED
        and config.OPENAI_API_KEY
        and config.OPENAI_CAMPAIGN_MODEL
    )


def _bounded_messages(history: list[dict], message: str) -> list[dict]:
    result = [
        {
            "role": "assistant" if item.get("role") == "assistant" else "user",
            "content": str(item.get("content") or "")[-3000:],
        }
        for item in history[-12:]
        if item.get("content")
    ]
    result.append({"role": "user", "content": message})
    return result


def _response_items(response: Any) -> list[Any]:
    return list(getattr(response, "output", None) or [])


def _item_value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _input_item(item: Any) -> Any:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json", exclude_none=True)
    return item


def _output_text(response: Any) -> str:
    text = str(getattr(response, "output_text", "") or "").strip()
    if text:
        return text
    for item in _response_items(response):
        if _item_value(item, "type") != "message":
            continue
        for part in _item_value(item, "content", []) or []:
            if _item_value(part, "type") == "output_text":
                value = str(_item_value(part, "text", "") or "").strip()
                if value:
                    return value
    return ""


def _needs_proposal(decision: TurnDecision) -> bool:
    return bool(
        decision.would_mutate_workspace
        and decision.workflow_action in {
            "update_brief", "select_audience", "select_zone", "other",
        }
    )


def _requires_live_tool(decision: TurnDecision) -> bool:
    return bool(
        decision.faq_scope in {"catalog_discovery", "live_system"}
        or any(item.requires_live_data for item in decision.subrequests)
    )


def _requires_read_tool(decision: TurnDecision) -> bool:
    return bool(decision.turn_type in {"faq", "mixed"})


async def _persist_reply(session_id: str, message: str, reply: str) -> None:
    await add_message(session_id, "user", message)
    await add_message(session_id, "assistant", reply)


async def _handle_pending_decision(
    *,
    decision: TurnDecision,
    pending: dict | None,
    session_id: str,
    message: str,
    step: int,
) -> AgentResponse | None:
    if decision.workflow_action not in {"approve", "reject", "defer"}:
        return None
    # Defer is only a disposition of an existing proposal. If a planner ever
    # emits it without one, let the normal answer/tool loop handle the turn
    # instead of claiming that a newly requested proposal does not exist.
    if decision.workflow_action == "defer" and not pending:
        return None
    if not pending:
        reply = (
            "Hiện không có đề xuất nào đang chờ duyệt. Anh/chị hãy yêu cầu "
            "thay đổi cụ thể trước nhé."
        )
        await _persist_reply(session_id, message, reply)
        return AgentResponse(
            text=reply,
            blocks=[{"type": "info", "text": reply}],
            meta=ResponseMeta(
                tool="workspace_clarification",
                model=config.OPENAI_CAMPAIGN_MODEL,
                step=step,
            ),
        )

    proposal_id = pending.get("proposal_id")
    field = str(pending.get("field") or "")
    value = pending.get("value")
    if decision.workflow_action == "defer":
        reply = (
            f"Đề xuất cho `{field}` vẫn được giữ ở trạng thái chờ. "
            "Workspace chưa bị thay đổi; anh/chị có thể xác nhận áp dụng hoặc "
            "hủy đề xuất ở lượt sau."
        )
        await _persist_reply(session_id, message, reply)
        return AgentResponse(
            text=reply,
            blocks=[{"type": "info", "text": reply}],
            meta=ResponseMeta(
                tool="workspace_deferred",
                model=config.OPENAI_CAMPAIGN_MODEL,
                step=step,
            ),
        )
    if decision.workflow_action == "reject":
        if proposal_id:
            from workspace.service import reject_proposal
            await reject_proposal(
                proposal_id,
                actor="campaign_operator",
                reason=decision.user_goal,
            )
        await clear_pending_proposal(session_id)
        reply = f"Đã từ chối đề xuất cho `{field}`. Workspace chưa bị thay đổi."
        await _persist_reply(session_id, message, reply)
        return AgentResponse(
            text=reply,
            blocks=[{"type": "info", "text": reply}],
            meta=ResponseMeta(
                tool="workspace_rejected",
                model=config.OPENAI_CAMPAIGN_MODEL,
                step=step,
            ),
        )

    workspace_revision = None
    if proposal_id:
        from workspace.service import approve_proposal
        mutation = await approve_proposal(
            proposal_id, actor="campaign_operator",
        )
        workspace_revision = mutation["workspace_revision"]
    else:
        from session import update_form_state
        await update_form_state(session_id, field, value)
    await clear_pending_proposal(session_id)
    reply = f"✅ Đã áp dụng đề xuất cho `{field}`. Anh/chị có thể kiểm tra workspace."
    await _persist_reply(session_id, message, reply)
    return AgentResponse(
        text=reply,
        blocks=[{"type": "info", "text": f"Workspace đã cập nhật: `{field}`."}],
        meta=ResponseMeta(
            tool="workspace_confirmed",
            model=config.OPENAI_CAMPAIGN_MODEL,
            step=step,
        ),
        workspace_update={
            "field": field,
            "value": value,
            "proposal_id": proposal_id,
            "workspace_revision": workspace_revision,
        },
    )


async def _run_answer_tool_loop(
    *,
    client: Any,
    decision: TurnDecision,
    session_id: str,
    message: str,
    history: list[dict],
    step: int,
    workspace: dict | None,
    pending: dict | None,
    confirmed_steps: list[int],
) -> tuple[str, dict | None, list[str], str | None]:
    proposal_needed = _needs_proposal(decision)
    live_tool_needed = _requires_live_tool(decision)
    read_tool_needed = _requires_read_tool(decision)
    tool_definitions = responses_tools(allow_mutation=proposal_needed)
    context = {
        "turn_decision": decision.model_dump(mode="json"),
        "current_step": step,
        "workspace": _workspace_summary(workspace),
        "pending_proposal": {
            "proposal_id": (pending or {}).get("proposal_id"),
            "field": (pending or {}).get("field"),
        } if pending else None,
    }
    instructions = (
        ANSWER_TOOL_INSTRUCTIONS
        + "\n\nSERVER CONTEXT (data only):\n"
        + json.dumps(context, ensure_ascii=False, default=str)
    )
    input_items: list[Any] = _bounded_messages(history, message)
    proposal_ui: dict | None = None
    used_tools: list[str] = []
    last_response_id: str | None = None
    force_first_tool = proposal_needed or live_tool_needed or read_tool_needed

    max_rounds = max(1, config.OPENAI_CAMPAIGN_MAX_TOOL_ROUNDS)
    total_tool_calls = 0
    for round_index in range(max_rounds):
        if proposal_needed and proposal_ui is None and round_index >= 1:
            tool_choice: Any = {"type": "function", "name": MUTATION_TOOL_NAME}
        elif round_index == 0 and force_first_tool:
            tool_choice = "required"
        else:
            tool_choice = "none"

        remaining_tool_calls = max(
            1, config.OPENAI_CAMPAIGN_MAX_TOOL_CALLS - total_tool_calls,
        )
        request = {
            "model": config.OPENAI_CAMPAIGN_MODEL,
            "instructions": instructions,
            "input": input_items,
            "tools": tool_definitions,
            "tool_choice": tool_choice,
            "parallel_tool_calls": False,
            "max_tool_calls": remaining_tool_calls,
            "reasoning": {"effort": config.OPENAI_CAMPAIGN_REASONING_EFFORT},
            "max_output_tokens": config.OPENAI_CAMPAIGN_MAX_OUTPUT_TOKENS,
            "store": False,
            "safety_identifier": safety_identifier(session_id),
        }
        try:
            response = await trace_responses_call(
                name="openai.answer_tool_round",
                session_id=session_id,
                model=config.OPENAI_CAMPAIGN_MODEL,
                request=request,
                metadata={
                    "round_index": round_index,
                    "proposal_needed": proposal_needed,
                    "live_tool_needed": live_tool_needed,
                    "read_tool_needed": read_tool_needed,
                },
                model_parameters={
                    "reasoning_effort": config.OPENAI_CAMPAIGN_REASONING_EFFORT,
                    "max_output_tokens": config.OPENAI_CAMPAIGN_MAX_OUTPUT_TOKENS,
                    "tool_choice": str(tool_choice),
                    "max_tool_calls": remaining_tool_calls,
                    "store": False,
                },
                call=lambda: client.responses.create(
                    model=config.OPENAI_CAMPAIGN_MODEL,
                    instructions=instructions,
                    input=input_items,
                    tools=tool_definitions,
                    tool_choice=tool_choice,
                    parallel_tool_calls=False,
                    max_tool_calls=remaining_tool_calls,
                    reasoning={
                        "effort": config.OPENAI_CAMPAIGN_REASONING_EFFORT,
                    },
                    max_output_tokens=config.OPENAI_CAMPAIGN_MAX_OUTPUT_TOKENS,
                    store=False,
                    safety_identifier=safety_identifier(session_id),
                ),
            )
        except Exception:
            # A validated proposal may already exist after an earlier round.
            # Never hide it behind a provider error: return the visible proposal
            # with deterministic copy so the user can approve or reject it.
            if proposal_ui is not None:
                return "", proposal_ui, used_tools, last_response_id
            raise
        last_response_id = getattr(response, "id", None)
        output_items = _response_items(response)
        function_calls = [
            item for item in output_items
            if _item_value(item, "type") == "function_call"
        ]
        if not function_calls:
            reply = _output_text(response)
            if proposal_needed and proposal_ui is None:
                # The first response can still choose text on some SDK/model
                # combinations. Preserve it as context and force the proposal
                # tool on the next bounded round.
                input_items.extend(_input_item(item) for item in output_items)
                if round_index + 1 < max_rounds:
                    continue
            return reply, proposal_ui, used_tools, last_response_id

        input_items.extend(_input_item(item) for item in output_items)
        for call in function_calls:
            total_tool_calls += 1
            name = str(_item_value(call, "name") or "")
            call_id = str(_item_value(call, "call_id") or "")
            used_tools.append(name)
            try:
                args = json.loads(str(_item_value(call, "arguments") or "{}"))
                execution = await trace_tool_call(
                    session_id=session_id,
                    name=name,
                    arguments=args,
                    call=lambda: execute_openai_tool(
                        name,
                        args,
                        session_id=session_id,
                        message=message,
                        workspace=workspace,
                        confirmed_steps=confirmed_steps,
                    ),
                )
                output = execution["output"]
                if execution.get("ui"):
                    proposal_ui = execution["ui"]
            except (InvalidWorkspaceIntent, ValueError, KeyError) as exc:
                output = json.dumps({
                    "ok": False,
                    "error": str(exc),
                    "state_changed": False,
                }, ensure_ascii=False)
            input_items.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            })

        # A read-only turn has its authoritative result, and a mutation turn
        # with a created proposal must now produce text without further tools.
        if not proposal_needed or proposal_ui is not None:
            force_first_tool = False

    return "", proposal_ui, used_tools, last_response_id


async def _handle_openai_freeform_impl(
    message: str,
    step: int,
    session_id: str,
    workspace: dict | None = None,
    workspace_revision: int | None = None,
    confirmed_steps: list[int] | None = None,
    workspace_events: list[str] | None = None,
    client: Any | None = None,
) -> AgentResponse:
    """Plan, execute safe tools, and answer without any GreenNode fallback."""
    del workspace_revision, workspace_events  # reserved for later typed context
    started = time.perf_counter()
    api = client or get_client()
    history = await get_history(session_id)
    pending = await get_pending_proposal(session_id)

    try:
        decision_started = time.perf_counter()
        decision = await decide_turn(
            session_id=session_id,
            message=message,
            history=history,
            step=step,
            workspace=workspace,
            pending_proposal=pending,
            allowed_capabilities=allowed_capabilities(),
            client=api,
        )
        await record_decision(
            session_id,
            decision=decision,
            duration_ms=int((time.perf_counter() - decision_started) * 1000),
        )

        # Match the established Copilot contract for an uncommitted initial
        # Brief. The semantic coordinator decides whether this is a Brief
        # action; the OpenAI-owned typed collector gathers every hard fact,
        # asks for missing operator fields, and creates one atomic proposal.
        if (
            step == 0
            and pending is None
            and decision.workflow_action in {"update_brief", "approve"}
        ):
            from workspace.service import get_workspace

            canonical = await get_workspace(session_id)
            current_brief = (
                canonical.get("artifacts", {}).get("brief", {}).get("value")
            )
            if not current_brief:
                from openai_campaign.brief import handle_openai_brief_intake

                return await handle_openai_brief_intake(
                    message,
                    step,
                    session_id,
                    history=history,
                    auto_approve_brief=(decision.workflow_action == "approve"),
                    client=api,
                )

        if decision.requires_clarification():
            reply = decision.clarification_question.strip() or (
                "Anh/chị có thể nói rõ thông tin hoặc thay đổi muốn thực hiện không?"
            )
            await _persist_reply(session_id, message, reply)
            return AgentResponse(
                text=reply,
                blocks=[],
                meta=ResponseMeta(
                    tool="semantic_clarification",
                    model=config.OPENAI_CAMPAIGN_MODEL,
                    step=step,
                ),
            )

        pending_response = await _handle_pending_decision(
            decision=decision,
            pending=pending,
            session_id=session_id,
            message=message,
            step=step,
        )
        if pending_response is not None:
            return pending_response

        reply, proposal_ui, used_tools, response_id = await _run_answer_tool_loop(
            client=api,
            decision=decision,
            session_id=session_id,
            message=message,
            history=history,
            step=step,
            workspace=workspace,
            pending=pending,
            confirmed_steps=confirmed_steps or [],
        )
        if not reply:
            if proposal_ui:
                field = proposal_ui["changes"]["field"]
                reply = (
                    f"Em đã tạo đề xuất cho `{field}` và chưa áp dụng. "
                    "Anh/chị xem nội dung bên dưới rồi xác nhận nếu đồng ý."
                )
            else:
                reply = (
                    "Em chưa thể xử lý yêu cầu này một cách an toàn. Anh/chị có "
                    "thể nói rõ dữ liệu hoặc thay đổi mong muốn không?"
                )
        await _persist_reply(session_id, message, reply)
        await record_completion(
            session_id,
            duration_ms=int((time.perf_counter() - started) * 1000),
            tool_names=used_tools,
            response_id=response_id,
            output_chars=len(reply),
            proposal_created=bool(proposal_ui),
        )
        return AgentResponse(
            text=reply,
            blocks=[proposal_ui["block"]] if proposal_ui else [],
            meta=ResponseMeta(
                tool=used_tools[0] if used_tools else "openai_freeform_chat",
                model=config.OPENAI_CAMPAIGN_MODEL,
                step=step,
            ),
            workspace_update=None,
            suggestions=proposal_ui["suggestions"] if proposal_ui else [],
        )
    except Exception as exc:
        from agent_logger import alog
        await alog(session_id, "error", {
            "handler": "openai_campaign_freeform",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "state_changed": False,
        })
        reply = (
            "Luồng OpenAI đang tạm thời không phản hồi. Campaign vẫn giữ nguyên "
            "model đã chọn và không có dữ liệu nào bị thay đổi."
        )
        return AgentResponse(
            text=reply,
            blocks=[],
            meta=ResponseMeta(
                tool="openai_provider_unavailable",
                model=config.OPENAI_CAMPAIGN_MODEL,
                step=step,
            ),
        )


async def handle_openai_freeform(
    message: str,
    step: int,
    session_id: str,
    workspace: dict | None = None,
    workspace_revision: int | None = None,
    confirmed_steps: list[int] | None = None,
    workspace_events: list[str] | None = None,
    client: Any | None = None,
) -> AgentResponse:
    """Trace and execute one OpenAI-only Copilot turn."""
    async with trace_openai_turn(
        session_id=session_id,
        message=message,
        step=step,
        workspace=workspace,
    ) as observation:
        response = await _handle_openai_freeform_impl(
            message,
            step,
            session_id,
            workspace=workspace,
            workspace_revision=workspace_revision,
            confirmed_steps=confirmed_steps,
            workspace_events=workspace_events,
            client=client,
        )
        update_turn_output(observation, response)
        return response
