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
    AUDIENCE_ENTRY_SYSTEM, AUDIENCE_ENTRY_USER,
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


def _normalize_dmp_attr(seg: dict) -> dict:
    """Normalize a raw MongoDB segment doc into the shape AudienceStep.jsx expects.
    
    AudienceStep needs: _uid, code, name, category, type, est_size, sizeMin, sizeMax, reason.
    Raw docs have: fullLabel, _id, type, sizeMin, sizeMax, sizeRaw, reason.
    """
    s_min = seg.get("sizeMin") or 0
    s_max = seg.get("sizeMax") or 0
    est_size = (s_min + s_max) // 2 if (s_min and s_max) else (s_min or s_max)
    full_label = seg.get("fullLabel") or seg.get("name", "")
    raw_id = seg.get("_id")
    return {
        **seg,
        # Fields required by AudienceStep getUid() and isSelected()
        "_uid": str(raw_id) if raw_id else full_label,
        "name": full_label,
        "code": seg.get("code", ""),
        "category": seg.get("category", seg.get("type", "")),
        "est_size": est_size,
        # Keep originals for compatibility
        "fullLabel": full_label,
    }


async def handle_audience(segment: SegmentData, session_id: str) -> AgentResponse:
    attrs = segment.attrs  # list of raw DMP attribute dicts (with _id)

    if not attrs:
        return AgentResponse(
            text="⚠ Anh/Chị chưa chọn audience segment nào.",
            blocks=[{"type": "info", "text": "Vui lòng chọn ít nhất 1 segment từ thư viện DMP."}],
            meta=ResponseMeta(tool="audience_handler", model="none", step=2),
        )

    # ── Calculate audience size ───────────────────────────────────────────────
    total_size = _calc_audience_size(attrs)

    # ── Store in session ──────────────────────────────────────────────────────
    await update_form_state(session_id, "segment", {"attrs": attrs, "size": total_size})

    # ── Get brief context ─────────────────────────────────────────────────────
    session = await get_or_create_session(session_id)
    brief = session.get("form_state", {}).get("brief", {})

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
    brief = session.get("form_state", {}).get("brief", {})
    segment = session.get("form_state", {}).get("segment", {})

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
            "text": "✅ Anh/Chị có thể điều chỉnh ở panel phải hoặc bấm tiếp tục để chấp nhận.",
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
    brief = session.get("form_state", {}).get("brief", {})

    # If brief not set yet, return empty gracefully
    if not brief.get("brand"):
        return {"recommendations": [], "total_segments": 0, "note": "brief_not_set"}

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


