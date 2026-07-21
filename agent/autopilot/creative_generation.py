"""AI creative generation and durable asset persistence for Autopilot."""
from __future__ import annotations

import asyncio
import base64
import hashlib
from io import BytesIO

import httpx
from PIL import Image, ImageOps

from config import config
from handlers.image_gen import AD_FORMATS, generation_provenance, handle_generate_image
from creative_assets import get_assets
from creative_prompt import compose_prompt_spec
from image_quota import actor_for_session
from creative_vlm import inspect_generated_creative
from workspace.service import get_workspace


DEFAULT_FORMAT_ID = "zuma-box"


def generation_idempotency_key(
    run_id: str,
    format_id: str,
    *,
    brief_revision: int,
    format_plan_revision: int,
    variant: int = 0,
) -> str:
    return (
        f"autopilot:{run_id}:{format_id}:variant-{variant}:"
        f"plan-r{format_plan_revision}:brief-r{brief_revision}"
    )


def _default_intended_format(format_id: str) -> str:
    return "skin" if format_id == "znews-Background" else "banner"


def _assert_current_inputs(
    current: dict, *, brief_revision: int, format_plan_revision: int,
) -> None:
    artifacts = current.get("artifacts", {})
    current_brief = int(artifacts.get("brief", {}).get("revision", 0))
    current_plan = int(artifacts.get("creative_format_plan", {}).get("revision", 0))
    if current_brief != brief_revision:
        raise RuntimeError("brief changed while AI creative was being generated")
    if current_plan != format_plan_revision:
        raise RuntimeError("creative format plan changed while AI creative was being generated")


def _fit_png(image_b64: str, width: int, height: int) -> str:
    """Crop an image to the target ratio and encode exact-size PNG bytes."""
    source = base64.b64decode(image_b64)
    with Image.open(BytesIO(source)) as image:
        fitted = ImageOps.fit(
            image.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS
        )
        output = BytesIO()
        fitted.save(output, format="PNG", optimize=True)
    return base64.b64encode(output.getvalue()).decode("ascii")


def _browser_url(url: str) -> str:
    """Translate Docker's backend hostname into the browser-visible local URL."""
    if url.startswith("http://backend:3000/"):
        return "http://localhost:3000/" + url.removeprefix("http://backend:3000/")
    return url


