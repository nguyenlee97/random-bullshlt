"""Deterministic creative analysis from the uploaded file bytes.

Images are decoded with Pillow. Videos are inspected with a bounded ffprobe
subprocess. Semantic interpretation remains the VLM's job.
"""
import asyncio
import io
import json
import subprocess

import httpx

_client = httpx.AsyncClient(timeout=20.0)

SKIN_MIN_HEIGHT = 1000
SKIN_MAX_RATIO = 0.95
MIN_IMAGE_WIDTH = 300
MIN_IMAGE_HEIGHT = 50
FFPROBE_TIMEOUT_SECONDS = 8
MAX_FFPROBE_OUTPUT_BYTES = 256_000


def _looks_like_video(name: str, mime_type: str) -> bool:
    mime = (mime_type or "").lower()
    suffix = (name or "").lower().rsplit(".", 1)[-1]
    return mime.startswith("video/") or suffix in {"mp4", "mov", "webm", "mkv", "avi"}


def _rate(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        numerator, denominator = value.split("/", 1)
        return round(float(numerator) / float(denominator), 3)
    except (ValueError, ZeroDivisionError):
        return None


def _probe_video(data: bytes, name: str) -> dict:
    """Extract bounded metadata from untrusted video bytes using ffprobe."""
    out: dict = {"bytes": len(data), "name": name, "kind": "video"}
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-of",
                "json",
                "-show_entries",
                "format=duration,size,format_name:stream=codec_type,codec_name,width,height,avg_frame_rate",
                "-i",
                "pipe:0",
            ],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=FFPROBE_TIMEOUT_SECONDS,
            check=False,
        )
        if proc.returncode != 0:
            detail = proc.stderr.decode("utf-8", errors="replace")[:160].strip()
            raise ValueError(detail or f"ffprobe exited {proc.returncode}")
        if len(proc.stdout) > MAX_FFPROBE_OUTPUT_BYTES:
            raise ValueError("ffprobe output exceeded safety limit")

        payload = json.loads(proc.stdout.decode("utf-8"))
        streams = payload.get("streams") or []
        video = next((item for item in streams if item.get("codec_type") == "video"), None)
        if not video:
            raise ValueError("no video stream found")

        width = int(video.get("width") or 0)
        height = int(video.get("height") or 0)
        fmt = payload.get("format") or {}
        duration = fmt.get("duration")
        out.update(
            {
                "width": width,
                "height": height,
                "format": fmt.get("format_name") or "video",
                "codec": video.get("codec_name") or "unknown",
                "duration_seconds": (
                    round(float(duration), 3) if duration not in (None, "N/A") else None
                ),
                "frame_rate": _rate(video.get("avg_frame_rate")),
                "aspect": round(width / height, 3) if height else None,
                "animated": True,
                "is_skin_layout": False,
                "min_size_ok": width >= MIN_IMAGE_WIDTH and height >= MIN_IMAGE_HEIGHT,
            }
        )
    except Exception as exc:
        out["decode_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return out


async def analyze_bytes(data: bytes, name: str = "", mime_type: str = "") -> dict:
    """Return deterministic facts from bytes without propagating decode errors."""
    if _looks_like_video(name, mime_type):
        return await asyncio.to_thread(_probe_video, data, name)

    out: dict = {"bytes": len(data), "name": name, "kind": "image"}
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        out.update(
            {
                "width": img.width,
                "height": img.height,
                "format": (img.format or "").lower(),
                "aspect": round(img.width / img.height, 3) if img.height else None,
                "animated": bool(getattr(img, "is_animated", False)),
                "mode": img.mode,
            }
        )
        out["is_skin_layout"] = (
            img.height >= SKIN_MIN_HEIGHT
            and out["aspect"] is not None
            and out["aspect"] <= SKIN_MAX_RATIO
        )
        out["min_size_ok"] = (
            img.width >= MIN_IMAGE_WIDTH and img.height >= MIN_IMAGE_HEIGHT
        )
    except Exception as exc:
        out["decode_error"] = f"{type(exc).__name__}: {str(exc)[:80]}"
    return out


async def analyze_url(url: str, name: str = "", mime_type: str = "") -> dict:
    try:
        response = await _client.get(url)
        response.raise_for_status()
        return await analyze_bytes(response.content, name=name, mime_type=mime_type)
    except Exception as exc:
        return {"name": name, "fetch_error": f"{type(exc).__name__}: {str(exc)[:80]}"}
