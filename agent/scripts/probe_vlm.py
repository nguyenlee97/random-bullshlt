"""
Find a vision-capable model on GreenNode MaaS (Phase 3).

Sends a tiny generated test image (with known text "ZUMA 500K") to each
candidate chat model via OpenAI-style image_url content. A model that echoes
the text back can do OCR → usable as VLM_MODEL.

Run from agent/:  python scripts/probe_vlm.py
"""
import asyncio
import base64
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from config import config  # noqa: E402

CANDIDATES = [
    "google/gemma-4-31b-it",      # gemma-4 class is multimodal
    "qwen/qwen3-5-27b",
    "minimax/minimax-m2.5",
    "greennode/idp",              # "intelligent document processing"?
]

EXPECT = "ZUMA 500K"


def make_test_image() -> str:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (400, 200), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 80), EXPECT, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


async def main():
    b64 = make_test_image()
    headers = {"Authorization": f"Bearer {config.AI_PLATFORM_API_KEY}"}
    passed: list[str] = []
    async with httpx.AsyncClient(timeout=60) as client:
        for model in CANDIDATES:
            try:
                r = await client.post(f"{config.LLM_BASE_URL}/chat/completions",
                    headers=headers, json={
                        "model": model, "max_tokens": 200,
                        "messages": [{"role": "user", "content": [
                            {"type": "text", "text": "Đọc chính xác chữ trong ảnh."},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/png;base64,{b64}"}},
                        ]}]})
                if r.status_code != 200:
                    print(f"❌ {model}: HTTP {r.status_code} — {r.text[:100]}")
                    continue
                text = r.json()["choices"][0]["message"].get("content") or ""
                ocr_ok = "ZUMA" in text.upper() and "500" in text
                print(f"{'✅' if ocr_ok else '⚠ '} {model}: {text[:100]!r}"
                      + ("" if ocr_ok else "  (accepted image but OCR wrong)"))
                if ocr_ok:
                    passed.append(model)
            except Exception as e:
                print(f"❌ {model}: {type(e).__name__}: {str(e)[:100]}")

    print()
    if passed:
        print(f"=== {len(passed)} VLM-capable model(s) found ===")
        for m in passed:
            print(f"  • {m}")
        print(f"\nRecommended (first passing):\nVLM_MODEL={passed[0]}")
    else:
        print("No vision model usable — VLM stage stays dormant.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
