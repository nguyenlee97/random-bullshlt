"""
Audience handler — Step 2.
Phase 1: DMP segment validation + LLM reasoning + audience size calc.
Phase 2: Targeting auto-pick (LLM suggests targeting fields).
"""
import json
from models import AgentResponse, SegmentData, ResponseMeta
from llm import simple_generate, parse_json_response
from session import get_or_create_session, update_form_state, log_event
from prompts.audience import (
    AUDIENCE_SYSTEM, AUDIENCE_USER,
    TARGETING_AUTOPICK_SYSTEM, TARGETING_AUTOPICK_USER,
    DMP_RECOMMEND_SYSTEM, DMP_RECOMMEND_USER,
)
from tools.targeting_options import get_targeting_options
from tools.audience_library import get_all_segments


def _calc_audience_size(attrs: list[dict]) -> int:
    """Union model: sort by size desc, 30% overlap discount per additional segment."""
    sizes = []
    for a in attrs:
        s_min = a.get("sizeMin") or 0
        s_max = a.get("sizeMax") or 0
        avg = (s_min + s_max) // 2 if (s_min and s_max) else (s_min or s_max)
        if avg > 0:
            sizes.append(avg)
    if not sizes:
        return 0
    sizes.sort(reverse=True)
    total = sum(s * (0.7 ** i) for i, s in enumerate(sizes))
    return round(total)


