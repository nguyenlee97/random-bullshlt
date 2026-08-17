"""State-aware chat boundary for Campaign Autopilot.

Autopilot owns workspace mutations while a run is active. Chat therefore has
three deliberately narrow roles: explain a locked run, record an explicit
review decision, or answer read-only questions from completed artifacts.
"""
from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from typing import Any

from models import AgentResponse, ResponseMeta
from session import add_message


ACTIVE_LOCKED = {"queued", "running", "paused"}
TERMINAL = {"completed", "failed", "cancelled"}


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    return " ".join(
        "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        .replace("đ", "d")
        .split()
    )


def review_intent(message: str) -> str:
    """Return approve/reject/retry/question at the authorization boundary.

    Mentioning approval while asking a question is not approval. Ambiguous,
    deferred, or explicitly "not yet" language always remains read-only.
    """
    folded = _fold(message)
    retry = re.search(
        r"\b("
        r"goi y lai audience|de xuat lai audience|tim lai audience"
        r"|recommend audience again|rerun audience|retry audience"
        r")\b",
        folded,
    )
    if retry:
        return "retry"
    deferred = re.search(
        r"\b("
        r"chua (dong y|xac nhan|chap nhan|duyet|phe duyet|quyet dinh)"
        r"|dung (duyet|phe duyet|xac nhan)"
        r"|khoan (duyet|phe duyet|xac nhan|tiep tuc)"
        r"|chi (dang )?hoi|dang hoi|hoi de (review|kiem tra)"
        r"|chua quyet dinh|not yet|do not approve|just asking"
        r")\b",
        folded,
    )
    if deferred or "?" in message:
        return "question"
    reject = re.search(
        r"\b(khong dong y|khong chap nhan|khong duyet|tu choi|huy bo|huy)\b",
        folded,
    )
    if reject:
        return "reject"
    approve = re.search(
        r"\b(dong y|xac nhan|chap nhan|duyet|phe duyet|tiep tuc)\b",
        folded,
    )
    return "approve" if approve else "question"


def _placement_selection_ordinals(message: str) -> list[int] | None:
    """Parse the bounded edit command; approval remains a separate action."""
    folded = _fold(message)
    if "?" in message or re.search(r"\b(khong chon|bo|loai)\b", folded):
        return None
    match = re.search(
        r"\bchon\b(?:\s+(?:cac|nhung))?\s+"
        r"(?:ad\s+zone|zone|placement|vi\s+tri)\b(?P<tail>.*)$",
        folded,
    )
    if not match:
        return None
    values = [int(value) for value in re.findall(r"\d+", match.group("tail"))]
    return list(dict.fromkeys(values)) if values else None


def _audience_selection_ordinals(message: str) -> list[int] | None:
    """Parse only explicit numbered audience edits; approval stays separate."""
    folded = _fold(message)
    if "?" in message or re.search(r"\b(khong chon|bo|loai)\b", folded):
        return None
    match = re.search(
        r"\bchon\b(?:\s+(?:cac|nhung))?\s+"
        r"(?:audience|segment|doi\s+tuong)\b(?P<tail>.*)$",
        folded,
    )
    if not match:
        return None
    values = [int(value) for value in re.findall(r"\d+", match.group("tail"))]
    return list(dict.fromkeys(values)) if values else None


def _is_creative_preview_request(message: str) -> bool:
    """Safe read-only fast path; never grants approval or mutates the run."""
    folded = _fold(message)
    if any(term in folded for term in (
        "chap nhan creative", "duyet creative", "phe duyet creative",
        "approve creative", "accept creative",
    )):
        return False
    creative_terms = (
        "creative", "banner", "hinh", "anh", "asset", "mau quang cao",
    )
    preview_terms = (
        "xem", "cho xem", "gui", "nhan", "mo", "preview", "show", "display",
    )
    return (
        any(term in folded for term in creative_terms)
        and any(term in folded for term in preview_terms)
    )


def _explicit_creative_override(message: str) -> dict | None:
    """Parse the documented manual-review command without an LLM round trip.

    The model classifier remains useful for free-form requests, but this exact
    command is part of the user-facing checkpoint contract and must be
    deterministic in both the workspace and Zalo chat.
    """
    folded = _fold(message)
    if not re.search(
        r"\b(?:chap nhan|duyet|phe duyet|approve|accept)\s+creative\b",
        folded,
    ):
        return None

    creative_numbers = list(dict.fromkeys(
        int(value) for value in re.findall(r"\d+", folded)
    ))
    reason_match = re.search(
        r"(?:\bvì\b|\bvi\b|\bbecause\b)\s+(.+?)\s*$",
        message,
        flags=re.IGNORECASE,
    )
    reason = reason_match.group(1).strip() if reason_match else ""
    if not creative_numbers or len(reason) < 5:
        return None
    return {
        "creative_numbers": creative_numbers,
        "reason": reason,
        "evidence": message.strip(),
    }


