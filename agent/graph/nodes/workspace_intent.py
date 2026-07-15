"""LangGraph node that turns explicit brief edits into durable proposals."""
from __future__ import annotations

from agent_logger import alog
from graph.state import AgentState
from handlers.freeform import (
    _STEP_NAMES_VI,
    _WORKSPACE_SUGGESTIONS,
    _build_update_summary,
    _field_to_step_index,
)
from session import add_message, set_pending_proposal
from workspace.intent import (
    InvalidWorkspaceIntent,
    classify_workspace_intent,
    is_explicit_decline,
    preserve_brief_context,
    resolve_workspace_intent,
)
from workspace.service import WorkspaceConflict, create_proposal, get_workspace


async def workspace_intent_node(state: AgentState) -> dict:
    """Create a proposal for an explicit edit; otherwise leave chat untouched."""
    canonical = await get_workspace(state["session_id"])
    if is_explicit_decline(state["user_message"]):
        text = "Đã hiểu. Em sẽ không áp dụng thay đổi đó; workspace được giữ nguyên."
        await add_message(state["session_id"], "user", state["user_message"])
        await add_message(state["session_id"], "assistant", text)
        return {
            "response_text": text,
            "response_blocks": [{"type": "info", "text": text}],
            "used_tool": "workspace_no_change",
        }
    try:
        intent = await classify_workspace_intent(state["user_message"], canonical)
    except Exception as exc:
        # Classification is an enhancement, not a new single point of failure.
        await alog(state["session_id"], "warn", {
            "event": "workspace_intent_classifier_failed",
            "error": str(exc)[:200],
        })
        return {}

    if intent is None:
        return {}

    if intent.requires_clarification:
        text = intent.clarification.strip() or "Anh/chị muốn thay đổi thành giá trị nào?"
        await add_message(state["session_id"], "user", state["user_message"])
        await add_message(state["session_id"], "assistant", text)
        return {
            "response_text": text,
            "response_blocks": [{"type": "info", "text": text}],
            "used_tool": "workspace_clarification",
        }

    intent.value = preserve_brief_context(
        intent.field, intent.value, state["user_message"]
    )

    try:
        command = await resolve_workspace_intent(intent, canonical)
    except InvalidWorkspaceIntent as exc:
        text = str(exc)
        await add_message(state["session_id"], "user", state["user_message"])
        await add_message(state["session_id"], "assistant", text)
        return {
            "response_text": text,
            "response_blocks": [{"type": "info", "text": text}],
            "used_tool": "workspace_clarification",
        }

    if command is None:
        return {}

    field, value, reason = command
    try:
        proposal = await create_proposal(
            state["session_id"],
            field,
            value,
            base_revision=canonical["revision"],
            actor="campaign_copilot",
            reason=reason or "Người dùng yêu cầu chỉnh sửa workspace qua chat",
        )
    except WorkspaceConflict as exc:
        return {
            "response_text": (
                "⚠ Workspace vừa được cập nhật ở nơi khác. Em chưa tạo đề xuất để "
                "tránh ghi đè; anh/chị tải lại workspace rồi thử lại nhé."
            ),
            "response_blocks": [{
                "type": "workspace_conflict",
                "expected_revision": exc.expected,
                "actual_revision": exc.actual,
            }],
            "used_tool": "workspace_conflict",
        }

    changes = {
        "field": field,
        "value": value,
        "reason": reason,
        "proposal_id": proposal["proposal_id"],
        "base_revision": proposal["base_revision"],
        "affected_artifacts": proposal["affected_artifacts"],
    }
    await set_pending_proposal(state["session_id"], changes)

    step_index = _field_to_step_index(field)
    is_locked = step_index in (state.get("confirmed_steps") or [])
    warning = ""
    if is_locked and proposal["affected_artifacts"]:
        affected = ", ".join(proposal["affected_artifacts"])
        warning = (
            f"⚠️ Bước {_STEP_NAMES_VI[step_index]} đã được xác nhận. "
            f"Nếu áp dụng, các phần phụ thuộc ({affected}) sẽ được đánh dấu cần xem lại."
        )

    reply = _build_update_summary(field, value, reason)
    if proposal["affected_artifacts"]:
        reply += (
            "\n\nNếu áp dụng, các phần phụ thuộc sau sẽ được đánh dấu cần xem lại: "
            + ", ".join(proposal["affected_artifacts"])
            + "."
        )
    await add_message(state["session_id"], "user", state["user_message"])
    await add_message(state["session_id"], "assistant", reply)
    await alog(state["session_id"], "info", {
        "event": "workspace_proposal_created",
        "field": field,
        "proposal_id": proposal["proposal_id"],
        "base_revision": proposal["base_revision"],
        "path": "structured_intent",
    })

    return {
        "response_text": reply,
        "response_blocks": [{
            "type": "workspace_proposal",
            "changes": changes,
            "is_locked": is_locked,
            "warning": warning,
            "affected_artifacts": proposal["affected_artifacts"],
        }],
        "suggestions": _WORKSPACE_SUGGESTIONS.get(field.split(".", 1)[0], []),
        "used_tool": "workspace_proposal",
    }
