"""OpenAI-owned model operations used by durable Campaign Autopilot runs."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from openai_campaign.guided import handle_openai_dmp_recommend
from openai_campaign.structured import generate_structured


class _AutopilotReadOnlyAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)


AUTOPILOT_READONLY_INSTRUCTIONS = """
You answer questions about a Campaign Autopilot run or its current human-review
checkpoint.
Use only the supplied artifact JSON. Never invent metrics, catalog entries,
delivery results, or campaign state. Clearly label forecasts as estimates.
Never interpret a question as approval and do not propose or perform workspace
changes. Answer concisely in Vietnamese and lead with the direct answer.
""".strip()


async def recommend_openai_autopilot_audience(
    *,
    session_id: str,
    brief_override: dict,
    client: Any | None = None,
) -> dict:
    """Use the OpenAI catalog-grounded audience sibling, never GreenNode."""
    return await handle_openai_dmp_recommend(
        session_id,
        brief_override=brief_override,
        client=client,
    )


async def answer_openai_autopilot_question(
    *,
    session_id: str,
    message: str,
    context: dict,
    client: Any | None = None,
) -> tuple[str, dict]:
    """Answer completed-run Q&A through the independent Responses boundary."""
    result, provenance = await generate_structured(
        session_id=session_id,
        instructions=AUTOPILOT_READONLY_INSTRUCTIONS,
        input_data=json.dumps(
            {"artifact_context": context, "question": message},
            ensure_ascii=False,
            default=str,
        )[:28000],
        schema=_AutopilotReadOnlyAnswer,
        schema_name="autopilot_readonly_answer",
        max_output_tokens=1200,
        client=client,
    )
    return result.answer.strip(), provenance
