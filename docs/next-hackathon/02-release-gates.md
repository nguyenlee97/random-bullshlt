# Release Gates and Cut Lines

## Gate 1 — Development baseline

Required before changing behavior:

- Clean branch.
- Reproducible dependencies.
- Healthy local Compose stack.
- Unit tests and smoke test green.
- Live rollback preserved.

Failure response: stop feature work and repair the baseline.

## Gate 2 — RAG candidate

Required before enabling RAG by default:

- Human-reviewed labels.
- `legacy-310`, `rag-no-rerank`, and `rag-reranked` reports.
- Recall and latency targets met.
- Zero exclusion violations.
- Index version/rebuild behavior tested.
- Fallback path tested by stopping Qdrant and disabling reranker.

Failure response: keep `USE_RAG_AUDIENCE=false`; retain the implementation for tuning.

## Gate 3 — VLM candidate

Required before claiming creative intelligence:

- Analysis occurs before assignment and order creation.
- UI shows verdict and reasons.
- Unsafe/low-confidence test creatives are blocked.
- Manual override is audited.
- Agent restart does not lose verdict state.
- Fixture-set regression passes.

Failure response: keep VLM advisory and do not market it as a safety guard.

## Gate 4 — Copilot and Autopilot candidate

Required before LangGraph becomes non-optional:

- At least 60 Vietnamese multi-turn Copilot scenarios pass.
- The opening selector reliably creates either a Guided workspace or an Autopilot workspace, and Guided mode never starts a run implicitly.
- Every chat mutation uses a validated proposal or an explicitly allowed policy action.
- Workspace revision conflicts reject stale writes and return a current diff.
- At least 30 non-linear scenarios produce the correct invalidation and reuse set.
- Durable Autopilot task and checkpoint restart tests pass.
- A mid-run user edit pauses, replans, and rejects late stale task output.
- Autopilot cannot create an order without explicit final launch approval.
- Duplicate launch approval creates exactly one order.
- Creative `needs_review` and safety overrides always pause for an authenticated human.
- Tool failures produce useful degraded responses.
- Plan, progress, evidence, blockers, and approval requests are visible in the UI.
- No stale response, stale artifact commit, unauthorized mutation, or cross-session state leakage occurs in soak testing.

Failure response: flip `USE_LANGGRAPH_FREEFORM=false` and ship deterministic/freeform legacy path.

## Gate 5 — Public staging

Required:

- Session authentication enabled.
- Secrets absent from frontend bundle and Git.
- PII redaction enabled for logs/traces.
- MongoDB not publicly exposed.
- Rate limits tested.
- Prompt-injection suite passes target threshold.
- Provider timeout/fallback behavior tested.

Failure response: staging remains private.

## Gate 6 — Hackathon release

Required:

- User-facing product name is Advertising Agent and the blue identity is consistent across Guided Workflow, Campaign Autopilot, reports, exports, and demo assets.
- Primary green branding has been removed while semantic success/warning/danger states remain distinguishable and accessible.
- Immutable image tags and release tag.
- Five consecutive rehearsals pass.
- Demo data reset succeeds.
- Offline fallback path demonstrated.
- Observability dashboard ready for judges.
- One hero feature fully polished.
- No P0/P1 defect open.
- Rollback tested in the final environment.

## Cut-line policy

When schedule pressure appears, cut in this order:

1. Kubernetes and self-hosted model serving.
2. Databricks/MLflow portfolio work.
3. Self-hosted Langfuse.
4. Extra hero features.
5. Sophisticated multi-agent delegation.
6. Visual polish outside the three-minute demo path.

Never cut:

- Order guard and idempotency.
- Human approval for irreversible actions.
- RAG quality evaluation.
- VLM pre-order gating if VLM is advertised.
- Smoke tests.
- Secret rotation.
- Rollback.
