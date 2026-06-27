"""
handlers/screenshot.py — Full-page headless screenshot via Playwright.
Zone-aware: uses Playwright bounding_box() + Pillow to produce per-zone crops
and an annotated full-page image.

Changes vs previous version:
  - Accepts `zone_ids` param to only capture zones the user actually selected
  - Forces sticky side-panel zones visible before querying bounding boxes
  - Clips screenshot height to deepest found zone (not full 8000px page)
  - Falls back to JS getBoundingClientRect for elements hidden via display:none
  - Increases post-scroll wait to 1500ms for async ad API responses

Resource safety: browser.close() is in try/finally — Chromium is ALWAYS killed.
"""
import base64
import io
from datetime import datetime, timezone
from urllib.parse import urlparse

# ── Allowed domains (whitelist) ────────────────────────────────────────────────
ALLOWED_DOMAINS = {
    "znews-stg.pawgrammers.io.vn",
    "baomoi-stg.pawgrammers.io.vn",
    "zingmp3-stg.pawgrammers.io.vn",
}

# ── All possible ad zone DOM IDs per site domain ───────────────────────────────
# zone_id matches `testSiteZone` / `id` field from the DB placements collection.
# These are used when no zone_ids filter is passed.
SITE_ZONES = {
    "znews-stg.pawgrammers.io.vn": [
        ("ZingNews_Masthead",           "Masthead Banner"),
        ("ZingNews_Halfpage",           "Halfpage"),
        ("ZingNews_PrBox_2",            "PR Box 2"),
        ("ZingNews_Masthead_Inline_1",  "Inline Banner"),
    ],
    "baomoi-stg.pawgrammers.io.vn": [
        ("BaoMoi_Background",   "Background / Skin"),
        ("BaoMoi_Masthead",     "Masthead Banner"),
        ("BaoMoi_StickyLeft",   "Sticky Left"),
        ("BaoMoi_StickyRight",  "Sticky Right"),
        ("BaoMoi_Box1",         "Sidebar Box 1"),
        ("BaoMoi_Box2",         "Sidebar Box 2"),
    ],
    "zingmp3-stg.pawgrammers.io.vn": [
        ("ZingMP3_Masthead", "Masthead Banner"),
    ],
}

# Friendly label lookup (id → label) for all sites combined
_ALL_ZONE_LABELS: dict[str, str] = {
    zone_id: label
    for zones in SITE_ZONES.values()
    for zone_id, label in zones
}

# Sticky zones that need the CSS "visible" class added before bbox query
_STICKY_ZONE_IDS = {
    "BaoMoi_StickyLeft",
    "BaoMoi_StickyRight",
}

# Highlight colours per zone index (RGB tuples)
ZONE_COLORS = [
    (239,  68,  68),
    ( 59, 130, 246),
    ( 34, 197,  94),
    (234, 179,   8),
    (168,  85, 247),
    (249, 115,  22),
]

# Padding around each zone crop (pixels)
CROP_PADDING = 250

# Hard cap on full-page scroll height (safety)
MAX_HEIGHT_PX = 8000

# Desktop viewport width
VIEWPORT_WIDTH = 1440


