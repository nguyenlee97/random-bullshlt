"""AI creative generation and durable asset persistence for Autopilot."""
from __future__ import annotations

import base64
import hashlib
from io import BytesIO

import httpx
from PIL import Image, ImageOps

from config import config
from handlers.image_gen import AD_FORMATS, generation_provenance, handle_generate_image
from workspace.service import get_workspace


DEFAULT_FORMAT_ID = "zuma-box"


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
) -> dict:
    """Generate, resize and persist one deterministic Autopilot creative asset.

    Storage uses a run-and-format idempotency key. If the worker retries after
    the upload committed, the backend returns the original asset rather than
    writing another file.
    """
    brief_item = workspace.get("artifacts", {}).get("brief", {})
    brief = brief_item.get("value") or {}
    brief_revision = int(brief_item.get("revision", 0))
    idempotency_key = (
        f"autopilot:{run['run_id']}:{format_id}:brief-r{brief_revision}"
    )
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:24]
    filename = f"creative_ai_{digest}.png"
    stored_url = f"{config.BACKEND_URL.rstrip('/')}/uploads/{filename}"
    provenance = generation_provenance(brief, format_id)

    # The deterministic storage path is also a durable generation checkpoint.
    # A worker crash after upload but before workspace commit can therefore
    # recover without spending another image-generation call.
    async with httpx.AsyncClient(timeout=10.0) as client:
        existing = await client.head(stored_url)
    if existing.status_code == 200:
        width = int(AD_FORMATS[format_id]["width"])
        height = int(AD_FORMATS[format_id]["height"])
        current = await get_workspace(run["session_id"])
        current_revision = int(
            current.get("artifacts", {}).get("brief", {}).get("revision", 0)
        )
        if current_revision != brief_revision:
            raise RuntimeError("brief changed while AI creative was being recovered")
        return {
            "id": idempotency_key,
            "name": filename,
            "url": _browser_url(stored_url),
            "size": int(existing.headers.get("content-length") or 0),
            "type": "image/png", "mimeType": "image/png",
            "width": width, "height": height,
            "formatId": format_id, "intendedFormat": format_id,
            "source": "ai_generated",
            "generation": {
                "idempotencyKey": idempotency_key, **provenance,
                "formatId": format_id, "reused": True,
            },
        }

    generated = await handle_generate_image(run["session_id"], brief, format_id)
    if not generated.get("ok"):
        raise RuntimeError(
            "AI creative generation failed: " + str(generated.get("error") or "unknown error")
        )

    width = int(generated["width"])
    height = int(generated["height"])
    png_b64 = _fit_png(generated["imageB64"], width, height)
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
    current_revision = int(
        current.get("artifacts", {}).get("brief", {}).get("revision", 0)
    )
    if current_revision != brief_revision:
        raise RuntimeError("brief changed while AI creative was being generated")

    generation = {
        "idempotencyKey": idempotency_key,
        "provider": generated.get("provider", "vngcloud_maas"),
        "model": generated.get("model", "openai/gpt-image-1"),
        "promptVersion": generated.get("promptVersion", "image-gen-v1"),
        "promptFingerprint": generated.get("promptFingerprint", ""),
        "formatId": format_id,
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
        "intendedFormat": format_id,
        "source": "ai_generated",
        "generation": generation,
    }
