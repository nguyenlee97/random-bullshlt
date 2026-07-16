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
    """Return approve/reject/question using only explicit decision language."""
    folded = _fold(message)
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
        "brief", "strategy", "audience", "targeting", "placements",
        "creative", "assignments", "forecast", "order", "report",
    )
    return {
        "run": {
            "run_id": run.get("run_id"),
            "status": run.get("status"),
            "trace_id": run.get("trace_id"),
        },
        "artifacts": {name: _artifact(workspace, name) for name in names},
    }


async def _recorded_response(
    session_id: str, message: str, text: str, *, tool: str, step: int,
    suggestions: list | None = None,
) -> AgentResponse:
    await add_message(session_id, "user", message)
    await add_message(session_id, "assistant", text)
    return AgentResponse(
        text=text,
        blocks=[],
        suggestions=suggestions or [],
        meta=ResponseMeta(tool=tool, model="none", step=step),
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
            detail = (waiting.get("result") or {}).get("message") \
                or "Agent cần bạn kiểm tra đầu ra hiện tại trước khi tiếp tục."
            return await _recorded_response(
                session_id,
                message,
                f"Autopilot đang chờ duyệt bước “{waiting.get('title') or waiting.get('key')}”. "
                f"{detail} Chat chỉ nhận quyết định rõ ràng ở thời điểm này; hãy chọn “Đồng ý, tiếp tục” "
                "hoặc “Từ chối”. Nếu cần thay đổi, hãy từ chối rồi chỉnh dữ liệu trong form.",
                tool="autopilot_review_explain",
                step=step,
                suggestions=["Đồng ý, tiếp tục", "Từ chối"],
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
        system = (
            "Bạn là trợ lý đọc kết quả Campaign Autopilot. Chỉ trả lời bằng tiếng Việt từ JSON artifact "
            "được cung cấp. Không gọi công cụ, không đề xuất hoặc thực hiện thay đổi workspace, không bịa số liệu. "
            "Nếu dữ liệu là forecast hoặc synthetic thì phải nói rõ đó là ước tính/mô phỏng. Trả lời ngắn, cụ thể."
        )
        user = f"ARTIFACT JSON:\n{json.dumps(context, ensure_ascii=False, default=str)[:24000]}\n\nCÂU HỎI:\n{message}"
        try:
            from llm import simple_generate
            text = await asyncio.to_thread(simple_generate, system, user)
        except Exception:
            brief = _artifact(workspace, "brief") or {}
            order = _artifact(workspace, "order") or {}
            order = order.get("order", order) if isinstance(order, dict) else {}
            text = (
                f"Campaign {brief.get('brand') or 'này'} đã ở trạng thái {status}. "
                f"Order: {order.get('id') or order.get('_id') or 'chưa có'} · "
                f"trạng thái giao quảng cáo: {order.get('status') or 'chưa xác định'}."
            )
        return await _recorded_response(
            session_id, message, text,
            tool="autopilot_readonly_qa", step=step,
        )

    return None
