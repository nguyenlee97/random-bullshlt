"""
Intercepts node — every deterministic pre-LLM path from freeform.py, as one node.

⛔ PARITY BY CONSTRUCTION: this module IMPORTS the trigger lists and helpers from
handlers.freeform instead of copying them. During the strangler migration both
paths share one source of truth; when the old path is deleted (after 2 clean
weeks in prod), move those helpers here.

Returns state update with `response_text` set → graph routes straight to respond.
Returns {} → fall through to the LLM agent node.
"""
from graph.state import AgentState
from handlers.freeform import (
    _AUTOPICK_TRIGGERS,
    _NEXT_STEP_TRIGGERS,
    _RESET_TRIGGERS,
    _is_confirm,
)
from handlers.audience import handle_targeting_autopick
from session import (
    add_message,
    clear_pending_proposal,
    get_pending_proposal,
    log_event,
    update_form_state,
)
from agent_logger import alog


async def intercepts_node(state: AgentState) -> dict:
    message = state["user_message"]
    step = state["step"]
    session_id = state["session_id"]
    workspace = state.get("workspace") or {}
    msg_lower = message.lower().strip()

    # 1. Targeting auto-pick ---------------------------------------------------
    if any(kw in msg_lower for kw in _AUTOPICK_TRIGGERS):
        await alog(session_id, "info", {"intent": "autopick_targeting", "path": "graph"})
        resp = await handle_targeting_autopick(session_id)
        return _from_agent_response(resp, used_tool="targeting_autopick")

    # 2. Next-step redirect (pure nav messages only, ≤80 chars — ported guard) --
    if len(msg_lower) <= 80 and any(kw in msg_lower for kw in _NEXT_STEP_TRIGGERS):
        texts = [
            "Anh/Chị đấn nút **Đồng ý & Tiếp tục** ở cuối panel phải để em chuyển sang bước tiếp theo nhé! 👉",
            "Tiếp tục bằng cách bấm **Đồng ý & Tiếp tục** ở cuối workspace bên phải à anh/chị.",
        ]
        await alog(session_id, "info", {"intent": "next_step_redirect", "step": step, "path": "graph"})
        return {
            "response_text": texts[step % len(texts)] if step >= 0 else texts[0],
            "response_blocks": [{"type": "info", "text": "Nhấn nút Đồng ý ở panel phải để chuyển bước."}],
            "used_tool": "freeform_chat",
        }

    # 3. Campaign reset ---------------------------------------------------------
    if any(kw in msg_lower for kw in _RESET_TRIGGERS):
        await alog(session_id, "info", {"intent": "reset_campaign", "path": "graph"})
        return {
            "response_text": (
                "Được rồi! Em sẽ giúp anh/chị bắt đầu chiến dịch mới. "
                "Anh/Chị bấm nút bên dưới để xóa toàn bộ thông tin và quay lại bước Brief nhé!"
            ),
            "response_blocks": [{
                "type": "action_reset",
                "text": "Tất cả dữ liệu (Brief, Audience, Creative, Setup) sẽ được xóa và anh/chị bắt đầu lại từ đầu.",
            }],
            "used_tool": "reset_intent",
        }

    # 4. Confirm handling (pending proposal + step-1/step-3 auto-confirm) -------
    is_confirm = _is_confirm(msg_lower)
    pending = await get_pending_proposal(session_id)

    if is_confirm and pending:
        proposal_id = pending.get("proposal_id")
        mutation = None
        if proposal_id:
            from workspace.service import WorkspaceConflict, approve_proposal
            try:
                mutation = await approve_proposal(
                    proposal_id, actor="campaign_operator"
                )
            except WorkspaceConflict as exc:
                return {
                    "response_text": (
                        "⚠ Workspace đã thay đổi sau khi đề xuất này được tạo. "
                        "Em chưa áp dụng để tránh ghi đè dữ liệu mới; Anh/Chị xem lại đề xuất nhé."
                    ),
                    "response_blocks": [{
                        "type": "workspace_conflict",
                        "expected_revision": exc.expected,
                        "actual_revision": exc.actual,
                    }],
                    "used_tool": "workspace_conflict",
                }
        await clear_pending_proposal(session_id)
        await log_event(session_id, "proposal_confirmed", {
            "proposal_id": proposal_id, "changes": pending,
        })
        await add_message(session_id, "user", message)
        field = pending.get("field", "")
        value = pending.get("value")
        if isinstance(value, str):
            import json as _j
            try:
                value = _j.loads(value)
            except Exception:
                pass
        if not proposal_id:
            await update_form_state(session_id, field, value)
        text = f"✅ Đã áp dụng thay đổi cho `{field}`. Anh/Chị xem panel phải nhé!"
        await add_message(session_id, "assistant", text)
        return {
            "response_text": text,
            "response_blocks": [{"type": "info", "text": f"Workspace đã cập nhật: `{field}`."}],
            "workspace_update": {
                "field": field,
                "value": value,
                "proposal_id": proposal_id,
                "workspace_revision": mutation.get("workspace_revision") if mutation else None,
            },
            "used_tool": "workspace_confirmed",
        }

    if step == 1 and is_confirm and not pending:
        seg = workspace.get("segment", {})
        if seg.get("attrs"):
            await add_message(session_id, "user", message)
            text = (f"✅ Audience đã xác nhận! {len(seg['attrs'])} segments được chọn — "
                    f"em sẽ chuyển sang bước **Creative**.")
            await add_message(session_id, "assistant", text)
            await update_form_state(session_id, "segment", seg)
            await alog(session_id, "confirm", {"auto_apply": True, "field": "segment", "path": "graph"})
            return {
                "response_text": text,
                "response_blocks": [{"type": "info",
                    "text": "Workspace đã cập nhật: `segment`. Upload creative ở panel phải hoặc hỏi em để tiếp tục."}],
                "workspace_update": {"field": "segment", "value": seg},
                "used_tool": "workspace_confirmed",
            }

    if step == 3 and is_confirm and not pending:
        setup_ws = workspace.get("setup", {})
        zone_ids = setup_ws.get("selectedZoneIds", [])
        if zone_ids:
            await add_message(session_id, "user", message)
            text = (f"✅ Zones đã được xác nhận! Em đã lưu **{len(zone_ids)} zones** vào chiến dịch. "
                    f"Anh/chị bấm **Tiếp tục gắn creative** trong panel bên phải để chuyển sang bước "
                    f"gắn creative vào từng zone.")
            await add_message(session_id, "assistant", text)
            await update_form_state(session_id, "setup", setup_ws)
            await alog(session_id, "confirm", {"auto_apply": True, "field": "setup", "path": "graph"})
            return {
                "response_text": text,
                "response_blocks": [{"type": "info",
                    "text": f"Đã chọn {len(zone_ids)} zones. Bấm 'Tiếp tục gắn creative' ở bên phải."}],
                "workspace_update": {"field": "setup", "value": setup_ws},
                "used_tool": "workspace_confirmed",
                "suggestions": [
                    {"label": "➕ Chọn thêm zone", "action": "prefill", "text": "Thêm zone "},
                    {"label": "🗑️ Bỏ zone", "action": "prefill", "text": "Bỏ zone "},
                ],
            }

    # No intercept hit → carry confirm flag forward for the agent node
    return {"pending_proposal": pending, "used_tool": ""}


def _from_agent_response(resp, used_tool: str) -> dict:
    return {
        "response_text": resp.text,
        "response_blocks": resp.blocks,
        "workspace_update": resp.workspace_update,
        "suggestions": resp.suggestions,
        "used_tool": used_tool,
    }
