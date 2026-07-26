"""Compatibility API over the typed guardrail service."""

from __future__ import annotations

from guardrails.models import GuardFinding as InjectionFinding
from guardrails.service import detect_text, evaluate_payload


def detect_prompt_injection(text: str | None) -> InjectionFinding | None:
    findings = detect_text(text)
    return findings[0] if findings else None


def scan_untrusted_payload(value, path: str = "input") -> tuple[str, InjectionFinding] | None:
    result = evaluate_payload(value, path)
    if not result.findings:
        return None
    first = result.findings[0]
    return first.path, first.finding