def _creative_analysis_choice(message: str) -> str | None:
    """Parse the same explicit Analyze/Skip choice exposed by the workspace UI."""
    folded = _fold(message)
    if re.search(
        r"\b(skip(?: duyet)?(?: creative)?|bo qua(?: phan tich)?|khong phan tich)\b",
        folded,
    ):
        return "skip"
    if re.search(
        r"\b(phan tich(?: creative)?|bat dau phan tich|kiem tra creative)\b",
        folded,
    ):
        return "analyze"
    return None


def _artifact(workspace: dict, name: str) -> Any:
    return (workspace.get("artifacts", {}).get(name, {}) or {}).get("value")


def _creative_review_items(
    workspace: dict, intel_docs: list[dict] | None = None,
) -> list[dict]:
    creative = _artifact(workspace, "creative") or {}
    files = creative.get("files") or []
    verdict = _artifact(workspace, "creative_verdict") or {}
    docs = list(intel_docs or verdict.get("files") or [])

    def matching_doc(file: dict) -> dict:
        return next(
            (
                doc for doc in docs
                if (
                    doc.get("analysis_id") == file.get("analysisId")
                    or (doc.get("url") and doc.get("url") == file.get("url"))
                    or (doc.get("name") and doc.get("name") == file.get("name"))
                )
            ),
            {},
        )

    items = []
    for index, file in enumerate(files, 1):
        doc = matching_doc(file)
        status = (
            doc.get("effective_status")
            or doc.get("status")
            or file.get("analysisStatus")
            or "analysis_required"
        )
        reasons = list(doc.get("review_reasons") or file.get("reviewReasons") or [])
        advisories = list(doc.get("generation_advisories") or [])
        items.append({
            "number": index,
            "name": file.get("name") or f"Creative {index}",
            "url": file.get("url") or "",
            "width": file.get("width"),
            "height": file.get("height"),
            "format_id": file.get("formatId") or "",
            "analysis_id": doc.get("analysis_id") or file.get("analysisId"),
            "status": status,
            "review_reasons": reasons,
            "advisories": advisories,
        })
    return items


def _creative_review_summary(items: list[dict]) -> str:
    labels = {
        "auto_approved": "Đạt kiểm tra",
        "approved_override": "Đã được duyệt thủ công",
        "needs_review": "Cần duyệt thủ công",
        "analysis_required": "Chưa có kết quả kiểm tra",
    }
    lines = [f"Có {len(items)} creative trong run hiện tại:"]
    for item in items:
        size = (
            f"{item.get('width')}×{item.get('height')}"
            if item.get("width") and item.get("height")
            else "chưa rõ kích thước"
        )
        line = (
            f"{item['number']}. Creative {item['number']} · {size} · "
            f"{labels.get(item.get('status'), item.get('status') or 'chưa kiểm tra')}"
        )
        if item.get("review_reasons"):
            line += "\n   Cảnh báo: " + "; ".join(
                str(reason)[:180] for reason in item["review_reasons"][:3]
            )
        elif item.get("advisories"):
            line += "\n   Lưu ý không chặn duyệt: " + "; ".join(
                str(note)[:180] for note in item["advisories"][:2]
            )
        lines.append(line)
    lines.append(
        "Ảnh được gửi ngay sau tin nhắn này. Việc xem ảnh không thay đổi checkpoint."
    )
    return "\n".join(lines)


_REVIEW_CONTEXT_ARTIFACTS = {
    "generate_strategy": ("brief", "strategy"),
    "retrieve_audience": ("brief", "strategy", "audience"),
    "derive_targeting": ("brief", "audience", "targeting"),
    "plan_placement_intent": (
        "brief", "strategy", "targeting", "placement_intent",
    ),
    "plan_creative_formats": (
        "brief", "placement_intent", "creative_format_plan",
    ),
    "prepare_creatives": (
        "brief", "creative_format_plan", "creative",
    ),
    "analyze_creatives": (
        "brief", "creative_format_plan", "creative", "creative_verdict",
    ),
    "rank_placements": (
        "brief", "placement_intent", "creative_verdict", "placements",
    ),
    "assign_creatives": (
        "brief", "creative", "creative_verdict", "placements", "assignments",
    ),
    "forecast": (
        "brief", "targeting", "placements", "assignments", "forecast",
    ),
    "build_order_draft": ("brief", "forecast", "order_draft"),
    "run_order_guard": (
        "brief", "creative_verdict", "assignments", "forecast", "order_draft",
    ),
    "launch_approval": (
        "brief", "strategy", "creative_verdict", "placements", "assignments",
        "forecast", "order_draft",
    ),
}


