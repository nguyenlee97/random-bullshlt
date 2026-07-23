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
    """Return approve/reject/question at the human authorization boundary.

    Mentioning approval while asking a question is not approval. Ambiguous,
    deferred, or explicitly "not yet" language always remains read-only.
    """
    folded = _fold(message)
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


def _artifact(workspace: dict, name: str) -> Any:
    return (workspace.get("artifacts", {}).get(name, {}) or {}).get("value")


def _read_only_context(workspace: dict, run: dict) -> dict:
    names = (
        "brief", "strategy", "audience", "targeting", "placement_intent",
        "creative_format_plan", "creative", "creative_verdict", "placements",
        "assignments", "forecast", "order_draft", "order", "report",
    )
    return {
        "run": {
            "run_id": run.get("run_id"),
            "status": run.get("status"),
            "trace_id": run.get("trace_id"),
        },
        "artifacts": {name: _artifact(workspace, name) for name in names},
    }


async def _answer_run_question(
    *, session_id: str, message: str, context: dict, run: dict,
) -> tuple[str, str]:
    """Answer one read-only run/review question through the locked provider."""
    system = (
        "Bạn là trợ lý đọc kết quả và checkpoint của Campaign Autopilot. Chỉ trả lời bằng "
        "tiếng Việt từ JSON artifact được cung cấp. Không gọi công cụ, không đề xuất hoặc "
        "thực hiện thay đổi workspace, không xem câu hỏi là quyết định duyệt, không bịa số "
        "liệu. Forecast phải được gọi rõ là ước tính. Trả lời trực tiếp, ngắn và cụ thể."
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
) -> AgentResponse:
    await add_message(session_id, "user", message)
    await add_message(session_id, "assistant", text)
    return AgentResponse(
        text=text,
        blocks=[],
        suggestions=suggestions or [],
        meta=ResponseMeta(tool=tool, model=model, step=step),
    )


async def route_autopilot_chat(
    message: str, session_id: str, step: int,
) -> AgentResponse | None:
    """Intercept chat only when this session is an Autopilot campaign/run."""
    from autopilot.service import get_latest_run, review_task
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
        intent = review_intent(message)
        if intent == "question":
            context = _read_only_context(workspace, run)
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
                suggestions=["Đồng ý, tiếp tục", "Từ chối"],
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
        # A completed Autopilot campaign uses the same isolated analytics Q&A
        # handler as Copilot while the Report module is active.
        if status == "completed" and step == 5:
            return None
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
