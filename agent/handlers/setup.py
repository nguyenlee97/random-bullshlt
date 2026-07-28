"""
Setup handler — Step 3.
Phase 0: Zone recommendation (zone ranker)
Phase 1: Creative assignment (auto_assign)
Phase 2: Order creation (single POST /api/orders with all zones + creatives[])
"""
from models import AgentResponse, SetupData, ResponseMeta
from session import add_message, get_or_create_session, update_form_state, update_order_ids, log_event
from tools.zone_ranker import rank_zones
from tools.creative_match import auto_assign
from tools.order_api import create_order
from tools.zone_catalog import get_zone_map
from config import config
from time_context import campaign_today


def initial_order_status(start_date: str, *, today=None) -> str:
    """Return the initial lifecycle state using the campaign's UTC+7 clock."""
    from datetime import date

    try:
        start = date.fromisoformat(str(start_date)[:10])
    except (TypeError, ValueError):
        return "pending"
    return "active" if start <= (today or campaign_today()) else "pending"


async def handle_setup(setup: SetupData, session_id: str) -> AgentResponse:
    phase = setup.phase if setup.phase is not None else 0
    if phase == 0:
        return await _zone_recommend(setup, session_id)
    elif phase == 1:
        return await _creative_match(setup, session_id)
    elif phase == 2:
        return await _order_create(setup, session_id)
    return AgentResponse(
        text="⚠ Phase không hợp lệ.",
        blocks=[],
        meta=ResponseMeta(tool="setup", model="none", step=3),
    )


