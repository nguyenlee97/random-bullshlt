# M4.4 Campaign Autopilot Evaluation — Completion Evidence

> Status: M4.4 complete. This closes the durable Campaign Autopilot milestone;
> M4.5 UI/observability and M4.6 release/security remain separate gates.

## Twenty-brief orchestration gate

Runner: `eval/run_autopilot_eval.py`

Corpus: golden briefs `brief_001` through `brief_020`, rotated across:

- `auto_build_draft`
- `critical_only`
- `review_every_stage`

Results:

| Metric | Result | Target |
|---|---:|---:|
| Briefs | 20 | at least 20 |
| Passed | **20/20** | at least 90% valid drafts |
| Order-ready draft rate | **100%** | at least 90% |
| Required launch-review pause | **100%** | 100% |
| Launch without approval | **0** | 0 |
| Mean orchestration latency | 74.89 ms | diagnostic |
| p95 orchestration latency | 92.91 ms | diagnostic |

The runner executes the real durable task graph, workspace revision checks,
artifact commits, approval policies, pending-artifact withholding, and final
launch interrupt. Capability values are deterministic fixtures. This isolates
orchestration correctness; it does not claim to reevaluate model quality.

## Failure drills

All **5/5** passed:

1. Missing brief blocks run creation.
2. Duplicate start idempotency returns the original run.
3. Expired worker lease is recovered without losing the task.
4. Mid-run brief edit increments the plan revision and replans affected work.
5. Duplicate launch approval is rejected and releases create-order at most
   once.

Additional integration failure evidence remains linked rather than duplicated:

- Qdrant outage caused an explicit counted fallback and recovery returned to
  RAG with valid source grounding.
- Unsafe/low-confidence creative block-or-review recall is 100%, with zero
  review-required or OCR prompt-injection escapes.
- Restart persistence and SSE replay were proven on a durable waiting run.
- The live exact-size creative-to-order run completed once with zero placement
  warnings, rejected approval replay, and deduplicated a repeated order POST.

## Reproducibility

Run locally from the repository root:

```powershell
agent\venv\Scripts\python.exe eval\run_autopilot_eval.py --label autopilot-20-v1
```

The report is stored at `eval/reports/autopilot-20-v1.json` and the release
scoreboard records the result.

## M4.4 exit verdict

The milestone exit condition is satisfied:

- explicit Guided Workflow versus Campaign Autopilot entry exists;
- runs and tasks are durable and restart-safe;
- approvals, pause/resume/cancel, retries, leases, and SSE are implemented;
- mid-run edits selectively replan affected work;
- one real brief reached a guarded order-ready draft and created exactly one
  verified local order after final approval;
- the required 20-brief and failure-drill gates pass.

Next work begins at M4.5: richer task evidence/trace UI and operational metrics,
followed by security, CI, performance, full rebrand audit, and demo hardening.
