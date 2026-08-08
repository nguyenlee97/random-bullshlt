---
title: Advertising Report v2 QA
date: 2026-08-08
status: passed
branch: feat/report-outcome-simulator
commit: bdeb09c
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
| `backend: npm test` | 68 passed |
| Agent report QA/media | 17 passed |
| Frontend production build | passed |
| Frontend report integration | 1 passed |
| Complete frontend suite | 195 passed, 2 pre-existing technical-doc copy checks failed |
| Immutable report-v2 evaluator | 100/100 |
| `git diff --check` | passed; line-ending warnings only |

## Real-model boundary

The production Agent model catalog reported OpenAI GPT-5.4-mini as available. A temporary owned anonymous conversation was created with `openai_gpt_5_4_mini`, verified as `tool=openai_brief_handler, model=gpt-5.4-mini`, and deleted after the check.

Three real-model observations were used as gates:

1. An unconstrained analysis softened the deterministic `BAD` state into `Watch`. Report Specialist now overwrites overall and insight status from the evidence contract, and replaces recommendations with contract-owned actions.
2. One structured response returned `answer.sections` as an object rather than an array. A near-schema normalizer now preserves usable model content before grounding; malformed output still fails closed to the deterministic full-answer fallback.
3. The final structured VoltRide response returned valid JSON from `gpt-5.4-mini`; after local grounding it passed `validateAnalysisResult` with overall `BAD`, question IDs `cv_q1` through `cv_q4`, and grounded action IDs for every recommendation.

The local workspace still has no `OPENAI_API_KEY`, so a local `--with-model` preview deliberately records `deterministic_fallback`. This is now separately verified from the real production model boundary and is not represented as an OpenAI response.

## Known non-report signal

The complete frontend suite has two documentation-copy failures in unchanged `tech-docs.html` content: `Bounded multi-format generation` and `Feedback tại điểm quyết định`. Neither the implementation diff nor the report UI touches that document. The report-related frontend test, production build, backend suite, and Agent report suite all pass.

## Completion audit

| Requirement | Authoritative evidence |
|---|---|
| Versioned upgrade, legacy-safe | `report-input-v2` / `report-evidence-v2`; legacy evidence-v1 and 14-day callers covered by backend tests |
| Full campaign period | VoltRide 35 days × 3 zones = 105 records |
| Dynamic outcomes | VoltRide test-ride funnel includes deposit/purchase; unrelated purchase fixture excludes deposit |
| Coherent simulated facts | Deterministic hash, full matrix, budget/formula/funnel invariant tests |
| Objective-aware analysis | Awareness, Consideration, Conversion, and Retention KPI parser tests |
| Actionable Good/Watch/Bad | Five VoltRide KPI states and five evidence/guardrail/review actions generated in code |
| Model cannot rewrite facts | Real model initially softened BAD to Watch; regression now locks overall, insight, and actions to contract |
| Model output tolerance | Real near-schema object sections normalized; invalid output falls back to complete deterministic answers |
| Real model interface | Production `gpt-5.4-mini` JSON passed local Report v2 grounder and validator |
| Fast brief testing | `npm run report:preview -- <fixture.json> --with-model` skips the upstream campaign workflow |
| Six optimization loops | `loop-results.tsv`: 0 → 30 → 60 → 90 → 90 → 90 → 100 |