async def handle_audience_entry(session_id: str) -> dict:
    """
    GET /api/agent/audience-entry?session_id=xxx
    Proactively generates full audience recommendation when user enters step 1.
    Returns a chat-ready AgentResponse dict with blocks for Targeting + DMP Segments.
    If brief lacks info → returns need_more_info questions instead.
    """
    session = await get_or_create_session(session_id)
    brief = session.get("form_state", {}).get("brief", {})

    if not brief.get("brand"):
        return {"skip": True, "reason": "brief_not_set"}

    # Check if audience already set (re-entry) → skip
    existing_segment = session.get("form_state", {}).get("segment", {})
    if existing_segment.get("attrs"):
        return {"skip": True, "reason": "audience_already_set"}

    # Fetch real targeting options + DMP segments
    options = await get_targeting_options()
    all_segs = await get_all_segments(limit=200)
    # Build enriched segment list for LLM: "fullLabel [Type]" format
    # Helps LLM match Vietnamese brief keywords to English segment names
    seg_labels = [
        f"{s.get('fullLabel') or s.get('name', '')} [{s.get('type', '')}]"
        for s in all_segs
        if s.get("fullLabel") or s.get("name")
    ]

    prompt = AUDIENCE_ENTRY_USER.format(
        brand=brief.get("brand", "?"),
        objective=brief.get("objective", "?"),
        kpi=brief.get("kpi", "(chưa có)"),
        notes=brief.get("notes", "(trống)"),
        options_json=json.dumps(options, ensure_ascii=False),
        segments_json=json.dumps(seg_labels[:200], ensure_ascii=False),  # send up to 200
    )

    try:
        raw = simple_generate(AUDIENCE_ENTRY_SYSTEM, prompt)
        data = parse_json_response(raw)
        await log_event(session_id, "llm_call", {"handler": "audience_entry", "response": raw[:500]})
    except Exception as e:
        await log_event(session_id, "error", {"handler": "audience_entry", "error": str(e)})
        return {"skip": True, "reason": f"llm_error: {str(e)}"}

    need_more = data.get("need_more_info", False)

    # Build label maps (exact + case-insensitive fallback for LLM output variation)
    label_map = {}
    label_map_lower = {}
    for s in all_segs:
        lbl = s.get("fullLabel") or s.get("name", "")
        if lbl:
            label_map[lbl] = s
            label_map_lower[lbl.lower().strip()] = s

    def _lookup_seg(full_label: str) -> dict | None:
        # 1. Exact match
        if full_label in label_map:
            return label_map[full_label]
        # 2. Case-insensitive match
        low = full_label.lower().strip()
        if low in label_map_lower:
            return label_map_lower[low]
        # 3. Substring match — DB label contains LLM label (e.g. "Real estate" in "Real estate (industry)")
        for db_label_low, seg in label_map_lower.items():
            if low in db_label_low or db_label_low.startswith(low):
                return seg
        # 4. Word-overlap match (>= 2 words in common)
        llm_words = set(low.split())
        best_seg, best_score = None, 0
        for db_label_low, seg in label_map_lower.items():
            db_words = set(db_label_low.split())
            score = len(llm_words & db_words)
            if score >= 2 and score > best_score:
                best_seg, best_score = seg, score
        return best_seg

    # ── Case 1: Need more info from user ──────────────────────────────────────
    if need_more:
        questions = data.get("questions", [
            "Anh/chị muốn nhắm đến độ tuổi và giới tính nào?",
            "Khu vực tập trung (TP.HCM, Hà Nội, toàn quốc...)?",
        ])
        dmp_recs = data.get("dmp_segments", [])
        enriched_dmp = [
            _normalize_dmp_attr({**_lookup_seg(r["fullLabel"]), "reason": r.get("reason", "")})
            for r in dmp_recs if r.get("fullLabel") and _lookup_seg(r["fullLabel"])
        ]
        blocks = [{"type": "info", "text": "Em cần thêm thông tin để gợi ý targeting chính xác:\n\n" + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))}]
        if enriched_dmp:
            rows = [[s.get("fullLabel", "?"), s.get("type", ""), s.get("sizeRaw", ""), s.get("reason", "")] for s in enriched_dmp[:6]]
            blocks.append({"type": "table", "title": "💡 DMP Segments sơ bộ gợi ý", "columns": ["Segment", "Loại", "Size ước tính", "Lý do"], "rows": rows})
        return {
            "skip": False,
            "need_more_info": True,
            "text": f"Dựa trên brief **{brief.get('brand')}**, em cần thêm vài thông tin để gợi ý audience chính xác hơn:",
            "blocks": blocks,
            "meta": {"tool": "audience_entry", "model": "minimax", "step": 1},
        }

    # ── Case 2: Full recommendation ───────────────────────────────────────────
    targeting = data.get("targeting", {})
    targeting_reasoning = data.get("targeting_reasoning", [])
    dmp_recs = data.get("dmp_segments", [])
    advanced_note = data.get("advanced_targeting_note", "")

    label_map = label_map  # already built above
    enriched_dmp = [
        _normalize_dmp_attr({**_lookup_seg(r["fullLabel"]), "reason": r.get("reason", "")})
        for r in dmp_recs if r.get("fullLabel") and _lookup_seg(r["fullLabel"])
    ]

    # ── Keyword fallback when LLM segment names don't match DB ────────────────
    # Score all_segs by word overlap with brief notes+brand and pick top 6.
    if not enriched_dmp:
        await log_event(session_id, "warn", {
            "handler": "audience_entry",
            "event": "enriched_dmp_empty",
            "llm_recs": [r.get("fullLabel", "") for r in dmp_recs],
            "note": "Using keyword fallback"
        })
        # Build keyword set from brief
        search_text = " ".join([
            brief.get("brand", ""),
            brief.get("notes", ""),
            brief.get("objective", ""),
        ]).lower()
        kw_set = set(w for w in search_text.split() if len(w) > 3)

        def _score_seg(seg: dict) -> int:
            lbl = (seg.get("fullLabel") or seg.get("name", "")).lower()
            return sum(1 for kw in kw_set if kw in lbl)

        # Sort by keyword overlap, then by size (sizeMax) as tiebreaker
        scored = sorted(all_segs, key=lambda s: (_score_seg(s), s.get("sizeMax", 0) or 0), reverse=True)
        fallback_segs = scored[:6]
        enriched_dmp = [
            _normalize_dmp_attr({**s, "reason": "Được chọn tự động dựa trên brief (fallback)"})
            for s in fallback_segs
        ]

    blocks = []

    # Block 1: Targeting Parameters table
    target_rows = [
        [r["field"].capitalize(), ", ".join(r.get("picks", [])), r.get("reason", "")]
        for r in targeting_reasoning if r.get("picks")
    ]
    if target_rows:
        blocks.append({
            "type": "table",
            "title": "🎯 Targeting Parameters gợi ý",
            "columns": ["Nhóm", "Giá trị đề xuất", "Lý do"],
            "rows": target_rows,
        })

    # Block 2: DMP Segments table
    if enriched_dmp:
        dmp_rows = [
            [s.get("fullLabel", "?"), s.get("type", ""), s.get("sizeRaw", "—"), s.get("reason", "")]
            for s in enriched_dmp
        ]
        blocks.append({
            "type": "table",
            "title": "👥 DMP Audience Segments gợi ý",
            "columns": ["Segment", "Loại", "Size ước tính", "Lý do phù hợp"],
            "rows": dmp_rows,
        })

    # Block 3: Advanced targeting note (optional)
    if advanced_note:
        blocks.append({"type": "info", "text": f"💡 Advanced Targeting: {advanced_note}"})

    # Block 4: Workspace proposal — renders Đồng ý / Bỏ qua buttons in chat
    # Compute audience size using same union-discount model as handle_audience
    audience_size = _calc_audience_size(enriched_dmp)
    blocks.append({
        "type": "workspace_proposal",
        "changes": {
            "field": "segment",
            "value": {
                "attrs": enriched_dmp,
                "targeting": targeting,
                "size": audience_size,
            },
            "reason": f"AI gợi ý {len(enriched_dmp)} segments phù hợp với brief {brief.get('brand', '')}",
        },
        "is_locked": False,
        "warning": "",
        "instruction": "Anh/chị bấm **Đồng ý** để áp dụng tất cả segments, hoặc vào panel phải để chọn/bỏ chọn từng segment trước khi xác nhận.",
    })

    await log_event(session_id, "audience_entry", {
        "brand": brief.get("brand"),
        "dmp_count": len(enriched_dmp),
        "audience_size": audience_size,
    })

    return {
        "skip": False,
        "need_more_info": False,
        "text": f"Dựa trên brief **{brief.get('brand')}** ({brief.get('objective', 'awareness')}), em gợi ý audience như sau:",
        "blocks": blocks,
        "meta": {"tool": "audience_entry", "model": "minimax", "step": 1},
    }


