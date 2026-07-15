"""Validate an Advertising Agent external test report without extra packages."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "testing" / "scenario-manifest.json"
VALID_STATUSES = {"pass", "fail", "blocked", "not_run"}
VALID_PRIORITIES = {"P0", "P1", "P2"}
VALID_SEVERITIES = {"blocker", "major", "minor", "cosmetic"}
JOURNEY_COMPONENTS = {
    "JOURNEY-GUIDED-01": ["UI-001", "BR-001", "BR-002", "RAG-002", "CR-001", "ORD-003", "ORD-007", "REP-001"],
    "JOURNEY-AUTO-01": ["UI-003", "BR-001", "BR-002", "AUTO-003", "AUTO-009", "AUTO-010", "AUTO-012", "REP-001"],
    "JOURNEY-NONLINEAR-01": ["UI-002", "NL-001", "BR-011", "NL-003", "WS-006", "ORD-009"],
    "JOURNEY-RECOVERY-01": ["BR-001", "RES-001", "AUTO-003", "RES-007", "AUTO-012"],
}


def load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"file not found: {path}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
    return None


def is_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def require_mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def require_list(value: Any, label: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return []
    return value


def require_keys(obj: dict[str, Any], keys: set[str], label: str, errors: list[str]) -> None:
    for key in sorted(keys - obj.keys()):
        errors.append(f"{label} missing required field: {key}")


def validate_environment(environment: dict[str, Any], errors: list[str]) -> None:
    required = {
        "git_commit",
        "dirty",
        "agent_version",
        "frontend_url",
        "agent_url",
        "backend_url",
        "feature_flags",
        "models",
        "containers",
        "browser_profiles",
    }
    require_keys(environment, required, "environment", errors)
    if not isinstance(environment.get("dirty"), bool):
        errors.append("environment.dirty must be boolean")
    if not isinstance(environment.get("git_commit"), str) or len(environment.get("git_commit", "")) < 7:
        errors.append("environment.git_commit must contain at least 7 characters")
    for key in ("feature_flags", "models", "containers"):
        if not isinstance(environment.get(key), dict):
            errors.append(f"environment.{key} must be an object")
    if not isinstance(environment.get("browser_profiles"), list):
        errors.append("environment.browser_profiles must be an array")


def validate_defects(defects: list[Any], label: str, errors: list[str]) -> Counter[str]:
    severities: Counter[str] = Counter()
    required = {"defect_id", "severity", "title", "fingerprint", "expected", "actual", "reproduction"}
    for index, raw in enumerate(defects):
        item_label = f"{label}.defects[{index}]"
        defect = require_mapping(raw, item_label, errors)
        require_keys(defect, required, item_label, errors)
        severity = defect.get("severity")
        if severity not in VALID_SEVERITIES:
            errors.append(f"{item_label}.severity must be one of {sorted(VALID_SEVERITIES)}")
        else:
            severities[severity] += 1
        if not isinstance(defect.get("reproduction"), list) or not defect.get("reproduction"):
            errors.append(f"{item_label}.reproduction must be a non-empty array")
        for key in ("defect_id", "title", "fingerprint", "expected", "actual"):
            if not isinstance(defect.get(key), str) or not defect.get(key, "").strip():
                errors.append(f"{item_label}.{key} must be a non-empty string")
    return severities


def validate_evidence(evidence: list[Any], label: str, errors: list[str]) -> None:
    required = {"kind", "path", "description"}
    for index, raw in enumerate(evidence):
        item_label = f"{label}.evidence[{index}]"
        item = require_mapping(raw, item_label, errors)
        require_keys(item, required, item_label, errors)
        for key in required:
            if not isinstance(item.get(key), str) or not item.get(key, "").strip():
                errors.append(f"{item_label}.{key} must be a non-empty string")


def validate_result(
    raw: Any,
    index: int,
    manifest_by_id: dict[str, dict[str, Any]],
    errors: list[str],
) -> tuple[str | None, str | None, Counter[str]]:
    label = f"results[{index}]"
    result = require_mapping(raw, label, errors)
    required = {
        "scenario_id",
        "suite",
        "priority",
        "status",
        "started_at",
        "duration_ms",
        "input",
        "expected_assertions",
        "observations",
        "evidence",
        "defects",
        "notes",
        "blocked_reason",
    }
    require_keys(result, required, label, errors)

    scenario_id = result.get("scenario_id")
    status = result.get("status")
    if not isinstance(scenario_id, str) or not scenario_id:
        errors.append(f"{label}.scenario_id must be a non-empty string")
        scenario_id = None
    elif scenario_id not in manifest_by_id:
        errors.append(f"{label}.scenario_id is not in manifest: {scenario_id}")
    else:
        expected = manifest_by_id[scenario_id]
        if result.get("suite") != expected["suite"]:
            errors.append(f"{scenario_id}: suite must be {expected['suite']!r}")
        if result.get("priority") != expected["priority"]:
            errors.append(f"{scenario_id}: priority must be {expected['priority']!r}")

    if result.get("priority") not in VALID_PRIORITIES:
        errors.append(f"{label}.priority must be one of {sorted(VALID_PRIORITIES)}")
    if status not in VALID_STATUSES:
        errors.append(f"{label}.status must be one of {sorted(VALID_STATUSES)}")
        status = None
    if not is_datetime(result.get("started_at")):
        errors.append(f"{label}.started_at must be an ISO-8601 date-time")
    if not isinstance(result.get("duration_ms"), int) or result.get("duration_ms", -1) < 0:
        errors.append(f"{label}.duration_ms must be a non-negative integer")

    assertions = require_list(result.get("expected_assertions"), f"{label}.expected_assertions", errors)
    if not assertions or any(not isinstance(item, str) or not item.strip() for item in assertions):
        errors.append(f"{label}.expected_assertions must contain non-empty strings")
    require_list(result.get("observations"), f"{label}.observations", errors)
    evidence = require_list(result.get("evidence"), f"{label}.evidence", errors)
    defects = require_list(result.get("defects"), f"{label}.defects", errors)
    validate_evidence(evidence, label, errors)
    severities = validate_defects(defects, label, errors)

    blocked_reason = result.get("blocked_reason")
    if status == "fail" and (not defects or not evidence):
        errors.append(f"{scenario_id or label}: fail requires at least one defect and one evidence item")
    if status == "pass" and defects:
        errors.append(f"{scenario_id or label}: pass cannot contain defect records")
    if status in {"blocked", "not_run"} and (not isinstance(blocked_reason, str) or not blocked_reason.strip()):
        errors.append(f"{scenario_id or label}: {status} requires blocked_reason")
    if status in {"pass", "fail"} and blocked_reason not in (None, ""):
        errors.append(f"{scenario_id or label}: {status} must not have blocked_reason")

    if scenario_id in JOURNEY_COMPONENTS:
        if result.get("constituent_scenarios") != JOURNEY_COMPONENTS[scenario_id]:
            errors.append(f"{scenario_id}: constituent_scenarios must exactly match the catalog order")

    return scenario_id, status, severities


def validate_summary(
    summary: dict[str, Any],
    statuses: Counter[str],
    suites: dict[str, Counter[str]],
    severities: Counter[str],
    errors: list[str],
) -> None:
    required = {"total", "pass", "fail", "blocked", "not_run", "by_suite", "release_gate", "blockers", "majors"}
    require_keys(summary, required, "summary", errors)
    expected_counts = {"total": sum(statuses.values()), **{status: statuses[status] for status in VALID_STATUSES}}
    for key, expected in expected_counts.items():
        if summary.get(key) != expected:
            errors.append(f"summary.{key}={summary.get(key)!r}, expected {expected}")
    if summary.get("blockers") != severities["blocker"]:
        errors.append(f"summary.blockers={summary.get('blockers')!r}, expected {severities['blocker']}")
    if summary.get("majors") != severities["major"]:
        errors.append(f"summary.majors={summary.get('majors')!r}, expected {severities['major']}")
    if summary.get("release_gate") not in {"pass", "fail", "incomplete"}:
        errors.append("summary.release_gate must be pass, fail, or incomplete")

    by_suite = require_mapping(summary.get("by_suite"), "summary.by_suite", errors)
    for suite, counts in suites.items():
        reported = require_mapping(by_suite.get(suite), f"summary.by_suite.{suite}", errors)
        expected = {"total": sum(counts.values()), **{status: counts[status] for status in VALID_STATUSES}}
        for key, value in expected.items():
            if reported.get(key) != value:
                errors.append(f"summary.by_suite.{suite}.{key}={reported.get(key)!r}, expected {value}")
    unknown_suites = set(by_suite) - set(suites)
    if unknown_suites:
        errors.append(f"summary.by_suite contains suites with no results: {sorted(unknown_suites)}")


def validate(report_path: Path, manifest_path: Path, allow_partial: bool) -> list[str]:
    errors: list[str] = []
    report = load_json(report_path, errors)
    manifest = load_json(manifest_path, errors)
    if not isinstance(report, dict) or not isinstance(manifest, dict):
        return errors

    scenarios = require_list(manifest.get("scenarios"), "manifest.scenarios", errors)
    manifest_by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(scenarios):
        item = require_mapping(raw, f"manifest.scenarios[{index}]", errors)
        scenario_id = item.get("id")
        if not isinstance(scenario_id, str) or not scenario_id:
            errors.append(f"manifest.scenarios[{index}].id must be non-empty")
        elif scenario_id in manifest_by_id:
            errors.append(f"duplicate manifest scenario: {scenario_id}")
        else:
            manifest_by_id[scenario_id] = item
    if manifest.get("scenario_count") != len(scenarios):
        errors.append(f"manifest.scenario_count={manifest.get('scenario_count')!r}, expected {len(scenarios)}")

    required_top = {"schema_version", "run", "environment", "results", "summary"}
    require_keys(report, required_top, "report", errors)
    if report.get("schema_version") != "1.0":
        errors.append("schema_version must equal '1.0'")

    run = require_mapping(report.get("run"), "run", errors)
    require_keys(run, {"run_id", "started_at", "ended_at", "executor", "scope"}, "run", errors)
    if not is_datetime(run.get("started_at")) or not is_datetime(run.get("ended_at")):
        errors.append("run.started_at and run.ended_at must be ISO-8601 date-times")
    if run.get("scope") not in {"full", "p0", "targeted"}:
        errors.append("run.scope must be full, p0, or targeted")
    validate_environment(require_mapping(report.get("environment"), "environment", errors), errors)

    results = require_list(report.get("results"), "results", errors)
    seen: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    suites: dict[str, Counter[str]] = defaultdict(Counter)
    severities: Counter[str] = Counter()
    for index, raw in enumerate(results):
        scenario_id, status, result_severities = validate_result(raw, index, manifest_by_id, errors)
        if scenario_id:
            seen[scenario_id] += 1
        if status:
            statuses[status] += 1
            if isinstance(raw, dict) and isinstance(raw.get("suite"), str):
                suites[raw["suite"]][status] += 1
        severities.update(result_severities)

    duplicates = sorted(scenario_id for scenario_id, count in seen.items() if count > 1)
    if duplicates:
        errors.append(f"scenario IDs must appear exactly once; duplicates: {duplicates}")
    if not allow_partial:
        missing = sorted(set(manifest_by_id) - set(seen))
        if missing:
            errors.append(f"missing {len(missing)} manifest scenarios: {missing}")

    validate_summary(require_mapping(report.get("summary"), "summary", errors), statuses, suites, severities, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to report.json")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--allow-partial", action="store_true", help="Allow manifest scenarios to be omitted")
    args = parser.parse_args()

    errors = validate(args.report.resolve(), args.manifest.resolve(), args.allow_partial)
    if errors:
        print(f"INVALID: {len(errors)} error(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    mode = "partial" if args.allow_partial else "complete"
    print(f"VALID: {args.report} ({mode} coverage)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
