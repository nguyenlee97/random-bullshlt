"""
Free-form chat handler — LLM + OpenAI tool calling.
Handles any text message not matched by form handlers.

Workspace Sync Protocol:
  - Receives live workspace state from frontend each call
  - Builds a fresh workspace snapshot (never stored in history)
  - Workspace diff events from direct UI edits are injected as system message
  - update_workspace tool produces a proposal block (Option B: confirm before apply)
"""
import asyncio
import json
import time
from models import AgentResponse, ResponseMeta
from llm import chat_completion, force_text_completion, sanitize_response
from session import (
    get_or_create_session, get_history, add_message, log_event,
    set_pending_proposal, get_pending_proposal, clear_pending_proposal,
    update_form_state,
)
from prompts.system import SYSTEM_PROMPT, STEP_NAMES
from tools.zone_catalog import get_all_zones
from agent_logger import alog
from time_context import campaign_time_system_message

from tools.registry import TOOL_DEFINITIONS, execute_tool
from handlers.audience import handle_targeting_autopick
from workspace.intent import InvalidWorkspaceIntent, resolve_legacy_update

# Intent keywords that trigger targeting auto-pick directly
_AUTOPICK_TRIGGERS = [
    "tự động chọn targeting",
    "agent chọn targeting",
    "chọn targeting giúp",
    "chọn giúp targeting",
    "targeting phù hợp",
    "set targeting giúp",
]

# Intent keywords that trigger full campaign reset
_RESET_TRIGGERS = [
    "tạo chiến dịch mới",
    "bắt đầu lại",
    "làm lại từ đầu",
    "chiến dịch mới",
    "reset chiến dịch",
    "thử lại từ đầu",
]

# Intent keywords that confirm a pending workspace proposal.
# ONLY long, unambiguous Vietnamese phrases that CANNOT appear in questions or
# negative sentences. Short words (ok, yes, sure, được...) are excluded — they
# are too risky and can be part of "không ok", "được không", etc.
_CONFIRM_TRIGGERS = [
    "đồng ý",
    "xác nhận",
    "đúng rồi",
    "chuẩn rồi",
    "chốt luôn",
    "nhất trí",
    "tiến hành đi",
    "triển đi",
    "triển luôn",
    "áp dụng đi",
    "chấp nhận",
    "xác nhận đi",
    "lưu lại đi",
    "ok luôn",
    "oke luôn",
    "oke nhé",
    "duyệt nhé",
    # Additional unambiguous approval words
    "duyệt",       # "oke duyệt", "duyệt luôn", "duyệt đi"
    "ổn rồi",      # "ổn rồi, lưu lại"
    "ok rồi",      # "ok rồi, tiếp theo đi"
    "oke rồi",     # "oke rồi"
    "chuẩn luôn",  # "chuẩn luôn, dùng cái này"
    "hợp lý",     # "hợp lý đấy, đồng ý"
    "lưu luôn",    # "lưu luôn đi"
]

# Negation prefixes: only 3 roots, but they are checked by building the FULL
# phrase "negation + trigger" (e.g. "không đồng ý"), not as bare substrings.
# This avoids "không sao, đồng ý" being incorrectly blocked.
_NEGATION_ROOTS = ["không", "chưa", "chẳng"]

# ── Quick-reply suggestions per workspace field ────────────────────────────────
# Shown as clickable chips below the agent message after a workspace_proposal.
# "send"    → immediately sends text as a chat message (goes through _is_confirm or LLM)
# "prefill" → puts text into the composer input so user can complete the thought
_WORKSPACE_SUGGESTIONS: dict[str, list[dict]] = {
    "brief": [
        {"label": "✅ Xác nhận brief",    "action": "send",    "text": "đồng ý, lưu brief lại nhé"},
        {"label": "✏️ Chỉnh sửa thêm",     "action": "prefill", "text": "Tôi muốn chỉnh sửa: "},
        {"label": "🔄 Nhập lại từ đầu",   "action": "send",    "text": "Tôi muốn nhập lại thông tin brief từ đầu"},
    ],
    "segment": [
        {"label": "✅ Áp dụng segments",  "action": "send",    "text": "đồng ý, áp dụng các segments này"},
        {"label": "🗑️ Bỏ bớt segment",    "action": "prefill", "text": "Bỏ segment "},
        {"label": "🔍 Tìm thêm segments",  "action": "prefill", "text": "Tìm thêm segments liên quan đến "},
    ],
    "creative": [
        {"label": "✅ Xác nhận creative",  "action": "send",    "text": "đồng ý, xác nhận creative"},
        {"label": "🔄 Upload file khác",  "action": "prefill", "text": "Tôi muốn đổi file: "},
    ],
    "setup": [
        {"label": "✅ Duyệt các zones",    "action": "send",    "text": "đồng ý, duyệt các zones này"},
        {"label": "➕ Thêm zone",           "action": "prefill", "text": "Thêm zone "},
        {"label": "🗑️ Bỏ zone",             "action": "prefill", "text": "Bỏ zone "},
    ],
}


