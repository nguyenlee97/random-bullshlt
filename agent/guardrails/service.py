"""Deterministic prompt-injection detection with staged policy modes."""

from __future__ import annotations

import hashlib
import re
import unicodedata

from config import config
from guardrails.models import (
    GuardDecision,
    GuardFinding,
    GuardResult,
    GuardSeverity,
    LocatedFinding,
)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = "".join(
        char for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )
    value = value.replace("đ", "d")
    value = re.sub(r"[\s._-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


_RULES = (
    ("instruction_override", GuardSeverity.high, re.compile(
        r"\b(ignore|disregard|forget|override)\b.{0,35}\b"
        r"(previous|prior|above|system|developer)\b.{0,25}\b"
        r"(instruction|instructions|rules|prompt|message)\b"
    )),
    ("instruction_override_vi", GuardSeverity.high, re.compile(
        r"\b(bo qua|quen|ghi de|vo hieu hoa)\b.{0,40}\b"
        r"(chi dan|huong dan|quy tac|lenh|prompt|thong diep)\b.{0,25}\b"
        r"(truoc|he thong|developer|ben tren)\b"
    )),
    ("role_spoof", GuardSeverity.high, re.compile(
        r"(^|[\n;])\s*(system|developer|assistant)\s*:|"
        r"\b(begin|new)\s+(system|developer)\s+(message|prompt)\b"
    )),
    ("secret_exfiltration", GuardSeverity.critical, re.compile(
        r"\b(reveal|show|print|leak|exfiltrate|tiet lo|hien thi|in ra)\b.{0,40}\b"
        r"(system prompt|prompt he thong|api key|secret|token|environment|bien moi truong)\b"
    )),
    ("tool_forcing", GuardSeverity.critical, re.compile(
        r"\b(call|invoke|execute|force|trigger|goi|thuc thi|bat buoc)\b.{0,35}\b"
        r"(update workspace|create order|order guard|commit workspace|delete session)\b"
    )),
    ("safety_override", GuardSeverity.critical, re.compile(
        r"\b(return|mark|set|tra ve|dat)\b.{0,35}\b"
        r"(safety false|safety flag false|safe true|all flags false)\b"
    )),
    ("jailbreak", GuardSeverity.critical, re.compile(
        r"\b(jailbreak|dan mode|do anything now|unrestricted mode|che do khong gioi han)\b"
    )),
    ("markup_injection", GuardSeverity.high, re.compile(
        r"<script\b|<system\b|\[system message\]|###\s*system\b"
    )),
)


def detect_text(text: str | None) -> list[GuardFinding]:
    normalized = _normalize(text or "")
    return [
        GuardFinding(rule=name, severity=severity)
        for name, severity, pattern in _RULES
        if pattern.search(normalized)
    ]


def _walk(value, path: str, findings: list[LocatedFinding]) -> None:
    if len(findings) >= config.GUARDRAIL_MAX_FINDINGS:
        return
    if isinstance(value, str):
        for finding in detect_text(value):
            findings.append(LocatedFinding(path=path, finding=finding))
            if len(findings) >= config.GUARDRAIL_MAX_FINDINGS:
                break
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk(item, f"{path}[{index}]", findings)
            if len(findings) >= config.GUARDRAIL_MAX_FINDINGS:
                break
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _walk(item, f"{path}.{key}", findings)
            if len(findings) >= config.GUARDRAIL_MAX_FINDINGS:
                break


def _decision(findings: list[LocatedFinding]) -> GuardDecision:
    if not findings or config.GUARDRAIL_MODE == "off":
        return GuardDecision.allow
    if config.GUARDRAIL_MODE == "shadow":
        return GuardDecision.audit
    return GuardDecision.block


def evaluate_text(text: str | None, *, surface: str = "input") -> GuardResult:
    findings = [
        LocatedFinding(path=surface, finding=finding)
        for finding in detect_text(text)
    ][:config.GUARDRAIL_MAX_FINDINGS]
    return GuardResult(
        decision=_decision(findings),
        policy_version=config.GUARDRAIL_POLICY_VERSION,
        findings=findings,
    )


def evaluate_payload(value, path: str = "input") -> GuardResult:
    findings: list[LocatedFinding] = []
    _walk(value, path, findings)
    return GuardResult(
        decision=_decision(findings),
        policy_version=config.GUARDRAIL_POLICY_VERSION,
        findings=findings,
    )


def event_payload(result: GuardResult, value) -> dict:
    raw = str(value)
    return {
        "mode": config.GUARDRAIL_MODE,
        "decision": result.decision.value,
        "highest_severity": (
            result.highest_severity.value if result.highest_severity else None
        ),
        "rules": [item.finding.rule for item in result.findings],
        "paths": [item.path for item in result.findings],
        "input_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "redacted_excerpt": raw[:config.GUARDRAIL_MAX_EXCERPT_CHARS],
        "workspace_mutated": False,
        "order_created": False,
    }
