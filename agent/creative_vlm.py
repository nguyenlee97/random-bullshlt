"""Low-cost OpenAI VLM acceptance check for generated ad creatives."""
from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

from config import config
from openai_campaign.client import get_client, safety_identifier
from openai_campaign.tracing import response_usage, trace_responses_call


class CreativeVLMVerdict(BaseModel):
    acceptable: bool
    composition_safe: bool
    text_readable: bool
    unexpected_text: list[str] = Field(default_factory=list, max_length=12)
    required_assets_present: list[str] = Field(default_factory=list, max_length=12)
    missing_required_assets: list[str] = Field(default_factory=list, max_length=12)
    brief_alignment: str = Field(min_length=1, max_length=500)
    review_notes: list[str] = Field(default_factory=list, max_length=12)
    confidence: str = Field(pattern="^(high|medium|low)$")


INSTRUCTIONS = """
Inspect one generated digital ad against its supplied brief, target format,
crop-safe prompt spec, and named required assets. Be conservative. Mark
acceptable false if critical content is visibly cropped, required named assets
are missing, the image contains material unexpected wording/claims, or core text
is unreadable. Do not infer off-image facts. This is a visual QA verdict, not a
marketing rewrite.
""".strip()


async def inspect_generated_creative(
    session_id: str, *, image_b64: str, brief: dict, format_contract: dict,
    prompt_spec: dict, assets: list[dict],
) -> tuple[dict, dict]:
    api = get_client()
    payload = {
        "brief": brief,
        "format": format_contract,
        "prompt_spec": prompt_spec,
        "named_assets": [{
            "name": item.get("name"), "kind": item.get("kind"),
            "required": item.get("required", False),
            "use_instruction": item.get("use_instruction"),
        } for item in assets],
    }
    input_data = [{
        "role": "user",
        "content": [
            {"type": "input_text", "text": json.dumps(payload, ensure_ascii=False, default=str)},
            {"type": "input_image", "image_url": f"data:image/png;base64,{image_b64}", "detail": "low"},
        ],
    }]
    request = {
        "model": config.OPENAI_VLM_MODEL, "instructions": INSTRUCTIONS,
        "input": input_data, "text_format": CreativeVLMVerdict.model_json_schema(),
        "max_output_tokens": 1000, "store": False,
    }
    started = time.perf_counter()
    response = await trace_responses_call(
        name="openai.vlm.creative_acceptance", session_id=session_id,
        model=config.OPENAI_VLM_MODEL, request=request,
        metadata={"schema": "creative_vlm_verdict", "specialist": "creative_vlm"},
        model_parameters={"max_output_tokens": 1000, "store": False, "image_detail": "low"},
        call=lambda: api.responses.parse(
            model=config.OPENAI_VLM_MODEL, instructions=INSTRUCTIONS,
            input=input_data, text_format=CreativeVLMVerdict,
            max_output_tokens=1000, store=False,
            safety_identifier=safety_identifier(session_id),
        ),
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise RuntimeError("OpenAI VLM returned no creative verdict")
    usage = response_usage(response)
    provenance = {
        "provider": "openai", "model": config.OPENAI_VLM_MODEL,
        "response_id": getattr(response, "id", None),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "input_tokens": usage["input"], "output_tokens": usage["output"],
        "total_tokens": usage["total"],
    }
    return parsed.model_dump(mode="json"), provenance
