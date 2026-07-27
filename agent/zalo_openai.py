"""OpenAI-backed conversation planning for the Zalo OA channel.

The model interprets language and conversation context. It never receives or
creates an authorization principal, and its plan never directly performs a
mutation. Ownership, campaign resolution, confirmations, and side effects stay
inside ``zalo_campaign_agent``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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


class ZaloPendingBriefDecision(BaseModel):
    intent: Literal[
        "approve", "reject", "question", "edit_request", "unclear",
    ]
    scope: Literal["pending_brief"] = "pending_brief"
    explicit: bool = False
    evidence: str = ""
    reply: str = ""


class ZaloSessionSummary(BaseModel):
    summary: str = ""
    user_goals: list[str] = Field(default_factory=list)
    campaigns_discussed: list[str] = Field(default_factory=list)
    resolved_questions: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    user_preferences: list[str] = Field(default_factory=list)
    last_topic: str = ""
    last_campaign_reference: str = ""


@dataclass
class ZaloToolTurnResult:
    text: str
    thread: dict
    media_parts: list[str | dict]
    tool_calls: list[str]


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


_TOOL_AGENT_INSTRUCTIONS = """
You are the Advertising Agent inside a Zalo OA chat. Reply in natural, concise
Vietnamese. Understand Vietnamese with or without accents, typos, pronouns and
follow-up references.

Do not dump campaign data when the user only greets, thanks you, or makes small
talk. Call tools only when facts or workflow actions are needed. You may call
multiple tools in sequence. If a campaign is ambiguous, use list_campaigns or
the candidates returned by a tool and ask one focused clarification question.
Never guess.

For a greeting, sound warm and human: greet the user, briefly introduce yourself
as their advertising campaign companion, mention two or three useful things in
one natural sentence, include the exact sentence "Nếu bạn muốn được hướng dẫn
kỹ hơn, hãy nói với mình nhé.", then ask what they would like to do. Avoid a
formal menu, a wall of bullets, or campaign facts. One friendly emoji is fine.

If the user asks for detailed guidance, give natural example requests using
generic placeholders such as "campaign A". Never use a real owned campaign name,
ID, metric, or account fact merely as an example, and do not call campaign tools
unless the user is asking about their actual data.

The model never decides ownership. Tool output is the only source of truth for
campaign status, setup, and reports. A memory summary is conversational context,
not current campaign state. Never describe report data to the user as synthetic,
demo, mock, fake, forecast, or showcase data. Present the existing report module
directly as the campaign report.

For comparisons across campaigns, including highest or lowest budget, call
list_campaigns once and compare the numeric fields in its returned summaries.
Do not call get_campaign_status separately for every campaign when the list
already contains the requested facts.

There are exactly six report views: Daily Ops, Awareness, Consideration,
Conversion, Retention, and Executive. If the user asks for "the report" without
naming or clearly implying one, call list_report_types and explain all six; do
not default to Daily Ops. If they ask to see a specific report, call
get_campaign_report with mode=show. A new show request must identify a campaign
by name, ID, ordinal, or an explicit contextual phrase such as "campaign này";
if it does not, let the tool ask which campaign and never choose the active or
only campaign silently. If they ask a question about the report currently being
discussed, call it with mode=question and use the returned cached analysis.
Recognize PDF requests despite missing accents or minor typos (for example pdf,
pfd, file report, file bao cao) and call get_campaign_report with mode=pdf. When
a tool says images, suggestions, PDF link, or ordered delivery were queued,
acknowledge it briefly and do not repeat those queued items or raw URLs.

For live captures, infer baomoi, znews, zingmp3, or all from the request and pass
that site to get_campaign_live_view. The tool owns the message/image ordering;
do not reproduce its delivery parts in your prose.

Existing campaigns are read-only except pause and resume. Do not change budget,
dates, audience, placement, or creative; direct those edits to the web workspace.
Whenever the user asks for a workspace link, web link, site link, or asks to
continue/check the campaign in the browser, call get_workspace_link. Return the
exact tool-provided URL; never construct a conversation URL yourself. If the
tool asks which campaign, ask one focused clarification question.
Pause/resume tools only prepare a proposal. Show their confirmation_prompt and
never say the mutation happened. New campaigns must use Campaign Autopilot.
Its only modes are fully_automatic and semi_automatic, and both stop for an
explicit confirmation before launch.