async def handle_setup_entry(session_id: str) -> dict:
    """
    GET /api/agent/setup-entry
    Proactive zone recommendation when user enters Step 3 (Setup).
    Like handle_audience_entry() but for ad zones:
    - Ranks all real zones based on brief objective/KPI/budget/creative
    - Annotates booking conflicts
    - Generates a chat explanation of WHY each zone was recommended
    - Returns a workspace_proposal so the frontend pre-populates selectedZoneIds
    Returns {skip: True} if zones already selected.
    """
    import asyncio
    from tools.placement_relevance import build_placement_context
    from tools.zone_catalog import get_all_zones
    from tools.order_api import fetch_zone_conflicts, public_conflict_details

    session = await get_or_create_session(session_id)
    brief = session["form_state"].get("brief", {})
    creative = session["form_state"].get("creative", {})
    segment = session["form_state"].get("segment", {})

    # Skip if zones already selected
    existing_zones = session["form_state"].get("setup", {}).get("selectedZoneIds", [])
    if existing_zones:
        return {"skip": True}

    # Also skip if no brief
    if not brief.get("brand"):
        return {"skip": True}

    start_date = brief.get("startDate", "")
    end_date = brief.get("endDate", "")

    # Fetch all zones + conflict map in parallel
    all_zones_raw, conflict_map = await asyncio.gather(
        get_all_zones(),
        fetch_zone_conflicts(start_date, end_date),
    )

    # Rank all zones by brief metrics
    ranked = await rank_zones(
        objective=brief.get("objective", "awareness"),
        budget=brief.get("budget", 0),
        kpi=brief.get("kpi", ""),
        creative_files=creative.get("files", []),
        placement_context=build_placement_context(brief, segment),
        limit=len(all_zones_raw),
    )

    # Annotate conflicts and mark recommendations
    top_set: set[str] = set()
    available = [z for z in ranked if not conflict_map.get(z["id"])]
    for z in available[:6]:
        top_set.add(z["id"])
    top_zones = [z for z in ranked if z["id"] in top_set]

    for z in ranked:
        z["conflict"] = public_conflict_details(conflict_map.get(z["id"]))
        z["recommended"] = z["id"] in top_set

    await update_form_state(session_id, "reco_zones", top_zones)

    # ── Build explanation text ──────────────────────────────────────────────────
    objective = brief.get("objective", "awareness")
    budget = brief.get("budget", 0)
    brand = brief.get("brand", "Brand")
    kpi = brief.get("kpi", "")
    segment_count = len(segment.get("attrs", []))

    OBJECTIVE_VI = {
        "awareness": "Nhận diện thương hiệu",
        "consideration": "Cân nhắc mua hàng",
        "conversion": "Chuyển đổi / Mua hàng",
        "retention": "Giữ chân khách hàng",
    }
    obj_vi = OBJECTIVE_VI.get(objective, objective)

    zone_lines = []
    for z in top_zones:
        reach_m = f"{z['reach'] / 1_000_000:.1f}M" if z.get("reach", 0) > 0 else "—"
        vi = z.get("vi", 0)
        ctr = z.get("ctr", 0)
        cpm = z.get("cpm", 0)
        reason = z.get("reason", "phù hợp với objective")
        zone_lines.append(
            f"- **{z['id']}** — Reach {reach_m}, VI {vi}%, CTR {ctr}%, CPM {cpm:,}đ\n"
            f"  💡 {reason}"
        )

    zones_text = "\n".join(zone_lines)

    reply_text = (
        f"🎯 Dựa trên brief **{brand}** (Objective: **{obj_vi}**, KPI: **{kpi}**, "
        f"Budget: **{budget:,.0f}M VND**, {segment_count} audience segments), "
        f"em đề xuất **{len(top_zones)} ad zones** tối ưu:\n\n"
        f"{zones_text}\n\n"
        f"Anh/chị có thể xem chi tiết ở panel phải. "
        f"Muốn **bỏ zone** nào hoặc **thêm** zone khác, cứ nhắn em nhé!"
    )

    # ── Workspace proposal value ────────────────────────────────────────────────
    # Includes ALL zones so SetupStep doesn't need a separate fetch
    proposal_value = {
        "selectedZoneIds": list(top_set),
        "recoZones": top_zones,
        "allZones": ranked,
        "initialized": True,
        "phase": "zones",
        "assignments": {},
        "submitted": False,
        "created": False,
    }

    blocks = [
        {
            "type": "workspace_proposal",
            "changes": {
                "field": "setup",
                "value": proposal_value,
                "reason": f"Gợi ý {len(top_zones)} zones tối ưu cho {brand} — {obj_vi}",
            },
            "is_locked": False,
            "warning": "",
        }
    ]

    suggestions = [
        {"label": "✅ Duyệt các zones này", "action": "send",    "text": "đồng ý, duyệt các zones này"},
        {"label": "➕ Thêm zone",           "action": "prefill", "text": "Thêm zone "},
        {"label": "🗑️ Bỏ zone",             "action": "prefill", "text": "Bỏ zone "},
    ]

    # Proactive messages are part of the conversation too. Persisting this is
    # essential: otherwise the next free-form turn sees incomplete history and
    # may answer as if the user were still on an earlier campaign step.
    await add_message(session_id, "assistant", reply_text)

    return {
        "skip": False,
        "text": reply_text,
        "blocks": blocks,
        "meta": {"tool": "setup_entry", "model": "none", "step": 3},
        "suggestions": suggestions,
    }




async def _zone_recommend(setup: SetupData, session_id: str) -> AgentResponse:
    from tools.placement_relevance import build_placement_context

    session = await get_or_create_session(session_id)
    brief = session["form_state"].get("brief", {})
    creative = session["form_state"].get("creative", {})
    segment = session["form_state"].get("segment", {})

    ranked = await rank_zones(
        objective=brief.get("objective", "awareness"),
        budget=brief.get("budget", 0),
        kpi=brief.get("kpi", ""),
        creative_files=creative.get("files", []),
        placement_context=build_placement_context(brief, segment),
        limit=6,
    )

    await update_form_state(session_id, "reco_zones", ranked)

    zone_rows = []
    for i, z in enumerate(ranked):
        imp = f"{z['est_impressions']:,}" if z.get("est_impressions") else "—"
        reach_m = f"{z['reach']/1_000_000:.1f}M" if z.get("reach", 0) > 0 else "—"
        zone_rows.append([
            str(i + 1), z["id"],
            f"Reach {reach_m} · VI {z['vi']}% · CTR {z['ctr']}% · CPM {z['cpm']:,}đ",
            imp, z["reason"],
        ])

    top3 = ", ".join(z["id"] for z in ranked[:3])
    blocks = [
        {
            "type": "table",
            "title": f"🎯 Top {len(ranked)} Zone gợi ý ({brief.get('objective', 'awareness')})",
            "columns": ["#", "Zone ID", "Metrics", "Est. Impressions", "Lý do"],
            "rows": zone_rows,
        },
        {"type": "info", "text": "👆 Anh/Chị chọn zone ở panel phải, rồi bấm tiếp tục để gán creative!"},
    ]

    return AgentResponse(
        text=f"✅ Em đã phân tích **{len(ranked)} zone** tối ưu. Top picks: {top3}.",
        blocks=blocks,
        meta=ResponseMeta(tool="zone_recommend", model="none", step=3),
    )


