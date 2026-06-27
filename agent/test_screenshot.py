"""
Test the zone-aware screenshot handler.
Run from the agent/ directory: python test_screenshot.py
Outputs:
  test_screenshot_full.jpg      - annotated full page (zone boxes drawn)
  test_screenshot_zone_N.png    - individual crop per zone
"""
import asyncio, sys, os, base64

if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(__file__))
from handlers.screenshot import handle_screenshot

async def main():
    print("=== Zone-aware screenshot test ===\n")

    # 1. Whitelist rejection
    print("1) Whitelist check (google.com)...")
    r = await handle_screenshot("https://google.com", "test")
    assert r["ok"] is False
    print(f"   Correctly rejected.\n")

    # 2. ZNews capture
    url = "https://znews-stg.pawgrammers.io.vn"
    print(f"2) Capturing: {url}")
    r = await handle_screenshot(url, "test")

    if not r["ok"]:
        print(f"   FAILED: {r['error']}")
        sys.exit(1)

    print(f"   Success! Found {r['zone_count']} zones.")
    print(f"   Full image: {r['width']}x{r['height']}px")

    # Save annotated full page
    full_path = os.path.join(os.path.dirname(__file__), "test_screenshot_full.jpg")
    with open(full_path, "wb") as f:
        f.write(base64.b64decode(r["full_b64"]))
    print(f"   Saved annotated full page: {full_path}")

    # Save individual zone crops
    for i, zone in enumerate(r["zones"]):
        crop_path = os.path.join(os.path.dirname(__file__), f"test_screenshot_zone_{i+1}_{zone['id']}.png")
        with open(crop_path, "wb") as f:
            f.write(base64.b64decode(zone["crop_b64"]))
        bbox = zone['bbox']
        print(f"   Zone {i+1}: [{zone['color']}] {zone['label']} ({zone['id']}) "
              f"@ ({int(bbox['x'])},{int(bbox['y'])}) {int(bbox['width'])}x{int(bbox['height'])}px")
        print(f"           -> {crop_path}")

    print(f"\n   Open the .jpg and .png files to verify zones are correctly highlighted.")


if __name__ == "__main__":
    asyncio.run(main())
