"""Guardrail decision contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GuardDecision(str, Enum):
    allow = "allow"
    audit = "audit"
    sanitize = "sanitize"
    block = "block"
    require_review = "require_review"


class GuardSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


@dataclass(frozen=True)
class GuardFinding:
    rule: str
    category: str = "prompt_injection"
    severity: GuardSeverity = GuardSeverity.high
    confidence: float = 1.0
    detector: str = "deterministic-v1"


@dataclass(frozen=True)
class LocatedFinding:
    path: str
    finding: GuardFinding


@dataclass(frozen=True)
class GuardResult:
    decision: GuardDecision
    policy_version: str
    findings: list[LocatedFinding] = field(default_factory=list)

    @property
    def highest_severity(self) -> GuardSeverity | None:
        order = {
            GuardSeverity.low: 0,
            GuardSeverity.medium: 1,
            GuardSeverity.high: 2,
            GuardSeverity.critical: 3,
        }
        return max(
            (item.finding.severity for item in self.findings),
            key=lambda value: order[value],
            default=None,
        )
