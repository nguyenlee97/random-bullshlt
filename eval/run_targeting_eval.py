"""Score targeting auto-pick against the labeled v2 golden-set cases.

The runner uses the real HTTP chat path so it also verifies the LangGraph tool
contract consumed by the frontend. Only dimensions explicitly labeled in a
case are graded; unspecified dimensions are neither rewarded nor penalized.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent
GOLDEN = ROOT / "golden_set"
REPORTS = ROOT / "reports"
TRIGGER = "Hãy tự động chọn targeting phù hợp nhất cho chiến dịch này"


def _allowed_values() -> dict[str, set[str]]:
    options = json.loads((GOLDEN / "targeting_options.json").read_text("utf-8"))
    allowed: dict[str, set[str]] = {}
    for dimension, values in options.items():
        if isinstance(values, dict):
            allowed[dimension] = {
                value for group in values.values() for value in group
            }
        else:
            allowed[dimension] = set(values)
    return allowed


def _extract_targeting(response: dict) -> dict[str, list[str]]:
    for block in response.get("blocks", []):
        if block.get("type") != "table":
            continue
        if "targeting" not in str(block.get("title", "")).casefold():
            continue
        result: dict[str, list[str]] = {}
        for row in block.get("rows", []):
            if not isinstance(row, list) or len(row) < 2:
                continue
            field = str(row[0]).strip()
            picks = [value.strip() for value in str(row[1]).split(",") if value.strip()]
            if field and picks:
                result[field] = picks
        return result
    return {}


async def _one(
    client: httpx.AsyncClient,
    case_path: Path,
    agent_url: str,
    headers: dict[str, str],
    allowed: dict[str, set[str]],
) -> dict:
    case = json.loads(case_path.read_text("utf-8"))
    session_id = f"target_eval_{uuid.uuid4().hex[:12]}"
    await client.post(
        f"{agent_url}/api/agent/commit-workspace",
        headers=headers,
        json={"session_id": session_id, "field": "brief", "value": case["brief"]},
    )

    started = time.perf_counter()
    response = await client.post(
        f"{agent_url}/api/agent/chat",
        headers=headers,
        json={"session_id": session_id, "step": 1, "message": TRIGGER},
    )
    response.raise_for_status()
    body = response.json()
    actual = _extract_targeting(body)
    labels = case["labels"]["targeting"]
    expected = labels.get("expected", {})
    forbidden = labels.get("must_not_set", {})

    expected_total = sum(len(values) for values in expected.values())
    expected_hits = sum(
        len(set(values) & set(actual.get(field, [])))
        for field, values in expected.items()
    )
    forbidden_hits = {
        field: sorted(set(values) & set(actual.get(field, [])))
        for field, values in forbidden.items()
    }
    forbidden_hits = {field: values for field, values in forbidden_hits.items() if values}
    catalog_violations = {
        field: sorted(set(values) - allowed.get(field, set()))
        for field, values in actual.items()
        if field not in allowed or set(values) - allowed.get(field, set())
    }
    dimension_exact = {
        field: set(actual.get(field, [])) == set(values)
        for field, values in expected.items()
    }
    return {
        "id": case["id"],
        "session_id": session_id,
        "tool": body.get("meta", {}).get("tool"),
        "actual": actual,
        "expected": expected,
        "forbidden": forbidden,
        "expected_value_recall": expected_hits / expected_total if expected_total else None,
        "expected_hits": expected_hits,
        "expected_total": expected_total,
        "dimension_exact": dimension_exact,
        "forbidden_hits": forbidden_hits,
        "catalog_violations": catalog_violations,
        "latency_s": round(time.perf_counter() - started, 3),
    }


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[int((len(ordered) - 1) * ratio)], 3)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", default="http://localhost:8080")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--label", default="targeting-v1")
    parser.add_argument("--case", default="", help="single case id, e.g. brief_067")
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args()

    case_paths = []
    for path in sorted(GOLDEN.glob("brief_*.json")):
        case = json.loads(path.read_text("utf-8"))
        if "targeting_labeled" in case.get("tags", []):
            case_paths.append(path)
    if args.case:
        case_paths = [path for path in case_paths if path.stem == args.case]
    if not case_paths:
        raise SystemExit("no targeting-labeled cases matched")
    allowed = _allowed_values()
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    semaphore = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(timeout=120) as client:
        async def guarded(path: Path) -> dict:
            async with semaphore:
                try:
                    result = await _one(client, path, args.agent_url, headers, allowed)
                except Exception as exc:
                    result = {"id": path.stem, "error": f"{type(exc).__name__}: {exc}"}
                print(
                    f"  {result['id']}: recall={result.get('expected_value_recall')} "
                    f"forbidden={result.get('forbidden_hits')} error={result.get('error', '')}"
                )
                return result

        results = await asyncio.gather(*(guarded(path) for path in case_paths))

    ok = [result for result in results if "error" not in result]
    recalls = [result["expected_value_recall"] for result in ok]
    dimension_values = [
        exact for result in ok for exact in result["dimension_exact"].values()
    ]
    latencies = [result["latency_s"] for result in ok]
    summary = {
        "n": len(results),
        "errors": len(results) - len(ok),
        "expected_value_recall": round(statistics.mean(recalls), 3) if recalls else None,
        "dimension_exact_rate": round(sum(dimension_values) / len(dimension_values), 3)
        if dimension_values else None,
        "forbidden_violations": sum(
            len(values) for result in ok for values in result["forbidden_hits"].values()
        ),
        "catalog_violations": sum(
            len(values) for result in ok for values in result["catalog_violations"].values()
        ),
        "tool_contract_failures": sum(
            result.get("tool") != "targeting_autopick" for result in ok
        ),
        "p50_latency_s": _percentile(latencies, 0.5),
        "p95_latency_s": _percentile(latencies, 0.95),
    }
    report = {
        "label": args.label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": results,
    }
    REPORTS.mkdir(exist_ok=True)
    output = REPORTS / f"{args.label}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report={output}")

    if args.gate and (
        summary["errors"]
        or (summary["expected_value_recall"] or 0) < 0.8
        or summary["forbidden_violations"]
        or summary["catalog_violations"]
        or summary["tool_contract_failures"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
