"""OpenAI-owned siblings for Guided campaign operations that require a model.

The existing handlers remain the GreenNode component. This module may share
deterministic catalogs, storage, validation, and retrieval services, but it does
not import or call ``llm.py`` or any GreenNode model handler.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from config import config
from models import AgentResponse, BriefData, ResponseMeta, SegmentData
from openai_campaign.structured import generate_structured
from session import (
    add_message,
    clear_pending_proposal,
    get_or_create_session,
    get_pending_proposal,
    log_event,
    update_form_state,
)
from tools.audience_library import get_all_segments
from tools.audience_provenance import catalog_source
from tools.targeting_options import get_targeting_options
from audience_reach import audience_selection, estimate_unique_reach


class _BriefAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=1200)
    audience_hint: list[str] = Field(default_factory=list, max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=10)
    suggested_kpis: list[str] = Field(default_factory=list, max_length=10)


class _SegmentNote(BaseModel):
    label: str = Field(min_length=1, max_length=500)
    note: str = Field(default="", max_length=600)


class _AudienceAnalysis(BaseModel):
    reasoning: str = Field(min_length=1, max_length=1600)
    match_quality: Literal["excellent", "good", "fair", "poor"] = "good"
    segment_notes: list[_SegmentNote] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=10)


class _DmpRecommendation(BaseModel):
    fullLabel: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=800)


class _DmpSelection(BaseModel):
    recommendations: list[_DmpRecommendation] = Field(min_length=1, max_length=6)


class _QueryRewrite(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=3)


class _TargetingReason(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    picks: list[str] = Field(default_factory=list, max_length=30)
    reason: str = Field(default="", max_length=600)


class _TargetingSelection(BaseModel):
    targeting: dict[str, list[str]]
    reasoning: list[_TargetingReason] = Field(default_factory=list, max_length=30)


BRIEF_INSTRUCTIONS = """
Bạn là chuyên gia lập kế hoạch quảng cáo. Phân tích brief được cung cấp và trả
về đúng schema. Tóm tắt ngắn gọn bằng tiếng Việt, nêu audience hints chỉ từ dữ
liệu brief, cảnh báo KPI/ngân sách/thời gian bất hợp lý, và đề xuất KPI bổ sung
phù hợp với objective. Không bịa dữ liệu hệ thống hoặc số liệu thị trường.
""".strip()


AUDIENCE_INSTRUCTIONS = """
Bạn là chuyên gia media planning. Đánh giá các DMP segment đã được người dùng
chọn so với brief. Chỉ nhận xét những segment có trong input; không tạo segment
hay ID mới. Trả reasoning, match_quality, ghi chú theo exact label và cảnh báo
ngắn gọn bằng tiếng Việt. Audience size trong input là dữ liệu, không tự tính lại.
""".strip()


DMP_SELECTION_INSTRUCTIONS = """
Chọn tối đa 6 DMP audience segment phù hợp nhất với brief từ danh sách ứng viên
được cung cấp. fullLabel phải được sao chép chính xác từ danh sách; tuyệt đối
không tạo label hoặc ID mới. Bao phủ các tín hiệu audience chính, tránh segment
trùng nghĩa và giải thích lý do cụ thể bằng tiếng Việt.
""".strip()


QUERY_REWRITE_INSTRUCTIONS = """
Tạo 2-3 truy vấn tìm kiếm DMP ngắn, mỗi truy vấn dưới 15 từ, dùng từ vựng về
interest/behavior và bao phủ các khía cạnh audience khác nhau trong brief.
Không thêm sản phẩm, đối tượng hoặc ràng buộc không có trong brief.
""".strip()


TARGETING_INSTRUCTIONS = """
Chọn targeting phù hợp với brief và các DMP segment từ catalog options được
cung cấp. Chỉ dùng exact dimension và exact value có trong options. Có thể trả
danh sách rỗng khi không đủ căn cứ. Giải thích ngắn gọn bằng tiếng Việt và không
bịa giá trị ngoài catalog.
""".strip()


def _calc_audience_size(attrs: list[dict]) -> int:
    return estimate_unique_reach(attrs)["unique_reach"] or 0


def _has_known_audience_size(attrs: list[dict]) -> bool:
    return any(
        int(item.get("sizeMin") or 0) > 0
        or int(item.get("sizeMax") or 0) > 0
        or int(item.get("est_size") or 0) > 0
        for item in attrs
    )


def _segment_identity(segment: dict) -> str:
    source = segment.get("source") if isinstance(segment.get("source"), dict) else {}
    return str(
        segment.get("segmentId")
        or segment.get("_id")
        or source.get("segmentId")
        or source.get("recordId")
        or segment.get("fullLabel")
        or segment.get("name")
        or ""
    ).strip().casefold()


def _dedupe_segments(segments: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        identity = _segment_identity(segment)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        result.append(segment)
    return result


def _normalize_dmp_attr(segment: dict) -> dict:
    low = int(segment.get("sizeMin") or 0)
    high = int(segment.get("sizeMax") or 0)
    estimated = (low + high) // 2 if low and high else (low or high)
    label = segment.get("fullLabel") or segment.get("name", "")
    raw_id = segment.get("_id")
    return {
        **segment,
        "_uid": str(raw_id) if raw_id else label,
        "name": label,
        "code": segment.get("code", ""),
        "category": segment.get("category", segment.get("type", "")),
        "est_size": estimated,
        "fullLabel": label,
    }


def _normalize_targeting(
    targeting: dict, options: dict,
) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    if not isinstance(targeting, dict) or not isinstance(options, dict):
        return normalized
    for dimension, raw_values in targeting.items():
        raw_options = options.get(dimension)
        if raw_options is None:
            continue
        allowed: set[str] = set()
        option_values: list = []
        if isinstance(raw_options, dict):
            option_values = [
                option
                for group in raw_options.values() if isinstance(group, list)
                for option in group
            ]
        elif isinstance(raw_options, list):
            option_values = raw_options
        for option in option_values:
            if isinstance(option, str):
                allowed.add(option)
            elif isinstance(option, dict):
                for key in ("value", "name", "label", "id"):
                    if option.get(key):
                        allowed.add(str(option[key]))
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        valid = [
            value for value in values
            if isinstance(value, str) and value in allowed
        ]
        if valid:
            normalized[dimension] = list(dict.fromkeys(valid))
    return normalized


async def handle_openai_brief(
    brief: BriefData, session_id: str, *, client: Any | None = None,
) -> AgentResponse:
    errors: list[str] = []
    if not brief.brand.strip():
        errors.append("Brand không được để trống.")
    if brief.budget <= 0:
        errors.append("Ngân sách phải lớn hơn 0.")
    if not brief.startDate or not brief.endDate:
        errors.append("Vui lòng chọn thời gian chạy.")
    if errors:
        return AgentResponse(
            text="⚠ Brief có lỗi:\n" + "\n".join(f"- {item}" for item in errors),
            blocks=[{"type": "info", "text": "Anh/Chị kiểm tra lại thông tin ở panel phải nhé!"}],
            meta=ResponseMeta(tool="brief_validate", model="none", step=0),
        )

    brief_dict = brief.model_dump()
    await update_form_state(session_id, "brief", brief_dict)
    payload = {"brief": brief_dict, "budget_unit": "million_VND"}
    try:
        output, provenance = await generate_structured(
            session_id=session_id,
            instructions=BRIEF_INSTRUCTIONS,
            input_data=json.dumps(payload, ensure_ascii=False),
            schema=_BriefAnalysis,
            schema_name="guided_brief_analysis",
            max_output_tokens=1400,
            client=client,
        )
        data = output.model_dump(mode="json")
        await log_event(session_id, "guided_model_provenance", {
            "operation": "brief", **provenance,
        })
    except Exception as exc:
        await log_event(session_id, "error", {
            "handler": "openai_guided_brief", "error": str(exc),
            "provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL,
        })
        data = {
            "summary": (
                f"Chiến dịch {brief.objective} cho {brief.brand}, ngân sách "
                f"{brief.budget:,.0f} triệu VND."
            ),
            "audience_hint": [], "warnings": [], "suggested_kpis": [],
        }

    audience_hint = ", ".join(data.get("audience_hint") or [])
    rows = [
        ["Brand", brief.brand],
        ["Objective", brief.objective.capitalize()],
        ["KPI", brief.kpi or "—"],
        ["Ngân sách", f"{brief.budget:,.0f} triệu VND"],
        ["Thời gian", f"{brief.startDate} → {brief.endDate}"],
        ["Audience hint", audience_hint or "—"],
    ]
    if data.get("suggested_kpis"):
        rows.append(["KPI đề xuất thêm", ", ".join(data["suggested_kpis"])])
    blocks: list[dict] = [{
        "type": "table", "title": "📋 Tóm tắt Brief",
        "columns": ["Thông tin", "Giá trị"], "rows": rows,
    }]
    if data.get("warnings"):
        blocks.append({
            "type": "info",
            "text": "⚠ Lưu ý:\n" + "\n".join(f"- {item}" for item in data["warnings"]),
        })
    blocks.append({
        "type": "info",
        "text": "✅ Anh/Chị tiếp tục bằng cách chọn **Audience segments** ở bước tiếp theo!",
    })
    return AgentResponse(
        text=f"✅ {data['summary']}", blocks=blocks,
        meta=ResponseMeta(
            tool="openai_brief_handler", model=config.OPENAI_CAMPAIGN_MODEL, step=0,
        ),
    )


async def handle_openai_audience(
    segment: SegmentData, session_id: str, *, client: Any | None = None,
) -> AgentResponse:
    attrs = segment.attrs
    if not attrs:
        return AgentResponse(
            text="⚠ Anh/Chị chưa chọn audience segment nào.",
            blocks=[{"type": "info", "text": "Vui lòng chọn ít nhất 1 segment từ thư viện DMP."}],
            meta=ResponseMeta(tool="audience_validate", model="none", step=1),
        )

    selection = audience_selection(attrs)
    total_size = selection["size"]
    size_known = selection["sizeKnown"]
    await update_form_state(session_id, "segment", selection)
    if segment.targeting:
        await update_form_state(session_id, "targeting", segment.targeting)
    session = await get_or_create_session(session_id)
    brief = session.get("form_state", {}).get("brief", {})
    payload = {
        "brief": brief,
        "selected_segments": [{
            "label": item.get("fullLabel") or item.get("name", ""),
            "type": item.get("type", ""),
        } for item in attrs],
        "audience_size": total_size if size_known else None,
        "audience_reach": selection["reach"],
        "audience_size_method": selection["reach"]["method"],
    }
    try:
        output, provenance = await generate_structured(
            session_id=session_id,
            instructions=AUDIENCE_INSTRUCTIONS,
            input_data=json.dumps(payload, ensure_ascii=False, default=str),
            schema=_AudienceAnalysis,
            schema_name="guided_audience_analysis",
            max_output_tokens=1600,
            client=client,
        )
        data = output.model_dump(mode="json")
        await log_event(session_id, "guided_model_provenance", {
            "operation": "audience", **provenance,
        })
    except Exception as exc:
        await log_event(session_id, "error", {
            "handler": "openai_guided_audience", "error": str(exc),
            "provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL,
        })
        data = {
            "reasoning": "Các audience segment đã chọn được giữ nguyên theo catalog.",
            "match_quality": "good", "segment_notes": [], "warnings": [],
        }

    notes = {item["label"]: item["note"] for item in data.get("segment_notes", [])}
    quality = data.get("match_quality", "good")
    emoji = {"excellent": "🟢", "good": "🟡", "fair": "🟠", "poor": "🔴"}.get(quality, "🟡")
    rows = []
    for item in attrs:
        label = item.get("fullLabel") or item.get("name", "?")
        low, high = item.get("sizeMin"), item.get("sizeMax")
        size_text = item.get("sizeRaw") or (
            f"{low:,} - {high:,}" if low and high else "—"
        )
        rows.append([label, item.get("type", ""), size_text, notes.get(label, "")])
    blocks: list[dict] = [
        {
            "type": "audience_size", "size": total_size,
            "size_known": size_known,
            "range": selection["reach"].get("range"),
            "method": selection["reach"].get("method"),
            "confidence": selection["reach"].get("confidence"),
            "universe": selection["reach"].get("universe"),
            "catalog_version": selection["reach"].get("catalog_version"),
            "size_source": "modeled_estimate" if any(
                item.get("sizeSource") == "modeled_estimate" for item in attrs
            ) else "catalog",
            "count": len(attrs),
            "breakdown": [{
                "label": item.get("fullLabel") or item.get("name", ""),
                "size": ((item.get("sizeMin") or 0) + (item.get("sizeMax") or 0)) // 2,
            } for item in attrs],
        },
        {
            "type": "table",
            "title": f"👥 Audience Segments ({emoji} {quality.capitalize()})",
            "columns": ["Segment", "Loại", "Size", "Nhận xét"],
            "rows": rows,
        },
        {"type": "info", "text": f"💡 {data['reasoning']}"},
    ]
    if data.get("warnings"):
        blocks.append({"type": "info", "text": "⚠ " + " · ".join(data["warnings"])})
    summary = (
        f"ước tính audience **{total_size:,} người**"
        if size_known else "catalog hiện chưa cung cấp audience size"
    )
    return AgentResponse(
        text=f"✅ Đã chọn **{len(attrs)} segments**; {summary}.",
        blocks=blocks,
        meta=ResponseMeta(
            tool="openai_audience_handler", model=config.OPENAI_CAMPAIGN_MODEL, step=1,
        ),
    )


async def _select_dmp_candidates(
    session_id: str, prompt: str, *, client: Any | None = None,
) -> tuple[list[dict], str]:
    output, _ = await generate_structured(
        session_id=session_id,
        instructions=DMP_SELECTION_INSTRUCTIONS,
        input_data=prompt,
        schema=_DmpSelection,
        schema_name="guided_dmp_selection",
        max_output_tokens=1600,
        client=client,
    )
    return [item.model_dump(mode="json") for item in output.recommendations], config.OPENAI_CAMPAIGN_MODEL


async def _rewrite_rag_queries(
    session_id: str, brief: dict, *, client: Any | None = None,
) -> list[str]:
    output, _ = await generate_structured(
        session_id=session_id,
        instructions=QUERY_REWRITE_INSTRUCTIONS,
        input_data=json.dumps({"brief": brief}, ensure_ascii=False),
        schema=_QueryRewrite,
        schema_name="guided_dmp_query_rewrite",
        max_output_tokens=500,
        client=client,
    )
    return output.queries


async def handle_openai_dmp_recommend(
    session_id: str,
    brief_override: dict | None = None,
    *,
    client: Any | None = None,
) -> dict:
    session = await get_or_create_session(session_id)
    brief = brief_override or session.get("form_state", {}).get("brief", {})
    if not brief.get("brand"):
        return {"recommendations": [], "total_segments": 0, "note": "brief_not_set"}

    if config.USE_RAG_AUDIENCE:
        try:
            from rag.recommend import recommend_rag

            result = await recommend_rag(
                session_id,
                brief,
                selector=lambda prompt: _select_dmp_candidates(
                    session_id, prompt, client=client,
                ),
                query_rewriter=lambda value: _rewrite_rag_queries(
                    session_id, value, client=client,
                ),
                provider="openai",
                # The legacy reranker belongs to the GreenNode boundary.
                # The optional nano mode is an explicitly shared fixed
                # relevance specialist, like the existing creative/report
                # specialists; it never becomes a conversational fallback.
                rerank_mode=(
                    "openai_nano"
                    if config.AUDIENCE_RERANK_MODE == "openai_nano"
                    else "off"
                ),
            )
            result.setdefault("provenance", {
                "provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL,
            })
            return result
        except Exception as exc:
            from metrics import RAG_REQUESTS

            RAG_REQUESTS.labels(outcome="fallback").inc()
            await log_event(session_id, "error", {
                "handler": "openai_dmp_recommend",
                "rag_fallback": str(exc)[:150],
                "provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL,
            })

    all_segments = await get_all_segments(limit=400)
    labels = [
        item.get("fullLabel") or item.get("name", "")
        for item in all_segments
        if item.get("fullLabel") or item.get("name")
    ]
    prompt = json.dumps({
        "brief": brief,
        "candidate_full_labels": labels,
    }, ensure_ascii=False)
    try:
        selected, _ = await _select_dmp_candidates(
            session_id, prompt, client=client,
        )
    except Exception as exc:
        await log_event(session_id, "error", {
            "handler": "openai_dmp_recommend", "error": str(exc),
            "provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL,
        })
        return {
            "recommendations": [], "total_segments": len(all_segments),
            "note": "openai_provider_unavailable",
            "provenance": {"provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL},
        }

    label_map = {
        item.get("fullLabel") or item.get("name", ""): item
        for item in all_segments
    }
    enriched = []
    for recommendation in selected:
        segment = label_map.get(recommendation.get("fullLabel", ""))
        if segment:
            enriched.append({
                **segment,
                "reason": recommendation.get("reason", ""),
                "source": catalog_source(segment),
            })
    result = {
        "recommendations": _dedupe_segments(enriched),
        "total_segments": len(all_segments),
        "provenance": {"provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL},
    }
    await log_event(session_id, "guided_model_provenance", {
        "operation": "dmp_recommend", **result["provenance"],
        "returned": len(result["recommendations"]),
    })
    return result


async def _recommend_targeting(
    session_id: str,
    brief: dict,
    options: dict,
    segments: list[dict] | None = None,
    *,
    client: Any | None = None,
) -> tuple[dict[str, list[str]], list[dict], str]:
    payload = {
        "brief": brief,
        "segments": [
            item.get("fullLabel") or item.get("name", "")
            for item in (segments or [])[:10]
        ],
        "catalog_options": options,
    }
    output, provenance = await generate_structured(
        session_id=session_id,
        instructions=TARGETING_INSTRUCTIONS,
        input_data=json.dumps(payload, ensure_ascii=False, default=str),
        schema=_TargetingSelection,
        schema_name="guided_targeting_selection",
        max_output_tokens=1400,
        client=client,
    )
    targeting = _normalize_targeting(output.targeting, options)
    reasoning = [item.model_dump(mode="json") for item in output.reasoning]
    await log_event(session_id, "guided_model_provenance", {
        "operation": "targeting", **provenance, "targeting": targeting,
    })
    return targeting, reasoning, config.OPENAI_CAMPAIGN_MODEL


async def _grounded_audience_entry(
    session_id: str, brief: dict, *, client: Any | None = None,
) -> dict:
    recommendation = await handle_openai_dmp_recommend(
        session_id, brief_override=brief, client=client,
    )
    enriched = _dedupe_segments([
        _normalize_dmp_attr(item)
        for item in recommendation.get("recommendations") or []
        if isinstance(item, dict)
    ])
    if not enriched:
        await log_event(session_id, "error", {
            "handler": "openai_audience_entry", "event": "grounded_retrieval_empty",
            "provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL,
        })
        return {
            "skip": False, "need_more_info": True,
            "text": "Em chưa lấy được audience an toàn từ catalog ở lượt này.",
            "blocks": [{
                "type": "info",
                "text": "Anh/chị thử lại để Agent truy xuất lại catalog; workspace chưa bị thay đổi.",
            }],
            "meta": {"tool": "audience_entry_retry", "model": config.OPENAI_CAMPAIGN_MODEL, "step": 1},
            "suggestions": [{
                "label": "🔄 Thử lại audience", "action": "send",
                "text": "Gợi ý lại audience phù hợp với brief này",
            }],
        }

    options = await get_targeting_options()
    try:
        targeting, targeting_reasoning, selected_model = await _recommend_targeting(
            session_id, brief, options, enriched, client=client,
        )
    except Exception as exc:
        await log_event(session_id, "error", {
            "handler": "openai_targeting", "error": str(exc),
            "provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL,
        })
        targeting, targeting_reasoning = {}, []
        selected_model = config.OPENAI_CAMPAIGN_MODEL

    reason_by_field = {
        item.get("field"): item.get("reason", "")
        for item in targeting_reasoning if item.get("field")
    }
    target_rows = [
        [field.capitalize(), ", ".join(picks), reason_by_field.get(field, "")]
        for field, picks in targeting.items() if picks
    ]
    blocks: list[dict] = []
    if target_rows:
        blocks.append({
            "type": "table", "title": "🎯 Targeting Parameters gợi ý",
            "columns": ["Nhóm", "Giá trị đề xuất", "Lý do"], "rows": target_rows,
        })
    blocks.append({
        "type": "table", "title": "👥 DMP Audience Segments gợi ý",
        "columns": ["Segment", "Loại", "Size ước tính", "Lý do phù hợp"],
        "rows": [[
            item.get("fullLabel", "?"), item.get("type", ""),
            item.get("sizeRaw") or "—", item.get("reason", ""),
        ] for item in enriched],
    })
    selection = audience_selection(enriched)
    audience_size = selection["size"]
    size_known = selection["sizeKnown"]
    blocks.append({
        "type": "workspace_proposal",
        "changes": {
            "field": "segment",
            "value": {
                **selection, "targeting": targeting,
            },
            "reason": (
                f"Agent gợi ý {len(enriched)} segment dựa trên catalog "
                f"phù hợp với brief {brief.get('brand', '')}"
            ),
        },
        "is_locked": False, "warning": "",
        "instruction": (
            "Anh/chị bấm **Đồng ý** để áp dụng tất cả segments, hoặc chỉnh trực tiếp "
            "ở panel phải trước khi xác nhận."
        ),
    })
    diagnostics = recommendation.get("rag") or {}
    await log_event(session_id, "audience_entry", {
        "brand": brief.get("brand"), "pipeline": "openai_grounded_retrieval",
        "provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL,
        "dmp_count": len(enriched), "audience_size": audience_size,
        "retrieval_candidates": diagnostics.get("candidates"),
    })
    reply = (
        f"Dựa trên brief **{brief.get('brand')}** "
        f"({brief.get('objective', 'awareness')}), em gợi ý audience như sau:"
    )
    # Preserve exact names and recommendation reasons for later explanation
    # turns. The old count-only history made this evidence disappear at once.
    history_rows = []
    for item in enriched[:12]:
        label = str(
            item.get("fullLabel") or item.get("name")
            or item.get("segmentId") or item.get("_id") or "?"
        ).strip()
        identity = str(item.get("segmentId") or item.get("_id") or "").strip()
        reason = str(item.get("reason") or "").strip()
        suffix = f" [{identity}]" if identity else ""
        history_rows.append(
            f"- {label}{suffix}" + (f": {reason[:500]}" if reason else "")
        )
    history_snapshot = "\n".join(history_rows)
    await add_message(
        session_id, "assistant",
        reply
        + f"\n\n(Đã gợi ý {len(enriched)} DMP segments duy nhất từ catalog và targeting params.)"
        + (f"\n\nRecommendation snapshot:\n{history_snapshot}" if history_snapshot else ""),
    )
    return {
        "skip": False, "need_more_info": False, "text": reply, "blocks": blocks,
        "meta": {
            "tool": "openai_audience_entry",
            "model": selected_model,
            "step": 1,
            "retrieval": {
                "applied": bool(diagnostics.get("applied")),
                "mode": diagnostics.get("mode", "legacy_full_catalog"),
                "candidates": diagnostics.get("candidates"),
                "reranked": bool(diagnostics.get("reranked")),
                "rerank_mode": diagnostics.get("rerank_mode", "off"),
                "rerank_model": diagnostics.get("rerank_model"),
            },
        },
        "suggestions": [
            {"label": "✅ Áp dụng tất cả", "action": "send", "text": "đồng ý, áp dụng tất cả segments này"},
            {"label": "🗑️ Bỏ bớt segment", "action": "prefill", "text": "Bỏ segment "},
            {"label": "🔍 Tìm thêm segments", "action": "prefill", "text": "Tìm thêm segments liên quan đến "},
        ],
    }


async def handle_openai_audience_entry(
    session_id: str,
    brief_hint: dict | None = None,
    *,
    client: Any | None = None,
) -> dict:
    session = await get_or_create_session(session_id)
    brief = session.get("form_state", {}).get("brief", {})
    source = "form_state"
    if not brief.get("brand"):
        pending = await get_pending_proposal(session_id)
        if pending and pending.get("field") == "brief" and pending.get("value"):
            value = pending["value"]
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    value = None
            if isinstance(value, dict) and value.get("brand"):
                brief, source = value, "pending_proposal"
                await update_form_state(session_id, "brief", brief)
                await clear_pending_proposal(session_id)
        if not brief.get("brand") and brief_hint and brief_hint.get("brand"):
            brief, source = brief_hint, "frontend_hint"
            await update_form_state(session_id, "brief", brief)
    if not brief.get("brand"):
        return {"skip": True, "reason": "brief_not_set"}
    if session.get("form_state", {}).get("segment", {}).get("attrs"):
        return {"skip": True, "reason": "audience_already_set"}
    await log_event(session_id, "audience_entry", {
        "brief_source": source, "brand": brief.get("brand"),
        "provider": "openai", "model": config.OPENAI_CAMPAIGN_MODEL,
    })
    return await _grounded_audience_entry(session_id, brief, client=client)