def _is_confirm(msg_lower: str) -> bool:
    """Return True only if message contains an unambiguous confirmation phrase
    that is NOT directly negated (e.g. 'không đồng ý', 'chưa xác nhận').

    Negation is detected by checking if the FULL phrase '<root> <trigger>'
    (e.g. 'không đồng ý') appears in the message — NOT by checking the
    negation root as a bare substring. This prevents 'không sao, đồng ý'
    from being falsely blocked.
    """
    for kw in _CONFIRM_TRIGGERS:
        if kw not in msg_lower:
            continue
        # Is this specific trigger directly negated? ("không đồng ý", "chưa xác nhận" ...)
        is_negated = any(f"{neg} {kw}" in msg_lower for neg in _NEGATION_ROOTS)
        # Approval-bypass requests are edits, not confirmations. Inspect only a
        # short prefix window so "không sao, đồng ý" remains a valid approval.
        position = msg_lower.find(kw)
        prefix = msg_lower[max(0, position - 28):position]
        is_bypass = any(
            phrase in prefix
            for phrase in ("bỏ qua", "không cần", "chưa cần", "khỏi cần", "đừng")
        )
        if not is_negated and not is_bypass:
            return True  # trigger present and not negated
    return False






# Intent keywords that mean "go to next step" — intercepted deterministically
_NEXT_STEP_TRIGGERS = [
    "sang bước tiếp",
    "bước tiếp theo",
    "next step",
    "tiếp tục sang",
    "chuyển sang bước",
    "move to next",
    "tiếp theo đi",
    "tiếp tục",
    "tiếp đi",
    "sang phần tiếp",
    "chuyển bước",
    "bước sau",
    "continue",
    "go next",
    "next đi",
]

# Step name mapping for lock warnings
_STEP_NAMES_VI = ["Brief", "Audience", "Creative", "Setup Camp", "Kết quả"]

# Map workspace field path prefix → step index
_FIELD_TO_STEP = {
    "brief": 0,
    "segment": 1,
    "creative": 2,
    "setup": 3,
}


def _field_to_step_index(field: str) -> int:
    """Map dotted field path (e.g. 'brief.brand') to step index."""
    prefix = field.split(".")[0] if "." in field else field
    return _FIELD_TO_STEP.get(prefix, -1)


def _build_update_summary(field: str, value, reason: str) -> str:
    """Build a deterministic summary message for update_workspace proposals."""
    if field == "brief" and isinstance(value, dict):
        parts = []
        if value.get("brand"):
            parts.append(f"Brand: **{value['brand']}**")
        if value.get("objective"):
            obj_vi = {"awareness": "Awareness", "consideration": "Consideration",
                      "conversion": "Conversion", "retention": "Retention"}
            parts.append(f"Objective: **{obj_vi.get(value['objective'], value['objective'])}**")
        if value.get("budget") is not None and value.get("budget") != "":
            parts.append(f"Budget: **{value['budget']:,} triệu VND**")
        if value.get("kpi"):
            parts.append(f"KPI: **{value['kpi']}**")
        if value.get("startDate") and value.get("endDate"):
            parts.append(f"Thời gian: **{value['startDate']} → {value['endDate']}**")
        if parts:
            summary = "\n".join(f"- {p}" for p in parts)
            return f"Em đã tổng hợp thông tin brief. Anh/chị xác nhận để lưu:\n\n{summary}"
        return "Em đề xuất cập nhật brief. Anh/Chị xem và xác nhận nhé!"

    if field.startswith("brief."):
        label = {
            "brief.brand": "thương hiệu",
            "brief.objective": "mục tiêu",
            "brief.kpi": "KPI",
            "brief.budget": "ngân sách (triệu VND)",
            "brief.startDate": "ngày bắt đầu",
            "brief.endDate": "ngày kết thúc",
            "brief.notes": "ghi chú",
        }.get(field, field)
        return f"Em đề xuất đổi **{label}** thành **{value}**. Anh/chị xác nhận để áp dụng nhé!"

    if field == "segment" and isinstance(value, dict):
        attrs = value.get("attrs", [])
        labels = [
            item.get("fullLabel") or item.get("name") or item.get("segmentId", "?")
            for item in attrs
        ]
        shown = ", ".join(labels[:6])
        suffix = f" và {len(labels) - 6} segment khác" if len(labels) > 6 else ""
        return (
            f"Em đề xuất chọn **{len(labels)} audience segment**: {shown}{suffix}. "
            f"Audience ước tính **{value.get('size', 0):,} người**. "
            "Anh/chị xác nhận để áp dụng nhé!"
        )

    if field == "targeting" and isinstance(value, dict):
        rows = []
        for dimension, picks in value.items():
            values = picks if isinstance(picks, list) else [picks]
            rows.append(f"**{dimension}**: {', '.join(map(str, values)) or '(trống)'}")
        return "Em đề xuất targeting:\n\n" + "\n".join(
            f"- {row}" for row in rows
        ) + "\n\nAnh/chị xác nhận để áp dụng nhé!"

    if field == "creative.files" and isinstance(value, list):
        names = [item.get("name") or item.get("id", "?") for item in value]
        return (
            f"Em đề xuất giữ lại **{len(names)} creative**: "
            f"{', '.join(names) or '(không còn file)'}. "
            "Anh/chị xác nhận để áp dụng nhé!"
        )

    if field == "setup.selectedZoneIds" and isinstance(value, list):
        return (
            f"Em đề xuất chọn **{len(value)} ad zone**: {', '.join(map(str, value))}. "
            "Anh/chị xác nhận để áp dụng nhé!"
        )

    if field == "assignments" and isinstance(value, dict):
        rows = []
        for zone, file_index in value.items():
            try:
                display_index = int(file_index) + 1
            except (TypeError, ValueError):
                display_index = file_index
            rows.append(f"`{zone}` → creative #{display_index}")
        return "Em đề xuất cách gắn creative:\n\n" + "\n".join(
            f"- {row}" for row in rows
        ) + "\n\nAnh/chị xác nhận để áp dụng nhé!"

    # Single field update
    value_str = str(value)[:80]
    return f"Em đề xuất cập nhật `{field}` → `{value_str}`. Anh/Chị xác nhận để lưu nhé!"