def _read_only_context(
    workspace: dict, run: dict, waiting: dict | None = None,
) -> dict:
    all_names = (
        "brief", "strategy", "audience", "targeting", "placement_intent",
        "creative_format_plan", "creative", "creative_verdict", "placements",
        "assignments", "forecast", "order_draft", "order", "report",
    )
    names = (
        _REVIEW_CONTEXT_ARTIFACTS.get(waiting.get("key"), ("brief",))
        if waiting
        else all_names
    )
    context = {}
    if waiting:
        # Keep the active review evidence first so bounded model input can never
        # lose the checkpoint behind unrelated historical artifacts.
        context["review_checkpoint"] = {
            "task_id": waiting.get("task_id"),
            "key": waiting.get("key"),
            "title": waiting.get("title"),
            "result": waiting.get("result"),
            "evidence": waiting.get("evidence") or [],
            "pending_artifact": (
                (waiting.get("pending_artifact") or {}).get("value")
            ),
        }
    context["run"] = {
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "trace_id": run.get("trace_id"),
    }
    context["artifacts"] = {
        name: value
        for name in names
        if (value := _artifact(workspace, name)) is not None
    }
    return context


async def _answer_run_question(
    *, session_id: str, message: str, context: dict, run: dict,
) -> tuple[str, str]:
    """Answer one read-only run/review question through the locked provider."""
    system = (
        "Bạn là trợ lý đọc kết quả và checkpoint của Campaign Autopilot. Chỉ trả lời bằng "
        "tiếng Việt từ JSON artifact được cung cấp. Không gọi công cụ, không đề xuất hoặc "
        "thực hiện thay đổi workspace, không xem câu hỏi là quyết định duyệt, không bịa số "
        "liệu. Forecast phải được gọi rõ là ước tính. Trả lời trực tiếp câu hỏi trước, ngắn "
        "và cụ thể. Khi có review_checkpoint, ưu tiên dữ liệu checkpoint đó và không tóm tắt "
        "audience, strategy hay trạng thái không liên quan. Nếu thiếu bằng chứng cần thiết, "
        "nói rõ dữ liệu nào chưa có thay vì thay thế bằng trạng thái khác."
    )
    user = (
        f"ARTIFACT JSON:\n"
        f"{json.dumps(context, ensure_ascii=False, default=str)[:24000]}"
        f"\n\nCÂU HỎI:\n{message}"
    )
    from campaign_engines.dispatcher import dispatch_autopilot
    from campaign_models import LEGACY_CONVERSATION_MODEL

    conversation_model = run.get("conversation_model") or LEGACY_CONVERSATION_MODEL
    text, provenance = await dispatch_autopilot(
        conversation_model,
        greennode_handler=_answer_greennode_autopilot_question,
        openai_handler=_answer_openai_autopilot_question,
        session_id=session_id,
        message=message,
        context=context,
        system=system,
        user=user,
    )
    answer_model = str(
        provenance.get("model")
        or run.get("conversation_model_version")
        or conversation_model
    )
    return text, answer_model


async def _answer_greennode_autopilot_question(
    *, session_id: str, message: str, context: dict, system: str, user: str,
) -> tuple[str, dict]:
    del session_id, message, context
    from llm import simple_generate

    text = await asyncio.to_thread(simple_generate, system, user)
    return text, {"provider": "greennode"}


async def _answer_openai_autopilot_question(
    *, session_id: str, message: str, context: dict, system: str, user: str,
) -> tuple[str, dict]:
    del system, user
    from openai_campaign.autopilot import answer_openai_autopilot_question

    return await answer_openai_autopilot_question(
        session_id=session_id,
        message=message,
        context=context,
    )


async def _recorded_response(
    session_id: str, message: str, text: str, *, tool: str, step: int,
    suggestions: list | None = None, model: str = "none",
    media_parts: list[dict] | None = None,
) -> AgentResponse:
    await add_message(session_id, "user", message)
    await add_message(session_id, "assistant", text)
    return AgentResponse(
        text=text,
        blocks=[],
        suggestions=suggestions or [],
        meta=ResponseMeta(tool=tool, model=model, step=step),
        media_parts=media_parts or [],
    )


