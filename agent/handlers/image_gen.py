"""
AI Image Generation handler — uses VNG Cloud gpt-image-1.
Tracks per-session generation count (max 10).
Builds a safe-zone prompt from the format catalog + campaign brief.
"""
import hashlib
import httpx
from config import config
from session import log_event

# ─── Max generations per session ─────────────────────────────────────────────
MAX_GENERATIONS = 10
IMAGE_MODEL = "openai/gpt-image-1"
PROMPT_VERSION = "image-gen-v1"

# In-memory generation counter: { session_id: int }
_gen_count: dict[str, int] = {}

# ─── Ad format catalog (mirrors adFormats.js on the frontend) ─────────────────
AD_FORMATS: dict[str, dict] = {
    "zmp3-top-banner": {
        "label": "ZingMP3 Top Banner",
        "width": 2032, "height": 528,
        "layoutDescription": (
            "A wide horizontal promotional banner. The background features a bright, "
            "out-of-focus outdoor landscape. On the far left, place massive, stylized 3D "
            "promotional typography. In the exact center, position a trio of cylindrical "
            "product mockups standing upright on reflective, geometric pedestals. On the "
            "right side, align clean, descriptive text accompanied by a horizontal row of "
            "three distinct, circular feature icons."
        ),
        "safeZoneConstraint": (
            "1. CANVAS CONSTRAINTS & SAFE ZONE (CRITICAL): You are generating a design that "
            "will be cropped into a 3.8:1 ultra-wide panoramic banner (2032x528). You MUST "
            "constrain ALL text, products, and critical design elements to a narrow horizontal "
            "strip directly in the vertical center of the image. The top 30% and bottom 30% "
            "of the generated canvas MUST be left as completely empty background so it can be "
            "cropped safely."
        ),
    },
    "znews-Background": {
        "label": "ZingNews Background Desktop",
        "width": 1504, "height": 704,
        "layoutDescription": (
            "A large desktop background layout utilizing a vibrant, radial sunburst or ray "
            "pattern expanding outward. In the top-center area, tightly cluster several product "
            "packaging mockups next to bold, stacked promotional text and a stylized price tag "
            "graphic. Leave the lower 80% and the outer edges of the canvas completely empty "
            "to act as negative space."
        ),
        "safeZoneConstraint": (
            "1. CANVAS CONSTRAINTS & SAFE ZONE (CRITICAL): You are generating a large 2.1:1 "
            "desktop wrapper (1504x704). You MUST cluster ALL critical ad elements (text, "
            "products) strictly in the TOP-CENTER of the canvas. The entire bottom 80% and "
            "the far left/right edges MUST be left as empty, unobtrusive background texture "
            "or negative space."
        ),
    },
    "znews-middle-banner": {
        "label": "ZingNews Middle Banner",
        "width": 2048, "height": 512,
        "layoutDescription": (
            "A wide horizontal banner with a dark, dynamic, heavily textured background. On "
            "the left side, arrange extremely large, bold headline text spanning two lines. "
            "In the center, place an energetic character mascot posing directly next to a "
            "central product mockup, surrounded by themed environmental props. On the right "
            "side, include a large, semi-transparent frosted-glass overlay box containing a "
            "bulleted list of promotional offers and corresponding icons."
        ),
        "safeZoneConstraint": (
            "1. CANVAS CONSTRAINTS & SAFE ZONE (CRITICAL): You are generating a design that "
            "will be cropped into a 4:1 ultra-wide panoramic banner (2048x512). You MUST "
            "constrain ALL text, characters, mockups, and critical design elements to a narrow "
            "horizontal strip right in the center of the image. The top 25% and the bottom "
            "25% of the canvas MUST be left as empty background texture."
        ),
    },
    "znews-side-banner": {
        "label": "ZingNews Side Banner (Skyscraper)",
        "width": 736, "height": 1456,
        "layoutDescription": (
            "A tall vertical banner layout with a dynamic radial burst background. Top "
            "section: a small brand logo placeholder. Center section: an energetic character "
            "mascot leaping from a stack of stylized geometric boxes, interacting with a "
            "floating central product. Lower center: a bold 3D text ribbon. Bottom section: "
            "a prominent, rounded white rectangle containing stacked, bold typography. "
            "Scatter dynamic environmental elements like sparkles or floating particles throughout."
        ),
        "safeZoneConstraint": (
            "1. CANVAS CONSTRAINTS & SAFE ZONE (CRITICAL): You are generating a design that "
            "will be cropped into a 1:2 vertical skyscraper banner (736x1456). You MUST "
            "constrain ALL critical elements (mascots, products, text) to a central vertical "
            "column. The far left and far right edges of the generated canvas MUST be left "
            "as extendable background texture so they can be cropped away safely."
        ),
    },
    "znews-top-banner": {
        "label": "ZingNews Top Banner",
        "width": 2224, "height": 480,
        "layoutDescription": (
            "A wide horizontal layout with an energetic radial line background. Far left: a "
            "tightly packed 2x2 grid of square feature boxes. Center-left: a vibrant character "
            "mascot standing and presenting the main product mockup. Center-right: large, "
            "heavily stylized 3D headline text. Far right: a brightly glowing, neon-styled "
            "rectangular frame enclosing a secondary call-to-action message."
        ),
        "safeZoneConstraint": (
            "1. CANVAS CONSTRAINTS & SAFE ZONE (CRITICAL): You are generating a design that "
            "will be cropped into an extremely wide 4.6:1 panoramic banner (2224x480). You "
            "MUST constrain ALL ad content to an incredibly narrow horizontal strip directly "
            "across the middle. Treat the entire top third and bottom third of the canvas as "
            "disposable background area."
        ),
    },
    "zuma-baomoi-masthead": {
        "label": "BaoMoi Masthead (1160×280)",
        "width": 1160, "height": 280,
        "layoutDescription": (
            "A clean horizontal masthead layout. The background features a soft, blurred "
            "outdoor setting. On the left side, place two slightly overlapping central product "
            "mockups tilted at a slight angle. In the center, position large, straightforward "
            "primary typography with smaller sub-text immediately below, followed by a "
            "pill-shaped call-to-action button. On the far right, anchor a distinct, brightly "
            "colored, folded tag or sticker graphic containing bold discount text."
        ),
        "safeZoneConstraint": (
            "1. CANVAS CONSTRAINTS & SAFE ZONE (CRITICAL): You are generating a design that "
            "will be cropped into a 4.1:1 panoramic masthead (1160x280). You MUST squish ALL "
            "text, products, and UI elements into a narrow horizontal band in the vertical "
            "center. The upper and lower edges must be plain, out-of-focus background."
        ),
    },
    "zuma-box": {
        "label": "Display Box (300×250)",
        "width": 300, "height": 250,
        "layoutDescription": (
            "A compact, roughly square layout with a simple radial gradient background. In "
            "the center, place two central product mockups positioned closely together, "
            "surrounded by a dynamic explosion of organic environmental props and liquid "
            "splashes. In the bottom right corner of the central grouping, overlap a tilted, "
            "circular promotional stamp. Include bold headline text at the top edge and clean, "
            "simple footer text at the bottom edge."
        ),
        "safeZoneConstraint": (
            "1. CANVAS CONSTRAINTS & SAFE ZONE (CRITICAL): You are generating a design that "
            "will be cropped into a 1.2:1 box (300x250). Since this is nearly square, fill "
            "the center canvas area with the design, but leave a small, safe margin of plain "
            "background color around all four outer edges to ensure no text or graphics are "
            "cut off if cropped slightly."
        ),
    },
    "zuma-Left": {
        "label": "Side Slider Left (465×1200)",
        "width": 465, "height": 1200,
        "layoutDescription": (
            "A tall vertical asset designed for a left-side slider ad. The actual ad content "
            "is confined to a compact, vertical rectangular block. Within this visible "
            "rectangular block, the layout is split: the top half features a brightly colored "
            "background with a central product mockup and energetic splash effects, while the "
            "bottom half is a solid dark contrasting panel containing a centered, brightly "
            "colored rectangular call-to-action button."
        ),
        "safeZoneConstraint": (
            "1. CANVAS CONSTRAINTS & SAFE ZONE (CRITICAL): You are generating a 465x1200 "
            "side-slider ad. Because this ad docks to the side of a screen, you MUST compress "
            "all ad content (graphics, colors, buttons, products) tightly into a vertical "
            "column positioned completely flush against the RIGHT side of the image. Leave the "
            "left side as plain, blank background space."
        ),
    },
    "zuma-Right": {
        "label": "Side Slider Right (465×1200)",
        "width": 465, "height": 1200,
        "layoutDescription": (
            "A tall vertical asset designed for a right-side slider ad. The actual ad content "
            "is confined to a compact, vertical rectangular block. Within this visible "
            "rectangular block, the layout is split: the top half features a brightly colored "
            "background with a central product mockup and energetic splash effects, while the "
            "bottom half is a solid dark contrasting panel containing a centered, brightly "
            "colored rectangular call-to-action button."
        ),
        "safeZoneConstraint": (
            "1. CANVAS CONSTRAINTS & SAFE ZONE (CRITICAL): You are generating a 465x1200 "
            "side-slider ad. Because this ad docks to the side of a screen, you MUST compress "
            "all ad content (graphics, colors, buttons, products) tightly into a vertical "
            "column positioned completely flush against the LEFT side of the image. Leave the "
            "right side as plain, blank background space."
        ),
    },
}

