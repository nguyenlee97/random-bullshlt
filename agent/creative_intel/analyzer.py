"""
Deterministic creative analysis (Phase 3, stage 1).

⛔ Right tool per check: dimensions/format/aspect/animation come from the
ACTUAL BYTES via PIL — exact, free, no hallucination. A VLM asked for pixel
dimensions is the wrong tool. The VLM (vlm.py) only handles semantics.
"""
import io

import httpx

_client = httpx.AsyncClient(timeout=20.0)

# Aspect-ratio → layout hint. Skin/takeover creatives are typically very tall
# page backgrounds; this replaces the `"skin" in filename` hack as the
# deterministic signal (VLM adds the semantic confirmation when enabled).
SKIN_MIN_HEIGHT = 1000
SKIN_MAX_RATIO = 0.95  # width/height — portrait-ish full-page background
MIN_IMAGE_WIDTH = 300
MIN_IMAGE_HEIGHT = 50  # standard leaderboard banners are commonly 90-250px tall


async def analyze_bytes(data: bytes, name: str = "") -> dict:
    """Deterministic facts from file bytes. Never raises — returns partials."""
    out: dict = {"bytes": len(data), "name": name}
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        out.update({
            "width": img.width,
            "height": img.height,
            "format": (img.format or "").lower(),
            "aspect": round(img.width / img.height, 3) if img.height else None,
            "animated": bool(getattr(img, "is_animated", False)),
            "mode": img.mode,
        })
        out["is_skin_layout"] = (
            img.height >= SKIN_MIN_HEIGHT
            and out["aspect"] is not None
            and out["aspect"] <= SKIN_MAX_RATIO
        )
        out["min_size_ok"] = (
            img.width >= MIN_IMAGE_WIDTH and img.height >= MIN_IMAGE_HEIGHT
        )
    except Exception as e:
        out["decode_error"] = f"{type(e).__name__}: {str(e)[:80]}"
        # video/unknown types can't be PIL-decoded — flag for review, never block
    return out


async def analyze_url(url: str, name: str = "") -> dict:
    try:
        resp = await _client.get(url)
        resp.raise_for_status()
        return await analyze_bytes(resp.content, name=name)
    except Exception as e:
        return {"name": name, "fetch_error": f"{type(e).__name__}: {str(e)[:80]}"}
