"""Low-cost OpenAI VLM acceptance check for generated ad creatives."""
from __future__ import annotations

import json
import time
from typing import Literal

from pydantic import BaseModel, Field

from config import config
from openai_campaign.client import get_client, safety_identifier
from openai_campaign.tracing import response_usage, trace_responses_call


class CreativeVLMVerdict(BaseModel):
    acceptable: bool
    composition_safe: bool
    text_readable: bool
    blocking_issues: list[Literal[
        "critical_crop",
        "core_text_unreadable",
        "missing_required_asset",
        "material_unsupported_claim",
        "safety_risk",
    ]] = Field(default_factory=list, max_length=8)
    unexpected_text: list[str] = Field(default_factory=list, max_length=12)
    required_assets_present: list[str] = Field(default_factory=list, max_length=12)
    missing_required_assets: list[str] = Field(default_factory=list, max_length=12)
    brief_alignment: str = Field(min_length=1, max_length=500)
    review_notes: list[str] = Field(default_factory=list, max_length=12)
    confidence: str = Field(pattern="^(high|medium|low)$")


INSTRUCTIONS = """
Inspect one generated digital ad against its supplied brief, target format,
crop-safe prompt spec, and named required assets. The prompt_spec is the
normalized creative authority. If raw brief notes conflict with prompt_spec,
follow prompt_spec and mention the conflict in review_notes; do not reject the
image solely for omitting an element that prompt_spec forbids.

Populate blocking_issues only for:
- critical_crop: important content is visibly cropped outside the safe area.
- core_text_unreadable: brand, primary message, or CTA is unreadable.
- missing_required_asset: a named required asset is visibly absent.
- material_unsupported_claim: unexpected wording makes a concrete price,
  legal, guarantee, certification, or technical-performance claim unsupported
  by the normalized prompt spec. A generic slogan is not blocking.
- safety_risk: visible content creates a material policy or brand-safety risk.

acceptable must be false exactly when blocking_issues is non-empty. Other
differences belong in review_notes as non-blocking advice. Do not infer
off-image facts. This is a visual QA verdict, not a marketing rewrite.
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
    blocking_issues = set(parsed.blocking_issues)
    if not parsed.composition_safe:
        blocking_issues.add("critical_crop")
    if not parsed.text_readable:
        blocking_issues.add("core_text_unreadable")
    if parsed.missing_required_assets:
        blocking_issues.add("missing_required_asset")
    parsed.blocking_issues = sorted(blocking_issues)
    parsed.acceptable = not parsed.blocking_issues
    usage = response_usage(response)
    provenance = {
        "provider": "openai", "model": config.OPENAI_VLM_MODEL,
        "response_id": getattr(response, "id", None),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "input_tokens": usage["input"], "output_tokens": usage["output"],
        "total_tokens": usage["total"],
    }
    return parsed.model_dump(mode="json"), provenance
