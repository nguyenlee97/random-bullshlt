# Advertising Agent testing pack

Use these documents together:

- `COMPREHENSIVE-TEST-PLAN.md` defines environments, stages, evidence and release gates.
- `SCENARIO-CATALOG.md` gives the exact actions, expected outcomes and forbidden outcomes for 112 isolated cases plus four journeys.
- `scenario-manifest.json` is the authoritative 116-result inventory.
- `AI-TEST-EXECUTOR-PROMPT.md` is the task to hand to another AI.
- `test-report.schema.json` defines the exchange format.
- `test-report.example.json` is a partial worked example.

Validate a complete report:

```powershell
python scripts\validate_external_test_report.py eval\external-reports\<run_id>\report.json
```

Validate the intentionally partial example:

```powershell
python scripts\validate_external_test_report.py docs\testing\test-report.example.json --allow-partial
```
