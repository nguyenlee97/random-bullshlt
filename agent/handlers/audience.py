"""
Audience handler — Step 2.
Phase 1: DMP segment validation + LLM reasoning + audience size calc.
Phase 2: Targeting auto-pick (LLM suggests targeting fields).
"""
import asyncio
import json
from pydantic import BaseModel, Field
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
from tools.audience_provenance import catalog_source


class _TargetingReason(BaseModel):
    field: str
    picks: list[str] = []
    reason: str = ""


class _TargetingSelection(BaseModel):
    targeting: dict[str, list[str]]
    reasoning: list[_TargetingReason] = Field(default_factory=list)



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


def _segment_identity(seg: dict) -> str:
    """Return one stable catalog identity across Mongo/API/RAG shapes."""
    source = seg.get("source") if isinstance(seg.get("source"), dict) else {}
    return str(
        seg.get("segmentId")
        or seg.get("_id")
        or source.get("segmentId")
        or source.get("recordId")
        or seg.get("fullLabel")
        or seg.get("name")
        or ""
    ).strip().casefold()


def _dedupe_segments(segments: list[dict]) -> list[dict]:
    """Preserve retrieval order while preventing duplicate catalog selections."""
    result: list[dict] = []
    seen: set[str] = set()
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        key = _segment_identity(segment)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(segment)
    return result


def _normalize_targeting(targeting: dict, options: dict) -> dict[str, list[str]]:
    """Keep only dimensions and exact values supplied by the backend catalog."""
    normalized: dict[str, list[str]] = {}
    if not isinstance(targeting, dict) or not isinstance(options, dict):
        return normalized

    for dimension, raw_values in targeting.items():
        raw_options = options.get(dimension)
        if raw_options is None:
            continue
        if isinstance(raw_options, dict):
            allowed = {
                value
                for grouped_values in raw_options.values()
                if isinstance(grouped_values, list)
                for value in grouped_values
            }
        elif isinstance(raw_options, list):
            allowed = set(raw_options)
        else:
            continue

        values = raw_values if isinstance(raw_values, list) else [raw_values]
        valid: list[str] = []
        for value in values:
            if isinstance(value, str) and value in allowed and value not in valid:
                valid.append(value)
        if valid:
            normalized[dimension] = valid
    return normalized


async def handle_audience(segment: SegmentData, session_id: str) -> AgentResponse:
    attrs = segment.attrs  # list of raw DMP attribute dicts (with _id)

    if not attrs:
        return AgentResponse(
            text="⚠ Anh/Chị chưa chọn audience segment nào.",
            blocks=[{"type": "info", "text": "Vui lòng chọn ít nhất 1 segment từ thư viện DMP."}],
            meta=ResponseMeta(tool="audience_validate", model="none", step=1),
        )

    # ── Calculate audience size ───────────────────────────────────────────────
    total_size = _calc_audience_size(attrs)

    # ── Store in session ──────────────────────────────────────────────────────
    await update_form_state(session_id, "segment", {"attrs": attrs, "size": total_size})
    if segment.targeting:
        # Targeting is a separate canonical artifact. Persist it independently
        # so an Autopilot edit replans from derive_targeting instead of hiding
        # the values inside the audience object.
        await update_form_state(session_id, "targeting", segment.targeting)

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
        raw = await asyncio.to_thread(simple_generate, AUDIENCE_SYSTEM, prompt)
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