# ── Zone map cache for workspace snapshot enrichment ──────────────────────────
_zone_map_cache: dict[str, dict] = {}


def _build_workspace_snapshot(workspace: dict, confirmed_steps: list[int], current_step: int = -1) -> str:
    """Build a compact workspace context string injected as system message each call."""
    confirmed = set(confirmed_steps or [])
    lines = ["=== TRẠNG THÁI WORKSPACE HIỆN TẠI ==="]

    # Tell LLM explicitly which step the user is CURRENTLY ON
    # (prevents hallucinating step numbering: 0-indexed step != 1-based "bước N")
    if 0 <= current_step < len(_STEP_NAMES_VI):
        step_ordinal = current_step + 1
        step_name_cur = _STEP_NAMES_VI[current_step]
        lines.append(f">>> NGƯỜI DÙNG ĐANG Ở BƯỚC {step_ordinal}/{len(_STEP_NAMES_VI)}: {step_name_cur} (index {current_step}) <<<")
        lines.append("")

    # Step lock status
    for i, name in enumerate(_STEP_NAMES_VI):
        status = "✅ Đã xác nhận (LOCKED)" if i in confirmed else "⏳ Chưa xác nhận"
        lines.append(f"  Bước {i+1} - {name}: {status}")
    lines.append("")

    # Brief
    brief = workspace.get("brief", {})
    if brief.get("brand"):
        OBJECTIVE_VI = {
            "awareness": "Awareness — Nhận diện thương hiệu",
            "consideration": "Consideration — Tăng quan tâm",
            "conversion": "Conversion — Chuyển đổi",
            "retention": "Retention — Giữ chân khách hàng",
        }
        lines.append("--- Brief ---")
        lines.append(f"Brand     : {brief.get('brand', '?')}")
        lines.append(f"Objective : {OBJECTIVE_VI.get(brief.get('objective', ''), brief.get('objective', '?'))}")
        lines.append(f"KPI       : {brief.get('kpi') or '(chưa chọn)'}")
        lines.append(f"Budget    : {brief.get('budget', 0):,} triệu VND")
        lines.append(f"Thời gian : {brief.get('startDate', '?')} → {brief.get('endDate', '?')}")
        if brief.get("notes"):
            lines.append(f"Ghi chú   : {brief['notes']}")
        lines.append("")

    # Audience
    segment = workspace.get("segment", {})
    attrs = segment.get("attrs", [])
    if attrs:
        import json as _json
        lines.append("--- Audience ---")
        lines.append(f"Segments hiện tại: {len(attrs)} đã chọn")
        audience_size = segment.get("size", 0)
        size_known = segment.get("sizeKnown", audience_size > 0)
        lines.append(
            f"Size ước tính: {audience_size:,} người dùng"
            if size_known
            else "Size ước tính: chưa biết (catalog không cung cấp size; không phải 0 người)"
        )
        # ─ Provide FULL segment data so LLM can modify without hallucinating ─
        # LLM must use this exact JSON as the base when calling update_workspace
        lines.append("CURRENT_SEGMENT_DATA (dùng làm base khi gọi update_workspace):")
        lines.append(_json.dumps(
            {
                "attrs": attrs,
                "targeting": segment.get("targeting", {}),
                "size": audience_size,
                "sizeKnown": size_known,
            },
            ensure_ascii=False, separators=(',', ':')
        ))
        lines.append("")

    # Creative
    creative = workspace.get("creative", {})
    files = creative.get("files", [])
    if files:
        lines.append("--- Creative ---")
        lines.append(f"Tổng số files: {len(files)} đã upload")
        for idx, f in enumerate(files):
            fname = f.get('name', f'file_{idx}')
            ftype = f.get('type', '?')
            fsize = f.get('size', 0)
            size_str = f"{fsize // 1024}KB" if fsize > 0 else "?"
            lines.append(f"  [{idx}] {fname} ({ftype}, {size_str})")
        lines.append("")

    # Setup — resolve zone IDs to full details from catalog cache
    setup = workspace.get("setup", {})
    selected_zone_ids = setup.get("selectedZoneIds", [])
    setup_phase = setup.get("phase", "zones")
    assignments = setup.get("assignments", {})
    _PHASE_LABELS = {
        "zones":  "1/3 — Chọn Ad Zones (user đang chọn zones)",
        "assign": "2/3 — Gắn Creative (user đang gán creative vào zones)",
        "confirm":"3/3 — Xác nhận & Tạo chiến dịch",
    }
    if selected_zone_ids or setup_phase != "zones":
        import json as _json2
        lines.append("--- Setup Camp ---")
        lines.append(f"Sub-step hiện tại: {_PHASE_LABELS.get(setup_phase, setup_phase)}")
        lines.append(f"Zones đã chọn: {len(selected_zone_ids)}")

        # Resolve zone IDs to human-readable details from zone catalog
        zone_map = _zone_map_cache or {}
        for i, zid in enumerate(selected_zone_ids, 1):
            z = zone_map.get(zid)
            if z:
                lines.append(
                    f"  {i}. {zid} — {z.get('channel','?')} {z.get('format','?')} "
                    f"{z.get('size','?')}, reach {z.get('reach',0):,}, "
                    f"CPM {z.get('cpm',0):,}đ, obj={z.get('obj','?')}"
                )
            else:
                lines.append(f"  {i}. {zid} — (chi tiết chưa load)")

        # Show assignments (creative → zone mapping)
        if assignments:
            lines.append("")
            lines.append("ASSIGNMENTS (creative index → zone):")
            for zone_id, file_idx in assignments.items():
                fname = files[int(file_idx)].get('name', f'file_{file_idx}') if files and int(file_idx) < len(files) else f'file_{file_idx}'
                lines.append(f"  {zone_id} ← [{file_idx}] {fname}")
            unassigned = [zid for zid in selected_zone_ids if zid not in assignments]
            if unassigned:
                lines.append(f"  ⚠️ Chưa gán creative: {', '.join(unassigned)}")

        # Raw IDs for update_workspace
        lines.append("")
        lines.append("CURRENT_SELECTED_ZONES (dùng làm base khi gọi update_workspace field=setup):")
        lines.append(_json2.dumps(selected_zone_ids, ensure_ascii=False))
        lines.append("")

    lines.append("QUY TẮC QUAN TRỌNG:")
    lines.append("- Dùng thông tin trên để trả lời. KHÔNG hỏi lại thông tin đã có.")
    lines.append("- Nếu bước ✅ LOCKED, hỏi xác nhận user trước khi thay đổi và cảnh báo reset downstream.")
    lines.append("- User có thể thao tác bước sau ngay cả khi đang ở bước trước — luôn hỗ trợ.")
    lines.append("- Khi sửa segment (bước 1): LUÔN lấy CURRENT_SEGMENT_DATA làm base, chỉ sửa entry cần thiết. KHÔNG tự tạo mới attrs.")
    lines.append("- Khi user yêu cầu chọn/giữ/bỏ/xóa segment: LUÔN gọi update_workspace ngay lập tức với danh sách attrs đã lọc đúng.")
    lines.append("  Ví dụ: user nói 'chỉ giữ X và Y' → lọc CURRENT_SEGMENT_DATA chỉ còn X và Y → gọi update_workspace field=segment.")
    lines.append("  KHÔNG chat hỏi lại ý kiến — gọi update_workspace trực tiếp rồi hỏi xác nhận.")
    lines.append("")
    lines.append("⚠️ QUAN TRỌNG — STEP ADVANCE:")
    lines.append("- Để chuyển bước (ví dụ từ Audience sang Creative), HÀNH ĐỘNG DUY NHẤT là gọi update_workspace với đúng field.")
    lines.append("- Chỉ trả lời text mà KHÔNG gọi update_workspace sẽ KHÔNG chuyển được bước — hệ thống frontend chỉ lắng nghe update_workspace.")
    lines.append("- Khi user duyệt/xác nhận/đồng ý với segment ở bước 1: Gọi update_workspace(field='segment', value=CURRENT_SEGMENT_DATA) ngay.")
    lines.append("- Khi user duyệt/xác nhận/đồng ý với brief ở bước 0: Gọi update_workspace(field='brief', value=<brief hiện tại>) ngay.")
    return "\n".join(lines)


