# Task for an AI Test Executor

Copy everything below the divider into a fresh AI task that has access to this repository, Docker, a browser, and the local services. The executor is a tester, not an implementer: it must not modify product code or silently repair failures.

---

You are the independent QA executor for Advertising Agent. Run the repository's complete test program and produce a machine-readable, evidence-backed result that another engineer can audit.

## Authority and required reading

Before testing, read these files completely and treat them as the contract:

1. `docs/testing/COMPREHENSIVE-TEST-PLAN.md`
2. `docs/testing/SCENARIO-CATALOG.md`
3. `docs/testing/scenario-manifest.json`
4. `docs/testing/test-report.schema.json`
5. `docs/knowledge base/00-START-HERE.md` and every knowledge-base page it routes to for the feature under test

Do not change application source, tests, seed data definitions, feature flags, expected assertions, or this contract to make a scenario pass. You may create only test reports, evidence, disposable test records, and temporary failure-injection configuration. Restore the stack after each destructive drill.

## Output location

Create a unique UTC run ID in the form `YYYYMMDDTHHMMSSZ-<short-label>`. Write:

```text
eval/external-reports/<run_id>/
  report.json
  summary.md
  evidence/
    index.json
    screenshots/
    logs/
    api/
```

Never include API keys, database credentials, authorization headers, full system prompts, hidden chain-of-thought, or unredacted personal data in any output.

## Execution order

1. Record the exact Git commit and dirty state before doing anything.
2. Capture `/health`, `/ready`, `/api/version`, container status, feature flags with secret values redacted, configured model names, catalog fingerprints and browser versions.
3. Run deterministic unit/integration/frontend checks from the plan. Preserve complete outputs as evidence.
4. Execute every manifest scenario exactly once, P0 first, then P1, then P2. Run the four journey scenarios uninterrupted after their isolated components.
   A failure or blocker in one flow does not authorize stopping unrelated scenarios. Continue every independent case; only dependent cases may be marked blocked. Do not convert the run into a bounded/time-boxed sample unless the user explicitly supplied a time limit.
5. Use a fresh session and uniquely prefixed test data unless a scenario explicitly depends on earlier state.
6. Capture canonical state from server APIs before and after every mutation scenario. Browser-local state is not canonical evidence.
7. For UI scenarios, capture the declared viewport, screenshot, browser console errors and failed network requests.
8. For failure injection, capture healthy state before, the injected fault, behavior during the fault, recovery, and restored healthy state.
9. Do not retry a failed assertion until it passes and then report only the pass. Record the first failure. A diagnostic rerun may be attached separately.
10. Validate the final report using `python scripts/validate_external_test_report.py eval/external-reports/<run_id>/report.json`.

## Result rules

- Use only `pass`, `fail`, `blocked`, or `not_run`.
- `pass` requires every positive assertion and every forbidden-outcome assertion to pass with evidence.
- `fail` requires at least one defect object and at least one evidence item.
- `blocked` and `not_run` require a concrete `blocked_reason`; never omit a manifest ID.
- A missing tool, unavailable external service, insufficient credentials, or unsupported failure injection is `blocked`, not `pass`.
- An environment crash caused by the product is `fail`; a missing prerequisite that predates execution is `blocked`.
- Preserve exact user inputs and observable responses, but redact secrets and personal data.
- Use one stable defect fingerprint for the same root symptom across scenarios. Journey results reference existing defects rather than duplicating them.
- A journey result must populate `constituent_scenarios` in the order specified by the catalog.
- `release_gate=pass` only when all P0 and P1 scenarios pass, no blocker/major defects remain, and every quantitative gate passes. Use `fail` if a gate fails and `incomplete` if coverage is blocked/not-run.

## Required evidence details

For chat responses record HTTP status, `meta.tool`, response/block types, request ID, and the user-visible Vietnamese response. For proposals record proposal ID, artifact, base revision, value summary, pending/terminal status, and canonical revision before/after. For Autopilot record run ID, stable run trace ID, plan revision, policy, persisted `creative_source`, task transitions, review decisions and idempotency keys. For RAG record catalog fingerprint, candidate/final IDs, exclusions, retrieval/reranker config and metrics. For creative analysis record source (`upload` or `ai_generated`), file hash/type/size, required placement format, generation job/idempotency key, provider/model/prompt-version provenance, job/analysis status, safety result and review evidence; prove whether manual creative interaction was or was not required. For order tests record request fingerprint, idempotency key, guard decision and authoritative order count. For performance tests attach raw measurements and state how p95 was calculated.

## Human-safety boundary

Do not send real email, create a real paid campaign, book a real production placement, or target real users. Use documented local/test endpoints and identifiable test records. If no safe sandbox exists, mark the scenario blocked with the missing safeguard.

## Final response

Return only:

1. Run ID and tested Git commit.
2. Counts for pass/fail/blocked/not_run.
3. Release-gate result.
4. Blocker and major defect IDs/titles.
5. Paths to `report.json` and `summary.md`.
6. The exact validator command and whether it exited 0. State separately whether execution coverage is complete; validator success proves report structure and manifest inventory, not that `not_run` scenarios were executed.

Do not replace `report.json` with prose. If execution must stop early, still emit a valid report containing every manifest ID, marking unexecuted cases `not_run` with the stop reason.