async def _recommend_targeting(
    session_id: str,
    brief: dict,
    options: dict,
    segments: list[dict] | None = None,
) -> tuple[dict[str, list[str]], list[dict], str]:
    """Select catalog-valid targeting for every Guided entry point."""
    seg_names = [
        item.get("fullLabel", item.get("name", ""))
        for item in (segments or [])[:10]
    ]
    prompt = TARGETING_AUTOPICK_USER.format(
        brand=brief.get("brand", "?"),
        objective=brief.get("objective", "?"),
        kpi=brief.get("kpi", "?"),
        notes=brief.get("notes", "(trống)"),
        segments=", ".join(seg_names) or "(chưa chọn)",
        options_json=json.dumps(options, ensure_ascii=False),
    )

    selected_model = "minimax"
    try:
        from config import config as _cfg
        from graph.structured import structured

        role = "critic" if (
            _cfg.CRITIC_BASE_URL and _cfg.CRITIC_MODEL and _cfg.CRITIC_API_KEY
        ) else "generator"
        output, tokens = await asyncio.to_thread(
            structured,
            [
                {"role": "system", "content": TARGETING_AUTOPICK_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            _TargetingSelection,
            "targeting_selection",
            role,
            1400,
        )
        parsed = output.model_dump()
        targeting = _normalize_targeting(parsed.get("targeting", {}), options)
        reasoning = parsed.get("reasoning", [])
        selected_model = _cfg.CRITIC_MODEL if role == "critic" else _cfg.LLM_MODEL
        await log_event(session_id, "llm_call", {
            "handler": "targeting_autopick",
            "model": selected_model,
            "tokens": tokens,
            "targeting": targeting,
        })
    except Exception as e:
        await log_event(session_id, "error", {"handler": "targeting_autopick", "error": str(e)})
        targeting = _normalize_targeting({
            "geo": ["Hà Nội", "TP.HCM", "Đà Nẵng"],
            "age": ["25-34", "35-44"],
            "gender": ["Male", "Female"],
            "deviceOS": [], "deviceBrand": [], "marital": [],
            "parental": [], "education": [], "income": [],
            "career": [], "interest": [], "weather": [],
        }, options)
        reasoning = [{"field": "geo", "picks": ["Hà Nội", "TP.HCM", "Đà Nẵng"], "reason": "3 thị trường lớn nhất"}]
        selected_model = "deterministic_fallback"

    return targeting, reasoning, selected_model


async def handle_targeting_autopick(session_id: str) -> AgentResponse:
    """
    LLM auto-picks targeting. Triggered when user sends:
    'Hãy tự động chọn targeting phù hợp nhất cho chiến dịch này'
    """
    session = await get_or_create_session(session_id)
    brief = session.get("form_state", {}).get("brief", {})
    segment = session.get("form_state", {}).get("segment", {})
    options = await get_targeting_options()
    targeting, reasoning, selected_model = await _recommend_targeting(
        session_id, brief, options, segment.get("attrs", [])
    )

    await update_form_state(session_id, "targeting", targeting)

    reason_by_field = {
        r.get("field"): r.get("reason", "")
        for r in reasoning if isinstance(r, dict) and r.get("field")
    }
    reason_rows = [
        [field, ", ".join(picks), reason_by_field.get(field, "")]
        for field, picks in targeting.items()
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
        meta=ResponseMeta(tool="targeting_autopick", model=selected_model, step=2),
    )

async def handle_dmp_recommend(session_id: str, brief_override: dict | None = None) -> dict:
    """
    GET /api/agent/dmp-recommend?session_id=xxx
    Returns AI-picked top segments based on real DMP data + brief context.
    Response: { recommendations: [{fullLabel, reason}], segments: [{fullLabel, segmentId, ...}] }
    """
    session = await get_or_create_session(session_id)
    brief = brief_override or session.get("form_state", {}).get("brief", {})

    # If brief not set yet, return empty gracefully
    if not brief.get("brand"):
        return {"recommendations": [], "total_segments": 0, "note": "brief_not_set"}

    # ── Phase 2: RAG path (query-rewrite → hybrid retrieve → rerank → LLM
    # over ~15 candidates). Falls back to the legacy full-dump path on ANY
    # failure — the Audience step must never break because of RAG infra ⛔.
    from config import config as _cfg
    if _cfg.USE_RAG_AUDIENCE:
        try:
            from rag.recommend import recommend_rag
            return await recommend_rag(session_id, brief)
        except Exception as e:
            from metrics import RAG_REQUESTS
            RAG_REQUESTS.labels(outcome="fallback").inc()
            await log_event(session_id, "error", {
                "handler": "dmp_recommend", "rag_fallback": str(e)[:150]})

    # ── Legacy path: dump the whole catalog into the prompt ──────────────────
    # (limit raised 200→400: with 310 live segments the old cap silently
    # hid a third of the catalog from the LLM)
    all_segs = await get_all_segments(limit=400)
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
        raw = await asyncio.to_thread(simple_generate, DMP_RECOMMEND_SYSTEM, prompt)
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
            enriched.append({
                **seg,
                "reason": rec.get("reason", ""),
                "source": catalog_source(seg),
            })

    return {
        "recommendations": _dedupe_segments(enriched),
        "total_segments": len(all_segs),
    }


async def _grounded_audience_entry(session_id: str, brief: dict) -> dict:
    """Build Guided's editable proposal from the shared audience pipeline."""
    recommendation = await handle_dmp_recommend(
        session_id, brief_override=brief
    )
    enriched_dmp = _dedupe_segments([
        _normalize_dmp_attr(item)
        for item in (recommendation.get("recommendations") or [])
        if isinstance(item, dict)
    ])
    if not enriched_dmp:
        await log_event(session_id, "error", {
            "handler": "audience_entry",
            "event": "grounded_retrieval_empty",
        })
        return {
            "skip": False,
            "need_more_info": True,
            "text": "Em chưa lấy được audience an toàn từ catalog ở lượt này.",
            "blocks": [{
                "type": "info",
                "text": "Anh/chị thử lại để Agent truy xuất lại catalog; workspace chưa bị thay đổi.",
            }],
            "meta": {"tool": "audience_entry_retry", "model": "none", "step": 1},
            "suggestions": [{
                "label": "🔄 Thử lại audience",
                "action": "send",
                "text": "Gợi ý lại audience phù hợp với brief này",
            }],
        }

    options = await get_targeting_options()
    targeting, targeting_reasoning, selected_model = await _recommend_targeting(
        session_id, brief, options, enriched_dmp
    )
    reason_by_field = {
        item.get("field"): item.get("reason", "")
        for item in targeting_reasoning
        if isinstance(item, dict) and item.get("field")
    }
    target_rows = [
        [field.capitalize(), ", ".join(picks), reason_by_field.get(field, "")]
        for field, picks in targeting.items()
        if picks
    ]
    blocks: list[dict] = []
    if target_rows:
        blocks.append({
            "type": "table",
            "title": "🎯 Targeting Parameters gợi ý",
            "columns": ["Nhóm", "Giá trị đề xuất", "Lý do"],
            "rows": target_rows,
        })

    blocks.append({
        "type": "table",
        "title": "👥 DMP Audience Segments gợi ý",
        "columns": ["Segment", "Loại", "Size ước tính", "Lý do phù hợp"],
        "rows": [[
            item.get("fullLabel", "?"),
            item.get("type", ""),
            item.get("sizeRaw") or "—",
            item.get("reason", ""),
        ] for item in enriched_dmp],
    })
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
            "reason": (
                f"AI gợi ý {len(enriched_dmp)} segment catalog-grounded "
                f"phù hợp với brief {brief.get('brand', '')}"
            ),
        },
        "is_locked": False,
        "warning": "",
        "instruction": (
            "Anh/chị bấm **Đồng ý** để áp dụng tất cả segments, hoặc vào panel "
            "phải để chọn/bỏ chọn từng segment trước khi xác nhận."
        ),
    })
    diagnostics = recommendation.get("rag") or recommendation.get("retrieval") or {}
    await log_event(session_id, "audience_entry", {
        "brand": brief.get("brand"),
        "pipeline": "shared_grounded_retrieval",
        "dmp_count": len(enriched_dmp),
        "audience_size": audience_size,
        "retrieval_candidates": diagnostics.get("candidates"),
        "targeting_model": selected_model,
    })

    reply_text = (
        f"Dựa trên brief **{brief.get('brand')}** "
        f"({brief.get('objective', 'awareness')}), em gợi ý audience như sau:"
    )
    from session import add_message as _add_message
    await _add_message(
        session_id,
        "assistant",
        reply_text
        + f"\n\n(Em đã gợi ý {len(enriched_dmp)} DMP segments duy nhất từ catalog "
          "và targeting params. Anh/chị có thể chỉnh trực tiếp ở workspace hoặc nhắn em.)",
    )
    return {
        "skip": False,
        "need_more_info": False,
        "text": reply_text,
        "blocks": blocks,
        "meta": {"tool": "audience_entry", "model": selected_model, "step": 1},
        "suggestions": [
            {"label": "✅ Áp dụng tất cả", "action": "send", "text": "đồng ý, áp dụng tất cả segments này"},
            {"label": "🗑️ Bỏ bớt segment", "action": "prefill", "text": "Bỏ segment "},
            {"label": "🔍 Tìm thêm segments", "action": "prefill", "text": "Tìm thêm segments liên quan đến "},
        ],
    }


