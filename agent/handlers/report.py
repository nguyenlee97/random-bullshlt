"""Report handler — Step 5. Triggers report generation and handles report chat."""
import json
import httpx
from models import AgentResponse, ResponseMeta
from session import get_or_create_session, add_message, log_event
from config import config


async def handle_report_entry(
    session_id: str,
    campaign_data: dict = None,
    *,
    suppress_message: bool = False,
) -> AgentResponse:
    """
    Called when user enters Report step (step 5).
    1. Fetches campaign info from session
    2. Triggers background report generation via Node.js backend
    3. Returns intro message
    """
    session = await get_or_create_session(session_id)
    form = session.get("form_state", {})
    brief = form.get("brief", {})
    setup = form.get("setup", {})
    segment = form.get("segment", {})
    order_ids = session.get("created_order_ids", [])

    # Autopilot stores its authoritative result in the canonical workspace,
    # while the older Copilot flow also mirrors data into ``form_state``.
    # Read both so one report pipeline works for either experience.
    canonical_workspace = {}
    try:
        from workspace.service import get_workspace
        canonical_workspace = await get_workspace(session_id)
    except Exception as exc:
        await log_event(session_id, "warn", {
            "handler": "report_entry", "workspace_error": str(exc),
        })
    artifacts = canonical_workspace.get("artifacts", {})

    def artifact_value(name: str) -> dict:
        value = (artifacts.get(name, {}) or {}).get("value")
        return value if isinstance(value, dict) else {}

    canonical_brief = artifact_value("brief")
    canonical_audience = artifact_value("audience")
    canonical_placements = artifact_value("placements")
    canonical_order = artifact_value("order")
    canonical_order = canonical_order.get("order", canonical_order)
    if canonical_brief:
        brief = canonical_brief
    if canonical_audience:
        segment = canonical_audience

    brand = brief.get("brand", "Unknown")
    objective = brief.get("objective", "awareness")
    budget = brief.get("budget", 100)
    start_date = brief.get("startDate", "2026-06-17")

    # Build campaign ID from first order
    canonical_order_id = canonical_order.get("id") or canonical_order.get("_id")
    campaign_id = str(canonical_order_id or (order_ids[0] if order_ids else f"CAMP-{session_id[:8]}"))

    # Build zone list — prefer fetching real order from backend
    zones = []

    def infer_zone(zid: str) -> dict:
        zl = zid.lower()
        if 'znews' in zl:
            channel, fmt, cpm = 'Znews', 'banner', 28000
        elif 'baomoi' in zl or 'bao' in zl:
            channel, fmt, cpm = 'BaoMoi', 'banner', 25000
        elif 'zingmp3' in zl or 'zing' in zl or 'mp3' in zl:
            channel, fmt, cpm = 'ZingMP3', 'audio_banner', 22000
        elif 'skin' in zl or 'wallpaper' in zl:
            channel, fmt, cpm = 'Znews', 'skin', 45000
        elif 'video' in zl or 'preroll' in zl:
            channel, fmt, cpm = 'ZingMP3', 'video', 60000
        elif 'native' in zl:
            channel, fmt, cpm = 'BaoMoi', 'native', 20000
        elif 'mobile' in zl:
            channel, fmt, cpm = 'Znews', 'mobile_banner', 18000
        elif 'sticky' in zl:
            channel, fmt, cpm = 'BaoMoi', 'skin', 45000
        else:
            channel, fmt, cpm = 'Znews', 'banner', 30000
        return {'id': zid, 'channel': channel, 'format': fmt, 'cpm': cpm}

    # Try to fetch order from backend API (most reliable source)
    if campaign_id and not campaign_id.startswith('CAMP-'):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                order_resp = await client.get(f"{config.BACKEND_URL}/api/orders/{campaign_id}")
                if order_resp.status_code == 200:
                    order_data = order_resp.json()
                    placements = order_data.get("placements", [])
                    # Also try creatives[].zones
                    if not placements:
                        for c in order_data.get("creatives", []):
                            placements.extend(c.get("zones", []))
                    placements = list(dict.fromkeys(placements))  # deduplicate
                    canonical_zone_by_id = {
                        str(zone.get("id")): zone
                        for zone in canonical_placements.get("zones", [])
                        if zone.get("id")
                    }
                    zones = []
                    for zid in placements[:8]:
                        source = canonical_zone_by_id.get(str(zid), {})
                        fallback = infer_zone(str(zid))
                        zones.append({
                            "id": str(zid),
                            "channel": source.get("channel") or source.get("platform") or fallback["channel"],
                            "format": source.get("format") or source.get("size") or fallback["format"],
                            "cpm": source.get("cpm") or fallback["cpm"],
                        })
                    # Also update brief from order if session was stale
                    if not brand or brand == "Unknown":
                        brand = order_data.get("brand", brand)
                    if not objective or objective == "awareness":
                        objective = order_data.get("objective", objective)
                    if not budget or budget == 100:
                        budget_raw = order_data.get("budget", 0)
                        budget = round(budget_raw / 1_000_000) if budget_raw > 1000 else budget_raw
                    if not start_date or start_date == "2026-06-17":
                        start_date = order_data.get("startDate", start_date)
                        if start_date:
                            start_date = start_date[:10]  # YYYY-MM-DD
        except Exception as e:
            await log_event(session_id, "warn", {"handler": "report_entry", "fetch_order_error": str(e)})

    # Fall back to session form_state if order fetch failed
    if not zones:
        canonical_zones = canonical_placements.get("zones", [])
        canonical_selected = canonical_placements.get("selectedZoneIds", [])
        selected = set(str(item) for item in canonical_selected)
        for zone in canonical_zones:
            zid = str(zone.get("id") or "")
            if not zid or (selected and zid not in selected):
                continue
            fallback = infer_zone(zid)
            zones.append({
                "id": zid,
                "channel": zone.get("channel") or zone.get("platform") or fallback["channel"],
                "format": zone.get("format") or zone.get("size") or fallback["format"],
                "cpm": zone.get("cpm") or fallback["cpm"],
            })

    if not zones:
        reco_zones = setup.get("recoZones", []) or setup.get("allZones", [])
        selected_ids = setup.get("selectedZoneIds", [])
        for z in reco_zones:
            if z.get("id") in selected_ids:
                zones.append({
                    "id": z["id"],
                    "channel": z.get("channel", ""),
                    "format": z.get("format", "banner"),
                    "cpm": z.get("cpm", 30000),
                })
        if not zones and selected_ids:
            zones = [infer_zone(zid) for zid in selected_ids[:8]]

    # Absolute fallback: generic zones so generation always produces data
    if not zones:
        zones = [
            {'id': 'znews_homepage_banner', 'channel': 'Znews',   'format': 'banner',       'cpm': 28000},
            {'id': 'baomoi_feed_native',    'channel': 'BaoMoi',  'format': 'native',        'cpm': 22000},
            {'id': 'zingmp3_audio_banner',  'channel': 'ZingMP3', 'format': 'audio_banner',  'cpm': 20000},
            {'id': 'znews_article_mrec',    'channel': 'Znews',   'format': 'mrec',          'cpm': 25000},
        ]

    # Trigger report generation via Node.js backend
    generate_payload = {
        "campaignId": campaign_id,
        "brand": brand,
        "objective": objective,
        "budget": budget * 1_000_000,  # Convert from M VND to VND
        "startDate": start_date,
        "zones": zones,
        "audience": [
            {
                "name": a.get("fullLabel") or a.get("label") or a.get("name", ""),
                "context": a.get("category") or a.get("reason", ""),
            }
            for a in segment.get("attrs", [])[:5]
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{config.BACKEND_URL}/api/reports/generate",
                json=generate_payload,
            )
            gen_status = resp.json() if resp.status_code == 200 else {"status": "error"}
    except Exception as e:
        gen_status = {"status": "error", "error": str(e)}
        await log_event(session_id, "error", {"handler": "report_entry", "error": str(e)})

    # Store report context in session
    report_ctx = {
        "campaignId": campaign_id,
        "brand": brand,
        "objective": objective,
        "budget": budget,
        "zones": [z["id"] for z in zones],
        "gen_status": gen_status.get("status", "unknown"),
    }
    from session import update_form_state
    await update_form_state(
        session_id, "report_context", report_ctx,
        sync_workspace=canonical_workspace.get("experience_mode") != "autopilot",
    )

    await log_event(session_id, "report_entry", {
        "campaign_id": campaign_id,
        "zones": len(zones),
        "gen_status": gen_status.get("status"),
    })

    zone_names = ", ".join(z["id"].replace("_", " ") for z in zones[:4])
    if len(zones) > 4:
        zone_names += f" +{len(zones) - 4} khác"

    intro_text = (
        f"📊 **Chào mừng đến bước Báo cáo!**\n\n"
        f"⚠️ *Lưu ý: Dữ liệu báo cáo là dữ liệu mô phỏng (showcase), "
        f"được tạo tự động dựa trên thông tin chiến dịch.*\n\n"
        f"**Chiến dịch:** {brand}\n"
        f"**Mục tiêu:** {objective}\n"
        f"**Ngân sách:** {budget}M VND\n"
        f"**Zones:** {zone_names}\n\n"
        f"🔄 Đang tạo báo cáo phân tích cho 6 hạng mục... "
        f"Em sẽ thông báo khi sẵn sàng!"
    )

    blocks = [
        {
            "type": "info",
            "text": "💡 Trong lúc chờ, anh/chị có thể xem tổng quan chiến dịch ở panel phải.",
        },
    ]

    suggestions = [
        "Tổng quan hiệu suất chiến dịch",
        "So sánh hiệu suất giữa các zone",
        "Gợi ý tối ưu chiến dịch",
    ]

    # Successful launch now starts report generation before the user opens the
    # Report tab. Keep that background trigger out of the visible chat history;
    # entering the tab still records and displays the same introduction.
    if not suppress_message:
        await add_message(session_id, "assistant", intro_text)

    return AgentResponse(
        text=intro_text,
        blocks=blocks,
        suggestions=suggestions,
        meta=ResponseMeta(tool="report_entry", model="none", step=5),
        workspace_update={"field": "report", "value": {"campaignId": campaign_id}},
    )


async def handle_report_chat(
    message: str,
    session_id: str,
    active_report_tab: str = "all",
    conversation_model: str | None = None,
) -> AgentResponse:
    """
    Handle freeform chat within the Report step.
    Tries to match user message to predefined questions, returns pre-generated analysis.
    Falls back to a generic helpful response if no match.
    """
    session = await get_or_create_session(session_id)
    report_ctx = session.get("form_state", {}).get("report_context", {})
    campaign_id = report_ctx.get("campaignId", "")
    brand = report_ctx.get("brand", "Unknown")

    if not campaign_id:
        return AgentResponse(
            text="⚠ Chưa có dữ liệu báo cáo. Vui lòng hoàn tất bước Result trước.",
            blocks=[],
            meta=ResponseMeta(tool="report_chat", model="none", step=5),
        )

    # Variables populated inside try block, used by matching logic after
    preferred_type = "daily_ops"
    all_analyses: dict = {}

    # Try to fetch pre-generated analysis
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # First check if reports are ready
            status_resp = await client.get(
                f"{config.BACKEND_URL}/api/reports/status/{campaign_id}"
            )
            status_data = status_resp.json() if status_resp.status_code == 200 else {}

            if status_data.get("ready", 0) == 0:
                return AgentResponse(
                    text="⏳ Báo cáo đang được tạo... Anh/chị vui lòng đợi 1-2 phút nhé!",
                    blocks=[],
                    meta=ResponseMeta(tool="report_chat", model="none", step=5),
                )

            # Determine which report type to query based on active tab
            tab_to_type = {
                "all": "daily_ops",
                "daily_ops": "daily_ops",
                "awareness": "awareness",
                "consideration": "consideration",
                "conversion": "conversion",
                "retention": "retention",
                "executive": "executive",
            }
            preferred_type = tab_to_type.get(active_report_tab, "daily_ops")

            # Fetch ALL analyses — search across all 6 for best match
            all_analyses = {}
            for rtype in ["daily_ops", "awareness", "consideration", "conversion", "retention", "executive"]:
                try:
                    r = await client.get(
                        f"{config.BACKEND_URL}/api/reports/analysis/{campaign_id}/{rtype}"
                    )
                    if r.status_code == 200:
                        all_analyses[rtype] = r.json()
                except Exception:
                    pass

            if not all_analyses:
                return AgentResponse(
                    text="⚠ Chưa có phân tích nào. Vui lòng đợi báo cáo hoàn tất.",
                    blocks=[],
                    meta=ResponseMeta(tool="report_chat", model="none", step=5),
                )

    except Exception as e:
        await log_event(session_id, "error", {"handler": "report_chat", "error": str(e)})
        return AgentResponse(
            text=f"⚠ Không thể tải phân tích: {str(e)[:100]}",
            blocks=[],
            meta=ResponseMeta(tool="report_chat", model="none", step=5),
        )

    # OpenAI-locked conversations use semantic, evidence-cited report Q&A.
    # GreenNode conversations retain their existing independent report matcher.
    from campaign_models import OPENAI_GPT_5_4_MINI
    if conversation_model == OPENAI_GPT_5_4_MINI:
        try:
            from openai_campaign.report_qa import answer_report_question

            answer, provenance = await answer_report_question(
                session_id=session_id, message=message,
                preferred_type=preferred_type, analyses=all_analyses,
                history=session.get("history") or [],
            )
            citations = [
                *[f"finding:{item}" for item in answer.finding_ids],
                *[f"metric:{item}" for item in answer.metric_ids],
            ]
            source_text = (
                "Nguồn: " + ", ".join(citations)
                if citations else "Nguồn: report-evidence-v1"
            )
            blocks = [{
                "type": "report_analysis",
                "title": f"Phân tích — {answer.report_type.replace('_', ' ').title()}",
                "sections": [
                    {"type": "summary", "text": answer.answer},
                    {"type": "limitation", "text": source_text},
                ],
            }]
            await add_message(session_id, "user", message)
            await add_message(session_id, "assistant", answer.answer)
            return AgentResponse(
                text=answer.answer, blocks=blocks,
                suggestions=answer.suggestions,
                meta=ResponseMeta(
                    tool="report_semantic_qa", model=provenance["model"], step=5,
                ),
            )
        except Exception as exc:
            await log_event(session_id, "error", {
                "handler": "report_semantic_qa", "error": str(exc),
                "state_changed": False,
            })
            return AgentResponse(
                text=(
                    "Em chưa thể trả lời an toàn từ report-evidence-v1 ở lượt này. "
                    "Các số liệu hiện có vẫn giữ nguyên; anh/chị thử lại sau khi báo cáo hoàn tất nhé."
                ),
                blocks=[],
                meta=ResponseMeta(tool="report_semantic_qa_unavailable", model="gpt-5.4-mini", step=5),
            )

    # ── GreenNode report matcher (independent legacy component) ───────────────
    # Score every question across all 6 analyses, prefer preferred_type on tie
    msg_lower = message.lower().strip()
    msg_words = set(msg_lower.split())

    best_score = -1
    matched_q = None
    matched_type = preferred_type
    matched_analysis = all_analyses.get(preferred_type, {})

    REPORT_TYPE_ORDER = [preferred_type] + [
        t for t in ["daily_ops", "awareness", "consideration", "conversion", "retention", "executive"]
        if t != preferred_type
    ]

    for rtype in REPORT_TYPE_ORDER:
        analysis = all_analyses.get(rtype, {})
        for q in analysis.get("questions", []):
            q_text = q.get("question", "").lower()
            q_words = set(q_text.split())
            overlap = len(q_words & msg_words)
            # Bonus score if the question text contains the full message or vice-versa
            exact_bonus = 5 if (q_text in msg_lower or msg_lower in q_text) else 0
            score = overlap + exact_bonus
            # preferred_type gets a tiebreak bonus of 0.5
            if rtype == preferred_type:
                score += 0.5
            if score > best_score and score >= 2:
                best_score = score
                matched_q = q
                matched_type = rtype
                matched_analysis = analysis

    # Collect suggestions: other questions from matched report type, then preferred_type
    def get_suggestions(exclude_id):
        seen = set()
        suggs = []
        for rtype in [matched_type, preferred_type]:
            for q in all_analyses.get(rtype, {}).get("questions", []):
                if q["id"] != exclude_id and q["question"] not in seen:
                    seen.add(q["question"])
                    suggs.append(q["question"])
                    if len(suggs) >= 6:
                        return suggs
        return suggs

    if matched_q:
        answer = matched_q.get("answer", {})
        report_label = matched_type.replace("_", " ").title()
        blocks = [{
            "type": "report_analysis",
            "title": matched_q["question"],
            "sections": answer.get("sections", []) if isinstance(answer, dict) else [],
        }]
        suggestions = get_suggestions(matched_q["id"])

        await add_message(session_id, "user", message)
        text = f"📊 **{matched_q['question']}** — {brand}"
        await add_message(session_id, "assistant", text)

        return AgentResponse(
            text=text,
            blocks=blocks,
            suggestions=suggestions,
            meta=ResponseMeta(tool="report_analysis", model="cached", step=5),
        )

    # No match found — return overall of preferred type with all question chips
    fallback = all_analyses.get(preferred_type, next(iter(all_analyses.values()), {}))
    overall = fallback.get("overall", "")
    report_label = preferred_type.replace("_", " ").title()

    all_questions = []
    seen = set()
    for rtype in REPORT_TYPE_ORDER:
        for q in all_analyses.get(rtype, {}).get("questions", []):
            if q["question"] not in seen:
                seen.add(q["question"])
                all_questions.append(q["question"])
            if len(all_questions) >= 6:
                break
        if len(all_questions) >= 6:
            break

    blocks = []
    if overall:
        blocks.append({
            "type": "report_analysis",
            "title": f"Tổng quan — {report_label}",
            "sections": [{"type": "summary", "text": overall}],
        })

    await add_message(session_id, "user", message)
    text = (
        f"📊 Đây là tổng quan cho report **{report_label}** "
        f"của chiến dịch **{brand}**:\n\n{overall}\n\n"
        f"💡 Anh/chị có thể hỏi chi tiết hơn bằng các gợi ý bên dưới!"
    )
    await add_message(session_id, "assistant", text)

    return AgentResponse(
        text=text,
        blocks=blocks,
        suggestions=all_questions,
        meta=ResponseMeta(tool="report_analysis", model="cached", step=5),
    )
