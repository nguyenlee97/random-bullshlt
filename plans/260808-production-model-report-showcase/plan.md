---
title: Production model report showcase — VoltRide and MộcAn Dairy
status: completed
priority: P1
effort: medium
branch: feat/report-outcome-simulator
tags: [report-v2, gpt-5.4-mini, html, charts]
created: 2026-08-08
---

# Production model report showcase

## Invocation

Create two Report v2 outputs for VoltRide and MộcAn Dairy, run the production `gpt-5.4-mini` model for both, and present the resulting analysis with charts in a local self-contained HTML artifact.

## Resolved presentation preferences

- Screenshots: enabled.
- Publishing: disabled for this run; the user requested a file for review, not public deployment.
- Language: Vietnamese for this run, matching both briefs and review context.

## Tasks

- [x] Normalize both briefs and generate Report v2 facts/contracts.
- [x] Run production GPT-5.4-mini and preserve sanitized provenance/output.
- [x] Validate model output against each evidence contract.
- [x] Write report content and self-contained HTML with charts.
- [x] Open locally, inspect responsive rendering, and capture screenshots.
- [x] Record QA results and artifact paths.

## Result

- Self-contained report: `assets/showoff/production-model-report-comparison/index.html`
- Sanitized data/model output: `assets/showoff/production-model-report-comparison/report-data.json`
- Production model: `gpt-5.4-mini`, two of two reports validated on attempt 1.
- QA details: `assets/showoff/production-model-report-comparison/QA.md`
