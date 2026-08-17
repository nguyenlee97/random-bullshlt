"""Fail the release gate until every v2 case has real human sign-off."""
from __future__ import annotations

import json
from pathlib import Path


STATUS = Path(__file__).resolve().parent / "v2_review_status.json"


def main() -> None:
    data = json.loads(STATUS.read_text("utf-8"))
    cases = data.get("cases", [])
    expected = {f"brief_{number:03d}" for number in range(41, 81)}
    actual = {case.get("id") for case in cases}
    problems = []
    if actual != expected:
        problems.append(f"case IDs differ: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")
    for case in cases:
        if case.get("status") not in {"approved", "edited"}:
            problems.append(f"{case.get('id')}: status={case.get('status', 'missing')}")
        if not str(case.get("reviewer") or "").strip():
            problems.append(f"{case.get('id')}: reviewer missing")
        if not str(case.get("reviewed_at") or "").strip():
            problems.append(f"{case.get('id')}: reviewed_at missing")
    if problems:
        print("V2 HUMAN REVIEW: PENDING")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print("V2 HUMAN REVIEW: PASS (40/40 signed off)")


if __name__ == "__main__":
    main()
