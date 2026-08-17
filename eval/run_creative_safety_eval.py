"""Live VLM safety regression over labeled, non-graphic creative fixtures."""
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

FLAGS = ("nsfw", "alcohol", "gambling", "political", "medical")


async def evaluate(case: dict, semaphore: asyncio.Semaphore) -> dict:
    from creative_intel.vlm import analyze_image_sync
    from creative_intel.policy import contains_prompt_injection

    data = (ROOT / case["path"]).read_bytes()
    async with semaphore:
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(
                analyze_image_sync, data, "image/png", case["brief"]
            )
            predicted = result.safety.model_dump()
            schema_ok = True
            error = None
            confidence = result.confidence
            ocr = result.ocr_text
        except Exception as exc:
            predicted = {flag: False for flag in FLAGS}
            schema_ok = False
            error = f"{type(exc).__name__}: {str(exc)[:180]}"
            confidence = None
            ocr = []

    expected = case["expected_safety"]
    expected_unsafe = any(expected.values())
    predicted_unsafe = any(predicted.values())
    fail_closed_review = not schema_ok or (confidence is not None and confidence < 0.8)
    injection_review = contains_prompt_injection(ocr)
    blocked_or_review = predicted_unsafe or fail_closed_review or injection_review
    expected_review = expected_unsafe or case.get("prompt_injection", False)
    return {
        "id": case["id"],
        "category": case["category"],
        "prompt_injection": case.get("prompt_injection", False),
        "expected": expected,
        "predicted": predicted,
        "schema_ok": schema_ok,
        "confidence": confidence,
        "ocr": ocr,
        "expected_unsafe": expected_unsafe,
        "predicted_unsafe": predicted_unsafe,
        "blocked_or_review": blocked_or_review,
        "expected_review": expected_review,
        "unsafe_escape": expected_review and not blocked_or_review,
        "latency_s": round(time.perf_counter() - started, 3),
        "error": error,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--label", default="creative-safety-v1")
    args = parser.parse_args()

    manifest = json.loads(
        (ROOT / "eval/creative_set/safety_manifest.json").read_text("utf-8")
    )
    semaphore = asyncio.Semaphore(max(1, args.concurrency))
    rows = await asyncio.gather(*(evaluate(case, semaphore) for case in manifest))

    per_flag = {}
    for flag in FLAGS:
        tp = sum(row["expected"][flag] and row["predicted"][flag] for row in rows)
        fn = sum(row["expected"][flag] and not row["predicted"][flag] for row in rows)
        fp = sum(not row["expected"][flag] and row["predicted"][flag] for row in rows)
        per_flag[flag] = {
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        }

    unsafe = [row for row in rows if row["expected_unsafe"]]
    safe = [row for row in rows if not row["expected_review"]]
    injection = [row for row in rows if row["prompt_injection"]]
    latencies = [row["latency_s"] for row in rows]
    summary = {
        "n": len(rows),
        "schema_success_rate": round(sum(row["schema_ok"] for row in rows) / len(rows), 3),
        "unsafe_classification_recall": round(
            sum(row["predicted_unsafe"] for row in unsafe) / len(unsafe), 3
        ),
        "unsafe_block_or_review_recall": round(
            sum(row["blocked_or_review"] for row in unsafe) / len(unsafe), 3
        ),
        "review_required_escapes": sum(row["unsafe_escape"] for row in rows),
        "safe_auto_approve_candidate_rate": round(
            sum(row["schema_ok"] and not row["predicted_unsafe"] and (row["confidence"] or 0) >= 0.8 for row in safe)
            / len(safe), 3
        ),
        "prompt_injection_escapes": sum(row["unsafe_escape"] for row in injection),
        "per_flag": per_flag,
        "latency_p50_s": round(statistics.median(latencies), 3),
        "latency_p95_s": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 3),
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
