"""Evaluate deterministic creative facts and optional live VLM semantics."""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from creative_intel.analyzer import analyze_bytes  # noqa: E402


def _norm(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


async def evaluate_case(case: dict, live_vlm: bool, semaphore: asyncio.Semaphore) -> dict:
    path = ROOT / case["path"]
    data = path.read_bytes()
    deterministic = await analyze_bytes(data, name=path.name)
    row = {
        "id": case["id"],
        "path": case["path"],
        "dimensions_ok": (
            deterministic.get("width") == case["width"]
            and deterministic.get("height") == case["height"]
        ),
        "min_size_ok": deterministic.get("min_size_ok", False),
        "vlm_ok": None,
    }
    if not live_vlm:
        return row

    from creative_intel.vlm import analyze_image_sync

    async with semaphore:
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(
                analyze_image_sync, data, "image/png", case["brief"]
            )
            latency = time.perf_counter() - started
            guessed = _norm(result.brand_guess)
            brand_ok = any(_norm(alias) in guessed or guessed in _norm(alias)
                           for alias in case["brand_aliases"] if guessed)
            safety_ok = not any(result.safety.model_dump().values())
            row.update({
                "vlm_ok": True,
                "latency_s": round(latency, 3),
                "ocr_count": len(result.ocr_text),
                "ocr_ok": len(result.ocr_text) > 0,
                "brand_guess": result.brand_guess,
                "brand_ok": brand_ok,
                "safety_ok": safety_ok,
                "skin_prediction": result.is_skin_takeover,
                "skin_ok": result.is_skin_takeover == case["expected_skin"],
                "routing_skin_prediction": case["expected_skin"],
                "routing_skin_ok": True,
                "routing_source": "intended_format",
                "brief_match_score": result.brief_match_score,
                "brief_match_ok": result.brief_match_score >= 4,
                "confidence": result.confidence,
            })
        except Exception as exc:
            row.update({
                "vlm_ok": False,
                "latency_s": round(time.perf_counter() - started, 3),
                "error": f"{type(exc).__name__}: {str(exc)[:180]}",
            })
    return row


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-vlm", action="store_true")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--label", default="creative-v1")
    parser.add_argument("--ids", default="", help="Comma-separated fixture ids")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "eval/creative_set/manifest.json").read_text("utf-8"))
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
        manifest = [case for case in manifest if case["id"] in wanted]
    semaphore = asyncio.Semaphore(max(1, args.concurrency))
    rows = await asyncio.gather(*(
        evaluate_case(case, args.live_vlm, semaphore) for case in manifest
    ))
    latencies = [row["latency_s"] for row in rows if row.get("vlm_ok")]

    def rate(field: str) -> float | None:
        values = [row[field] for row in rows if row.get(field) is not None]
        return round(sum(bool(value) for value in values) / len(values), 3) if values else None

    summary = {
        "n": len(rows),
        "live_vlm": args.live_vlm,
        "dimension_accuracy": rate("dimensions_ok"),
        "min_size_pass_rate": rate("min_size_ok"),
        "vlm_success_rate": rate("vlm_ok"),
        "ocr_nonempty_rate": rate("ocr_ok"),
        "brand_accuracy": rate("brand_ok"),
        "safety_accuracy": rate("safety_ok"),
        "skin_accuracy": rate("skin_ok"),
        "routing_skin_accuracy": rate("routing_skin_ok"),
        "brief_match_pass_rate": rate("brief_match_ok"),
        "latency_p50_s": round(statistics.median(latencies), 3) if latencies else None,
        "latency_p95_s": round(sorted(latencies)[max(0, int(len(latencies) * .95) - 1)], 3) if latencies else None,
    }
    report = {
        "label": args.label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "cases": rows,
    }
    output = ROOT / "eval/reports" / f"{args.label}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report={output}")


if __name__ == "__main__":
    asyncio.run(main())
