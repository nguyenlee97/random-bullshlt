---
title: Report v2 — real-model grounding
date: 2026-08-08
branch: feat/report-outcome-simulator
status: completed
---

# Report v2 — real-model grounding

Report v2 replaced template-shaped synthetic reporting with a brief-derived measurement specification, deterministic full-period facts, business-outcome funnels, KPI status, and evidence-owned actions. The legacy report API, evidence-v1 path, PDF shape, and Mongo documents remain readable.

The most important lesson came from running the production GPT-5.4-mini boundary rather than trusting prompt instructions. One response softened an evidence-defined `BAD` campaign into `Watch`; another returned `answer.sections` as an object instead of the requested array. Both outputs were plausible enough to pass a visual review but violated the report contract.

The final boundary is therefore asymmetric: code owns facts, formulas, KPI status, action IDs, guardrails, and review windows; the model owns only explanation. Near-schema sections are normalized, invalid evidence references fail validation, and any unusable model response falls back to complete deterministic answers rather than question placeholders.

VoltRide proved the behavior across 35 days and five business outcomes. A final real-model structured response passed the local grounder and validator with overall `BAD`, all four conversion questions, and contract-grounded actions. Six mechanical loops moved the evaluator from 0 to 100, while backend, Agent report, frontend report integration, and production build gates passed.
