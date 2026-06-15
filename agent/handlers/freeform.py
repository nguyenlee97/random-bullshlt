"""
Free-form chat handler — LLM + OpenAI tool calling.
Handles any text message not matched by form handlers.
"""
import json
from models import AgentResponse, ResponseMeta
from llm import chat_completion
from session import get_or_create_session, get_history, add_message, log_event
from prompts.system import SYSTEM_PROMPT, STEP_NAMES

from tools.registry import TOOL_DEFINITIONS, execute_tool
from handlers.audience import handle_targeting_autopick

# Intent keywords that trigger targeting auto-pick directly
_AUTOPICK_TRIGGERS = [
    "tự động chọn targeting",
    "agent chọn targeting",
    "chọn targeting giúp",
    "chọn giúp targeting",
    "targeting phù hợp",
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


async def handle_freeform(message: str, step: int, session_id: str) -> AgentResponse:
    # ── Check for targeting auto-pick intent ──────────────────────────────────
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in _AUTOPICK_TRIGGERS):
        return await handle_targeting_autopick(session_id)

    # ── Check for campaign reset intent ──────────────────────────────────────
    if any(kw in msg_lower for kw in _RESET_TRIGGERS):
        return AgentResponse(
            text="Được rồi! Em sẽ giúp anh bắt đầu chiến dịch mới. Anh bấm nút bên dưới để xóa toàn bộ thông tin và quay lại bước Brief nhé!",
            blocks=[{
                "type": "action_reset",
                "text": "Tất cả dữ liệu (Brief, Creative, Audience, Setup) sẽ được xóa và anh bắt đầu lại từ đầu.",
            }],
            meta=ResponseMeta(tool="reset_intent", model="none", step=step),
        )

    # ── Build rich campaign context ───────────────────────────────────────────
    session = await get_or_create_session(session_id)
    form = session.get("form_state", {})
    brief = form.get("brief", {})

    step_label = STEP_NAMES[step] if 0 <= step < len(STEP_NAMES) else f"Bước {step}"

    ctx_lines = [
        "=== TRẠNG THÁI CHIẾN DỊCH HIỆN TẠI ===",
        f"Bước hiện tại: {step_label}",
        "",
    ]

    # Brief
    if brief:
        OBJECTIVE_VI = {
            "awareness": "Awareness — Nhận diện thương hiệu",
            "consideration": "Consideration — Tăng quan tâm",
            "conversion": "Conversion — Chuyển đổi",
            "retention": "Retention — Giữ chân khách hàng",
        }
        ctx_lines.append("--- Brief chiến dịch ---")
        ctx_lines.append(f"Brand       : {brief.get('brand', '?')}")
        ctx_lines.append(f"Objective   : {OBJECTIVE_VI.get(brief.get('objective',''), brief.get('objective','?'))}")
        ctx_lines.append(f"KPI         : {brief.get('kpi') or '(chưa chọn)'}")
        ctx_lines.append(f"Budget      : {brief.get('budget', 0):,.0f} triệu VND")
        ctx_lines.append(f"Thời gian   : {brief.get('startDate','?')} → {brief.get('endDate','?')}")
        if brief.get('notes'):
            ctx_lines.append(f"Ghi chú     : {brief['notes']}")
        ctx_lines.append("")

    # Audience
    segment = form.get("segment", {})
    attrs = segment.get("attrs", [])
    if attrs:
        ctx_lines.append("--- Audience đã chọn ---")
        ctx_lines.append(f"Số segments : {len(attrs)}")
        ctx_lines.append(f"Audience size ước tính: {segment.get('size', 0):,} người dùng")
        names = [a.get('name', '') for a in attrs[:8] if a.get('name')]
        if names:
            ctx_lines.append(f"Segments    : {', '.join(names)}" + (" ..." if len(attrs) > 8 else ""))
        ctx_lines.append("")

    # Setup — recommended/selected zones (stored as reco_zones in session)
    reco_zones = form.get("reco_zones", [])
    if reco_zones:
        ctx_lines.append("--- Ad Zones (AI gợi ý) ---")
        zone_ids = [str(z.get('id') or z.get('name', '')) for z in reco_zones[:6]]
        ctx_lines.append(f"Zones       : {', '.join(zone_ids)}" + (" ..." if len(reco_zones) > 6 else ""))
        ctx_lines.append("")

    # Orders
    if session.get("created_order_ids"):
        ctx_lines.append(f"Orders đã tạo: {', '.join(session['created_order_ids'])}")
        ctx_lines.append("")

    ctx_lines.append("QUAN TRỌNG: Dùng thông tin trên để trả lời — KHÔNG hỏi lại các thông tin đã có (objective, brand, budget, ...).")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": "\n".join(ctx_lines)},
    ]
    messages.extend(await get_history(session_id))
    messages.append({"role": "user", "content": message})

    # ── Call LLM ─────────────────────────────────────────────────────────────
    try:
        response = chat_completion(messages=messages, tools=TOOL_DEFINITIONS)
        msg = response.choices[0].message

        # ── Handle tool calls ─────────────────────────────────────────────────
        if msg.tool_calls:
            tool_results = []
            used_tool = msg.tool_calls[0].function.name

            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                result = await execute_tool(tc.function.name, args)
                await log_event(session_id, "tool_call", {"tool": tc.function.name, "args": args})
                tool_results.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # Second LLM call with tool results
            messages.append({
                "role": "assistant",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            messages.extend(tool_results)
            final = chat_completion(messages=messages)
            reply = final.choices[0].message.content or ""
        else:
            reply = msg.content or ""
            used_tool = "freeform_chat"

        await log_event(session_id, "llm_call", {"handler": "freeform", "tool": used_tool, "reply_len": len(reply)})
        await add_message(session_id, "user", message)
        await add_message(session_id, "assistant", reply)

        return AgentResponse(
            text=reply,
            blocks=[],
            meta=ResponseMeta(tool=used_tool, model="minimax", step=step),
        )

    except Exception as e:
        await log_event(session_id, "error", {"handler": "freeform", "error": str(e)})
        return AgentResponse(
            text=f"Em gặp lỗi khi xử lý: {str(e)[:100]}. Anh thử lại nhé!",
            blocks=[],
            meta=ResponseMeta(tool="freeform_chat", model="none", step=step),
        )
