#!/usr/bin/env python3
"""
Image Generation API Test Script
Tests all 9 ad format types against the live API and saves full (uncropped) images.
Results are saved to ./image_test_results/ with an HTML report.

Usage:
    pip install httpx pillow
    python test_image_gen.py
"""

import asyncio
import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx

# ─── Config ───────────────────────────────────────────────────────────────────
API_URL    = "https://agent-api.pawgrammers.io.vn/api/agent/generate-image"
SESSION_ID = f"test_sess_{int(time.time())}_imgtest"
OUTPUT_DIR = Path("image_test_results")

HEADERS = {
    "Content-Type": "application/json",
    "sec-ch-ua-platform": '"Windows"',
    "Referer": "https://agent.pawgrammers.io.vn/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": (
        '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"'
    ),
    "sec-ch-ua-mobile": "?0",
}

# Shared test brief (same as the example in the request)
BRIEF = {
    "brand": "Tiki",
    "objective": "awareness",
    "kpi": "CTR",
    "budget": 40,
    "startDate": "2026-07-20",
    "endDate": "2026-08-20",
    "notes": "Audience: 20-45 tuổi, thích mua sắm online và deals",
}

# All 9 ad format IDs with expected dimensions
FORMAT_SPECS = [
    {
        "format_id": "zmp3-top-banner",
        "label": "ZingMP3 Top Banner",
        "width": 2032,
        "height": 528,
        "ratio": "3.85:1 ultra-wide",
    },
    {
        "format_id": "znews-Background",
        "label": "ZingNews Background Desktop",
        "width": 1504,
        "height": 704,
        "ratio": "2.14:1 wide",
    },
    {
        "format_id": "znews-middle-banner",
        "label": "ZingNews Middle Banner",
        "width": 2048,
        "height": 512,
        "ratio": "4:1 ultra-wide",
    },
    {
        "format_id": "znews-side-banner",
        "label": "ZingNews Side Banner (Skyscraper)",
        "width": 736,
        "height": 1456,
        "ratio": "1:2 vertical",
    },
    {
        "format_id": "znews-top-banner",
        "label": "ZingNews Top Banner",
        "width": 2224,
        "height": 480,
        "ratio": "4.63:1 ultra-wide",
    },
    {
        "format_id": "zuma-baomoi-masthead",
        "label": "BaoMoi Masthead",
        "width": 1160,
        "height": 280,
        "ratio": "4.14:1 wide",
    },
    {
        "format_id": "zuma-box",
        "label": "Display Box",
        "width": 300,
        "height": 250,
        "ratio": "1.2:1 near-square",
    },
    {
        "format_id": "zuma-Left",
        "label": "Side Slider Left",
        "width": 465,
        "height": 1200,
        "ratio": "1:2.58 vertical",
    },
    {
        "format_id": "zuma-Right",
        "label": "Side Slider Right",
        "width": 465,
        "height": 1200,
        "ratio": "1:2.58 vertical",
    },
]

# ─── Result store ─────────────────────────────────────────────────────────────
results: list[dict] = []