# ─── Prompt builder ───────────────────────────────────────────────────────────
PROMPT_WRAPPER = """\
You are an expert commercial art director and AI image generator. Your task is to generate a single digital marketing ad image that combines a campaign brief with a specific layout structure.

=== INPUT 1: CAMPAIGN BRIEF ===
{brief_text}

=== INPUT 2: AD FORMAT ===
Format: {label}
Output ratio: {api_ratio} (standard generation size — do NOT try to simulate a different aspect ratio inside the canvas)

=== INPUT 3: LAYOUT STRUCTURE ===
{layout_description}
{custom_prompt_block}
=== GENERATION INSTRUCTIONS ===
1. FILL THE FULL CANVAS: Generate content that fills the entire image naturally at the output ratio. Do NOT leave large empty areas or squish elements into a narrow strip.

2. THEMATIC ADAPTATION: Do not use placeholder objects or branding from the layout description. Replace all elements with visually appropriate equivalents based on the campaign brief.
   - Match the mood, color palette, and energy described in the campaign notes.

3. SPATIAL ADHERENCE: Follow the structural arrangement described (left/center/right, top/bottom zones) adapted naturally to the actual canvas shape.

4. TEXT & TYPOGRAPHY: Incorporate the brand name and key message from the brief into the design. Keep text clean, bold, and readable. Do not hallucinate extra words.

Generate the image now.\
"""


