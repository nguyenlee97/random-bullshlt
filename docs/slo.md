# Advertising Agent service-level objectives

These objectives apply to the local release candidate and future staging environment. They are measured from Prometheus; model-quality gates remain in the evaluation scoreboard.

| Signal | Objective | Window |
|---|---:|---:|
| HTTP availability (non-5xx) | ≥ 99.5% | rolling 30 days |
| Guided deterministic form request p95 | < 3 seconds | 10 minutes |
| Freeform chat p95 | < 8 seconds | 10 minutes |
| Audience recommendation p95 | < 20 seconds | 10 minutes |
| Creative VLM verdict availability | ≥ 95% within 20 seconds | 1 hour |
| Level-3 hardcoded fallback rate | < 2% of tool turns | 15 minutes |
| Duplicate order rate | 0 | release lifetime |
| Unauthorized order launch | 0 | release lifetime |

The model-provider deadline is 45 seconds by default. A provider timeout is therefore a controlled degraded request, not an unbounded hang. Cross-provider fallback is disabled unless both the operator switch and data-classification allow-list permit it.

## Correlation

Every HTTP response carries `X-Request-Id`. The same value appears in agent logs, Langfuse generation metadata, outbound order requests, Express logs, and persisted backend API logs. User-supplied IDs are accepted only when they match a 64-character safe alphabet; otherwise a new ID is generated.

## Alert response

- Availability or chat latency alert: inspect the Agent Ops dashboard, then group errors by request ID.
- Primary-model alert: confirm circuit state and provider status. Keep fallback disabled when the current data classification forbids it.
- Hard-fallback alert: inspect trace inputs after redaction, compare the latest offline evaluation, and roll back the model/prompt change if quality regressed.
- Duplicate or unauthorized order: stop campaign launches immediately. Preserve order/workspace evidence and exercise idempotent rollback procedures.
