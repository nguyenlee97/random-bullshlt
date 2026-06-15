"""
Brief handler — Step 0.
LLM validates and summarizes the brief, extracts audience hints.
"""
from models import AgentResponse, BriefData, ResponseMeta
from llm import simple_generate, parse_json_response
from session import get_or_create_session, update_form_state, log_event
from prompts.brief import BRIEF_SYSTEM, BRIEF_USER


async def handle_brief(brief: BriefData, session_id: str) -> AgentResponse:
    # ── Validate required fields ──────────────────────────────────────────────
    errors = []
    if not brief.brand.strip():
        errors.append("Brand không được để trống.")
    if brief.budget <= 0:
        errors.append("Ngân sách phải lớn hơn 0.")
    if not brief.startDate or not brief.endDate:
        errors.append("Vui lòng chọn thời gian chạy.")

    if errors:
        return AgentResponse(
            text="⚠ Brief có lỗi:\n" + "\n".join(f"- {e}" for e in errors),
            blocks=[{"type": "info", "text": "Anh/Chị kiểm tra lại thông tin ở panel phải nhé!"}],
            meta=ResponseMeta(tool="brief_validate", model="none", step=0),
        )

    # ── Store brief in session ────────────────────────────────────────────────
    brief_dict = brief.model_dump()
    await update_form_state(session_id, "brief", brief_dict)

    # ── LLM analysis ─────────────────────────────────────────────────────────
    prompt = BRIEF_USER.format(
        brand=brief.brand,
        objective=brief.objective,
        kpi=brief.kpi or "(chưa chọn)",
        budget=brief.budget,
        start=brief.startDate,
        end=brief.endDate,
        notes=brief.notes or "(trống)",
    )

    try:
        raw = simple_generate(BRIEF_SYSTEM, prompt)
        data = parse_json_response(raw)
        await log_event(session_id, "llm_call", {"handler": "brief", "response": raw[:500]})
    except Exception as e:
        await log_event(session_id, "error", {"handler": "brief", "error": str(e)})
        data = {}

    summary = data.get("summary", f"Chiến dịch {brief.objective} cho {brief.brand}, ngân sách {brief.budget}M VND.")
    raw_hint = data.get("audience_hint", "")
    audience_hint = ", ".join(raw_hint) if isinstance(raw_hint, list) else (raw_hint or "")
    warnings = data.get("warnings", [])
    suggested_kpis = data.get("suggested_kpis", [])

    # ── Build blocks ──────────────────────────────────────────────────────────
    info_rows = [
        ["Brand", brief.brand],
        ["Objective", brief.objective.capitalize()],
        ["KPI", brief.kpi or "—"],
        ["Ngân sách", f"{brief.budget:,.0f} triệu VND"],
        ["Thời gian", f"{brief.startDate} → {brief.endDate}"],
        ["Audience hint", audience_hint or "—"],
    ]
    if suggested_kpis:
        info_rows.append(["KPI đề xuất thêm", ", ".join(suggested_kpis)])

    blocks = [
        {
            "type": "table",
            "title": "📋 Tóm tắt Brief",
            "columns": ["Thông tin", "Giá trị"],
            "rows": info_rows,
        }
    ]

    if warnings:
        blocks.append({
            "type": "info",
            "text": "⚠ Lưu ý:\n" + "\n".join(f"- {w}" for w in warnings),
        })

    blocks.append({
        "type": "info",
        "text": "✅ Anh/Chị tiếp tục bằng cách upload creative ở bước tiếp theo!",
    })

    return AgentResponse(
        text=f"✅ {summary}",
        blocks=blocks,
        meta=ResponseMeta(tool="brief_handler", model="minimax", step=0),
    )
