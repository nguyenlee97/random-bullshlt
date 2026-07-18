"""OpenAI-backed conversation planning for the Zalo OA channel.

The model interprets language and conversation context. It never receives or
creates an authorization principal, and its plan never directly performs a
mutation. Ownership, campaign resolution, confirmations, and side effects stay
inside ``zalo_campaign_agent``.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from config import config


ZaloIntent = Literal[
    "greet", "help", "smalltalk", "list_campaigns", "select_campaign",
    "status", "setup", "report", "live_view", "pause", "resume",
    "start_autopilot", "clarify", "unsupported",
]


class ZaloTurnPlan(BaseModel):
    intent: ZaloIntent
    campaign_reference: str = ""
    campaign_status_filter: Literal["", "all", "active", "paused"] = ""
    report_type: Literal[
        "", "daily_ops", "awareness", "consideration", "conversion",
        "retention", "executive",
    ] = ""
    selected_campaign_index: int = Field(default=0, ge=0, le=8)
    autopilot_mode: Literal["", "fully_automatic", "semi_automatic"] = ""
    needs_clarification: bool = False
    clarification_question: str = ""
    conversational_reply: str = ""


class ZaloRenderedReply(BaseModel):
    text: str


class ZaloBriefDraft(BaseModel):
    brand: str = ""
    advertiser: str = ""
    objective: Literal["", "awareness", "consideration", "conversion", "retention"] = ""
    kpi: str = ""
    budget: float = 0
    startDate: str = ""
    endDate: str = ""
    notes: str = ""


_client: AsyncOpenAI | None = None


def openai_configured() -> bool:
    return bool(
        config.ZALO_OPENAI_ENABLED
        and config.OPENAI_API_KEY
        and config.ZALO_CHAT_MODEL
    )


def _get_client() -> AsyncOpenAI:
    global _client
    if not openai_configured():
        raise RuntimeError("Zalo OpenAI planner is not configured")
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=config.ZALO_CHAT_TIMEOUT_SECONDS,
            max_retries=config.ZALO_CHAT_MAX_RETRIES,
        )
    return _client


def reset_zalo_openai_for_test() -> None:
    global _client
    _client = None


def _safety_identifier(thread_id: str) -> str:
    return "zalo_" + hashlib.sha256(thread_id.encode("utf-8")).hexdigest()[:32]


def _bounded_history(history: list[dict]) -> list[dict]:
    return [
        {
            "role": "assistant" if item.get("role") == "assistant" else "user",
            "content": str(item.get("content") or "")[-1500:],
        }
        for item in history[-12:]
        if item.get("content")
    ]


_PLAN_INSTRUCTIONS = """
Bạn là bộ lập kế hoạch hội thoại cho Advertising Agent trên Zalo OA.
Đọc tin nhắn mới cùng lịch sử gần đây, chiến dịch mà người dùng thực sự sở hữu,
campaign đang được chọn và pending action. Hiểu tiếng Việt tự nhiên, không dấu,
lỗi gõ, đại từ và tham chiếu như "cái đó", "chiến dịch đang chạy", "cái thứ hai".

Chọn đúng một intent. Không tự bịa chiến dịch, ID, số liệu hoặc trạng thái. Không
quyết định quyền sở hữu và không phê duyệt mutation. Nếu yêu cầu thiếu thông tin
và không thể suy ra duy nhất từ context, đặt needs_clarification=true và hỏi đúng
một câu ngắn, cụ thể. Nếu người dùng hỏi chiến dịch "đang chạy", dùng
list_campaigns với campaign_status_filter=active. Nếu họ chỉ chào/cảm ơn/trò
chuyện, trả lời tự nhiên trong conversational_reply, không đổ dữ liệu chiến dịch.
Nếu họ muốn xem/sửa trường không được hỗ trợ, chọn unsupported và giải thích ngắn.

