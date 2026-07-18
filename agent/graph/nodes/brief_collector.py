"""Typed Brief collection for a canonical, always-approvable draft.

The ordinary tool-capable model is allowed to answer questions, but an initial
Brief may never exist only as prose. This node forces one of three typed
outcomes: clarify, answer, or create a durable proposal.
"""
from __future__ import annotations

import asyncio
from datetime import date
import json
import re
import time
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from agent_logger import alog
from autopilot.capabilities import validate_brief_value
from graph.state import AgentState
from graph.structured import StructuredOutputError, structured
from handlers.freeform import _WORKSPACE_SUGGESTIONS, _build_update_summary
from session import add_message, clear_pending_proposal, set_pending_proposal
from time_context import campaign_now, campaign_today
from workspace.service import approve_proposal, create_proposal, get_workspace


class BriefDraft(BaseModel):
    brand: str = Field(min_length=1, max_length=200)
    objective: Literal["awareness", "consideration", "conversion", "retention"]
    kpi: str = Field(min_length=1, max_length=500)
    budget: float = Field(
        gt=0,
        le=5000,
        description="Campaign budget in millions of VND; 2 means 2,000,000 VND",
    )
    startDate: str = Field(min_length=10, max_length=10)
    endDate: str = Field(min_length=10, max_length=10)
    notes: str = Field(default="", max_length=12000)

    model_config = {"extra": "forbid"}

    @field_validator("budget", mode="before")
    @classmethod
    def normalize_budget_to_millions(cls, value):
        """Accept a provider returning raw VND although the workspace uses millions.

        MiniMax can correctly understand ``2 triệu`` but still serialize it as
        ``2000000``. Values just above the workspace ceiling remain invalid;
        only amounts large enough to be unambiguously raw VND are converted.
        """
        if isinstance(value, bool):
            raise ValueError("budget must be a number")
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return value
        if amount >= 100_000:
            amount /= 1_000_000
        return amount


class BriefTurn(BaseModel):
    action: Literal["ask_clarification", "propose_brief", "answer"]
    message: str = Field(min_length=1, max_length=4000)
    brief: BriefDraft | None = None
    reason: str = Field(default="", max_length=1000)
    missing_fields: list[str] = Field(default_factory=list, max_length=7)

    model_config = {"extra": "forbid"}

    @field_validator("brief", mode="before")
    @classmethod
    def parse_nested_brief_json(cls, value):
        # MiniMax function calling is reliable at the outer schema boundary but
        # occasionally stringifies nested objects. Coerce only valid JSON here;
        # Pydantic still validates every authoritative field afterward.
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    @model_validator(mode="after")
    def proposal_requires_brief(self):
        if self.action == "propose_brief" and self.brief is None:
            raise ValueError("propose_brief requires brief")
        if self.action != "propose_brief" and self.brief is not None:
            raise ValueError("brief is only allowed for propose_brief")
        return self


def _brief_messages(state: AgentState) -> list[dict]:
    now = campaign_now()
    instructions = (
        "Bạn là bộ thu thập Brief có output bắt buộc theo schema. "
        f"Thời gian hiện tại có thẩm quyền: {now.isoformat(timespec='seconds')} "
        "(Asia/Ho_Chi_Minh). "
        "Dùng ask_clarification khi thiếu brand, budget hoặc thời gian chạy và người dùng "
        "chưa cho phép tự chọn. Dùng answer cho câu hỏi chỉ cần giải thích. "
        "Dùng propose_brief ngay khi đủ dữ liệu hoặc khi người dùng nói chọn/gợi ý giúp: "
        "được phép đề xuất objective và KPI hợp lý, nhưng không bịa brand, budget hay lịch chạy. "
        "Nếu ngày không có năm, dùng lần xuất hiện gần nhất không sớm hơn ngày hiện tại. "
        "Số ngày chạy tính bao gồm ngày bắt đầu. Ví dụ chạy 3 ngày từ 2026-07-15 thì "
        "endDate=2026-07-17. Audience, geo, sở thích và sản phẩm phải lưu trong notes. "
        "budget BẮT BUỘC dùng đơn vị TRIỆU VND: 2 triệu ghi budget=2, 2 tỷ ghi budget=2000; "
        "không ghi budget=2000000 cho 2 triệu. "
        "propose_brief chỉ tạo bản nháp chờ người dùng duyệt, không có nghĩa đã áp dụng. "
        "message phải ngắn, bằng tiếng Việt và không được nói rằng Brief đã được lưu."
    )
    conversation = [
        message for message in state.get("messages", [])
        if message.get("role") in {"user", "assistant"} and message.get("content")
    ]
    return [{"role": "system", "content": instructions}, *conversation]


async def generate_brief_turn(state: AgentState) -> tuple[BriefTurn, int]:
    return await asyncio.to_thread(
        structured,
        _brief_messages(state),
        BriefTurn,
        "brief_turn",
        "generator",
        1600,
    )


def _user_supplied_explicit_year(messages: list[dict]) -> bool:
    user_text = "\n".join(
        str(message.get("content", ""))
        for message in messages if message.get("role") == "user"
    )
    return bool(re.search(r"\b(?:19|20)\d{2}\b", user_text))


def _next_year(value: date) -> date:
    try:
        return value.replace(year=value.year + 1)
    except ValueError:  # February 29 -> February 28 in a non-leap year.
        return value.replace(year=value.year + 1, day=28)


