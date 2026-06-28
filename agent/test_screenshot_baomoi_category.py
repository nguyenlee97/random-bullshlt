"""
Test BaoMoi and ZNews category pages specifically.
Run from the agent/ directory: python test_screenshot_baomoi_category.py
"""
import asyncio, sys, os, base64

if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))
from handlers.screenshot import handle_screenshot

def save(name, b64_data, ext):
    path = os.path.join(os.path.dirname(__file__), f"test_{name}.{ext}")
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return path

async def test(label, url, zone_ids):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  URL:   {url}")
    print(f"  Zones: {zone_ids}")
    print(f"{'='*60}")
    r = await handle_screenshot(url, "test", zone_ids=zone_ids)
    if not r["ok"]:
        print(f"  FAILED: {r['error']}")
        return
    print(f"  OK — Full image: {r['width']}x{r['height']}px, {r['zone_count']} zones found")
    slug = label.lower().replace(" ", "_").replace("/", "_")
    p = save(f"{slug}_full", r["full_b64"], "jpg")
    print(f"  Full page saved: {p}")
    for z in r["zones"]:
        p2 = save(f"{slug}_{z['id']}", z["crop_b64"], "png")
        bbox = z['bbox']
        print(f"  Zone [{z['color']}] {z['label']} ({z['id']}) "
              f"@ ({int(bbox['x'])},{int(bbox['y'])}) {int(bbox['width'])}x{int(bbox['height'])}px")
        print(f"         -> {p2}")
    if r["zone_count"] == 0:
        print("  WARNING: No zones were identified in the DOM.")

async def main():
    # ── BaoMoi: Background + StickyLeft + StickyRight ─────────────────────────
    await test(
        "BaoMoi Background+Sticky",
        "https://baomoi-stg.pawgrammers.io.vn/",
        ["BaoMoi_Background", "BaoMoi_StickyLeft", "BaoMoi_StickyRight"],
    )

    # ── BaoMoi: Box1 + Box2 (banners) ─────────────────────────────────────────
    await test(
        "BaoMoi Boxes",
        "https://baomoi-stg.pawgrammers.io.vn/",
        ["BaoMoi_Box1", "BaoMoi_Box2"],
    )

    # ── ZNews TheThao category page ────────────────────────────────────────────
    await test(
        "ZNews TheThao category",
        "https://znews-stg.pawgrammers.io.vn/the-thao.html",
        ["Znews_TheThao_SidebarBox", "Znews_TheThao_Background",
         "Znews_TheThao_SideLeft", "Znews_TheThao_SideRight"],
    )

    # ── ZNews KinhDoanh category page ─────────────────────────────────────────
    await test(
        "ZNews KinhDoanh category",
        "https://znews-stg.pawgrammers.io.vn/kinh-doanh.html",
        ["Znews_KinhDoanh_SidebarBox", "Znews_KinhDoanh_Background",
         "Znews_KinhDoanh_SideLeft", "Znews_KinhDoanh_SideRight"],
    )


if __name__ == "__main__":
    asyncio.run(main())
