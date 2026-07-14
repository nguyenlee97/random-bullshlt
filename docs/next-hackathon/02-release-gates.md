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

## Gate 4 — Agent candidate

Required before LangGraph becomes non-optional:

- Multi-turn parity suite passes.
- Checkpoint restart test passes.
- Auto mode cannot create an order without confirmation.
- Tool failures produce useful degraded responses.
- No stale response or cross-session state leakage in soak testing.

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