async def generate_creative(
    run: dict,
    workspace: dict,
    *,
    format_id: str = DEFAULT_FORMAT_ID,
    intended_format: str | None = None,
    intended_zone_ids: list[str] | None = None,
    variant: int = 0,
) -> dict:
    """Generate, resize and persist one deterministic Autopilot creative asset.

    Storage uses a run-and-format idempotency key. If the worker retries after
    the upload committed, the backend returns the original asset rather than
    writing another file.
    """
    brief_item = workspace.get("artifacts", {}).get("brief", {})
    format_plan_item = workspace.get("artifacts", {}).get("creative_format_plan", {})
    brief = brief_item.get("value") or {}
    brief_revision = int(brief_item.get("revision", 0))
    format_plan_revision = int(format_plan_item.get("revision", 0))
    idempotency_key = generation_idempotency_key(
        run["run_id"], format_id, brief_revision=brief_revision,
        format_plan_revision=format_plan_revision, variant=variant,
    )
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:24]
    filename = f"creative_ai_{digest}.png"
    stored_url = f"{config.BACKEND_URL.rstrip('/')}/uploads/{filename}"
    actor = await actor_for_session(run["session_id"])
    assets = await get_assets(actor, run.get("creative_asset_ids") or [])
    provenance = generation_provenance(
        brief, format_id, run.get("creative_direction") or "",
        assets=assets,
    )

    # The deterministic storage path is also a durable generation checkpoint.
    # A worker crash after upload but before workspace commit can therefore
    # recover without spending another image-generation call.
    async with httpx.AsyncClient(timeout=10.0) as client:
        existing = await client.head(stored_url)
    if existing.status_code == 200:
        width = int(AD_FORMATS[format_id]["width"])
        height = int(AD_FORMATS[format_id]["height"])
        current = await get_workspace(run["session_id"])
        _assert_current_inputs(
            current, brief_revision=brief_revision,
            format_plan_revision=format_plan_revision,
        )
        return {
            "id": idempotency_key,
            "name": filename,
            "url": _browser_url(stored_url),
            "size": int(existing.headers.get("content-length") or 0),
            "type": "image/png", "mimeType": "image/png",
            "width": width, "height": height,
            "formatId": format_id,
            "intendedFormat": intended_format or _default_intended_format(format_id),
            "intendedZoneIds": list(intended_zone_ids or []),
            "source": "ai_generated",
            "generation": {
                "idempotencyKey": idempotency_key, **provenance,
                "formatId": format_id, "variant": variant,
                "briefRevision": brief_revision,
                "formatPlanRevision": format_plan_revision,
                "reused": True,
            },
        }

    prompt_spec, prompt_provenance = await compose_prompt_spec(
        run["session_id"], brief=brief, format_id=format_id,
        assets=assets, direction=run.get("creative_direction") or "",
    )
    provenance = generation_provenance(
        brief, format_id, run.get("creative_direction") or "",
        assets=assets, prompt_spec=prompt_spec,
    )
    generated = await handle_generate_image(
        run["session_id"], brief, format_id,
        run.get("creative_direction") or "", actor=actor, assets=assets,
        prompt_spec=prompt_spec, idempotency_key=idempotency_key,
        quality=prompt_spec.get("quality", "medium"),
    )
    if not generated.get("ok"):
        raise RuntimeError(
            "AI creative generation failed: " + str(generated.get("error") or "unknown error")
        )

    width = int(generated["width"])
    height = int(generated["height"])
    png_b64 = _fit_png(generated["imageB64"], width, height)
    try:
        vlm_verdict, vlm_provenance = await inspect_generated_creative(
            run["session_id"], image_b64=png_b64, brief=brief,
            format_contract={
                "format_id": format_id, "width": width, "height": height,
                "intended_zone_ids": list(intended_zone_ids or []),
            },
            prompt_spec=prompt_spec, assets=assets,
        )
    except Exception as exc:
        vlm_verdict = {
            "acceptable": False, "confidence": "low",
            "review_notes": [f"VLM acceptance check unavailable: {type(exc).__name__}"],
        }
        vlm_provenance = {"provider": "openai", "model": config.OPENAI_VLM_MODEL, "error": type(exc).__name__}
    upload_url = f"{config.BACKEND_URL.rstrip('/')}/api/creative/upload-base64"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            upload_url,
            json={
                "base64": png_b64,
                "filename": f"ai-{format_id}-{run['run_id']}.png",
                "mimeType": "image/png",
                "idempotencyKey": idempotency_key,
            },
        )
    if response.status_code not in {200, 201}:
        raise RuntimeError(
            f"AI creative upload failed ({response.status_code}): {response.text[:240]}"
        )
    stored = response.json()
    if not stored.get("ok") or not stored.get("url"):
        raise RuntimeError("AI creative upload returned no durable asset URL")

    current = await get_workspace(run["session_id"])
    _assert_current_inputs(
        current, brief_revision=brief_revision,
        format_plan_revision=format_plan_revision,
    )

    generation = {
        "idempotencyKey": idempotency_key,
        "provider": generated.get("provider", "openai"),
        "model": generated.get("model", "gpt-image-2"),
        "promptVersion": generated.get("promptVersion", "creative-prompt-v2"),
        "promptFingerprint": generated.get("promptFingerprint", ""),
        "promptSpec": prompt_spec,
        "promptComposer": prompt_provenance,
        "assetIds": [item.get("asset_id") for item in assets],
        "vlmVerdict": vlm_verdict,
        "vlmProvenance": vlm_provenance,
        "exactDimensionsVerified": True,
        "formatId": format_id,
        "variant": variant,
        "briefRevision": brief_revision,
        "formatPlanRevision": format_plan_revision,
        "reused": bool(stored.get("reused")),
    }
    return {
        "id": idempotency_key,
        "name": stored.get("filename") or f"ai-{format_id}.png",
        "url": _browser_url(stored["url"]),
        "size": int(stored.get("size") or 0),
        "type": "image/png",
        "mimeType": "image/png",
        "width": width,
        "height": height,
        "formatId": format_id,
        "intendedFormat": intended_format or _default_intended_format(format_id),
        "intendedZoneIds": list(intended_zone_ids or []),
        "source": "ai_generated",
        "generation": generation,
    }


async def generate_creatives(
    run: dict,
    workspace: dict,
    format_plan: dict,
    *,
    concurrency: int = 2,
) -> tuple[list[dict], list[dict]]:
    """Generate all planned formats with bounded concurrency and partial evidence."""
    formats = list(format_plan.get("formats") or [])
    semaphore = asyncio.Semaphore(max(1, min(int(concurrency or 1), 4)))

    async def one(spec: dict) -> dict:
        async with semaphore:
            return await generate_creative(
                run,
                workspace,
                format_id=spec["format_id"],
                intended_format=spec.get("intended_format"),
                intended_zone_ids=spec.get("zone_ids") or [],
                variant=0,
            )

    results = await asyncio.gather(*(one(spec) for spec in formats), return_exceptions=True)
    generated: list[dict] = []
    failures: list[dict] = []
    for spec, result in zip(formats, results):
        if isinstance(result, Exception):
            failures.append({
                "format_id": spec.get("format_id"),
                "zone_ids": spec.get("zone_ids") or [],
                "error": str(result)[:300],
            })
        else:
            generated.append(result)
    return generated, failures