async def handle_audience_entry(session_id: str, brief_hint: dict | None = None) -> dict:
    """
    GET /api/agent/audience-entry?session_id=xxx[&brief_hint=...]
    Proactively generates full audience recommendation when user enters step 1.
    Returns a chat-ready AgentResponse dict with blocks for Targeting + DMP Segments.
    brief_hint: optional brief dict from frontend (used when pending_proposal hasn't committed yet).
    """
    from session import get_pending_proposal, update_form_state, clear_pending_proposal
    session = await get_or_create_session(session_id)
    brief = session.get("form_state", {}).get("brief", {})

    # ── Brief resolution with fallback chain ──────────────────────────────────
    brief_source = "form_state"
    if not brief.get("brand"):
        # Fallback 1: check pending_proposal (user clicked 'Đồng ý' but didn't type 'oke')
        pending = await get_pending_proposal(session_id)
        if pending and pending.get("field") == "brief" and pending.get("value"):
            raw_val = pending["value"]
            if isinstance(raw_val, str):
                try:
                    import json as _j; raw_val = _j.loads(raw_val)
                except Exception:
                    pass
            if isinstance(raw_val, dict) and raw_val.get("brand"):
                brief = raw_val
                brief_source = "pending_proposal"
                # Auto-commit: persist so downstream calls also have it
                await update_form_state(session_id, "brief", brief)
                await clear_pending_proposal(session_id)
                await log_event(session_id, "audience_entry", {"auto_committed_pending_brief": True})

        # Fallback 2: use brief_hint passed directly from frontend
        if not brief.get("brand") and brief_hint and brief_hint.get("brand"):
            brief = brief_hint
            brief_source = "frontend_hint"
            # Also persist so backend session is consistent
            await update_form_state(session_id, "brief", brief)

    if not brief.get("brand"):
        await log_event(session_id, "warn", {"handler": "audience_entry", "skip": True, "reason": "brief_not_set", "source_tried": brief_source})
        return {"skip": True, "reason": "brief_not_set"}

    await log_event(session_id, "audience_entry", {"brief_source": brief_source, "brand": brief.get("brand")})

    # Check if audience already set (re-entry) → skip
    existing_segment = session.get("form_state", {}).get("segment", {})
    if existing_segment.get("attrs"):
        return {"skip": True, "reason": "audience_already_set"}

    # Guided consumes the same catalog-grounded retrieval contract as Autopilot.
    return await _grounded_audience_entry(session_id, brief)