async def handle_audience(segment: SegmentData, session_id: str) -> AgentResponse:
    attrs = segment.attrs  # list of raw DMP attribute dicts (with _id)

    if not attrs:
        return AgentResponse(
            text="⚠ Anh chưa chọn audience segment nào.",
            blocks=[{"type": "info", "text": "Vui lòng chọn ít nhất 1 segment từ thư viện DMP."}],
            meta=ResponseMeta(tool="audience_handler", model="none", step=2),
        )

    # ── Calculate audience size ───────────────────────────────────────────────
    total_size = _calc_audience_size(attrs)

    # ── Store in session ──────────────────────────────────────────────────────
    await update_form_state(session_id, "segment", {"attrs": attrs, "size": total_size})

    # ── Get brief context ─────────────────────────────────────────────────────
    session = await get_or_create_session(session_id)
    brief = session["form_state"].get("brief", {})

    # ── LLM reasoning ────────────────────────────────────────────────────────
    segments_json = json.dumps(
        [{"label": a.get("fullLabel", a.get("name", "")), "type": a.get("type", "")} for a in attrs[:15]],
        ensure_ascii=False,
    )
    prompt = AUDIENCE_USER.format(
        brand=brief.get("brand", "?"),
        objective=brief.get("objective", "?"),
        kpi=brief.get("kpi", "?"),
        notes=brief.get("notes", "(trống)"),
        segments_json=segments_json,
        total_size=total_size,
    )

    try:
        raw = simple_generate(AUDIENCE_SYSTEM, prompt)
        data = parse_json_response(raw)
        await log_event(session_id, "llm_call", {"handler": "audience", "response": raw[:500]})
    except Exception as e:
        await log_event(session_id, "error", {"handler": "audience", "error": str(e)})
        data = {}

    reasoning = data.get("reasoning", "Audience segments phù hợp với mục tiêu chiến dịch.")
    match_quality = data.get("match_quality", "good")
    seg_notes = data.get("segment_notes", [])
    warnings = data.get("warnings", [])

    # ── Build blocks ──────────────────────────────────────────────────────────
    quality_emoji = {"excellent": "🟢", "good": "🟡", "fair": "🟠", "poor": "🔴"}.get(match_quality, "🟡")

    seg_rows = []
    for a in attrs:
        label = a.get("fullLabel") or a.get("name", "?")
        seg_type = a.get("type", "")
        s_min = a.get("sizeMin")
        s_max = a.get("sizeMax")
        size_str = a.get("sizeRaw") or (f"{s_min:,} - {s_max:,}" if s_min and s_max else "—")
        note = next((n["note"] for n in seg_notes if n.get("label") == label), "")
        seg_rows.append([label, seg_type, size_str, note])

    blocks: list[dict] = [
        {
            "type": "audience_size",
            "size": total_size,
            "breakdown": [
                {"label": a.get("fullLabel", a.get("name", "")), "size": ((a.get("sizeMin") or 0) + (a.get("sizeMax") or 0)) // 2}
                for a in attrs
            ],
        },
        {
            "type": "table",
            "title": f"👥 Audience Segments ({quality_emoji} {match_quality.capitalize()})",
            "columns": ["Segment", "Loại", "Size", "Nhận xét"],
            "rows": seg_rows,
        },
        {
            "type": "info",
            "text": f"💡 {reasoning}",
        },
    ]

    if warnings:
        blocks.append({"type": "info", "text": "⚠ " + " · ".join(warnings)})

    # NOTE: "Targeting nâng cao" prompt removed — targeting form is now in the UI panel.

    total_str = f"{total_size:,}"
    return AgentResponse(
        text=f"✅ Đã chọn **{len(attrs)} segments**, ước tính audience **{total_str} người**.",
        blocks=blocks,
        meta=ResponseMeta(tool="audience_handler", model="minimax", step=2),
    )


async def handle_targeting_autopick(session_id: str) -> AgentResponse:
    """
    LLM auto-picks targeting. Triggered when user sends:
    'Hãy tự động chọn targeting phù hợp nhất cho chiến dịch này'
    """
    session = await get_or_create_session(session_id)
    brief = session["form_state"].get("brief", {})
    segment = session["form_state"].get("segment", {})

    options = await get_targeting_options()
    seg_names = [a.get("fullLabel", a.get("name", "")) for a in segment.get("attrs", [])[:10]]

    prompt = TARGETING_AUTOPICK_USER.format(
        brand=brief.get("brand", "?"),
        objective=brief.get("objective", "?"),
        kpi=brief.get("kpi", "?"),
        notes=brief.get("notes", "(trống)"),
        segments=", ".join(seg_names) or "(chưa chọn)",
        options_json=json.dumps(options, ensure_ascii=False),
    )

    try:
        raw = simple_generate(TARGETING_AUTOPICK_SYSTEM, prompt)
        parsed = parse_json_response(raw)
        targeting = parsed.get("targeting", {})
        reasoning = parsed.get("reasoning", [])
        await log_event(session_id, "llm_call", {"handler": "targeting_autopick", "response": raw[:500]})
    except Exception as e:
        await log_event(session_id, "error", {"handler": "targeting_autopick", "error": str(e)})
        targeting = {
            "geo": ["Hà Nội", "TP.HCM", "Đà Nẵng"],
            "age": ["25-34", "35-44"],
            "gender": ["Male", "Female"],
            "deviceOS": [], "deviceBrand": [], "marital": [],
            "parental": [], "education": [], "income": [],
            "career": [], "interest": [], "weather": [],
        }
        reasoning = [{"field": "geo", "picks": ["Hà Nội", "TP.HCM", "Đà Nẵng"], "reason": "3 thị trường lớn nhất"}]

    await update_form_state(session_id, "targeting", targeting)

    reason_rows = [
        [r["field"], ", ".join(r.get("picks", [])), r.get("reason", "")]
        for r in reasoning if r.get("picks")
    ]

    blocks = [
        {
            "type": "table",
            "title": "🎯 Targeting được Agent đề xuất",
            "columns": ["Nhóm targeting", "Lựa chọn", "Lý do"],
            "rows": reason_rows,
        },
        {
            "type": "info",
            "text": "✅ Anh có thể điều chỉnh ở panel phải hoặc bấm tiếp tục để chấp nhận.",
        },
    ]

    return AgentResponse(
        text="✅ Em đã phân tích brief và chọn targeting phù hợp:",
        blocks=blocks,
        meta=ResponseMeta(tool="targeting_autopick", model="minimax", step=2),
    )

async def handle_dmp_recommend(session_id: str) -> dict:
    """
    GET /api/agent/dmp-recommend?session_id=xxx
    Returns AI-picked top segments based on real DMP data + brief context.
    Response: { recommendations: [{fullLabel, reason}], segments: [{fullLabel, segmentId, ...}] }
    """
    session = await get_or_create_session(session_id)
    brief = session["form_state"].get("brief", {})

    # Fetch real DMP segments
    all_segs = await get_all_segments(limit=200)
    await log_event(session_id, "api_call", {"endpoint": "GET /api/dmp/attributes", "count": len(all_segs)})

    # Build compact label list for LLM context
    seg_labels = [s.get("fullLabel") or s.get("name", "") for s in all_segs if s.get("fullLabel") or s.get("name")]
    seg_labels_json = json.dumps(seg_labels, ensure_ascii=False)

    prompt = DMP_RECOMMEND_USER.format(
        brand=brief.get("brand", "?"),
        objective=brief.get("objective", "?"),
        kpi=brief.get("kpi", "?"),
        notes=brief.get("notes", "(trống)"),
        segments_json=seg_labels_json,
    )

    try:
        raw = simple_generate(DMP_RECOMMEND_SYSTEM, prompt)
        data = parse_json_response(raw)
        recs = data.get("recommendations", [])
        await log_event(session_id, "llm_call", {"handler": "dmp_recommend", "count": len(recs)})
    except Exception as e:
        await log_event(session_id, "error", {"handler": "dmp_recommend", "error": str(e)})
        recs = []

    # Enrich recommendations with full segment metadata (sizeMin, sizeMax, segmentId, etc.)
    label_map = {(s.get("fullLabel") or s.get("name", "")): s for s in all_segs}
    enriched = []
    for rec in recs:
        label = rec.get("fullLabel", "")
        seg = label_map.get(label)
        if seg:
            enriched.append({**seg, "reason": rec.get("reason", "")})

    return {"recommendations": enriched, "total_segments": len(all_segs)}