Never invent a tool result, campaign ID, or metric. Do not use Markdown tables.
Lead with the answer, include only useful detail, and suggest a next step only
when it genuinely helps.
""".strip()


def _dump_item(item) -> dict:
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    if isinstance(item, dict):
        return dict(item)
    return {
        key: getattr(item, key) for key in
        ("type", "id", "call_id", "name", "arguments", "content", "status")
        if getattr(item, key, None) is not None
    }


def _item_value(item, key: str, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


async def run_zalo_tool_turn(
    *, thread: dict, message: str, messages: list[dict], bridge_summary: dict | None,
) -> ZaloToolTurnResult:
    """Run a bounded Responses API function-calling loop for one OA turn."""
    from zalo_tools import ToolExecutionContext, ZALO_TOOLS, execute_zalo_tool, tool_output_json

    input_items: list[dict] = []
    if bridge_summary:
        input_items.append({
            "role": "user",
            "content": "Memory summary from the previous Zalo chat session (not current campaign state):\n"
                       + json.dumps(bridge_summary, ensure_ascii=False),
        })
    pending = thread.get("pending_action") or {}
    pending_report = thread.get("pending_report_request") or {}
    if pending or pending_report or thread.get("active_report_view"):
        input_items.append({
            "role": "user",
            "content": "SERVER_WORKFLOW_STATE (server-authoritative): " + json.dumps({
                "pending_kind": pending.get("kind"),
                "autopilot_mode": pending.get("mode"),
                "active_campaign_id": thread.get("active_campaign_id"),
                "active_report_campaign_id": thread.get("active_report_campaign_id"),
                "active_report_view": thread.get("active_report_view"),
                "pending_report_request": {
                    "view": pending_report.get("view"),
                    "mode": pending_report.get("mode"),
                } if pending_report else None,
            }, ensure_ascii=False),
        })
    input_items.extend({"role": item["role"], "content": item["content"]} for item in messages)
    if not input_items or input_items[-1].get("role") != "user":
        input_items.append({"role": "user", "content": message})

    execution = ToolExecutionContext(thread=thread, current_message=message, history=messages)
    call_names: list[str] = []
    total_calls = 0
    client = _get_client()
    for _round in range(max(1, config.ZALO_CHAT_MAX_TOOL_ROUNDS)):
        response = await client.responses.create(
            model=config.ZALO_CHAT_MODEL,
            instructions=_TOOL_AGENT_INSTRUCTIONS,
            input=input_items,
            tools=ZALO_TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False,
            max_tool_calls=max(1, config.ZALO_CHAT_MAX_TOOL_CALLS - total_calls),
            reasoning={"effort": config.ZALO_CHAT_REASONING_EFFORT},
            max_output_tokens=config.ZALO_CHAT_MAX_OUTPUT_TOKENS,
            store=False,
            safety_identifier=_safety_identifier(thread["thread_id"]),
        )
        outputs = list(getattr(response, "output", None) or [])
        calls = [item for item in outputs if _item_value(item, "type") == "function_call"]
        if not calls:
            text = str(getattr(response, "output_text", "") or "").strip()
            if not text:
                raise RuntimeError("OpenAI returned neither text nor a function call")
            return ZaloToolTurnResult(
                text=text[:2000], thread=execution.thread,
                media_parts=execution.media_parts, tool_calls=call_names,
            )
        input_items.extend(_dump_item(item) for item in outputs)
        for call in calls:
            total_calls += 1
            name = str(_item_value(call, "name") or "")
            call_names.append(name)
            call_id = str(_item_value(call, "call_id") or "")
            if total_calls > config.ZALO_CHAT_MAX_TOOL_CALLS:
                result = {"ok": False, "error": "tool_call_limit_reached"}
            else:
                try:
                    raw_arguments = _item_value(call, "arguments", "{}")
                    arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments or {})
                    result = await execute_zalo_tool(execution, name, arguments)
                except (TypeError, ValueError, json.JSONDecodeError):
                    result = {"ok": False, "error": "invalid_tool_arguments"}
                except Exception as exc:
                    from agent_logger import alog
                    await alog(
                        str(thread.get("session_id") or thread["thread_id"]),
                        "error",
                        {
                            "handler": "zalo_tool_execution",
                            "tool": name,
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:500],
                        },
                    )
                    result = {"ok": False, "error": "tool_execution_failed"}
            input_items.append({
                "type": "function_call_output", "call_id": call_id,
                "output": tool_output_json(result),
            })
    raise RuntimeError("Zalo tool loop reached its maximum number of rounds")


_SUMMARY_INSTRUCTIONS = """
Summarize this Zalo conversation as memory for a later session. Preserve user
goals, campaigns discussed, resolved and unresolved questions, decisions,
preferences, the last topic, and the last campaign reference. Merge the prior
summary when supplied. Never invent facts, treat campaign status as current,
or include secrets and tokens. Keep text in the language used by the user.
""".strip()


async def summarize_zalo_session(
    *, previous_summary: dict | None, messages: list[dict], thread_id: str,
) -> dict:
    payload = {
        "previous_summary": previous_summary,
        "messages": [{"role": item.get("role"), "content": str(item.get("content") or "")[:6000]}
                     for item in messages[-30:]],
    }
    response = await _get_client().responses.parse(
        model=config.ZALO_CHAT_MODEL, instructions=_SUMMARY_INSTRUCTIONS,
        input=json.dumps(payload, ensure_ascii=False), text_format=ZaloSessionSummary,
        reasoning={"effort": config.ZALO_CHAT_REASONING_EFFORT},
        max_output_tokens=min(config.ZALO_CHAT_MAX_OUTPUT_TOKENS, 1200),
        store=False, safety_identifier=_safety_identifier(thread_id),
    )
    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no Zalo session summary")
    return response.output_parsed.model_dump()


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
Report dùng dữ liệu hiện có của module báo cáo. Không gọi report là synthetic,
demo, mock, fake hay forecast. Output phải tuân thủ schema, không thêm text.
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
            "list", "status", "setup", "report", "live_view",
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
câu trả lời ngắn, dễ đọc trên điện thoại; không dùng bảng Markdown. Không gọi
report là synthetic, demo, mock, fake hay forecast. Không hứa thực hiện mutation.
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


_PENDING_BRIEF_DECISION_INSTRUCTIONS = """
Classify the latest Vietnamese or English message about a server-owned campaign
brief that is already waiting for confirmation. Understand natural language,
missing accents, typos, slang, and short follow-ups.

