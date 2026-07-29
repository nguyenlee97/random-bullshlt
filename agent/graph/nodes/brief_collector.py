"""Typed Brief collection for a canonical, always-approvable draft.

The ordinary tool-capable model is allowed to answer questions, but an initial
Brief may never exist only as prose. This node forces one of three typed
outcomes: clarify, answer, or create a durable proposal.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
import json
import re
import time
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator

from agent_logger import alog
from autopilot.capabilities import validate_brief_value
from graph.state import AgentState
from graph.structured import StructuredOutputError, structured
from handlers.freeform import _WORKSPACE_SUGGESTIONS, _build_update_summary
from session import add_message, clear_pending_proposal, set_pending_proposal
from time_context import campaign_now, campaign_today
from workspace.service import approve_proposal, create_proposal, get_workspace


StructuredRunner = Callable[
    [list[dict], type[BaseModel], str, str, int],
    Awaitable[tuple[BaseModel, int]],
]


async def _legacy_structured_runner(
    messages: list[dict],
    schema: type[BaseModel],
    schema_name: str,
    role: str,
    max_tokens: int,
) -> tuple[BaseModel, int]:
    """Preserve the existing GreenNode/critic boundary as the default.

    A sibling campaign engine may inject its own structured runner. The default
    remains equivalent at the call boundary, so GreenNode's Brief Collector is
    not redirected or coupled to OpenAI availability.
    """
    return await asyncio.to_thread(
        structured, messages, schema, schema_name, role, max_tokens,
    )


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


MissingBriefField = Literal[
    "brand", "objective", "kpi", "budget", "startDate", "endDate", "notes",
]
AdvisoryBriefField = Literal["objective", "kpi", "notes"]


class BriefTurn(BaseModel):
    action: Literal["ask_clarification", "propose_brief", "answer"]
    message: str = Field(min_length=1, max_length=4000)
    brief: BriefDraft | None = None
    reason: str = Field(default="", max_length=1000)
    # Every field in the Guided Brief is operator-provided. The model may
    # normalize wording and units, but it may not invent objective, KPI,
    # audience/geo notes or any of the hard campaign facts.
    missing_fields: list[MissingBriefField] = Field(default_factory=list, max_length=7)
    suggestion_fields: list[AdvisoryBriefField] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "Advisory fields the user explicitly delegated to the Agent to suggest. "
            "Never include brand, budget, startDate or endDate."
        ),
    )

    model_config = {"extra": "forbid"}
    # OpenAI's lenient transport may expose a complete working draft while it
    # chooses ask_clarification. Keep that candidate out of serialization and
    # canonical state; it is eligible only after the server proves that every
    # required field was explicitly supplied or delegated.
    _provider_working_brief: BriefDraft | None = PrivateAttr(default=None)

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
        if self.action == "ask_clarification" and not self.missing_fields:
            raise ValueError(
                "ask_clarification requires at least one missing Brief field"
            )
        if self.action != "ask_clarification" and self.missing_fields:
            raise ValueError("missing_fields is only allowed for ask_clarification")
        return self


class BriefIntakeTurn(BriefTurn):
    """Campaign intake statements must either propose or ask for hard facts."""

    action: Literal["ask_clarification", "propose_brief"]


class BriefProposalTurn(BriefTurn):
    """Repair schema when the provider asks for fields already supplied."""

    action: Literal["propose_brief"]


class BriefDelegationDecision(BaseModel):
    """Semantic classification of advisory decisions delegated by the user."""

    mode: Literal["none", "advice_only", "fill_brief"]
    provided_fields: list[AdvisoryBriefField] = Field(max_length=3)
    delegated_fields: list[AdvisoryBriefField] = Field(max_length=3)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def fields_match_mode(self):
        if self.mode == "fill_brief" and not self.delegated_fields:
            raise ValueError("fill_brief requires delegated_fields")
        if self.mode != "fill_brief" and self.delegated_fields:
            raise ValueError("only fill_brief may contain delegated_fields")
        overlap = set(self.provided_fields) & set(self.delegated_fields)
        if overlap:
            raise ValueError(
                "a field cannot be both provided and delegated: "
                + ", ".join(sorted(overlap))
            )
        return self


_BRIEF_CLARIFICATION_QUESTIONS = {
    "brand": "Thương hiệu hoặc tên sản phẩm cần quảng cáo là gì?",
    "objective": (
        "Mục tiêu campaign là Awareness, Consideration, Conversion hay Retention?"
    ),
    "kpi": (
        "KPI mong muốn là gì (ví dụ Reach, Impressions, CTR, lượt xem hoặc số chuyển đổi)?"
    ),
    "budget": "Tổng ngân sách là bao nhiêu triệu VND?",
    "startDate": "Campaign bắt đầu ngày nào?",
    "endDate": "Campaign kết thúc ngày nào hoặc chạy trong bao nhiêu ngày?",
    "notes": (
        "Đối tượng mục tiêu và phạm vi địa lý là ai/ở đâu? "
        "Anh/chị có yêu cầu đặc biệt nào về sở thích, hành vi hoặc creative không?"
    ),
}


def _clarification_message(turn: BriefTurn) -> str:
    """Render an actionable clarification even when the model returns vague prose."""
    fields = list(dict.fromkeys(
        field for field in turn.missing_fields
        if field in _BRIEF_CLARIFICATION_QUESTIONS
    ))
    if not fields:
        return turn.message.strip()
    questions = "\n".join(
        f"- {_BRIEF_CLARIFICATION_QUESTIONS[field]}" for field in fields
    )
    return "Em cần thêm các thông tin sau để hoàn thiện Brief:\n" + questions


def _brief_messages(state: AgentState) -> list[dict]:
    now = campaign_now()
    instructions = (
        "Bạn là bộ thu thập Brief có output bắt buộc theo schema. "
        f"Thời gian hiện tại có thẩm quyền: {now.isoformat(timespec='seconds')} "
        "(Asia/Ho_Chi_Minh). "
        "Mặc định dùng ask_clarification khi thiếu bất kỳ field nào trong brand, objective, KPI, budget, "
        "startDate, endDate/thời lượng hoặc notes (đối tượng mục tiêu + geo/yêu cầu). "
        "Nhưng phải hiểu yêu cầu ủy quyền tự nhiên của người dùng: nếu họ bảo gợi ý, chọn giúp, tự hoàn thiện "
        "hoặc tương đương, hãy ghi chính xác objective/kpi/notes được ủy quyền vào suggestion_fields và "
        "đề xuất giá trị hợp lý cho các field đó. Một câu như 'gợi ý giúp mình đi' sau danh sách câu hỏi "
        "ủy quyền tất cả advisory field đang thiếu. Nếu chỉ nhờ chọn KPI thì chỉ thêm kpi. "
        "Không bao giờ đưa brand, budget, startDate hoặc endDate vào suggestion_fields hay tự bịa các field cứng. "
        "Dùng answer cho câu hỏi chỉ cần giải thích. Dùng propose_brief khi mọi field đã được cung cấp hoặc "
        "các advisory field còn thiếu đều đã được người dùng ủy quyền đề xuất. "
        "Nếu ngày không có năm, dùng lần xuất hiện gần nhất không sớm hơn ngày hiện tại. "
        "Số ngày chạy tính bao gồm ngày bắt đầu. Ví dụ chạy 3 ngày từ 2026-07-15 thì "
        "endDate=2026-07-17. Audience, geo, sở thích và sản phẩm phải lưu trong notes. "
        "budget BẮT BUỘC dùng đơn vị TRIỆU VND: 2 triệu ghi budget=2, 2 tỷ ghi budget=2000; "
        "không ghi budget=2000000 cho 2 triệu. "
        "propose_brief chỉ tạo bản nháp chờ người dùng duyệt, không có nghĩa đã áp dụng. "
        "Với ask_clarification, missing_fields phải có ít nhất một field và chỉ được gồm "
        "brand, objective, kpi, budget, startDate, endDate, notes; phải liệt kê chính xác tất cả field còn thiếu "
        "sau khi loại các advisory field đã có trong suggestion_fields. "
        "và message phải nêu câu hỏi có thể trả lời được, không chỉ viết một câu dẫn chung. "
        "message phải ngắn, bằng tiếng Việt và không được nói rằng Brief đã được lưu."
    )
    conversation = [
        message for message in state.get("messages", [])
        if message.get("role") in {"user", "assistant"} and message.get("content")
    ]
    return [{"role": "system", "content": instructions}, *conversation]


def _brief_delegation_messages(state: AgentState) -> list[dict]:
    instructions = (
        "Bạn là bộ phân loại ngữ nghĩa cho Campaign Copilot. Xác định người dùng có CHỦ ĐỘNG "
        "field advisory nào đã có GIÁ TRỊ THỰC TẾ do người dùng cung cấp và field nào được ủy quyền "
        "cho Agent tự ĐIỀN vào Brief. "
        "Hiểu ý định tự nhiên theo toàn bộ hội thoại, không chỉ keyword. Nếu Agent vừa hỏi nhiều field "
        "và người dùng trả lời 'gợi ý giúp mình', 'chọn giúp', 'tự hoàn thiện đi', 'sao không gợi ý' "
        "hoặc cách nói tương đương, mode=fill_brief và delegated_fields gồm tất cả advisory field "
        "đang được hỏi. Nếu họ nói 'KPI chọn giúp mình, phần còn lại để tôi cung cấp' thì "
        "mode=fill_brief, delegated_fields=[kpi]. Nếu chỉ hỏi kiến thức như 'Objective nào phù hợp?' "
        "mà chưa bảo điền vào Brief, mode=advice_only và delegated_fields=[]. Nếu chỉ cung cấp campaign "
        "facts mà chưa nhờ Agent chọn, mode=none và delegated_fields=[]. provided_fields chỉ gồm field "
        "có giá trị cụ thể: câu 'audience để tôi cung cấp sau' KHÔNG có notes; câu 'audience game thủ "
        "18-30 tại Hà Nội' CÓ notes. Tương tự, chỉ nhắc tên objective/KPI trong câu hỏi không có nghĩa "
        "đã cung cấp giá trị. Không bao giờ trả brand, budget, startDate hoặc endDate. Một field không "
        "được xuất hiện đồng thời trong provided_fields và delegated_fields. Bắt buộc trả mode, "
        "provided_fields và delegated_fields."
    )
    conversation = [
        message for message in state.get("messages", [])[-12:]
        if message.get("role") in {"user", "assistant"} and message.get("content")
    ]
    return [{"role": "system", "content": instructions}, *conversation]


async def _classify_brief_delegation(
    state: AgentState,
    *,
    structured_runner: StructuredRunner | None = None,
) -> tuple[BriefDelegationDecision | None, int]:
    try:
        runner = structured_runner or _legacy_structured_runner
        return await runner(
            _brief_delegation_messages(state),
            BriefDelegationDecision,
            "brief_delegation_decision",
            "critic",
            1000,
        )
    except StructuredOutputError:
        # A classifier outage must not grant suggestion permission. The
        # generator result remains usable, but server enforcement defaults to
        # asking instead of inventing fields.
        return None, 0


_BRIEF_QUESTION_RE = re.compile(
    r"(?:[?？]\s*$|\b(?:là gì|bao nhiêu|như thế nào|tại sao|vì sao|"
    r"có nên|được không|objective\s+nào|kpi\s+nào|kpi\s+gì|"
    r"mục tiêu\s+nào|ngân sách\s+tối thiểu)\b)",
    re.IGNORECASE,
)


def _is_brief_question(message: str) -> bool:
    """Keep explanatory Q&A while routing campaign statements to intake."""
    return bool(_BRIEF_QUESTION_RE.search((message or "").strip()))


_OBJECTIVE_SIGNAL_RE = re.compile(
    r"\b(?:awareness|consideration|conversion|retention|nhận\s*biết|nhận\s*diện|"
    r"tăng\s*quan\s*tâm|cân\s*nhắc|chuyển\s*đổi|giữ\s*chân)\b",
    re.IGNORECASE,
)
_KPI_SIGNAL_RE = re.compile(
    r"\b(?:kpi|reach|impressions?|ctr|cpm|cpa|roas|vtr|cvr|viewability|frequency|"
    r"engagement|return\s*visit|lượt\s*xem|tương\s*tác|số\s*chuyển\s*đổi)\b",
    re.IGNORECASE,
)
_NOTES_SIGNAL_RE = re.compile(
    r"\b(?:audience|target|đối\s*tượng|khách\s*hàng|người\s*(?:dùng|hâm\s*mộ)|"
    r"game\s*thủ|nam|nữ|tuổi|gen\s*[xyz]|geo|khu\s*vực|toàn\s*quốc|"
    r"hà\s*nội|tp\.?\s*hcm|hồ\s*chí\s*minh|đà\s*nẵng|sở\s*thích|hành\s*vi)\b",
    re.IGNORECASE,
)
_BRAND_SIGNAL_RE = re.compile(
    r"(?:\b(?:brand|thương\s*hiệu)\s*[:=\-]?\s*[\wÀ-ỹ]|"
    r"\bcủa\s+[\wÀ-ỹ][\wÀ-ỹ.\-]*|\b[A-ZĐ]{2,}\b)",
)
_BUDGET_SIGNAL_RE = re.compile(
    r"(?:\b(?:budget|ngân\s*sách)\b[^\n,;]{0,35}\d|"
    r"\d[\d.,]*\s*(?:triệu|tỷ|tỉ|vnd|đồng)\b)",
    re.IGNORECASE,
)
_DATE_SIGNAL_RE = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b"
)
_DURATION_SIGNAL_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:ngày|tuần|tháng)\b", re.IGNORECASE,
)


def _all_user_text(state: AgentState) -> str:
    return "\n".join(
        str(message.get("content", ""))
        for message in state.get("messages", [])
        if message.get("role") == "user"
    )


def _explicit_hard_present_fields(state: AgentState) -> set[str]:
    user_text = _all_user_text(state)
    present: set[str] = set()
    if _BRAND_SIGNAL_RE.search(user_text):
        present.add("brand")
    if _BUDGET_SIGNAL_RE.search(user_text):
        present.add("budget")
    dates = _DATE_SIGNAL_RE.findall(user_text)
    if dates:
        present.add("startDate")
    if len(dates) >= 2 or (dates and _DURATION_SIGNAL_RE.search(user_text)):
        present.add("endDate")
    return present


def _explicit_advisory_missing_fields(
    state: AgentState,
    provided_fields: list[AdvisoryBriefField] | None = None,
) -> list[MissingBriefField]:
    """Detect advisory fields that must not be synthesized by the model.

    Scan all user turns so multi-turn collection naturally removes a field
    from the missing set once the operator supplies it.
    """
    if provided_fields is not None:
        provided = set(provided_fields)
        # OpenAI opts into deterministic transcript evidence so a stochastic
        # classifier omission cannot make it re-ask a fact from an earlier
        # user turn. GreenNode does not set this state flag.
        if state.get("merge_explicit_text_evidence"):
            user_text = _all_user_text(state)
            if _OBJECTIVE_SIGNAL_RE.search(user_text):
                provided.add("objective")
            if _KPI_SIGNAL_RE.search(user_text):
                provided.add("kpi")
            if _NOTES_SIGNAL_RE.search(user_text):
                provided.add("notes")
        return [
            field for field in ("objective", "kpi", "notes")
            if field not in provided
        ]

    user_text = _all_user_text(state)
    missing: list[MissingBriefField] = []
    if not _OBJECTIVE_SIGNAL_RE.search(user_text):
        missing.append("objective")
    if not _KPI_SIGNAL_RE.search(user_text):
        missing.append("kpi")
    if not _NOTES_SIGNAL_RE.search(user_text):
        missing.append("notes")
    return missing


def _enforce_explicit_brief_fields(
    turn: BriefTurn,
    state: AgentState,
    *,
    provided_fields: list[AdvisoryBriefField] | None = None,
) -> BriefTurn | None:
    if turn.action == "answer" and not turn.suggestion_fields:
        return turn

    advisory_missing = _explicit_advisory_missing_fields(state, provided_fields)
    delegated = set(turn.suggestion_fields)
    unresolved_advisory = [
        field for field in advisory_missing if field not in delegated
    ]
    if turn.action in {"propose_brief", "answer"} and unresolved_advisory:
        return BriefTurn(
            action="ask_clarification",
            message="Brief còn thiếu thông tin người dùng cần cung cấp.",
            missing_fields=unresolved_advisory,
            suggestion_fields=turn.suggestion_fields,
        )

    if turn.action == "answer":
        return None

    if turn.action == "ask_clarification":
        # The server owns advisory completeness: discard model-reported
        # fields that are explicitly present and add any advisory field it
        # omitted. This also prevents stochastic re-asking of visible brand,
        # budget and schedule values.
        hard_present = _explicit_hard_present_fields(state)
        hard_fields = [
            field for field in turn.missing_fields
            if field in {"brand", "budget", "startDate", "endDate"}
            and field not in hard_present
        ]
        missing = list(dict.fromkeys([*hard_fields, *unresolved_advisory]))
        if not missing:
            return None
        return BriefTurn(
            action="ask_clarification",
            message=turn.message,
            missing_fields=missing,
            suggestion_fields=turn.suggestion_fields,
        )
    return turn


async def generate_brief_turn(
    state: AgentState,
    *,
    structured_runner: StructuredRunner | None = None,
) -> tuple[BriefTurn, int]:
    is_question = _is_brief_question(state.get("user_message", ""))
    schema = BriefTurn if is_question else BriefIntakeTurn
    schema_name = "brief_turn" if is_question else "brief_intake_turn"
    runner = structured_runner or _legacy_structured_runner
    generator_call = runner(
        _brief_messages(state), schema, schema_name, "generator", 1600,
    )
    # Keep the legacy call signature unchanged for callers/tests that monkeypatch
    # this classifier. Only the sibling OpenAI route passes an injected runner.
    delegation_call = (
        _classify_brief_delegation(state)
        if structured_runner is None
        else _classify_brief_delegation(
            state, structured_runner=structured_runner,
        )
    )
    (turn, tokens), (delegation, delegation_tokens) = await asyncio.gather(
        generator_call,
        delegation_call,
    )
    # Normalize the narrower intake result and apply the server-owned
    # explicit-field policy before any proposal can be created.
    normalized_data = turn.model_dump()
    provided_fields = delegation.provided_fields if delegation is not None else None
    if delegation is not None:
        normalized_data["suggestion_fields"] = (
            list(dict.fromkeys(delegation.delegated_fields))
            if delegation.mode == "fill_brief"
            else []
        )
    normalized = BriefTurn.model_validate(normalized_data)
    tokens += delegation_tokens
    enforced = _enforce_explicit_brief_fields(
        normalized, state, provided_fields=provided_fields,
    )
    if enforced is not None:
        return enforced, tokens

    # The provider may choose clarification despite already producing a
    # complete working draft. When transcript evidence proves there is
    # genuinely nothing left to clarify, reuse that validated draft instead of
    # asking the provider to reconstruct the same object in a second call.
    working_brief = getattr(turn, "_provider_working_brief", None)
    if working_brief is not None:
        recovered = BriefTurn(
            action="propose_brief",
            message=normalized.message,
            brief=working_brief,
            reason=normalized.reason,
            suggestion_fields=normalized.suggestion_fields,
        )
        enforced = _enforce_explicit_brief_fields(
            recovered, state, provided_fields=provided_fields,
        )
        if enforced is not None:
            await alog(state["session_id"], "info", {
                "event": "brief_working_draft_recovered",
                "source_action": normalized.action,
            })
            return enforced, tokens

    # The provider asked for advisory values the user already supplied. Force
    # one schema-repaired proposal instead of repeating an unnecessary question.
    delegated = normalized.suggestion_fields
    proposal, repair_tokens = await runner(
        _brief_messages(state),
        BriefProposalTurn,
        "brief_proposal_turn",
        "generator",
        1600,
    )
    repaired_data = proposal.model_dump()
    if delegated:
        repaired_data["suggestion_fields"] = delegated
    repaired = BriefTurn.model_validate(repaired_data)
    enforced = _enforce_explicit_brief_fields(
        repaired, state, provided_fields=provided_fields,
    )
    if enforced is None:
        raise StructuredOutputError("brief proposal repair produced no actionable result")
    return enforced, tokens + repair_tokens


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


async def brief_collector_node(
    state: AgentState,
    *,
    structured_runner: StructuredRunner | None = None,
    proposal_actor: str = "campaign_copilot",
) -> dict:
    session_id = state["session_id"]
    await alog(session_id, "llm_call_start", {
        "handler": "brief_collector", "messages_count": len(state.get("messages", [])),
    })
    started = time.perf_counter()
    try:
        turn, tokens = (
            await generate_brief_turn(state)
            if structured_runner is None
            else await generate_brief_turn(
                state, structured_runner=structured_runner,
            )
        )
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
            "response_text": (
                _clarification_message(turn)
                if turn.action == "ask_clarification"
                else turn.message.strip()
            ),
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
    current_brief = canonical.get("artifacts", {}).get("brief", {}).get("value")
    _, current_errors = validate_brief_value(
        current_brief, today=campaign_today(),
    )
    if current_brief and not (
        state.get("replace_incomplete_brief") and current_errors
    ):
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
        actor=proposal_actor,
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