async def test_format(client: httpx.AsyncClient, spec: dict, idx: int) -> dict:
    """Call the API for one format and return a result dict."""
    format_id = spec["format_id"]
    label     = spec["label"]

    print(f"\n[{idx}/9] Testing '{format_id}' ({label}) ...", flush=True)
    t0 = time.time()

    payload = {
        "session_id": SESSION_ID,
        "brief": BRIEF,
        "format_id": format_id,
    }

    try:
        resp = await client.post(API_URL, headers=HEADERS, json=payload, timeout=180.0)
        elapsed = round(time.time() - t0, 1)

        if resp.status_code != 200:
            print(f"  ✗ HTTP {resp.status_code} — {resp.text[:200]}", flush=True)
            return {
                **spec,
                "ok": False,
                "elapsed": elapsed,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "actual_size": None,
                "image_file": None,
            }

        data = resp.json()

        if not data.get("ok"):
            err = data.get("error", "Unknown error")
            print(f"  ✗ API error: {err}", flush=True)
            return {
                **spec,
                "ok": False,
                "elapsed": elapsed,
                "error": err,
                "actual_size": None,
                "image_file": None,
            }

        # Decode and save image
        b64: str = data.get("imageB64", "")
        if not b64:
            return {
                **spec,
                "ok": False,
                "elapsed": elapsed,
                "error": "API returned ok=True but no imageB64",
                "actual_size": None,
                "image_file": None,
            }

        img_bytes  = base64.b64decode(b64)
        img_path   = OUTPUT_DIR / f"{idx:02d}_{format_id}.png"
        img_path.write_bytes(img_bytes)

        # Get actual image dimensions via Pillow (optional)
        actual_size = None
        try:
            from PIL import Image as PILImage
            import io
            img = PILImage.open(io.BytesIO(img_bytes))
            actual_size = f"{img.width}×{img.height}"
            print(
                f"  ✓ Saved {img_path.name}  |  "
                f"Expected: {spec['width']}×{spec['height']}  |  "
                f"Actual: {actual_size}  |  {elapsed}s",
                flush=True,
            )
        except ImportError:
            print(
                f"  ✓ Saved {img_path.name}  |  "
                f"Expected: {spec['width']}×{spec['height']}  |  "
                f"(install Pillow to see actual dimensions)  |  {elapsed}s",
                flush=True,
            )

        return {
            **spec,
            "ok": True,
            "elapsed": elapsed,
            "error": None,
            "actual_size": actual_size,
            "image_file": str(img_path),
            "remaining": data.get("remaining"),
        }

    except httpx.TimeoutException:
        elapsed = round(time.time() - t0, 1)
        print(f"  ✗ TIMEOUT after {elapsed}s", flush=True)
        return {
            **spec,
            "ok": False,
            "elapsed": elapsed,
            "error": f"Timeout after {elapsed}s",
            "actual_size": None,
            "image_file": None,
        }
    except Exception as exc:
        elapsed = round(time.time() - t0, 1)
        print(f"  ✗ Exception: {exc}", flush=True)
        return {
            **spec,
            "ok": False,
            "elapsed": elapsed,
            "error": str(exc),
            "actual_size": None,
            "image_file": None,
        }