def _build_brief_text(brief: dict) -> str:
    """Only include visually-relevant fields. Budget, KPI, dates pollute the image prompt."""
    lines = []
    if brief.get("brand"):
        lines.append(f"Brand: {brief['brand']}")
    if brief.get("notes"):
        lines.append(f"Campaign Theme / Audience:\n{brief['notes']}")
    return "\n".join(lines) if lines else "No brief provided."


def _build_prompt(fmt: dict, brief: dict, custom_prompt: str = "") -> str:
    # Determine which of the 3 standard gpt-image-1 ratios this format maps to
    ratio = fmt["width"] / fmt["height"]
    if ratio > 1.2:
        api_ratio = "1536×1024 (landscape, ~3:2)"
    elif ratio < 0.9:
        api_ratio = "1024×1536 (portrait, ~2:3)"
    else:
        api_ratio = "1024×1024 (square, 1:1)"

    custom_block = ""
    if custom_prompt and custom_prompt.strip():
        custom_block = f"\n=== INPUT 4: CUSTOM STYLE INSTRUCTIONS ===\n{custom_prompt.strip()}\n"
    return PROMPT_WRAPPER.format(
        brief_text=_build_brief_text(brief),
        label=fmt["label"],
        api_ratio=api_ratio,
        layout_description=fmt["layoutDescription"],
        custom_prompt_block=custom_block,
    )