async def route_autopilot_chat(
    message: str, session_id: str, step: int,
    active_report_tab: str = "daily_ops",
) -> AgentResponse | None:
    """Intercept chat only when this session is an Autopilot campaign/run."""
    from autopilot.service import (
        choose_creative_analysis,
        get_latest_run,
        rerun_review_task,
        review_task,
        select_audience_recommendations,
        select_placement_intent,
    )
    from workspace.service import get_workspace

    workspace = await get_workspace(session_id)
    if workspace.get("experience_mode") != "autopilot":
        return None
    run = await get_latest_run(session_id)
    if not run:
        return None

    status = run.get("status")
    if status in ACTIVE_LOCKED:
        return await _recorded_response(
            session_id,
            message,
            "Autopilot đang thực thi và tạm khóa chat để tránh thay đổi workspace giữa run. "
            "Chat sẽ tự mở khi Agent cần xác nhận hoặc khi run kết thúc.",
            tool="autopilot_chat_locked",
            step=step,
        )

    waiting = next(
        (task for task in run.get("tasks", []) if task.get("status") == "waiting_review"),
        None,
    )
    if status == "waiting_review" and waiting:
        from campaign_models import OPENAI_GPT_5_4_MINI

        if (
            run.get("conversation_model") == OPENAI_GPT_5_4_MINI
            and waiting.get("key") in {"analyze_creatives", "assign_creatives"}
        ):
            creative_value = _artifact(workspace, "creative") or {}
            creative_files = creative_value.get("files") or []
            waiting_value = (
                (waiting.get("pending_artifact") or {}).get("value")
                or waiting.get("result")
                or {}
            )
            if (
                waiting.get("key") == "analyze_creatives"
                and waiting_value.get("reason") == "analysis_confirmation_required"
            ):
                creative_items = _creative_review_items(workspace)
                if _is_creative_preview_request(message):
                    media_parts = [
                        {"kind": "image", "image_url": item["url"]}
                        for item in creative_items
                        if str(item.get("url") or "").startswith("https://")
                    ]
                    return await _recorded_response(
                        session_id,
                        message,
                        _creative_review_summary(creative_items),
                        tool="autopilot_creative_preview",
                        step=step,
                        suggestions=[
                            "Phân tích creative",
                            "Skip duyệt creative",
                            "Hủy",
                        ],
                        media_parts=media_parts,
                    )
                analysis_choice = _creative_analysis_choice(message)
                if analysis_choice:
                    try:
                        await choose_creative_analysis(
                            run["run_id"],
                            analysis_choice,
                            actor="zalo_campaign_operator",
                        )
                    except Exception as exc:
                        return await _recorded_response(
                            session_id,
                            message,
                            f"Chưa thể cập nhật lựa chọn creative: {str(exc)}. "
                            "Checkpoint chưa thay đổi.",
                            tool="autopilot_creative_analysis_conflict",
                            step=step,
                        )
                    text = (
                        "Đã bắt đầu Phân tích creative. Agent sẽ gửi kết quả VLM "
                        "cho từng creative khi hoàn tất."
                        if analysis_choice == "analyze"
                        else
                        "Đã Skip duyệt creative: bỏ qua Creative Intelligence và "
                        "duyệt thủ công toàn bộ creative. Quyết định này được lưu "
                        "trong audit trail."
                    )
                    return await _recorded_response(
                        session_id,
                        message,
                        text,
                        tool="autopilot_creative_analysis_choice",
                        step=step,
                    )
                return await _recorded_response(
                    session_id,
                    message,
                    "Creative đã sẵn sàng. Hãy chọn “Phân tích creative” để chạy "
                    "Creative Intelligence hoặc “Skip duyệt creative” để bỏ qua "
                    "phân tích và duyệt thủ công toàn bộ. “Xác nhận” đơn lẻ chưa "
                    "chọn thay bạn.",
                    tool="autopilot_creative_analysis_choice_required",
                    step=step,
                    suggestions=["Phân tích creative", "Skip duyệt creative", "Xem creative"],
                )
            from creative_intel.service import (
                approve_override,
                sync_generation_vlm_reviews,
            )

            intel_docs = await sync_generation_vlm_reviews(
                session_id, creative_files,
            )
            creative_items = _creative_review_items(workspace, intel_docs)
            if _is_creative_preview_request(message):
                media_parts = [
                    {"kind": "image", "image_url": item["url"]}
                    for item in creative_items
                    if str(item.get("url") or "").startswith("https://")
                ]
                return await _recorded_response(
                    session_id,
                    message,
                    _creative_review_summary(creative_items),
                    tool="autopilot_creative_preview",
                    step=step,
                    suggestions=[
                        "Chấp nhận creative 1 vì tôi đã kiểm tra thủ công",
                        "Tạo lại creative",
                        "Xác nhận",
                    ],
                    media_parts=media_parts,
                )
            plain_decisions = {
                "xac nhan", "dong y", "duyet", "tiep tuc",
                "huy", "tu choi", "khong duyet",
            }
            action = None
            explicit_override = _explicit_creative_override(message)
            if explicit_override:
                from openai_campaign.autopilot import CreativeReviewAction

                action = CreativeReviewAction(
                    intent="approve_override",
                    explicit=True,
                    **explicit_override,
                )
            elif _fold(message) not in plain_decisions:
                try:
                    from openai_campaign.autopilot import (
                        classify_openai_creative_review_action,
                    )

                    action = await classify_openai_creative_review_action(
                        session_id=session_id,
                        message=message,
                        creatives=creative_items,
                    )
                except Exception:
                    action = None

            action_evidence = _fold(getattr(action, "evidence", ""))
            valid_action = bool(
                action
                and action_evidence
                and action_evidence in _fold(message)
            )
            if valid_action and action.intent == "show_creatives":
                media_parts = [
                    {"kind": "image", "image_url": item["url"]}
                    for item in creative_items
                    if str(item.get("url") or "").startswith("https://")
                ]
                return await _recorded_response(
                    session_id,
                    message,
                    _creative_review_summary(creative_items),
                    tool="autopilot_creative_preview",
                    step=step,
                    suggestions=[
                        "Chấp nhận creative 1 vì tôi đã kiểm tra thủ công",
                        "Tạo lại creative",
                        "Xác nhận",
                    ],
                    media_parts=media_parts,
                )

            if valid_action and action.intent == "replace_or_regenerate":
                return await _recorded_response(
                    session_id,
                    message,
                    "Mình chưa thay creative chỉ từ câu hỏi này. Hãy mở workspace và chọn "
                    "“Chỉnh hoặc thay creative” để tải file khác hoặc tạo lại; run hiện tại "
                    "được giữ nguyên và chỉ các bước phụ thuộc sẽ chạy lại.",
                    tool="autopilot_creative_replace_guidance",
                    step=step,
                )

            if valid_action and action.intent == "approve_override":
                flagged = [
                    item for item in creative_items
                    if item.get("status") == "needs_review"
                ]
                requested_numbers = list(dict.fromkeys(action.creative_numbers))
                if not requested_numbers and len(flagged) == 1:
                    requested_numbers = [flagged[0]["number"]]
                chosen = [
                    item for item in flagged
                    if item["number"] in requested_numbers
                ]
                invalid_numbers = [
                    number for number in requested_numbers
                    if number < 1
                    or number > len(creative_items)
                    or not any(item["number"] == number for item in flagged)
                ]
                reason = action.reason.strip()
                if (
                    not action.explicit
                    or len(reason) < 5
                    or not chosen
                    or invalid_numbers
                    or any(not item.get("analysis_id") for item in chosen)
                ):
                    return await _recorded_response(
                        session_id,
                        message,
                        "Chưa ghi nhận phê duyệt thủ công. Hãy nêu rõ creative và lý do, "
                        "ví dụ: “Chấp nhận creative 1 vì tôi đã kiểm tra chữ và thương hiệu”. "
                        "Checkpoint chưa thay đổi.",
                        tool="autopilot_creative_override_invalid",
                        step=step,
                    )
                for item in chosen:
                    await approve_override(
                        session_id,
                        item["analysis_id"],
                        reason,
                        actor="zalo_campaign_operator",
                    )
                from autopilot.service import reconcile_workspace_changes

                await reconcile_workspace_changes(run["run_id"])
                approved_labels = ", ".join(
                    f"Creative {item['number']}" for item in chosen
                )
                return await _recorded_response(
                    session_id,
                    message,
                    f"Đã lưu phê duyệt thủ công cho {approved_labels}. Lý do: {reason}. "
                    "Cảnh báo gốc và người duyệt đã được giữ trong audit trail. "
                    "Autopilot đang kiểm tra lại các bước phụ thuộc và sẽ gửi phân bổ "
                    "creative mới để bạn xác nhận.",
                    tool="autopilot_creative_override",
                    step=step,
                    suggestions=["Xem creative", "Hủy"],
                )

            blocked_creatives = [
                item for item in creative_items
                if item.get("status") not in {"auto_approved", "approved_override"}
            ]
            if blocked_creatives and review_intent(message) == "approve":
                blocked_labels = ", ".join(
                    f"Creative {item['number']}" for item in blocked_creatives
                )
                return await _recorded_response(
                    session_id,
                    message,
                    f"Chưa thể xác nhận bước này vì {blocked_labels} chưa đạt kiểm tra "
                    "hoặc chưa được duyệt thủ công. Bạn có thể nhắn “Xem creative”, "
                    "thay/tạo lại creative, hoặc chấp nhận một creative kèm lý do.",
                    tool="autopilot_creative_review_required",
                    step=step,
                    suggestions=["Xem creative", "Chỉnh hoặc thay creative", "Hủy"],
                )

        audience_ordinals = _audience_selection_ordinals(message)
        audience_task = next(
            (task for task in run.get("tasks", []) if task.get("key") == "retrieve_audience"),
            None,
        )
        audience_review_checkpoint = bool(
            audience_task
            and audience_task.get("status") == "waiting_review"
            and waiting.get("key") == "retrieve_audience"
        )
        current_audience_value = (
            (
                (audience_task.get("pending_artifact") or {}).get("value")
                or audience_task.get("result")
                or {}
            )
            if audience_review_checkpoint
            else (_artifact(workspace, "audience") or {})
        )
        audience_candidates = (
            current_audience_value.get("recommendations")
            or [
                *(current_audience_value.get("attrs") or []),
                *(current_audience_value.get("adjacent_attrs") or []),
            ]
        )
        can_edit_openai_audience = (
            run.get("conversation_model") == OPENAI_GPT_5_4_MINI
            and audience_review_checkpoint
            and bool(audience_candidates)
        )
        if (
            can_edit_openai_audience
            and audience_ordinals is None
            and review_intent(message) == "question"
        ):
            try:
                from openai_campaign.autopilot import (
                    classify_openai_audience_review_selection,
                )

                selection_action = (
                    await classify_openai_audience_review_selection(
                        session_id=session_id,
                        message=message,
                        candidates=audience_candidates,
                    )
                )
            except Exception as exc:
                from agent_logger import alog

                await alog(session_id, "error", {
                    "handler": "autopilot_audience_review_selection",
                    "conversation_model": run.get("conversation_model"),
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                    "cross_provider_fallback": False,
                })
                selection_action = None

            raw_action_evidence = str(
                getattr(selection_action, "evidence", "")
            ).strip()
            quote_pairs = {('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")}
            if (
                len(raw_action_evidence) >= 2
                and (
                    raw_action_evidence[0],
                    raw_action_evidence[-1],
                ) in quote_pairs
            ):
                raw_action_evidence = raw_action_evidence[1:-1].strip()
            action_evidence = _fold(raw_action_evidence)
            valid_selection_action = bool(
                selection_action
                and selection_action.intent == "select"
                and selection_action.explicit
                and action_evidence
                and action_evidence in _fold(message)
            )
            if valid_selection_action and (
                selection_action.ambiguous
                or not selection_action.candidate_numbers
            ):
                clarification = (
                    selection_action.clarification_question.strip()
                    or "Bạn muốn chọn những audience nào trong danh sách đang chờ duyệt?"
                )
                return await _recorded_response(
                    session_id,
                    message,
                    f"{clarification} Checkpoint chưa bị thay đổi.",
                    tool="autopilot_audience_selection_clarification",
                    step=step,
                )
            if valid_selection_action:
                audience_ordinals = list(dict.fromkeys(
                    selection_action.candidate_numbers
                ))

        if can_edit_openai_audience and audience_ordinals is not None:
            candidates = audience_candidates
            invalid = [
                ordinal for ordinal in audience_ordinals
                if ordinal < 1 or ordinal > len(candidates)
            ]
            if invalid:
                return await _recorded_response(
                    session_id,
                    message,
                    "Không thể cập nhật audience: số "
                    + ", ".join(str(value) for value in invalid)
                    + f" nằm ngoài danh sách 1–{len(candidates)}. "
                    "Checkpoint chưa bị thay đổi.",
                    tool="autopilot_audience_selection_invalid",
                    step=step,
                )
            selected_segments = [
                candidates[ordinal - 1] for ordinal in audience_ordinals
            ]
            selected_ids = [
                str(
                    segment.get("segmentId")
                    or segment.get("_id")
                    or segment.get("code")
                    or segment.get("fullLabel")
                    or segment.get("name")
                    or ""
                ).strip()
                for segment in selected_segments
                if isinstance(segment, dict)
            ]
            try:
                await select_audience_recommendations(
                    run["run_id"],
                    selected_ids,
                    actor="campaign_operator",
                    reason="explicit ordinal audience selection from Autopilot chat",
                )
            except Exception as exc:
                return await _recorded_response(
                    session_id,
                    message,
                    f"Chưa thể cập nhật audience: {str(exc)}. "
                    "Checkpoint chưa bị thay đổi.",
                    tool="autopilot_audience_selection_conflict",
                    step=step,
                )
            chosen = ", ".join(
                f"{ordinal}. "
                + str(
                    segment.get("fullLabel")
                    or segment.get("name")
                    or segment.get("code")
                    or segment.get("_id")
                )
                for ordinal, segment in zip(audience_ordinals, selected_segments)
            )
            return await _recorded_response(
                session_id,
                message,
                (
                    f"Đã cập nhật audience được chọn: {chosen}. "
                    "Nhóm liên quan chỉ được áp dụng vì bạn vừa yêu cầu rõ. "
                    "Checkpoint vẫn đang chờ duyệt; hãy gửi “Xác nhận” riêng để tiếp tục."
                    if audience_review_checkpoint
                    else
                    f"Đã cập nhật audience được chọn: {chosen}. "
                    "Autopilot đang tính lại Targeting, placement và kế hoạch creative phụ thuộc "
                    "trên đúng run hiện tại; quyết định checkpoint cũ không được tự động áp dụng."
                ),
                tool="autopilot_audience_selection",
                step=step,
                suggestions=(
                    ["Xác nhận", "Gợi ý lại audience", "Hủy"]
                    if audience_review_checkpoint
                    else []
                ),
            )

        placement_ordinals = _placement_selection_ordinals(message)
        if (
            run.get("conversation_model") == OPENAI_GPT_5_4_MINI
            and waiting.get("key") == "plan_placement_intent"
            and placement_ordinals is not None
        ):
            pending_value = (
                (waiting.get("pending_artifact") or {}).get("value")
                or waiting.get("result")
                or {}
            )
            candidates = pending_value.get("candidates") or []
            invalid = [
                ordinal
                for ordinal in placement_ordinals
                if ordinal < 1 or ordinal > len(candidates)
            ]
            if invalid:
                return await _recorded_response(
                    session_id,
                    message,
                    "Không thể cập nhật ad zone: số "
                    + ", ".join(str(value) for value in invalid)
                    + f" nằm ngoài danh sách 1–{len(candidates)}. "
                    "Checkpoint chưa bị thay đổi.",
                    tool="autopilot_placement_selection_invalid",
                    step=step,
                )
            selected_zones = [
                candidates[ordinal - 1] for ordinal in placement_ordinals
            ]
            selected_ids = [
                str(zone.get("id"))
                for zone in selected_zones
                if isinstance(zone, dict) and zone.get("id")
            ]
            try:
                await select_placement_intent(
                    run["run_id"],
                    selected_ids,
                    actor="campaign_operator",
                    reason="explicit ordinal selection from Autopilot chat",
                )
            except Exception as exc:
                return await _recorded_response(
                    session_id,
                    message,
                    f"Chưa thể cập nhật ad zone: {str(exc)}. "
                    "Checkpoint chưa bị thay đổi.",
                    tool="autopilot_placement_selection_conflict",
                    step=step,
                )
            chosen = ", ".join(
                f"{ordinal}. "
                + str(
                    zone.get("name")
                    or zone.get("label")
                    or zone.get("id")
                )
                for ordinal, zone in zip(placement_ordinals, selected_zones)
            )
            return await _recorded_response(
                session_id,
                message,
                f"Đã cập nhật danh sách ad zone còn lại: {chosen}. "
                "Đây mới là chỉnh sửa danh sách; checkpoint vẫn đang chờ duyệt. "
                "Hãy gửi “Xác nhận” riêng khi bạn muốn tiếp tục.",
                tool="autopilot_placement_selection",
                step=step,
                suggestions=["Xác nhận", "Hủy"],
            )

        intent = review_intent(message)
        if intent == "retry":
            if waiting.get("key") != "retrieve_audience":
                return await _recorded_response(
                    session_id,
                    message,
                    "Chỉ có thể gợi ý lại khi Autopilot đang dừng ở checkpoint Audience. "
                    "Checkpoint hiện tại chưa bị thay đổi.",
                    tool="autopilot_audience_rerun_unavailable",
                    step=step,
                )
            try:
                await rerun_review_task(
                    run["run_id"],
                    waiting["task_id"],
                    actor="campaign_operator",
                    reason="explicit audience rerun from Autopilot chat",
                )
            except Exception as exc:
                return await _recorded_response(
                    session_id,
                    message,
                    f"Chưa thể gợi ý lại audience: {str(exc)}. "
                    "Danh sách hiện tại vẫn được giữ để review.",
                    tool="autopilot_audience_rerun_conflict",
                    step=step,
                    suggestions=[
                        "Gợi ý lại audience",
                        "Đồng ý, tiếp tục",
                        "Từ chối",
                    ],
                )
            return await _recorded_response(
                session_id,
                message,
                "Đã yêu cầu Autopilot truy xuất và xếp hạng lại audience. "
                "Danh sách cũ chưa được duyệt; Agent sẽ gửi danh sách mới khi hoàn tất.",
                tool="autopilot_audience_rerun",
                step=step,
            )
        if intent == "question":
            context = _read_only_context(workspace, run, waiting)
            try:
                text, answer_model = await _answer_run_question(
                    session_id=session_id,
                    message=message,
                    context=context,
                    run=run,
                )
                text = (
                    f"{text}\n\n"
                    "Đây chỉ là câu trả lời review; checkpoint vẫn đang chờ quyết định của bạn."
                )
            except Exception as exc:
                from agent_logger import alog

                await alog(session_id, "error", {
                    "handler": "autopilot_review_qa",
                    "conversation_model": run.get("conversation_model"),
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                    "cross_provider_fallback": False,
                })
                detail = (waiting.get("result") or {}).get("message") \
                    or "Agent cần bạn kiểm tra đầu ra hiện tại trước khi tiếp tục."
                text = (
                    f"Autopilot đang chờ duyệt bước "
                    f"“{waiting.get('title') or waiting.get('key')}”. {detail} "
                    "Câu hỏi này chưa làm thay đổi trạng thái checkpoint."
                )
                answer_model = str(
                    run.get("conversation_model_version")
                    or run.get("conversation_model")
                    or "none"
                )
            return await _recorded_response(
                session_id,
                message,
                text,
                tool="autopilot_review_qa",
                step=step,
                suggestions=(
                    ["Gợi ý lại audience", "Đồng ý, tiếp tục", "Từ chối"]
                    if waiting.get("key") == "retrieve_audience"
                    else ["Đồng ý, tiếp tục", "Từ chối"]
                ),
                model=answer_model,
            )

        approved = intent == "approve"
        try:
            await review_task(
                run["run_id"], waiting["task_id"], approved=approved,
                actor="campaign_operator", reason="explicit decision from Autopilot chat",
            )
        except Exception as exc:
            return await _recorded_response(
                session_id, message,
                f"Chưa thể ghi nhận quyết định: {str(exc)}. Workspace chưa bị thay đổi.",
                tool="autopilot_review_conflict", step=step,
                suggestions=["Đồng ý, tiếp tục", "Từ chối"],
            )
        if approved:
            text = (
                f"Đã xác nhận bước “{waiting.get('title') or waiting.get('key')}”. "
                "Autopilot tiếp tục thực thi theo kế hoạch hiện tại."
            )
        else:
            text = (
                f"Đã từ chối bước “{waiting.get('title') or waiting.get('key')}”. "
                "Run đã dừng; bạn có thể mở form, chỉnh dữ liệu rồi bắt đầu một run mới."
            )
        await add_message(session_id, "user", message)
        await add_message(session_id, "assistant", text)
        return AgentResponse(
            text=text,
            blocks=[],
            meta=ResponseMeta(tool="autopilot_review_chat", model="none", step=step),
            suggestions=[],
        )

    if status in TERMINAL:
        # A completed Autopilot campaign uses the same evidence-cited report
        # analyst as Copilot. Resume can restore an older UI step even though
        # the durable report artifact already exists, so artifact state wins.
        if status == "completed" and (
            step == 5 or _artifact(workspace, "report") is not None
        ):
            from handlers.report import handle_report_chat

            return await handle_report_chat(
                message,
                session_id,
                active_report_tab,
                conversation_model=run.get("conversation_model"),
            )
        context = _read_only_context(workspace, run)
        try:
            text, answer_model = await _answer_run_question(
                session_id=session_id,
                message=message,
                context=context,
                run=run,
            )
        except Exception as exc:
            from agent_logger import alog

            await alog(session_id, "error", {
                "handler": "autopilot_readonly_qa",
                "conversation_model": run.get("conversation_model"),
                "error_type": type(exc).__name__,
                "error": str(exc)[:300],
                "cross_provider_fallback": False,
            })
            brief = _artifact(workspace, "brief") or {}
            order = _artifact(workspace, "order") or {}
            order = order.get("order", order) if isinstance(order, dict) else {}
            text = (
                f"Campaign {brief.get('brand') or 'này'} đã ở trạng thái {status}. "
                f"Order: {order.get('id') or order.get('_id') or 'chưa có'} · "
                f"trạng thái giao quảng cáo: {order.get('status') or 'chưa xác định'}."
            )
            answer_model = str(
                run.get("conversation_model_version")
                or run.get("conversation_model")
                or "none"
            )
        return await _recorded_response(
            session_id, message, text,
            tool="autopilot_readonly_qa", step=step, model=answer_model,
        )

    return None