def generate_html_report(results: list[dict]) -> str:
    """Build a standalone HTML file showing all test results and full images."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total   = len(results)
    passed  = sum(1 for r in results if r["ok"])
    failed  = total - passed

    rows_html = ""
    for r in results:
        status_icon  = "✅" if r["ok"] else "❌"
        status_class = "pass" if r["ok"] else "fail"
        img_block    = ""

        if r["ok"] and r.get("image_file"):
            # Embed the image as base64 so the HTML is self-contained
            img_bytes_b64 = base64.b64encode(Path(r["image_file"]).read_bytes()).decode()
            img_block = (
                f'<img src="data:image/png;base64,{img_bytes_b64}" '
                f'style="width:100%;height:auto;border:1px solid #444;border-radius:4px;" '
                f'alt="{r["label"]}" />'
            )
        elif not r["ok"]:
            img_block = f'<div class="error-box">❌ {r["error"]}</div>'

        size_match = ""
        if r["ok"] and r.get("actual_size"):
            expected = f"{r['width']}×{r['height']}"
            actual   = r["actual_size"]
            match    = "✅ Match" if actual == expected else f"⚠️ Mismatch (expected {expected})"
            size_match = f"<br><small>{match}</small>"

        rows_html += f"""
        <div class="card {status_class}">
            <div class="card-header">
                <span class="status-icon">{status_icon}</span>
                <span class="format-id">{r['format_id']}</span>
                <span class="label">{r['label']}</span>
                <span class="meta">
                    {r['ratio']} &nbsp;|&nbsp;
                    Target: {r['width']}×{r['height']}
                    {size_match}
                    &nbsp;|&nbsp; ⏱ {r['elapsed']}s
                </span>
            </div>
            <div class="card-body">
                {img_block}
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Image Gen Test Report — {now}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0d0d0d; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 6px; color: #fff; }}
    .subtitle {{ color: #888; font-size: 0.9rem; margin-bottom: 20px; }}
    .summary {{ display: flex; gap: 16px; margin-bottom: 28px; }}
    .badge {{ padding: 8px 18px; border-radius: 20px; font-weight: 700; font-size: 0.9rem; }}
    .badge.total  {{ background: #2a2a2a; border: 1px solid #444; }}
    .badge.passed {{ background: #0d3d0d; border: 1px solid #2a7a2a; color: #6fcf6f; }}
    .badge.failed {{ background: #3d0d0d; border: 1px solid #7a2a2a; color: #cf6f6f; }}
    .card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px;
             margin-bottom: 28px; overflow: hidden; }}
    .card.pass {{ border-color: #1e4a1e; }}
    .card.fail {{ border-color: #4a1e1e; }}
    .card-header {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
                    padding: 14px 18px; background: #222; border-bottom: 1px solid #333; }}
    .status-icon {{ font-size: 1.2rem; }}
    .format-id {{ font-family: monospace; font-size: 0.95rem; color: #7dd3fc; font-weight: 700; }}
    .label {{ color: #ccc; font-size: 0.9rem; }}
    .meta {{ margin-left: auto; color: #888; font-size: 0.82rem; text-align: right; }}
    .card-body {{ padding: 14px 18px; }}
    .error-box {{ background: #2a0000; border: 1px solid #7a2a2a; border-radius: 6px;
                  padding: 12px 16px; color: #ff8888; font-family: monospace; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <h1>🖼️ Image Generation API — Test Report</h1>
  <div class="subtitle">Generated: {now} &nbsp;|&nbsp; Session: {SESSION_ID}</div>
  <div class="summary">
    <div class="badge total">📊 Total: {total}</div>
    <div class="badge passed">✅ Passed: {passed}</div>
    <div class="badge failed">❌ Failed: {failed}</div>
  </div>
  {rows_html}
</body>
</html>"""


async def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Image Gen Test — Session: {SESSION_ID}")
    print(f"API: {API_URL}")
    print(f"Output dir: {OUTPUT_DIR.resolve()}")
    print(f"Testing {len(FORMAT_SPECS)} formats sequentially (API has 10/session quota)...\n")

    # Run sequentially to avoid burning the 10/session quota all at once
    # and to get cleaner logs
    async with httpx.AsyncClient() as client:
        for idx, spec in enumerate(FORMAT_SPECS, start=1):
            result = await test_format(client, spec, idx)
            results.append(result)

    # Save JSON summary
    json_path = OUTPUT_DIR / "results.json"
    json_path.write_text(
        json.dumps(
            [
                {k: v for k, v in r.items() if k != "imageB64"}
                for r in results
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Build HTML report (self-contained with embedded images)
    html = generate_html_report(results)
    html_path = OUTPUT_DIR / "report.html"
    html_path.write_text(html, encoding="utf-8")

    # Print summary
    passed = sum(1 for r in results if r["ok"])
    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{len(results)} passed")
    print(f"  JSON:    {json_path.resolve()}")
    print(f"  HTML:    {html_path.resolve()}")
    print(f"  Images:  {OUTPUT_DIR.resolve()}/")
    print(f"{'='*60}")

    if passed < len(results):
        print("\nFailed formats:")
        for r in results:
            if not r["ok"]:
                print(f"  - {r['format_id']}: {r['error']}")

    print("\nOpen image_test_results/report.html in your browser to see all full images.")


if __name__ == "__main__":
    asyncio.run(main())
