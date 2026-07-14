"""Build a human-readable v2 label packet and a non-overwriting sign-off file."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKET = HERE / "V2-HUMAN-REVIEW-PACKET.md"
STATUS = HERE / "v2_review_status.json"


def _labels(values: list[str], catalog: dict[str, str]) -> str:
    if not values:
        return "—"
    return "; ".join(f"{catalog.get(value, 'UNKNOWN')} (`{value}`)" for value in values)


def main() -> None:
    raw_catalog = json.loads((HERE / "catalog_full.json").read_text("utf-8"))
    if isinstance(raw_catalog, dict):
        raw_catalog = raw_catalog.get("data") or raw_catalog.get("attributes") or []
    catalog = {
        item["_id"]: item.get("fullLabel") or item.get("name") or item["_id"]
        for item in raw_catalog
    }
    cases = [
        json.loads(path.read_text("utf-8"))
        for path in sorted(HERE.glob("brief_*.json"))
        if 41 <= int(path.stem.split("_")[1]) <= 80
    ]

    lines = [
        "# V2 Golden-Set Human Review Packet",
        "",
        "> Scope: briefs 041–080. Review labels from the advertiser brief and full 310-segment catalog only. Do not inspect current agent recommendations before deciding.",
        "",
        "Reviewer: ____________________  Date: ____________________",
        "",
        "For every case, choose `approved`, `edited`, or `rejected` in `v2_review_status.json`. If edited, change the source brief JSON, explain why, rerun `python eval/golden_set/validate.py`, then rebuild this packet. A secondary model may identify candidates and inconsistencies, but a human owns the final status.",
        "",
    ]
    statuses = []
    for case in cases:
        audience = case["labels"]["audience"]
        targeting = case["labels"].get("targeting") or {}
        brief = case["brief"]
        lines.extend([
            f"## {case['id']} — {brief['brand']}",
            "",
            f"- Objective/KPI: `{brief['objective']}` — {brief['kpi']}",
            f"- Budget/dates: {brief['budget']} triệu VND; {brief['startDate']} → {brief['endDate']}",
            f"- Notes: {brief.get('notes') or '—'}",
            f"- Tags: {', '.join(case.get('tags', []))}",
            f"- Must include: {_labels(audience.get('must_include', []), catalog)}",
            f"- Acceptable: {_labels(audience.get('acceptable', []), catalog)}",
            f"- Must exclude: {_labels(audience.get('must_exclude', []), catalog)}",
            f"- Targeting expected: `{json.dumps(targeting.get('expected', {}), ensure_ascii=False)}`",
            f"- Targeting forbidden: `{json.dumps(targeting.get('must_not_set', {}), ensure_ascii=False)}`",
            f"- Labeler rationale: {case['labels'].get('labeler_note') or 'MISSING'}",
            "- Reviewer verdict/comments: ________________________________________________",
            "",
        ])
        statuses.append({
            "id": case["id"],
            "status": "pending",
            "reviewer": "",
            "reviewed_at": "",
            "comment": "",
        })

    PACKET.write_text("\n".join(lines), "utf-8")
    status_existed = STATUS.exists()
    if not status_existed:
        STATUS.write_text(json.dumps({
            "schema_version": 1,
            "instructions": "Set every status to approved or edited after human review. Never use model-only review as sign-off.",
            "cases": statuses,
        }, ensure_ascii=False, indent=2), "utf-8")
    print(f"packet={PACKET}")
    print(f"status={STATUS} ({'preserved' if status_existed else 'created'})")


if __name__ == "__main__":
    main()
