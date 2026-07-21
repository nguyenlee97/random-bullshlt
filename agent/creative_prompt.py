"""Schema-validated GPT-5.4-mini creative prompt composer."""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from handlers.image_gen import AD_FORMATS, PROMPT_VERSION, generation_size
from openai_campaign.structured import generate_structured


class AssetBinding(BaseModel):
    asset_id: str
    name: str
    role: str = Field(min_length=1, max_length=300)
    placement: str = Field(default="crop-safe primary area", max_length=200)
    required: bool = False


class CreativePromptSpec(BaseModel):
    objective: str = Field(min_length=1, max_length=120)
    audience: str = Field(min_length=1, max_length=500)
    primary_promise: str = Field(min_length=1, max_length=400)
    cta: str = Field(min_length=1, max_length=160)
    message_hierarchy: list[str] = Field(default_factory=list, max_length=6)
    creative_direction: str = Field(min_length=1, max_length=1200)
    tone: str = Field(min_length=1, max_length=200)
    colors: list[str] = Field(default_factory=list, max_length=8)
    required_text: list[str] = Field(default_factory=list, max_length=6)
    forbidden_elements: list[str] = Field(default_factory=list, max_length=10)
    asset_bindings: list[AssetBinding] = Field(default_factory=list, max_length=8)
    target_width: int = Field(gt=0, le=3840)
    target_height: int = Field(gt=0, le=3840)
    proxy_size: str
    safe_area: str = Field(min_length=1, max_length=700)
    crop_strategy: Literal["exact", "center_crop_from_3_to_1_proxy", "center_crop"]
    overlay_policy: str = Field(min_length=1, max_length=500)
    quality: Literal["low", "medium", "high"] = "medium"
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=10)
    template_version: str = PROMPT_VERSION


INSTRUCTIONS = """
You are the creative prompt composer for a paid digital advertising workflow.
Return a production-ready CreativePromptSpec grounded only in the supplied brief,
format contract, user direction, and named assets. Do not invent offers, prices,
legal claims, product features, or brand rules. Keep copy short because the final
placement may be small. Bind each named asset explicitly by asset_id and name.
For required logos/products, preserve identity and keep them in the crop-safe area.
Use medium quality unless the user explicitly asks for a draft (low) or premium
final (high). Required text must be minimal; deterministic overlays are preferred
for exact logos, legal copy, and critical CTA wording.
""".strip()


async def compose_prompt_spec(
    session_id: str, *, brief: dict, format_id: str,
    assets: list[dict] | None = None, direction: str = "",
) -> tuple[dict, dict]:
    fmt = AD_FORMATS.get(format_id)
    if not fmt:
        raise ValueError(f"Unknown format_id: {format_id}")
    payload = {
        "brief": brief,
        "format": {
            "id": format_id, "label": fmt["label"],
            "target_width": fmt["width"], "target_height": fmt["height"],
            "proxy_size": generation_size(fmt),
            "layout": fmt["layoutDescription"],
            "safe_zone": fmt["safeZoneConstraint"],
        },
        "named_assets": [{
            "asset_id": item.get("asset_id"), "name": item.get("name"),
            "kind": item.get("kind"), "use_instruction": item.get("use_instruction"),
            "required": item.get("required", False),
        } for item in (assets or [])],
        "user_direction": direction,
        "mandatory_contract": {
            "target_width": fmt["width"], "target_height": fmt["height"],
            "proxy_size": generation_size(fmt), "template_version": PROMPT_VERSION,
            "crop_strategy": (
                "center_crop_from_3_to_1_proxy"
                if max(fmt["width"] / fmt["height"], fmt["height"] / fmt["width"]) > 3
                else "center_crop"
            ),
        },
    }
    output, provenance = await generate_structured(
        session_id=session_id, instructions=INSTRUCTIONS,
        input_data=json.dumps(payload, ensure_ascii=False, default=str),
        schema=CreativePromptSpec, schema_name="creative_prompt_spec",
        max_output_tokens=2200,
    )
    spec = output.model_dump(mode="json")
    # Format geometry is server authoritative even if the model drifts.
    spec.update(
        target_width=fmt["width"], target_height=fmt["height"],
        proxy_size=generation_size(fmt), template_version=PROMPT_VERSION,
    )
    return spec, provenance
