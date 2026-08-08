# Advertising Report v2 Implementation

---
date: 2026-08-08
status: in-progress
branch: feat/report-outcome-simulator
base: origin/revamp/next-hackathon@a8c97db
---

## Overview

Upgrade the existing report workflow without changing audience, creative, placement-ranking, or order-creation behavior. Preserve the existing report API and analytics-record shape while adding a versioned input contract, dynamic business outcomes, deterministic facts, evidence-based performance status, and actionable report output.

## Expected Output

- Backend report v2 contract and deterministic simulator.
- Additive report input from the existing Agent workflow.
- Existing `/api/reports/*` routes continue to work.
- Report UI shows Overview plus the active objective, business KPI scorecard, funnel, and prioritized actions.
- Fast local fixture command/test can generate and inspect a VoltRide report without running the complete campaign workflow.

## Acceptance Criteria

1. A campaign with `startDate` and `endDate` generates deterministic daily media facts for the complete period and selected zones.
2. Repeating the same normalized input produces the same facts and input hash.
3. Old callers without `endDate`, KPI, notes, strategy, or forecast still generate a compatible report.
4. Measurement planning converts brief context into a typed `OutcomeGraph` and KPI definitions.
5. Outcome events are dynamic; `deposit` is included only when relevant to the brief.
6. VoltRide distinguishes at least test-ride registration, qualified test ride, attended test ride, deposit, and purchase.
7. Funnel child counts never exceed parent counts, media formulas remain valid, total spend stays within budget, and every date-zone cell is present.
8. Evidence v2 contains campaign totals, KPI attainment, funnel, period comparison, zone findings, performance status, and action recommendations.
9. Good/Watch/Bad is calculated deterministically from KPI targets; the model cannot choose or override it.
10. Report Specialist answers from evidence v2 and returns actual answers/actions, not question-only placeholders.
11. Report Chat remains evidence-cited and refuses metrics absent from the contract.
12. ReportStep presents Overview and active objective without separate duplicate Executive content.
13. Existing backend report, PDF, Agent report-QA, and frontend tests pass, plus new v2 and VoltRide cases.

## Scope Boundary

- No changes to audience retrieval or audience ranking.
- No changes to creative generation or Creative Intelligence decisions.
- No changes to placement catalog ranking or order API semantics.
- No production deployment, database migration command, or external write.
- Existing Mongo documents remain readable; schema additions are optional/additive.

## Constraints

- Fixed report specialist model remains GPT-5.4-mini.
- Facts and KPI evaluation must be deterministic code, not LLM output.
- Existing APIs and legacy report-type IDs remain available during transition.
- Report generation must not require one model prompt containing all daily rows.
- Changes stay inside report workflow boundaries and additive campaign-to-report payload fields.

## Phases

1. [in-progress] Contract and deterministic simulator.
2. [pending] Evidence v2, KPI evaluation, and actions.
3. [pending] Report Specialist and persistence compatibility.
4. [pending] Agent payload and ReportStep presentation.
5. [pending] Fixture harness, regression tests, and six optimization loops.

## Success Criteria

- Six mechanical iterations logged with increasing report-v2 requirement score.
- VoltRide fixture reaches a reproducible evidence contract with business funnel, KPI statuses, and actionable recommendations.
- Targeted and affected regression suites pass with no new build errors.

