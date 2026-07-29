"""OpenAI-owned provider boundary for the shared typed Brief Collector."""
from __future__ import annotations

from datetime import date
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from config import config
from graph.nodes.brief_collector import (
    AdvisoryBriefField,
    BriefDraft,
    MissingBriefField,
    StructuredOutputError,
    brief_collector_node,
)
from models import AgentResponse, ResponseMeta
from openai_campaign.structured import generate_structured
from session import add_message
from time_context import campaign_today


_EXPLICIT_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_OPENAI_YEARLESS_DATE_RULE = (
    "\nQUY TẮC NGÀY RIÊNG CHO OPENAI CAMPAIGN: Khi người dùng không ghi năm, "
    "giữ khoảng ngày trong năm hiện tại nếu endDate vẫn là hôm nay hoặc tương lai, "
    "kể cả startDate đã qua. Chỉ chuyển cả khoảng sang năm sau khi toàn bộ khoảng "
    "ngày của năm hiện tại đã kết thúc. Quy tắc này thay thế mọi chỉ dẫn trước đó "
    "yêu cầu startDate không được sớm hơn hôm nay."
)


class _OpenAIBriefTurnTransport(BaseModel):
    """Provider transport without domain cross-field validators.

    Responses structured parsing validates the Pydantic class before returning
    control to us. GPT can legitimately choose ``ask_clarification`` while also
    serializing the partial draft it used to reason. The strict domain schema
    must still reject that draft as a proposal, but the transport first needs
    to let us discard it instead of failing the whole turn.
    """

    action: Literal["ask_clarification", "propose_brief", "answer"]
    message: str = Field(min_length=1, max_length=4000)
    brief: BriefDraft | None = None
    reason: str = Field(default="", max_length=1000)
    missing_fields: list[MissingBriefField] = Field(default_factory=list, max_length=7)
    suggestion_fields: list[AdvisoryBriefField] = Field(default_factory=list, max_length=3)

    model_config = {"extra": "forbid"}


class _OpenAIBriefIntakeTransport(_OpenAIBriefTurnTransport):
    action: Literal["ask_clarification", "propose_brief"]


class _OpenAIBriefProposalTransport(_OpenAIBriefTurnTransport):
    action: Literal["propose_brief"]
    # A repair response has exactly one legal outcome. Making the nested draft
    # required at the provider schema boundary prevents a formally successful
    # `propose_brief` response with `brief: null`.
    brief: BriefDraft


# Preserve the schema names in OpenAI traces and test doubles. The classes stay
# private to this component and do not replace the shared GreenNode schemas.
_OpenAIBriefTurnTransport.__name__ = "BriefTurn"
_OpenAIBriefIntakeTransport.__name__ = "BriefIntakeTurn"
_OpenAIBriefProposalTransport.__name__ = "BriefProposalTurn"

_OPENAI_BRIEF_TRANSPORTS = {
    "brief_turn": _OpenAIBriefTurnTransport,
    "brief_intake_turn": _OpenAIBriefIntakeTransport,
    "brief_proposal_turn": _OpenAIBriefProposalTransport,
}


def _date_in_year(value: date, year: int) -> date:
    """Move a month/day into ``year`` with the legacy Feb-29 fallback."""
    try:
        return value.replace(year=year)
    except ValueError:
        return value.replace(year=year, day=28)


def normalize_openai_yearless_dates(
    value: dict,
    messages: list[dict],
    *,
    today: date | None = None,
) -> dict:
    """Apply OpenAI's in-progress campaign policy without changing GreenNode.

    The model can choose next year because its general date guidance avoids past
    start dates. Campaign creation already supports an in-progress window, so a
    yearless ``20/7-22/7`` on 21/7 must resolve to this year and launch active.
    """
    normalized = dict(value)
    user_text = "\n".join(
        str(message.get("content", ""))
        for message in messages
        if message.get("role") == "user"
    )
    if _EXPLICIT_YEAR_RE.search(user_text):
        return normalized

    today = today or campaign_today()
    try:
        model_start = date.fromisoformat(str(normalized.get("startDate", "")))
        model_end = date.fromisoformat(str(normalized.get("endDate", "")))
    except ValueError:
        return normalized

    start = _date_in_year(model_start, today.year)
    end_year = today.year + (
        (model_end.month, model_end.day) < (model_start.month, model_start.day)
    )
    end = _date_in_year(model_end, end_year)
    if end < today:
        start = _date_in_year(start, start.year + 1)
        end = _date_in_year(end, end.year + 1)

    normalized["startDate"] = start.isoformat()
    normalized["endDate"] = end.isoformat()
    return normalized