async def handle_zone_recommend_api(session_id: str) -> dict:
    """
    GET /api/agent/zones-recommend?session_id=xxx
    Returns all real zones + ranked top list based on brief.
    Zones with booking conflicts for this campaign's date range are annotated
    with a `conflict` object and excluded from AI recommendations.
    """
    from tools.zone_catalog import get_all_zones
    from tools.order_api import fetch_zone_conflicts, public_conflict_details
    from tools.placement_relevance import build_placement_context

    session = await get_or_create_session(session_id)
    brief = session["form_state"].get("brief", {})
    creative = session["form_state"].get("creative", {})
    segment = session["form_state"].get("segment", {})

    start_date = brief.get("startDate", "")
    end_date = brief.get("endDate", "")

    # Fetch all zones + conflict map in parallel
    import asyncio
    all_zones, conflict_map = await asyncio.gather(
        get_all_zones(),
        fetch_zone_conflicts(start_date, end_date),
    )

    # Rank all zones by brief metrics
    ranked = await rank_zones(
        objective=brief.get("objective", "awareness"),
        budget=brief.get("budget", 0),
        kpi=brief.get("kpi", ""),
        creative_files=creative.get("files", []),
        placement_context=build_placement_context(brief, segment),
        limit=len(all_zones),  # return all zones, sorted
    )

    # Annotate each zone with conflict info (if any)
    for z in ranked:
        z["conflict"] = public_conflict_details(conflict_map.get(z["id"]))

    # Recommend top 6 available zones only (skip conflicted)
    available = [z for z in ranked if not z["conflict"]]
    top_ids = {z["id"] for z in available[:6]}

    for z in ranked:
        z["recommended"] = z["id"] in top_ids

    await update_form_state(session_id, "reco_zones", [z for z in ranked if z["id"] in top_ids])
    return {"zones": ranked, "recommended_ids": list(top_ids)}


async def _creative_match(setup: SetupData, session_id: str) -> AgentResponse:
    session = await get_or_create_session(session_id)
    creative = session["form_state"].get("creative", {})
    files = creative.get("files", [])
    zone_ids = setup.selectedZoneIds or []

    if not zone_ids:
        return AgentResponse(
            text="⚠ Anh/Chị chưa chọn zone nào. Vui lòng chọn ít nhất 1 zone.",
            blocks=[],
            meta=ResponseMeta(tool="creative_match", model="none", step=3),
        )

    zone_map = await get_zone_map()
    selected_zones = [zone_map[zid] for zid in zone_ids if zid in zone_map]

    # Phase 3: measured creative facts beat filename heuristics when available
    from config import config as _cfg
    if _cfg.USE_VLM_CREATIVE:
        from creative_intel.service import get_intel
        from tools.creative_match import enrich_files_with_intel
        files = enrich_files_with_intel(files, await get_intel(session_id))

    result = auto_assign(selected_zones, files)

    await update_form_state(session_id, "assignments", result["assignments"])

    rows = []
    for zone in selected_zones:
        zid = zone["id"]
        fidx = result["assignments"].get(zid, 0)
        fname = files[fidx]["name"] if fidx < len(files) else "—"
        zone_warns = [w["message"] for w in result["warnings"] if w["zoneId"] == zid]
        status = " · ".join(zone_warns) if zone_warns else "✅ Phù hợp"
        rows.append([zid, zone.get("format", ""), fname, status])

    blocks = [
        {
            "type": "table",
            "title": "🔗 Gán Creative → Zone",
            "columns": ["Zone ID", "Format", "Creative", "Trạng thái"],
            "rows": rows,
        },
    ]
    if result["warnings"]:
        blocks.append({"type": "info", "text": f"⚠ {len(result['warnings'])} cảnh báo — anh/chị kiểm tra và điều chỉnh nếu cần."})
    blocks.append({"type": "info", "text": "✅ Anh/Chị xem lại và bấm **Xác nhận & Tạo chiến dịch** để hoàn tất!"})

    return AgentResponse(
        text=f"✅ Em đã gán **{len(files)} creative** vào **{len(selected_zones)} zone**.",
        blocks=blocks,
        meta=ResponseMeta(tool="creative_match", model="none", step=3),
    )


