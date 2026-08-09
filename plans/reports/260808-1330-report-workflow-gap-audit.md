# Report Workflow Gap Audit

---
date: 2026-08-08
branch: feat/report-outcome-simulator
base: origin/revamp/next-hackathon@a8c97db
scope: Advertising Agent report generation and report Q&A
status: audit-only
---

## Summary

The current product already has the two major AI surfaces discussed for the optimized design: a Campaign Agent and a Report Specialist. It should not add four new AI agents.

However, the current Campaign Agent does not produce a measurement/outcome contract for the report. The report path also contains additional model calls: one to invent 14-day media records, six parallel analysis calls, and a semantic report Q&A call. The missing layer is not another chat agent; it is a typed contract and deterministic business-outcome simulation between campaign planning and report analysis.

## Current Workflow

1. Campaign Agent validates and analyzes the brief, then supports audience, targeting, placement, creative, and order creation.
2. Autopilot deterministically creates three directional media-plan scenarios: `balanced`, `reach_first`, and `quality_first`.
3. Autopilot deterministically forecasts impressions, reach, average CPM, frequency, and inventory risk from the selected placement catalog.
4. Report entry calls the backend with only campaign ID, brand, objective, budget, start date, zones, and a short audience list.
5. The backend Report Generator asks GPT-5.4-mini to invent exactly 14 days of media delivery rows.
6. A deterministic `report-evidence-v1` contract aggregates campaign totals, a first-half/second-half comparison, top CTR zone, and lowest CPM zone.
7. GPT-5.4-mini generates six fixed report analyses in parallel: Daily Ops, Awareness, Consideration, Conversion, Retention, and Executive.
8. Report Chat makes another GPT-5.4-mini call to answer the user's free-form question from the generated analyses and evidence contract.

## Role Inventory

| Proposed role | Current implementation | Status | Audit conclusion |
|---|---|---|---|
| Campaign / Measurement Planner (AI) | Campaign Agent brief analysis, Autopilot workflow, brief KPI suggestions | Partial | It plans campaign setup, but does not emit a typed `MeasurementSpec`, `OutcomeGraph`, or report scenario requirements. Suggested KPIs are displayed but are not promoted into the report input contract. |
| Scenario Planner | Deterministic Autopilot Strategy Simulator (`brief_scenario_v2`) | Partial | It creates three pre-launch media allocation directions and chooses one by objective. It does not plan post-launch performance scenarios, business events, lag windows, KPI thresholds, or causal assumptions. |
| Fact Simulator | GPT-based `generateRecords()` plus deterministic pre-launch forecast | Partial / wrong boundary | Media rows exist, but the report rows are invented directly by the model. The deterministic forecast is not consumed by the report generator. There are no qualified lead, attendance, purchase, deposit, activation, or retention facts. |
| Evidence Builder / Validator | `report-evidence-v1` and `validateAnalysisResult()` | Partial | Citation integrity and metric allow-listing are good. Evidence is limited to media totals and two zone rankings; there is no KPI attainment, outcome funnel, segment/creative/geo comparison, anomaly, confidence, or action eligibility. |
| Report Specialist (AI) | GPT-5.4-mini `generateAnalysis()` | Present | It answers fixed questions with structured sections and evidence IDs. Its insight ceiling is limited by the thin evidence contract and generic `conversions` field. |
| Report Chat Analyst (AI) | GPT-5.4-mini semantic Q&A | Present | It correctly refuses unsupported facts and cites evidence, but it cannot answer business questions absent from the contract. This can remain the conversational surface of the Report Specialist rather than becoming a new business-planning agent. |

## Step-by-step Gaps