Return approve only when the user explicitly authorizes starting the pending
brief now. Return reject only for an explicit cancellation. A question about
confirmation is question, a requested brief change is edit_request, and vague
sentiment is unclear. Negation, deferral, questions, and edit requests always
take precedence over words such as confirm, approve, OK, or continue.

The evidence must be an exact non-empty span copied from latest_message when
intent is approve or reject. Set explicit=false when the decision is inferred,
ambiguous, conditional, or lacks an exact evidence span. The reply must be a
short Vietnamese response for question, edit_request, or unclear; it must say
that the pending brief was not started or changed. Never invent campaign state,
never approve a different scope, and output only the schema.
""".strip()


async def classify_pending_brief_decision(
    *,
    message: str,
    pending: dict,
    history: list[dict],
    thread_id: str,
) -> ZaloPendingBriefDecision:
    """Interpret unrestricted language without granting mutation authority."""
    brief = pending.get("brief") if isinstance(pending.get("brief"), dict) else {}
    context = {
        "latest_message": message,
        "pending_state": {
            "kind": pending.get("kind"),
            "mode": pending.get("mode"),
            "brief": {
                key: brief.get(key)
                for key in (
                    "brand", "objective", "kpi", "budget",
                    "startDate", "endDate", "notes",
                )
            },
        },
        "recent_messages": _bounded_history(history)[-6:],
    }
    response = await _get_client().responses.parse(
        model=config.ZALO_CHAT_MODEL,
        instructions=_PENDING_BRIEF_DECISION_INSTRUCTIONS,
        input=json.dumps(context, ensure_ascii=False),
        text_format=ZaloPendingBriefDecision,
        reasoning={"effort": config.ZALO_CHAT_REASONING_EFFORT},
        max_output_tokens=min(config.ZALO_CHAT_MAX_OUTPUT_TOKENS, 500),
        store=False,
        safety_identifier=_safety_identifier(thread_id),
    )
    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no pending brief decision")
    return response.output_parsed


def reset_zalo_openai_for_test() -> None:
    global _client
    _client = None