async def _order_create(setup: SetupData, session_id: str) -> AgentResponse:
    session = await get_or_create_session(session_id)
    brief = session["form_state"].get("brief", {})
    creative = session["form_state"].get("creative", {})
    segment = session["form_state"].get("segment", {})
    targeting = session["form_state"].get("targeting", {})

    zone_ids = setup.selectedZoneIds or []
    assignments = setup.assignments or session["form_state"].get("assignments", {})
    files = creative.get("files", [])

    from config import config as _cfg
    if _cfg.USE_VLM_CREATIVE:
        from creative_intel.service import get_intel
        from tools.creative_match import enrich_files_with_intel

        files = enrich_files_with_intel(files, await get_intel(session_id))

    if not zone_ids:
        return AgentResponse(
            text="⚠ Không có zone nào được chọn.",
            blocks=[],
            meta=ResponseMeta(tool="order_create", model="none", step=3),
        )

    # ── Build creatives[] — group zones by file index ─────────────────────────
    file_to_zones: dict[int, list[str]] = {}
    for zone_id, file_idx in assignments.items():
        if zone_id in zone_ids:
            file_to_zones.setdefault(int(file_idx), []).append(zone_id)

    # Any zones not in assignments → assign file 0 as fallback
    creatives_payload = []
    for file_idx, z_ids in file_to_zones.items():
        f = files[file_idx] if file_idx < len(files) else {}
        intel = f.get("intel") or {}
        is_skin = intel.get("is_skin")
        if is_skin is None:
            is_skin = "skin" in (f.get("name") or "").lower()
        measured_width = intel.get("width") or f.get("width", 0)
        measured_height = intel.get("height") or f.get("height", 0)
        # Prefer URL uploaded by frontend (base64→VPS), fall back to session-stored url
        resolved_url = setup.fileUrls.get(str(file_idx)) or f.get("url", "")
        creatives_payload.append({
            "groupId": f"g_{file_idx}",
            "name": f.get("name", ""),
            "size": "skin" if is_skin else f"{measured_width}x{measured_height}",
            "format": "skin" if is_skin else "banner",
            "url": resolved_url,
            "zones": z_ids,
            "label": f.get("name", ""),
            "analysisId": f.get("analysisId") or intel.get("analysis_id", ""),
        })

    # ── DMP: use _id values ───────────────────────────────────────────────────
    dmp_include = [a.get("_id", "") for a in segment.get("attrs", []) if a.get("_id")]

    # ── Default targeting if none set ─────────────────────────────────────────
    empty_targeting = {
        "geo": [], "age": [], "gender": [], "deviceOS": [], "deviceBrand": [],
        "marital": [], "parental": [], "education": [], "income": [],
        "career": [], "interest": [], "weather": [],
    }
    final_targeting = {**empty_targeting, **targeting}

    # ── Build single order payload ────────────────────────────────────────────
    total_budget_vnd = brief.get("budget", 0) * 1_000_000

    # Auto-activate if campaign start date is today or already past.
    order_status = initial_order_status(brief.get("startDate", ""))

    payload = {
        "brand": brief.get("brand", "Brand"),
        "advertiser": brief.get("brand", ""),
        "objective": brief.get("objective", "awareness"),
        "status": order_status,
        "budget": total_budget_vnd,
        "daily": 0,
        "rate": 0,
        "rateType": "CPM",
        "startDate": brief.get("startDate", ""),
        "endDate": brief.get("endDate", ""),
        "creative": creatives_payload[0] if creatives_payload else {},
        "creatives": creatives_payload,
        "placements": zone_ids,
        "targeting": final_targeting,
        "dmp": {"include": dmp_include, "exclude": []},
        "freqCap": "3",
        # Phase 0 idempotency: frontend-provided key, or generated here as fallback
        # (fallback still protects against the create_order internal retry).
        "demoNamespace": config.DEMO_NAMESPACE,
        "idempotencyKey": setup.idempotencyKey or f"agent_{config.DEMO_NAMESPACE}_{session_id}_{__import__('uuid').uuid4().hex[:12]}",
    }

    # ── Phase 0 order guard ⛔ — deterministic server-side validation.
    # No payload reaches POST /api/orders without passing this, regardless of
    # whether it came from the form flow or (Phase 1) the agentic loop.
    from validation.order_guard import OrderValidationError, guard_order
    from metrics import ORDERS_CREATED, ORDERS_REJECTED
    try:
        await guard_order(payload, session)
    except OrderValidationError as ve:
        ORDERS_REJECTED.labels(reason=ve.reasons[0][:40] if ve.reasons else "unknown").inc()
        await log_event(session_id, "order_rejected", {"reasons": ve.reasons})
        return AgentResponse(
            text=ve.as_user_message(),
            blocks=[{"type": "info", "text": "Anh/Chị kiểm tra lại các bước trước rồi thử lại nhé."}],
            meta=ResponseMeta(tool="order_guard", model="none", step=3),
        )

    await log_event(session_id, "api_call", {"endpoint": "POST /api/orders", "placements": zone_ids})

    try:
        result = await create_order(payload)
        if "error" in result:
            return AgentResponse(
                text=f"⚠ Lỗi tạo order: {result.get('detail', result['error'])}",
                blocks=[],
                meta=ResponseMeta(tool="order_create", model="none", step=3),
            )
    except Exception as e:
        await log_event(session_id, "error", {"handler": "order_create", "error": str(e)})
        return AgentResponse(
            text=f"⚠ Không thể tạo order: {str(e)[:120]}",
            blocks=[],
            meta=ResponseMeta(tool="order_create", model="none", step=3),
        )

    order_id = result.get("id", "—")
    ORDERS_CREATED.inc()
    await update_order_ids(session_id, [order_id])
    from campaign_ownership import register_campaign_for_session
    await register_campaign_for_session(session_id, order_id)

    api_warnings = result.get("warnings", [])
    budget_display = brief.get("budget", 0)

    campaigns = [{
        "id": order_id,
        "name": f"{brief.get('brand', 'Brand')} — {len(zone_ids)} zones",
        "status": result.get("status", "pending"),
        "budget": budget_display,
        "reach": 0,
        "impressions": 0,
        "ctr": 0,
    }]

    blocks: list[dict] = [{"type": "campaign_list", "campaigns": campaigns}]
    if api_warnings:
        blocks.append({"type": "info", "text": "⚠ API cảnh báo:\n" + "\n".join(f"- {w}" for w in api_warnings)})
    blocks.append({"type": "info", "text": "🎉 Chiến dịch đã được khởi tạo! Anh/Chị xem tổng kết ở bước tiếp theo."})

    return AgentResponse(
        text=f"✅ Tạo thành công order **{order_id}** với **{len(zone_ids)} zone**, ngân sách **{budget_display:,.0f} triệu đồng**!",
        blocks=blocks,
        meta=ResponseMeta(tool="order_create", model="none", step=3),
    )