def normalize_inferred_dates(
    value: dict, messages: list[dict], *, today: date | None = None,
) -> dict:
    """Repair a model-supplied stale year only when the user omitted the year."""
    normalized = dict(value)
    if _user_supplied_explicit_year(messages):
        return normalized
    today = today or campaign_today()
    try:
        start = date.fromisoformat(str(normalized.get("startDate", "")))
        end = date.fromisoformat(str(normalized.get("endDate", "")))
    except ValueError:
        return normalized
    while end < today:
        start, end = _next_year(start), _next_year(end)
    normalized["startDate"] = start.isoformat()
    normalized["endDate"] = end.isoformat()
    return normalized


async def brief_collector_node(state: AgentState) -> dict:
    session_id = state["session_id"]
    await alog(session_id, "llm_call_start", {
        "handler": "brief_collector", "messages_count": len(state.get("messages", [])),
    })
    started = time.perf_counter()
    try:
        turn, tokens = await generate_brief_turn(state)
    except StructuredOutputError as exc:
        await alog(session_id, "error", {
            "handler": "brief_collector", "error": str(exc)[:300],
        })
        reply = (
            "Em chưa thể tổng hợp Brief thành dữ liệu an toàn ở lượt này. "
            "Anh/chị gửi lại brand, ngân sách và thời gian chạy giúp em nhé."
        )
        await add_message(session_id, "user", state["user_message"])
        await add_message(session_id, "assistant", reply)
        return {
            "response_text": reply,
            "used_tool": "provider_unavailable",
        }

    await alog(session_id, "llm_call_end", {
        "handler": "brief_collector",
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "action": turn.action,
        "tokens": tokens,
        "has_brief": turn.brief is not None,
    })

    if turn.action != "propose_brief":
        return {
            "response_text": turn.message.strip(),
            "used_tool": "freeform_chat",
            "tokens_spent": state.get("tokens_spent", 0) + tokens,
        }

    value = normalize_inferred_dates(
        turn.brief.model_dump(), state.get("messages", []), today=campaign_today()
    )
    _, errors = validate_brief_value(value, today=campaign_today())
    if errors:
        reply = (
            "Em chưa tạo đề xuất vì Brief còn chưa hợp lệ: "
            + "; ".join(errors)
            + ". Anh/chị bổ sung hoặc sửa thông tin trên giúp em nhé."
        )
        await add_message(session_id, "user", state["user_message"])
        await add_message(session_id, "assistant", reply)
        return {
            "response_text": reply,
            "response_blocks": [{"type": "info", "text": "; ".join(errors)}],
            "used_tool": "workspace_clarification",
            "tokens_spent": state.get("tokens_spent", 0) + tokens,
        }

    canonical = await get_workspace(session_id)
    if canonical.get("artifacts", {}).get("brief", {}).get("value"):
        reply = (
            "Workspace đã có Brief được duyệt trong lúc em tổng hợp. "
            "Anh/chị tải lại workspace trước khi yêu cầu thay đổi nhé."
        )
        await add_message(session_id, "user", state["user_message"])
        await add_message(session_id, "assistant", reply)
        return {
            "response_text": reply,
            "response_blocks": [{"type": "workspace_conflict"}],
            "used_tool": "workspace_conflict",
        }

    reason = turn.reason.strip() or "Brief do Agent tổng hợp từ hội thoại để người dùng duyệt"
    proposal = await create_proposal(
        session_id,
        "brief",
        value,
        base_revision=canonical["revision"],
        actor="campaign_copilot",
        reason=reason,
    )
    changes = {
        "field": "brief",
        "value": value,
        "reason": reason,
        "proposal_id": proposal["proposal_id"],
        "base_revision": proposal["base_revision"],
        "affected_artifacts": proposal["affected_artifacts"],
    }

    # A plain approval can arrive after an older/model-only recommendation that
    # never created a durable proposal. The typed collector reconstructs the
    # exact validated draft from history; approve that newly-created proposal
    # in the same turn so the user does not have to approve twice.
    if state.get("auto_approve_brief"):
        mutation = await approve_proposal(
            proposal["proposal_id"], actor="campaign_operator"
        )
        await clear_pending_proposal(session_id)
        reply = "✅ Brief đã được xác nhận và lưu vào workspace."
        await add_message(session_id, "user", state["user_message"])
        await add_message(session_id, "assistant", reply)
        await alog(session_id, "confirm", {
            "event": "brief_proposal_recovered_and_approved",
            "proposal_id": proposal["proposal_id"],
            "workspace_revision": mutation["workspace_revision"],
        })
        return {
            "response_text": reply,
            "response_blocks": [{
                "type": "info",
                "text": "Workspace đã cập nhật Brief và sẵn sàng cho bước tiếp theo.",
            }],
            "workspace_update": {
                "field": "brief",
                "value": value,
                "proposal_id": proposal["proposal_id"],
                "workspace_revision": mutation["workspace_revision"],
            },
            "used_tool": "workspace_confirmed",
            "tokens_spent": state.get("tokens_spent", 0) + tokens,
        }

    await set_pending_proposal(session_id, changes)
    reply = _build_update_summary("brief", value, reason)
    await add_message(session_id, "user", state["user_message"])
    await add_message(session_id, "assistant", reply)
    await alog(session_id, "info", {
        "event": "brief_proposal_created",
        "proposal_id": proposal["proposal_id"],
        "base_revision": proposal["base_revision"],
    })
    return {
        "response_text": reply,
        "response_blocks": [{
            "type": "workspace_proposal",
            "changes": changes,
            "is_locked": False,
            "warning": "",
            "affected_artifacts": proposal["affected_artifacts"],
        }],
        "suggestions": _WORKSPACE_SUGGESTIONS.get("brief", []),
        "used_tool": "workspace_proposal",
        "tokens_spent": state.get("tokens_spent", 0) + tokens,
    }