| Step / contract | Current state | Reuse | Missing before implementation |
|---|---|---|---|
| Brief collection | Brand, objective, KPI text, budget, dates, and notes exist | Yes | KPI text needs structured extraction into metric, target, comparator, attribution window, and business event semantics. |
| Brief analysis | AI flags risks and suggests KPIs | Yes | Output is UI text only; it is not a canonical measurement artifact used by report generation. |
| Campaign strategy scenarios | Three deterministic media options respond to objective, duration, and budget | Yes | Do not confuse this with report performance scenarios. Add a separate typed outcome scenario spec or extend the artifact with report assumptions. |
| Placement forecast | Deterministic impressions/reach/CPM/frequency with provenance | Yes | Pass selected strategy and forecast into report generation; currently this evidence is disconnected. |
| Report input payload | Brand, objective, budget, start date, zones, short audience list | Replace contract | Missing end date, KPI targets, notes, geo, strategy, forecast, targeting, creative metadata, business funnel, attribution windows, and input revision/hash. |
| Report timeframe | Fixed 14 days from start date | Replace | Must use campaign duration or a bounded grain policy, while preserving daily/weekly aggregation. Long campaigns should not require one model-generated row per day. |
| Media facts | GPT invents daily-by-zone rows | Replace generator, keep schema compatibility where useful | Generate deterministic facts from a scenario seed and validate exact date-zone coverage, formulas, spend, bounds, and reproducibility. |
| Business facts | Single generic `conversions` count | New | Add dynamic events such as qualified leads, bookings, attendance, purchases, deposits, subscriptions, activations, and retained users, chosen from the brief's outcome graph. |
| Evidence contract | Media totals, period split, top CTR, lowest CPM | Extend to v2 | Add KPI attainment, funnel transitions, lagged outcomes, breakdowns, anomaly/fatigue/pacing signals, confidence, limitations, and action eligibility. |
| Performance status | LLM may label each answer `good`, `warning`, or `bad` | Replace with deterministic evaluator | Add KPI- and objective-aware `good/watch/bad` rules. The model should explain a status, not invent it. |
| Actionability | Every answer requests a recommendation | Extend | Add structured action: observed problem, evidence, affected scope, proposed change, expected movement, guardrail, confidence, and next review window. |
| Report structure | Six fixed report types and 36 fixed questions | Simplify | Merge Daily Ops and Executive into Overview, render Overview plus the campaign's active objective, and derive specific questions from available evidence. |
| Report Q&A | Semantic evidence-cited answer with unknown-ID validation | Yes | Feed evidence v2 and dynamic event vocabulary; retain refusal behavior for unavailable metrics. |
| Regeneration / versioning | Existing records are reused by campaign ID | Replace | Add input hash, seed, schema version, revision, snapshot, and explicit regenerate semantics so changed briefs do not silently reuse stale facts. |

## Important Disconnections

### Forecast is not report input

Autopilot already computes campaign-specific `estimated_impressions`, `estimated_reach`, `average_cpm`, `frequency`, inventory reach cap, and evidence. None of these fields are sent through `handle_report_entry()` to `launchReportGeneration()`.

### End date and KPI are dropped

The canonical brief contains `kpi`, `startDate`, `endDate`, and `notes`. The report payload omits `kpi`, `endDate`, and `notes`, and `generateRecords()` always creates 14 days.

### Business meaning is collapsed into `conversions`

The analytics schema has one generic conversion counter. Therefore a VoltRide report cannot distinguish registration, qualified registration, attended test ride, deposit, and purchase. A stronger language model cannot infer these values safely because they do not exist in evidence.

### Good / watch / bad is not a fact

The report prompt lets the model choose `good|warning|bad`, but the evidence contract contains no target-comparison rule. This makes performance status narrative rather than reproducible evaluation.

## Recommended Target with Two AI Agents

### AI Agent 1: Campaign Agent extended with Measurement Planning

Reuse the current Campaign Agent. At brief approval, produce a typed measurement artifact containing:

- primary objective and optimization event;
- KPI definitions and target values;
- dynamic `OutcomeGraph` with event names supplied by the brief;
- attribution and lag windows;
- report dimensions and required breakdowns;
- scenario assumptions and confidence bounds;
- legal or business guardrails.

This is an extension of the existing agent, not a new user-facing agent.

### Deterministic middle layer

Implement as code, not agents:

1. Scenario/fact simulation seeded by campaign and scenario revision.
2. Media fact generation consistent with budget, dates, strategy, forecast, and placements.
3. Business event simulation consistent with the `OutcomeGraph` and funnel constraints.
4. Evidence v2 aggregation and mechanical validation.
5. Objective-aware KPI status and action eligibility.

### AI Agent 2: Report Specialist

Keep the current Report Specialist and semantic Q&A, but give them evidence v2. It should explain findings, prioritize actions, state limitations, and answer follow-ups without generating facts.

## Dynamic Outcome Example

For VoltRide, the outcome graph can be:

`impression -> click -> test_ride_registration -> qualified_test_ride -> attended_test_ride -> deposit -> purchase`

For another campaign it can be:

- ecommerce: `click -> product_view -> add_to_cart -> checkout -> purchase`;
- lead generation: `click -> lead -> qualified_lead -> sales_accepted_lead`;
- subscription: `click -> trial_started -> activated -> subscribed -> retained_30d`;
- awareness: `impression -> viewable_impression -> completed_view -> brand_search` where available.

`deposit` is therefore not mandatory. It is one event type selected only when the brief or product journey requires it.

## Recommendations

1. Reuse the existing Campaign Agent, Strategy Simulator, catalog Forecast, report evidence citation validation, Report Specialist, and semantic Report Q&A.
2. Do not add four autonomous agents. Add one canonical measurement artifact and deterministic simulators/validators.
3. First implementation slice should connect the complete brief, selected strategy, and forecast to the report input contract before changing UI.
4. Second slice should add dynamic business events and objective-aware KPI evaluation.
5. Third slice should simplify the report presentation to Overview plus active objective and generate evidence-driven questions/actions.

## Unresolved Questions

- Whether the first version should support every custom event name or a canonical event taxonomy with user-facing aliases.
- Whether long campaign reports should default to daily facts with weekly UI aggregation, or directly generate weekly facts after a configured duration threshold.
- Whether Report Specialist pre-generation and interactive Report Q&A should remain two model calls or share one cached analysis artifact.
