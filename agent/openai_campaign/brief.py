"""OpenAI-owned provider boundary for the shared typed Brief Collector."""
from __future__ import annotations

from typing import Any

from config import config
from graph.nodes.brief_collector import (
    StructuredOutputError,
    brief_collector_node,
)
from models import AgentResponse, ResponseMeta
from openai_campaign.structured import generate_structured
from session import add_message


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
    try:
        parsed, provenance = await generate_structured(
            session_id=session_id,
            instructions=instructions,
            input_data=input_items,
            schema=schema,
            schema_name=schema_name,
            max_output_tokens=max_tokens,
            client=client,
        )
    except Exception as exc:
        raise StructuredOutputError(
            f"{schema_name} OpenAI structured call failed: {str(exc)[:200]}"
        ) from exc
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
