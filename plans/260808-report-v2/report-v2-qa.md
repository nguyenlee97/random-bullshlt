---
title: Advertising Report v2 QA
date: 2026-08-08
status: passed-with-external-verification-pending
branch: feat/report-outcome-simulator
commit: a2a4167
---

# Advertising Report v2 QA

## Outcome

The v2 implementation is mechanically complete and compatible with the existing report boundary. It generates a brief-derived measurement plan, deterministic full-period facts, business outcomes, KPI status, evidence-bounded actions, and complete Report Specialist answers. The existing v1 evidence path remains available for legacy callers.

## VoltRide result

- Timeframe: 2026-08-20 through 2026-09-23 (35 days).
- Matrix: 105 date-zone records for three fixture zones.
- Funnel: 2,853 registrations → 2,475 qualified registrations → 1,708 attended test rides → 408 deposits → 289 purchases.
- KPI state: 0 good, 3 watch, 2 bad; overall `bad`.
- Actions include creative-audience testing, controlled zone reallocation, and follow-up/reminder cohort testing, each with evidence, guardrail, and review window.

## Checks

| Check | Result |
|---|---:|
| `backend: npm test` | 66 passed |
| Agent report QA/media | 17 passed |
| Frontend production build | passed |
| Frontend report integration | 1 passed |
| Immutable report-v2 evaluator | 100/100 |
| `git diff --check` | passed; line-ending warnings only |

## Model boundary

The production code still targets GPT-5.4-mini. The local workspace contains no `OPENAI_API_KEY`, so `report:preview -- --with-model` deliberately used `deterministic_fallback` and recorded that provenance. A final environment verification should inject the existing backend secret and confirm `analysisProvenance.provider = openai`; no code change is required for that check.

## Known non-report signal

The complete frontend suite previously had two documentation-copy failures in unchanged files. The report-related frontend test, production build, backend suite, and Agent report suite all pass.