def _build_workspace_diff(events: list[str]) -> str | None:
    """Build system message for direct UI edits made outside chat."""
    if not events:
        return None
    lines = ["=== THAY ĐỔI TRÊN WORKSPACE (người dùng thao tác trực tiếp, không qua chat) ==="]
    for e in events:
        lines.append(f"• {e}")
    lines.append("Hãy ghi nhận những thay đổi này. Nếu user hỏi về trạng thái, phản ánh đúng thực tế hiện tại.")
    return "\n".join(lines)


async def handle_freeform(
    message: str,
    step: int,
    session_id: str,
    workspace: dict | None = None,
    workspace_revision: int | None = None,
    confirmed_steps: list[int] | None = None,
    workspace_events: list[str] | None = None,
) -> AgentResponse:

    # ── Check for targeting auto-pick intent ──────────────────────────────────
    msg_lower = message.lower().strip()
    await alog(session_id, "request", {
        "step": step,
        "msg_preview": message[:120],
        "has_workspace": bool(workspace),
        "workspace_events": len(workspace_events or []),
        "confirmed_steps": confirmed_steps or [],
    })
    if any(kw in msg_lower for kw in _AUTOPICK_TRIGGERS):
        await alog(session_id, "info", {"intent": "autopick_targeting"})
        return await handle_targeting_autopick(session_id)

    # ── Intercept "next step" intent — only when message is PURELY a step-nav request ──
    # Guard: long messages (>80 chars) likely contain substantive data + a casual "tiếp tục"
    # → let LLM handle them instead of swallowing the data with this shortcut.
    is_pure_step_nav = len(msg_lower) <= 80 and any(kw in msg_lower for kw in _NEXT_STEP_TRIGGERS)
    if is_pure_step_nav:
        _STEP_NEXT_MSG = [
            "Anh/Chị bấm nút **Đồng ý & Tiếp tục** ở cuối panel phải để em chuyển sang bước tiếp theo nhé! 👉",
            "Tiếp tục bằng cách bấm **Đồng ý & Tiếp tục** ở cuối workspace bên phải à anh/chị.",
        ]
        reply_text = _STEP_NEXT_MSG[step % len(_STEP_NEXT_MSG)] if step >= 0 else _STEP_NEXT_MSG[0]
        await alog(session_id, "info", {"intent": "next_step_redirect", "step": step})
        return AgentResponse(
            text=reply_text,
            blocks=[{"type": "info", "text": "Nhấn nút Đồng ý ở panel phải để chuyển bước."}],
            meta=ResponseMeta(tool="freeform_chat", model="none", step=step),
        )

    # Track if this message is a confirmation (affects update_workspace handling)
    # Uses two-tier system + negation guard (see _is_confirm() above)
    is_confirm_trigger = _is_confirm(msg_lower)

    # ── Check for campaign reset intent ──────────────────────────────────────
    if any(kw in msg_lower for kw in _RESET_TRIGGERS):
        await alog(session_id, "info", {"intent": "reset_campaign"})
        return AgentResponse(
            text="Được rồi! Em sẽ giúp anh/chị bắt đầu chiến dịch mới. Anh/Chị bấm nút bên dưới để xóa toàn bộ thông tin và quay lại bước Brief nhé!",
            blocks=[{
                "type": "action_reset",
                "text": "Tất cả dữ liệu (Brief, Audience, Creative, Setup) sẽ được xóa và anh/chị bắt đầu lại từ đầu.",
            }],
            meta=ResponseMeta(tool="reset_intent", model="none", step=step),
        )

    # ── Check if this message confirms a pending proposal ─────────────────────
    # NOTE: pending must be loaded BEFORE the step-1 auto-confirm block below
    pending = await get_pending_proposal(session_id)

    # The legacy path used to let an initial Brief recommendation exist only as
    # prose. Route every uncommitted step-0 turn through the same typed collector
    # used by LangGraph. If this turn is an explicit approval, the collector can
    # safely reconstruct and approve the validated proposal in one operation.
    if step == 0 and not pending:
        from workspace.service import get_workspace

        canonical = await get_workspace(session_id)
        if not canonical.get("artifacts", {}).get("brief", {}).get("value"):
            from graph.nodes.brief_collector import brief_collector_node

            history = await get_history(session_id)
            typed = await brief_collector_node({
                "session_id": session_id,
                "step": step,
                "user_message": message,
                "messages": [
                    *history,
                    {"role": "user", "content": message},
                ],
                "tokens_spent": 0,
                "auto_approve_brief": is_confirm_trigger,
            })
            # The graph's respond node normally persists explanatory/clarifying
            # replies. This direct legacy adapter must do that itself.
            if typed.get("used_tool") == "freeform_chat" and typed.get("response_text"):
                await add_message(session_id, "user", message)
                await add_message(session_id, "assistant", typed["response_text"])
            return AgentResponse(
                text=typed.get("response_text", ""),
                blocks=typed.get("response_blocks", []),
                meta=ResponseMeta(
                    tool=typed.get("used_tool") or "freeform_chat",
                    model="minimax",
                    step=step,
                ),
                workspace_update=typed.get("workspace_update"),
                suggestions=typed.get("suggestions", []),
            )

    if is_confirm_trigger:
        await alog(session_id, "confirm", {"has_pending": bool(pending), "trigger_word": msg_lower[:20]})
        if pending:
            field = pending.get("field", "")
            value = pending.get("value")
            # Parse JSON-stringified value if needed
            if isinstance(value, str):
                try:
                    import json as _j
                    value = _j.loads(value)
                except Exception:
                    pass
            proposal_id = pending.get("proposal_id")
            workspace_revision = None
            if proposal_id:
                from workspace.service import approve_proposal
                mutation = await approve_proposal(
                    proposal_id, actor="campaign_operator"
                )
                workspace_revision = mutation["workspace_revision"]
            else:
                await update_form_state(session_id, field, value)
            await clear_pending_proposal(session_id)
            await log_event(session_id, "proposal_confirmed", {
                "proposal_id": proposal_id, "changes": pending,
            })
            await add_message(session_id, "user", message)
            text = f"✅ Đã áp dụng thay đổi cho `{field}`. Anh/chị xem workspace nhé!"
            await add_message(session_id, "assistant", text)
            return AgentResponse(
                text=text,
                blocks=[{"type": "info", "text": f"Workspace đã cập nhật: `{field}`."}],
                meta=ResponseMeta(tool="workspace_confirmed", model="none", step=step),
                workspace_update={
                    "field": field, "value": value,
                    "proposal_id": proposal_id,
                    "workspace_revision": workspace_revision,
                },
            )

    # ── Step 1 (Audience) auto-confirm ───────────────────────────────────────
    # No pending_proposal for segment (audience-entry doesn't use pending_proposal).
    # When user confirms at step 1 with non-empty segment in workspace, persist it
    # and return workspace_update so the frontend auto-advances to Creative.
    if step == 1 and is_confirm_trigger and not pending:
        seg = (workspace or {}).get("segment", {})
        if seg.get("attrs"):
            await add_message(session_id, "user", message)
            confirm_text = f"✅ Audience đã xác nhận! {len(seg['attrs'])} segments được chọn — em sẽ chuyển sang bước **Creative**."
            await add_message(session_id, "assistant", confirm_text)
            await update_form_state(session_id, "segment", seg)
            await alog(session_id, "confirm", {"auto_apply": True, "field": "segment", "attrs_count": len(seg["attrs"])})
            return AgentResponse(
                text=confirm_text,
                blocks=[{"type": "info", "text": "Workspace đã cập nhật: `segment`. Upload creative ở panel phải hoặc hỏi em để tiếp tục."}],
                meta=ResponseMeta(tool="workspace_confirmed", model="none", step=step),
                workspace_update={"field": "segment", "value": seg},
            )

    # ── Step 3 (Setup) auto-confirm ───────────────────────────────────────
    # setup-entry auto-applies zones to formState but does NOT set pending_proposal.
    # When user says "đồng ý/duyệt" at step 3 with zones already in workspace,
    # return deterministic confirm — do NOT let LLM handle it (it hallucinates step names).
    if step == 3 and is_confirm_trigger and not pending:
        setup_ws = (workspace or {}).get("setup", {})
        zone_ids = setup_ws.get("selectedZoneIds", [])
        if zone_ids:
            await add_message(session_id, "user", message)
            confirm_text = (
                f"✅ Zones đã được xác nhận! Em đã lưu **{len(zone_ids)} zones** vào chiến dịch. "
                f"Anh/chị bấm **Tiếp tục gắn creative** trong panel bên phải để chuyển sang bước gắn creative vào từng zone."
            )
            await add_message(session_id, "assistant", confirm_text)
            await update_form_state(session_id, "setup", setup_ws)
            await alog(session_id, "confirm", {"auto_apply": True, "field": "setup", "zone_count": len(zone_ids)})
            return AgentResponse(
                text=confirm_text,
                blocks=[{"type": "info", "text": f"Đã chọn {len(zone_ids)} zones. Bấm 'Tiếp tục gắn creative' ở bên phải để chuyển sang bước gán creative."}],
                meta=ResponseMeta(tool="workspace_confirmed", model="none", step=step),
                workspace_update={"field": "setup", "value": setup_ws},
                suggestions=[
                    {"label": "➕ Chọn thêm zone", "action": "prefill", "text": "Thêm zone "},
                    {"label": "🗑️ Bỏ zone",          "action": "prefill", "text": "Bỏ zone "},
                ],
            )

    if is_confirm_trigger and not pending:
        text = (
            "Hiện không có đề xuất nào đang chờ duyệt. "
            "Anh/chị hãy yêu cầu thay đổi cụ thể trước nhé."
        )
        await add_message(session_id, "user", message)
        await add_message(session_id, "assistant", text)
        return AgentResponse(
            text=text,
            blocks=[{"type": "info", "text": text}],
            meta=ResponseMeta(tool="workspace_clarification", model="none", step=step),
        )

    effective_workspace = workspace or {}

    if not effective_workspace:
        session = await get_or_create_session(session_id)
        effective_workspace = session.get("form_state", {})

    # ── Populate zone map cache for workspace snapshot enrichment ──────────
    global _zone_map_cache
    if not _zone_map_cache:
        try:
            all_zones = await get_all_zones()
            _zone_map_cache = {z["id"]: z for z in all_zones}
        except Exception:
            _zone_map_cache = {}

    step_label = STEP_NAMES[step] if 0 <= step < len(STEP_NAMES) else f"Bước {step}"

    # ── Build message array ───────────────────────────────────────────────────
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": campaign_time_system_message()},
        {"role": "system", "content": _build_workspace_snapshot(effective_workspace, confirmed_steps or [], current_step=step)},
    ]

    workspace_diff = _build_workspace_diff(workspace_events or [])
    if workspace_diff:
        messages.append({"role": "system", "content": workspace_diff})

    messages.extend(await get_history(session_id))
    messages.append({"role": "user", "content": message})

    # ── Log LLM call context (stdout + MongoDB) ─────────────────────────────
    await alog(session_id, "llm_call_start", {
        "handler": "freeform",
        "step": step_label,
        "messages_count": len(messages),
        "history_turns": len([m for m in messages if m["role"] in ("user", "assistant")]),
        "tools": [t["function"]["name"] for t in TOOL_DEFINITIONS],
    })

    # ── Call LLM ─────────────────────────────────────────────────────────────
    try:
        response = await asyncio.to_thread(
            chat_completion, messages=messages, tools=TOOL_DEFINITIONS
        )
        msg = response.choices[0].message
        raw_content = msg.content or ""
        tool_calls_names = [tc.function.name for tc in (msg.tool_calls or [])]
        await alog(session_id, "llm_call_done", {
            "finish_reason": response.choices[0].finish_reason,
            "has_content": bool(raw_content),
            "content_len": len(raw_content),
            "tool_calls": tool_calls_names,
            "content_preview": raw_content[:200],
        })

        # ── Handle token limit exhaustion ─────────────────────────────────────
        # finish_reason='length' means the LLM ran out of output tokens and
        # returned nothing useful. Retry with a truncated context (system + last
        # 6 turns) using force_text so we always get a response.
        if response.choices[0].finish_reason == "length" and not msg.tool_calls:
            await alog(session_id, "warn", {
                "event": "llm_length_truncated",
                "original_msgs": len(messages),
                "note": "Retrying with shortened context (last 6 turns)",
            })
            short_msgs = [messages[0]] + messages[-6:]  # system prompt + last 6 turns
            try:
                retry_resp = await asyncio.to_thread(
                    force_text_completion, messages=short_msgs
                )
                retry_content = sanitize_response(retry_resp.choices[0].message.content or "")
                raw_content = retry_content or (
                    "Xin lỗi anh/chị, em bị quá tải ngữ cảnh ở tin nhắn này. "
                    "Anh/chị có thể hỏi ngắn hơn hoặc bắt đầu lại không ạ?"
                )
            except Exception as retry_err:
                await alog(session_id, "error", {"event": "length_retry_failed", "error": str(retry_err)})
                raw_content = (
                    "Xin lỗi anh/chị, em đang gặp giới hạn xử lý. "
                    "Anh/chị thử hỏi ngắn gọn hơn hoặc tóm tắt câu hỏi giúp em nhé!"
                )
            msg.tool_calls = None  # ensure we go to freeform_chat path below

        # ── Handle tool calls ─────────────────────────────────────────────────
        if msg.tool_calls:
            tool_results = []
            used_tool = msg.tool_calls[0].function.name

            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)

                # ── Auto-inject brief dates into zone tools ───────────────────
                # The LLM may forget to pass start_date/end_date even though the
                # tool definition says to. Inject from workspace so conflict
                # detection always runs with the campaign date range.
                if tc.function.name in ("get_zone_list", "search_zones"):
                    brief = (workspace or {}).get("brief") or {}
                    if not args.get("start_date") and brief.get("startDate"):
                        args["start_date"] = brief["startDate"]
                    if not args.get("end_date") and brief.get("endDate"):
                        args["end_date"] = brief["endDate"]

                await alog(session_id, "tool_call", {
                    "tool": tc.function.name,
                    "args": {k: str(v)[:100] for k, v in args.items()},
                })
                t_tool = time.time()
                result = await execute_tool(tc.function.name, args)
                await alog(session_id, "tool_result", {
                    "tool": tc.function.name,
                    "duration_ms": int((time.time() - t_tool) * 1000),
                    "result_len": len(json.dumps(result)) if result else 0,
                    "result_preview": json.dumps(result, ensure_ascii=False)[:300],
                })
                tool_results.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # ── Handle update_workspace specially (proposal flow) ─────────────
            if used_tool == "update_workspace":
                # Extract proposed changes from the first tool call
                first_args = json.loads(msg.tool_calls[0].function.arguments)
                field = first_args.get("field", "")
                value = first_args.get("value")
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except Exception:
                        pass

                # Validate and rebuild the model payload from authoritative
                # catalogs/current workspace before it becomes approvable.
                from workspace.service import create_proposal, get_workspace
                canonical = await get_workspace(session_id)
                try:
                    field, value, reason = await resolve_legacy_update(
                        field, value, canonical, first_args.get("reason", ""),
                        source_message=message,
                    )
                except InvalidWorkspaceIntent as exc:
                    reply = f"Em chưa thể tạo đề xuất an toàn: {exc}"
                    await add_message(session_id, "user", message)
                    await add_message(session_id, "assistant", reply)
                    return AgentResponse(
                        text=reply,
                        blocks=[],
                        meta=ResponseMeta(
                            tool="workspace_clarification", model="minimax", step=step
                        ),
                        workspace_update=None,
                    )

                first_args.update({"field": field, "value": value, "reason": reason})

                # Build a deterministic confirmation message — skip 2 LLM calls entirely
                # (MiniMax consistently returns empty on the second call after update_workspace)
                reply = _build_update_summary(field, value, reason)
                await alog(session_id, "info", {"update_workspace": "skipped_llm_summary", "field": field})

                step_index = _field_to_step_index(field)
                is_locked = step_index in (confirmed_steps or [])

                # Build cascading reset warning
                warning = ""
                if is_locked and step_index >= 0:
                    downstream = [_STEP_NAMES_VI[i] for i in range(step_index + 1, len(_STEP_NAMES_VI))]
                    if downstream:
                        warning = f"⚠️ Bước {_STEP_NAMES_VI[step_index]} đã được xác nhận. Nếu thay đổi, các bước sau ({', '.join(downstream)}) sẽ bị reset."

                # Store a durable proposal. Even if this tool call was triggered
                # by a bare confirmation phrase, it is never auto-applied: only
                # confirmation of an already-visible proposal may mutate state.
                proposal = await create_proposal(
                    session_id, field, value,
                    base_revision=canonical["revision"],
                    actor="legacy_campaign_copilot",
                    reason=reason,
                )
                first_args.update({
                    "proposal_id": proposal["proposal_id"],
                    "base_revision": proposal["base_revision"],
                    "affected_artifacts": proposal["affected_artifacts"],
                })
                await set_pending_proposal(session_id, first_args)
                await alog(session_id, "info", {"pending_proposal_stored": True, "field": field, "is_locked": is_locked})

                await add_message(session_id, "user", message)
                await add_message(session_id, "assistant", reply)

                return AgentResponse(
                    text=reply,
                    blocks=[{
                        "type": "workspace_proposal",
                        "changes": first_args,
                        "is_locked": is_locked,
                        "warning": warning,
                    }],
                    meta=ResponseMeta(tool="update_workspace", model="minimax", step=step),
                    workspace_update=None,  # Not applied yet — waiting for user confirmation
                    suggestions=_WORKSPACE_SUGGESTIONS.get(field, []),
                )

            # ── Normal tool call: second LLM call with tool results ───────────
            messages.append({
                "role": "assistant",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            messages.extend(tool_results)

            # Attempt 1: normal second call (model summarises tool results)
            await alog(session_id, "llm_call_start", {"attempt": 1, "purpose": f"{used_tool}_summary"})
            t1 = time.time()
            final = await asyncio.to_thread(
                chat_completion, messages=messages, tools=TOOL_DEFINITIONS
            )
            reply = sanitize_response(final.choices[0].message.content or "")
            await alog(session_id, "llm_call_done", {"attempt": 1, "duration_ms": int((time.time()-t1)*1000), "reply_len": len(reply), "empty": not reply})

            # Attempt 2: force text — do NOT pass tools so model can't call them again
            if not reply:
                from metrics import FALLBACK_LEVEL
                FALLBACK_LEVEL.labels(level="2").inc()
                await alog(session_id, "fallback", {"attempt": 2, "tool": used_tool, "reason": "attempt1_empty"})
                t2 = time.time()
                forced = await asyncio.to_thread(
                    force_text_completion, messages=messages
                )  # no tools!
                reply = sanitize_response(forced.choices[0].message.content or "")
                await alog(session_id, "llm_call_done", {"attempt": 2, "duration_ms": int((time.time()-t2)*1000), "reply_len": len(reply), "empty": not reply})

            # Attempt 3: fully deterministic per-tool fallback (no LLM at all)
            if not reply:
                _TOOL_FALLBACKS = {
                    "get_audience_list": "Đã tìm thấy các đối tượng phù hợp. Anh/Chị xem danh sách ở panel phải và chọn nhé!",
                    "search_zones": "Đã tìm thấy các zone phù hợp. Anh/Chị xem danh sách ở panel phải và chọn nhé!",
                    "update_workspace": "Workspace đã được cập nhật. Anh/Chị xem thông tin bên phải và xác nhận nhé!",
                }
                reply = _TOOL_FALLBACKS.get(
                    used_tool,
                    f"Em đã xử lý xong ({used_tool}). Anh/Chị hỏi thêm hoặc xem thông tin ở panel phải nhé!",
                )
                from metrics import FALLBACK_LEVEL as _FL3
                _FL3.labels(level="3").inc()
                await alog(session_id, "fallback", {"attempt": 3, "tool": used_tool, "using": "hardcoded", "reply": reply})

        else:
            reply = sanitize_response(raw_content)
            used_tool = "freeform_chat"
            # Warn if sanitization stripped significant content
            if len(reply) != len(raw_content):
                await alog(session_id, "warn", {
                    "event": "content_sanitized",
                    "original_len": len(raw_content),
                    "sanitized_len": len(reply),
                    "stripped_think": "<think>" in raw_content,
                    "stripped_xml": any(tag in raw_content for tag in ["minimax:tool_call", "<invoke", "</invoke"]),
                })
            # ── Clear stale pending_proposal ──────────────────────────────────
            # After a freeform discussion (no update_workspace call), the old pending
            # may be outdated. Clear it so user confirming later always goes back
            # through the LLM which will re-call update_workspace with fresh values.
            await clear_pending_proposal(session_id)

        await alog(session_id, "reply", {
            "tool": used_tool,
            "reply_len": len(reply),
            "reply_preview": reply[:200],
        })
        await add_message(session_id, "user", message)
        await add_message(session_id, "assistant", reply)

        return AgentResponse(
            text=reply,
            blocks=[],
            meta=ResponseMeta(tool=used_tool, model="minimax", step=step),
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        await alog(session_id, "error", {
            "handler": "freeform",
            "error": str(e),
            "traceback": tb[-600:],  # last 600 chars of traceback
        })
        from provider_resilience import PROVIDER_UNAVAILABLE_MESSAGE
        return AgentResponse(
            text=PROVIDER_UNAVAILABLE_MESSAGE,
            blocks=[],
            meta=ResponseMeta(tool="freeform_chat", model="none", step=step),
        )