New campaign chỉ dùng start_autopilot. Existing campaign chỉ được đọc hoặc
pause/resume; không được sửa budget, ngày, audience, placement hoặc creative.
Report là dữ liệu synthetic hiện có. Output phải tuân thủ schema, không thêm text.
""".strip()


async def plan_zalo_turn(
    *, message: str, history: list[dict], campaigns: list[dict], thread: dict,
) -> ZaloTurnPlan:
    campaign_summaries = [
        {
            "index": index,
            "campaign_id": item.get("campaign_id"),
            "brand": (item.get("order") or {}).get("brand"),
            "status": (item.get("order") or {}).get("status"),
            "objective": (item.get("order") or {}).get("objective"),
        }
        for index, item in enumerate(campaigns[:8], 1)
    ]
    context = {
        "latest_message": message,
        "recent_messages": _bounded_history(history),
        "owned_campaigns": campaign_summaries,
        "active_campaign_id": thread.get("active_campaign_id"),
        "pending_action": (thread.get("pending_action") or {}).get("kind"),
        "supported_existing_campaign_actions": [
            "list", "status", "setup", "synthetic_report", "live_view",
            "pause_with_confirmation", "resume_with_confirmation",
        ],
    }
    response = await _get_client().responses.parse(
        model=config.ZALO_CHAT_MODEL,
        instructions=_PLAN_INSTRUCTIONS,
        input=json.dumps(context, ensure_ascii=False),
        text_format=ZaloTurnPlan,
        reasoning={"effort": config.ZALO_CHAT_REASONING_EFFORT},
        max_output_tokens=config.ZALO_CHAT_MAX_OUTPUT_TOKENS,
        store=False,
        safety_identifier=_safety_identifier(thread["thread_id"]),
    )
    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no Zalo turn plan")
    return response.output_parsed


_RENDER_INSTRUCTIONS = """
Bạn là Advertising Agent đang trả lời trong Zalo OA. Trả lời đúng câu hỏi mới
nhất bằng tiếng Việt tự nhiên dựa duy nhất trên TOOL_RESULT và hội thoại gần đây.
Không bịa số liệu hay chiến dịch. Không đổ toàn bộ field nếu người dùng chỉ hỏi
một ý; nêu kết luận trước, rồi thông tin cần thiết và một next step hữu ích. Giữ
câu trả lời ngắn, dễ đọc trên điện thoại; không dùng bảng Markdown. Nếu là report,
nói rõ đây là dữ liệu synthetic/demo hiện có. Không hứa thực hiện mutation.
Với intent list_campaigns, giữ đủ số thứ tự, brand, trạng thái và campaign ID của
từng dòng TOOL_RESULT để người dùng có thể chọn bằng số ở lượt sau.
""".strip()


async def render_zalo_reply(
    *, message: str, history: list[dict], intent: str, tool_result: str,
    thread_id: str,
) -> str:
    context = {
        "latest_message": message,
        "intent": intent,
        "recent_messages": _bounded_history(history),
        "tool_result": str(tool_result)[:12000],
    }
    response = await _get_client().responses.parse(
        model=config.ZALO_CHAT_MODEL,
        instructions=_RENDER_INSTRUCTIONS,
        input=json.dumps(context, ensure_ascii=False),
        text_format=ZaloRenderedReply,
        reasoning={"effort": config.ZALO_CHAT_REASONING_EFFORT},
        max_output_tokens=config.ZALO_CHAT_MAX_OUTPUT_TOKENS,
        store=False,
        safety_identifier=_safety_identifier(thread_id),
    )
    parsed = response.output_parsed
    if parsed is None or not parsed.text.strip():
        raise RuntimeError("OpenAI returned no Zalo reply")
    return parsed.text.strip()[:2000]


_BRIEF_INSTRUCTIONS = """
Trích xuất brief quảng cáo từ tin nhắn và lịch sử gần đây. Không bịa field còn
thiếu. objective chỉ là awareness, consideration, conversion hoặc retention.
budget dùng đơn vị triệu VND. Ngày dùng YYYY-MM-DD. notes giữ thông điệp và yêu
cầu creative quan trọng. Output chỉ theo schema.
""".strip()


async def extract_zalo_brief(
    *, message: str, history: list[dict], thread_id: str,
) -> dict:
    context = {
        "latest_message": message,
        "recent_messages": _bounded_history(history),
    }
    response = await _get_client().responses.parse(
        model=config.ZALO_CHAT_MODEL,
        instructions=_BRIEF_INSTRUCTIONS,
        input=json.dumps(context, ensure_ascii=False),
        text_format=ZaloBriefDraft,
        reasoning={"effort": config.ZALO_CHAT_REASONING_EFFORT},
        max_output_tokens=config.ZALO_CHAT_MAX_OUTPUT_TOKENS,
        store=False,
        safety_identifier=_safety_identifier(thread_id),
    )
    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no Zalo brief")
    return response.output_parsed.model_dump()


def reset_zalo_openai_for_test() -> None:
    global _client
    _client = None