def generation_provenance(brief: dict, format_id: str, custom_prompt: str = "") -> dict:
    """Return stable metadata for one generation request without calling MaaS."""
    fmt = AD_FORMATS.get(format_id)
    if not fmt:
        raise ValueError(f"Unknown format_id: {format_id}")
    prompt = _build_prompt(fmt, brief, custom_prompt=custom_prompt)
    return {
        "provider": "vngcloud_maas",
        "model": IMAGE_MODEL,
        "promptVersion": PROMPT_VERSION,
        "promptFingerprint": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }


# ─── Handler ──────────────────────────────────────────────────────────────────
async def handle_generate_image(session_id: str, brief: dict, format_id: str, custom_prompt: str = "") -> dict:
    """
    Generate an ad image using gpt-image-1.
    Returns: {ok, imageB64, formatId, width, height, remaining} | {ok: False, error}
    """
    # Validate format
    fmt = AD_FORMATS.get(format_id)
    if not fmt:
        return {"ok": False, "error": f"Unknown format_id: {format_id}"}

    # Check session limit
    count = _gen_count.get(session_id, 0)
    if count >= MAX_GENERATIONS:
        await log_event(session_id, "image_gen_limit", {"format_id": format_id})
        return {
            "ok": False,
            "error": "Đã đạt giới hạn 10 ảnh/phiên",
            "remaining": 0,
        }

    # Build prompt
    prompt = _build_prompt(fmt, brief, custom_prompt=custom_prompt)
    provenance = generation_provenance(brief, format_id, custom_prompt)

    # Call VNG Cloud image API
    api_key = config.AI_PLATFORM_API_KEY
    base_url = config.LLM_BASE_URL  # https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
    images_url = f"{base_url}/images/generations"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                images_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json={
                    "model": IMAGE_MODEL,
                    "prompt": prompt,
                    "n": 1,
                    "quality": "medium",
                    "size": "auto",
                },
            )

        if resp.status_code != 200:
            body = resp.text[:300]
            await log_event(session_id, "image_gen_error", {"status": resp.status_code, "body": body})
            return {"ok": False, "error": f"API error {resp.status_code}: {body}"}

        data = resp.json()
        # gpt-image-1 returns data[0].b64_json
        b64 = (data.get("data") or [{}])[0].get("b64_json") or ""
        if not b64:
            return {"ok": False, "error": "API returned no image data"}

        # Increment counter
        _gen_count[session_id] = count + 1
        remaining = MAX_GENERATIONS - _gen_count[session_id]

        await log_event(session_id, "image_gen_success", {
            "format_id": format_id,
            "count": _gen_count[session_id],
            "remaining": remaining,
        })

        return {
            "ok": True,
            "imageB64": b64,
            "formatId": format_id,
            "width": fmt["width"],
            "height": fmt["height"],
            "remaining": remaining,
            **provenance,
        }

    except httpx.TimeoutException:
        return {"ok": False, "error": "Request timed out (120s) — hãy thử lại"}
    except Exception as e:
        await log_event(session_id, "image_gen_exception", {"error": str(e)})
        return {"ok": False, "error": str(e)}


def get_remaining(session_id: str) -> int:
    """Return how many generations are left for this session."""
    return max(0, MAX_GENERATIONS - _gen_count.get(session_id, 0))