async def _openai_structured_runner(
    messages: list[dict],
    schema,
    schema_name: str,
    _role: str,
    max_tokens: int,
    *,
    session_id: str,
    client: Any | None,
):
    instructions = ""
    input_items = list(messages)
    if input_items and input_items[0].get("role") == "system":
        instructions = str(input_items.pop(0).get("content") or "")
    instructions += _OPENAI_YEARLESS_DATE_RULE
    transport_schema = _OPENAI_BRIEF_TRANSPORTS.get(schema_name, schema)
    try:
        parsed, provenance = await generate_structured(
            session_id=session_id,
            instructions=instructions,
            input_data=input_items,
            schema=transport_schema,
            schema_name=schema_name,
            max_output_tokens=max_tokens,
            client=client,
        )
    except Exception as exc:
        raise StructuredOutputError(
            f"{schema_name} OpenAI structured call failed: {str(exc)[:200]}"
        ) from exc
    if schema_name in _OPENAI_BRIEF_TRANSPORTS:
        parsed_data = parsed.model_dump()
        provider_working_brief = None
        if parsed_data.get("action") != "propose_brief":
            # A clarification may expose the model's working draft, but it is
            # neither user-approved nor eligible to become canonical state.
            provider_working_brief = parsed_data.get("brief")
            parsed_data["brief"] = None
        elif parsed_data.get("brief") is not None:
            parsed_data["brief"] = normalize_openai_yearless_dates(
                parsed_data["brief"], input_items,
            )
        if parsed_data.get("action") != "ask_clarification":
            parsed_data["missing_fields"] = []
        try:
            parsed = schema.model_validate(parsed_data)
        except ValidationError as exc:
            raise StructuredOutputError(
                f"{schema_name} invalid after OpenAI transport normalization: {exc}"
            ) from exc
        if provider_working_brief is not None:
            parsed._provider_working_brief = BriefDraft.model_validate(
                provider_working_brief
            )
    return parsed, int(provenance.get("total_tokens") or 0)


async def handle_openai_brief_intake(
    message: str,
    step: int,
    session_id: str,
    *,
    history: list[dict],
    auto_approve_brief: bool = False,
    client: Any | None = None,
) -> AgentResponse:
    """Collect an initial Brief atomically without calling GreenNode.

    The domain collector is shared so both engines keep the same validation,
    missing-field, budget, date, proposal, and approval semantics. Only the
    structured model runner and proposal provenance differ.
    """

    async def runner(messages, schema, schema_name, role, max_tokens):
        return await _openai_structured_runner(
            messages,
            schema,
            schema_name,
            role,
            max_tokens,
            session_id=session_id,
            client=client,
        )

    result = await brief_collector_node(
        {
            "session_id": session_id,
            "step": step,
            "user_message": message,
            "messages": [
                *history,
                {"role": "user", "content": message},
            ],
            "tokens_spent": 0,
            "auto_approve_brief": auto_approve_brief,
            # These safeguards are intentionally enabled only by the OpenAI
            # campaign adapter; the GreenNode collector path is unchanged.
            "merge_explicit_text_evidence": True,
            "replace_incomplete_brief": True,
        },
        structured_runner=runner,
        proposal_actor="openai_campaign_copilot",
    )

    reply = str(result.get("response_text") or "")
    # Proposal/error paths persist inside the collector. Clarification and
    # read-only answers are persisted by the legacy adapter, so mirror that
    # behavior here without importing the GreenNode free-form handler.
    if result.get("used_tool") == "freeform_chat" and reply:
        await add_message(session_id, "user", message)
        await add_message(session_id, "assistant", reply)

    return AgentResponse(
        text=reply,
        blocks=result.get("response_blocks", []),
        meta=ResponseMeta(
            tool=result.get("used_tool") or "openai_brief_collector",
            model=config.OPENAI_CAMPAIGN_MODEL,
            step=step,
        ),
        workspace_update=result.get("workspace_update"),
        suggestions=result.get("suggestions", []),
    )
