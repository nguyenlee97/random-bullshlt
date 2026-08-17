"""Apply the human-accepted 041-080 audit and record review ownership.

This script is intentionally tied to LABEL-REVIEW-041-080-20260716.json. It
does not ask a model to relabel anything. It applies only the operations already
present in that review artifact after the project owner has accepted them.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
REVIEW_PATH = HERE / "LABEL-REVIEW-041-080-20260716.json"
STATUS_PATH = HERE / "v2_review_status.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _ops(case: dict) -> list[dict]:
    value = case.get("proposed_changes") or []
    return value if isinstance(value, list) else [value]


def _remove(bucket: list[str], item_id: str, context: str) -> None:
    if item_id not in bucket:
        raise ValueError(f"{context}: expected {item_id} in source bucket")
    bucket.remove(item_id)


def _append_unique(bucket: list[str], item_id: str, context: str) -> None:
    if item_id in bucket:
        raise ValueError(f"{context}: duplicate add/move target {item_id}")
    bucket.append(item_id)


def _apply_operation(document: dict, operation: dict, case_id: str) -> None:
    audience = document["labels"]["audience"]
    op = operation["op"]
    context = f"{case_id}/{op}"

    if op == "remove":
        _remove(audience[operation["bucket"]], operation["_id"], context)
        return

    if op == "add":
        _append_unique(audience[operation["bucket"]], operation["_id"], context)
        return

    if op == "replace":
        bucket = audience[operation["bucket"]]
        source_id = operation["from"]["_id"]
        target_id = operation["to"]["_id"]
        if source_id not in bucket:
            raise ValueError(f"{context}: expected replacement source {source_id}")
        if target_id in bucket and target_id != source_id:
            raise ValueError(f"{context}: replacement target already exists {target_id}")
        bucket[bucket.index(source_id)] = target_id
        return

    if op == "move":
        item_id = operation["_id"]
        source = audience[operation["from_bucket"]]
        target = audience[operation["to_bucket"]]
        _remove(source, item_id, context)
        _append_unique(target, item_id, context)
        return

    if op == "remove_tag":
        tag = operation["tag"]
        tags = document.get("tags", [])
        if tag not in tags:
            raise ValueError(f"{context}: expected tag {tag}")
        tags.remove(tag)
        return

    raise ValueError(f"{context}: unsupported operation")


def apply(*, reviewer: str, reviewed_at: str) -> tuple[int, int, int]:
    review = _load(REVIEW_PATH)
    status = _load(STATUS_PATH)
    status_by_id = {case["id"]: case for case in status["cases"]}

    # The accepted audit is a one-time migration. A second invocation should be
    # a safe no-op instead of trying to remove already-removed labels.
    if status_by_id and all(
        case.get("status") in {"approved", "edited"} for case in status_by_id.values()
    ):
        approved = sum(case["status"] == "approved" for case in status_by_id.values())
        edited = sum(case["status"] == "edited" for case in status_by_id.values())
        catalog_gaps = sum(
            "catalog_gap" in _load(HERE / f"{case_id}.json").get("tags", [])
            for case_id in status_by_id
        )
        return approved, edited, catalog_gaps

    approved = edited = catalog_gaps = 0

    for case in review["cases"]:
        case_id = case["id"]
        verdict = case["status"]
        operations = _ops(case)
        status_case = status_by_id[case_id]

        if verdict == "PASS":
            if operations:
                raise ValueError(f"{case_id}: PASS case unexpectedly has operations")
            status_case.update(
                {
                    "status": "approved",
                    "reviewer": reviewer,
                    "reviewed_at": reviewed_at,
                    "comment": "Accepted independent audit; no label changes required.",
                }
            )
            approved += 1
            continue

        brief_path = HERE / f"{case_id}.json"
        document = _load(brief_path)
        for operation in operations:
            _apply_operation(document, operation, case_id)

        note = document["labels"].get("labeler_note", "").rstrip()
        audit_note = (
            f"Human review {reviewed_at[:10]}: accepted and applied the independent "
            f"audit. {case['assessment']}"
        )
        if verdict == "CATALOG_GAP":
            audit_note += " Remaining catalog gap is intentional; no substitute label was invented."
            catalog_gaps += 1
        document["labels"]["labeler_note"] = f"{note}\n\n{audit_note}".strip()
        _dump(brief_path, document)

        status_case.update(
            {
                "status": "edited",
                "reviewer": reviewer,
                "reviewed_at": reviewed_at,
                "comment": (
                    "Applied accepted audit operations; catalog gap remains documented "
                    "in labeler_note."
                    if verdict == "CATALOG_GAP"
                    else "Applied accepted audit operations; source labels edited."
                ),
            }
        )
        edited += 1

    missing = set(status_by_id) - {case["id"] for case in review["cases"]}
    if missing:
        raise ValueError(f"status cases absent from audit: {sorted(missing)}")

    status["instructions"] = (
        "Human review completed 2026-07-16. `approved` means no source edit was "
        "needed; `edited` means the accepted audit operations were applied."
    )
    _dump(STATUS_PATH, status)
    return approved, edited, catalog_gaps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write accepted changes")
    parser.add_argument("--reviewer", default="project_owner")
    parser.add_argument("--reviewed-at", default="")
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("Refusing to write without --apply")

    reviewed_at = args.reviewed_at or datetime.now(timezone.utc).isoformat()
    approved, edited, gaps = apply(reviewer=args.reviewer, reviewed_at=reviewed_at)
    print(f"approved={approved} edited={edited} catalog_gaps={gaps}")


if __name__ == "__main__":
    main()