def _is_allowed(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        return host in ALLOWED_DOMAINS
    except Exception:
        return False


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _b64(img_bytes: bytes) -> str:
    return base64.b64encode(img_bytes).decode("utf-8")


def _annotate_and_crop(screenshot_bytes: bytes, found_zones: list, clip_h: int) -> tuple:
    from PIL import Image, ImageDraw

    full_img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
    annotated = full_img.copy()
    draw = ImageDraw.Draw(annotated)
    img_w, img_h = full_img.size

    zone_results = []

    for z in found_zones:
        bbox = z["bbox"]
        color = z["color"]
        x, y, w, h = int(bbox["x"]), int(bbox["y"]), int(bbox["width"]), int(bbox["height"])

        # Skip zones that lie entirely outside the screenshot bounds
        if y >= img_h or x >= img_w:
            continue

        # Draw highlight box on annotated image
        for i in range(4):
            draw.rectangle(
                [x - i, y - i, x + w + i, y + h + i],
                outline=color + (220,),
            )

        # Label badge above box
        label_text = z["label"]
        lx, ly = max(0, x), max(0, y - 28)
        draw.rectangle([lx, ly, lx + len(label_text) * 8 + 16, ly + 24], fill=color + (230,))
        try:
            draw.text((lx + 8, ly + 4), label_text, fill=(255, 255, 255, 255))
        except Exception:
            pass

        # Crop around zone with padding — fully clamped to image bounds
        cx1 = max(0, x - CROP_PADDING)
        cy1 = max(0, y - CROP_PADDING)
        cx2 = min(img_w, x + w + CROP_PADDING)
        cy2 = min(img_h, y + h + CROP_PADDING)

        # Safety: skip if crop rectangle is degenerate
        if cx2 <= cx1 or cy2 <= cy1:
            continue

        crop = full_img.crop((cx1, cy1, cx2, cy2))
        cd = ImageDraw.Draw(crop)
        zic = (x - cx1, y - cy1, x - cx1 + w, y - cy1 + h)
        for i in range(3):
            cd.rectangle(
                [zic[0]-i, zic[1]-i, zic[2]+i, zic[3]+i],
                outline=color + (255,),
            )

        crop_buf = io.BytesIO()
        crop.convert("RGB").save(crop_buf, format="PNG", optimize=True)

        zone_results.append({
            "id":       z["id"],
            "label":    z["label"],
            "crop_b64": _b64(crop_buf.getvalue()),
            "bbox":     {"x": x, "y": y, "width": w, "height": h},
            "color":    "#{:02x}{:02x}{:02x}".format(*color),
        })

    ann_buf = io.BytesIO()
    annotated.convert("RGB").save(ann_buf, format="JPEG", quality=82, optimize=True)
    return ann_buf.getvalue(), zone_results


async def handle_screenshot(url: str, session_id: str, zone_ids: list[str] | None = None) -> dict:
    """
    Capture a full-page screenshot + per-zone crops.

    Args:
        url       — staging site URL (must be in ALLOWED_DOMAINS)
        session_id — current session (for logging)
        zone_ids  — list of DOM element IDs to capture (from selectedZoneIds).
                    If None or empty, falls back to all known zones for this site.

    Returns:
        { ok, full_b64, zones, zone_count, width, height, captured_at, url }
    or:
        { ok: False, error }
    """
    if not url:
        return {"ok": False, "error": "url is required"}

    if not _is_allowed(url):
        return {
            "ok": False,
            "error": f"Domain not in whitelist. Allowed: {', '.join(sorted(ALLOWED_DOMAINS))}",
        }

    host = _host(url)
    all_site_zones = SITE_ZONES.get(host, [])

    # Filter to only the zone IDs the user selected (if provided)
    if zone_ids:
        requested = set(zone_ids)
        # Zones from SITE_ZONES that the user selected
        zone_defs = [(zid, lbl) for zid, lbl in all_site_zones if zid in requested]
        # Also include any requested IDs not in our SITE_ZONES catalog (unknown zones)
        known_ids = {zid for zid, _ in all_site_zones}
        for zid in zone_ids:
            if zid not in known_ids:
                zone_defs.append((zid, _ALL_ZONE_LABELS.get(zid, zid)))
    else:
        zone_defs = all_site_zones

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
        }

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                ],
            )

            screenshot_bytes = None
            dims = {"width": VIEWPORT_WIDTH, "height": 0}
            raw_zones = []
            clip_h = MAX_HEIGHT_PX

            try:
                page = await browser.new_page(
                    viewport={"width": VIEWPORT_WIDTH, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                )

                # Navigate
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                except Exception:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)

                # ── Scroll top → bottom to trigger lazy-loaded ad zones ────────
                scroll_height = await page.evaluate("document.body.scrollHeight")
                scroll_height = min(scroll_height, MAX_HEIGHT_PX)

                current = 0
                while current < scroll_height:
                    await page.evaluate(f"window.scrollTo(0, {current})")
                    await page.wait_for_timeout(200)
                    current += 600

                # Back to top, then wait longer for async ad API responses (1500ms)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(1500)

                # ── Force sticky elements visible before bbox query ─────────────
                sticky_ids = [zid for zid, _ in zone_defs if zid in _STICKY_ZONE_IDS]
                if sticky_ids:
                    ids_js = ", ".join(f'"{zid}"' for zid in sticky_ids)
                    await page.evaluate(f"""
                        [{ids_js}].forEach(id => {{
                            const el = document.getElementById(id);
                            if (el) el.classList.add('visible');
                        }});
                    """)
                    await page.wait_for_timeout(300)

                # ── Collect bounding boxes ─────────────────────────────────────
                for idx, (zone_id, zone_label) in enumerate(zone_defs):
                    bbox = None
                    try:
                        el = page.locator(f"#{zone_id}")
                        if await el.count() > 0:
                            bbox = await el.first.bounding_box()
                    except Exception:
                        pass

                    # Fallback for hidden elements (display:none, collapsed)
                    if bbox is None or bbox.get("width", 0) < 2 or bbox.get("height", 0) < 2:
                        try:
                            rect = await page.evaluate(f"""() => {{
                                const el = document.getElementById('{zone_id}');
                                if (!el) return null;
                                const r = el.getBoundingClientRect();
                                // For hidden elements, use offsetTop/offsetHeight
                                return {{
                                    x: el.offsetLeft || r.left,
                                    y: el.offsetTop  || r.top,
                                    width:  el.offsetWidth  || r.width,
                                    height: el.offsetHeight || r.height,
                                }};
                            }}""")
                            if rect and rect.get("width", 0) > 2 and rect.get("height", 0) > 2:
                                bbox = rect
                        except Exception:
                            pass

                    if bbox is None or bbox.get("width", 0) < 2 or bbox.get("height", 0) < 2:
                        continue

                    raw_zones.append({
                        "id":    zone_id,
                        "label": zone_label,
                        "bbox":  bbox,
                        "color": ZONE_COLORS[idx % len(ZONE_COLORS)],
                    })

                # ── Clip screenshot: deepest found zone + 400px padding ─────────
                # This avoids capturing many empty pages below the last ad zone.
                # Scroll still goes to full height above to trigger lazy-load.
                if raw_zones:
                    deepest = max(z["bbox"]["y"] + z["bbox"]["height"] for z in raw_zones)
                    # Ensure clip_h is at least the deepest zone bottom + padding
                    clip_h = min(int(deepest) + 400, MAX_HEIGHT_PX)
                else:
                    # No zones found — capture at least one viewport
                    clip_h = min(1800, scroll_height)

                # Playwright clip option — height clamped to actual page
                screenshot_bytes = await page.screenshot(
                    clip={"x": 0, "y": 0, "width": VIEWPORT_WIDTH, "height": clip_h},
                    type="png",
                )

                dims = {"width": VIEWPORT_WIDTH, "height": clip_h}

            finally:
                await browser.close()

        if screenshot_bytes is None:
            return {"ok": False, "error": "Screenshot produced no data"}

        try:
            annotated_bytes, zone_results = _annotate_and_crop(screenshot_bytes, raw_zones, clip_h)
        except ImportError:
            annotated_bytes = screenshot_bytes
            zone_results = []

        return {
            "ok":          True,
            "full_b64":    _b64(annotated_bytes),
            "zones":       zone_results,
            "zone_count":  len(zone_results),
            "width":       dims["width"],
            "height":      dims["height"],
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "url":         url,
        }

    except Exception as e:
        return {"ok": False, "error": f"Screenshot failed: {str(e)}"}
