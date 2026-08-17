# Drill 001 — simulated primary model outage

Date: 2026-07-15
Environment: isolated local agent container
Customer impact: none; synthetic prompt only, no order or workspace mutation

## Scenario

The primary MaaS endpoint was replaced with a black-holed localhost port. SDK retries were disabled for the drill, the circuit threshold was set to one failure, and the normal cross-provider fallback remained forbidden by the `confidential` data classification.

## Timeline and evidence

| Event | Result |
|---|---|
| First generation call reaches unavailable primary | `APIConnectionError` after 0.367 s |
| Circuit state after transient failure | Open |
| Second generation call | `CircuitOpenError` in 0.000 s; no network wait |
| Cross-provider request | Not attempted; fallback client absent under classification policy |
| User response behavior | Graph regression test returns the fixed Vietnamese provider-unavailable response and preserves workspace state |

The automated drill is `scripts/drills/provider_outage.py`; provider routing, open/close behavior, non-retryable errors, fallback parameter adaptation, and safe graph degradation are covered by `agent/tests/test_provider_resilience.py`.

## Detection

- `agent_llm_provider_events_total{provider="primary", outcome="error|bypassed"}` records provider routing failures.
- Prometheus loads `AgentPrimaryModelUnavailable` after repeated failures.
- The Grafana Agent Ops dashboard shows provider route/outcome and LLM latency.
- Request IDs correlate the user request, agent log/trace, and backend log.

## Why the fallback did not run

This is expected policy, not a failover defect. Cross-provider generation requires all of the following:

1. `ALLOW_OFFSHORE_LLM_FALLBACK=true`;
2. a configured fallback endpoint/key/model; and
3. the current `DATA_CLASSIFICATION` in `LLM_FALLBACK_ALLOWED_CLASSIFICATIONS`.

The default classification is `confidential`, while the default allowed list is `public,internal`. A provider outage must not silently broaden where campaign data is processed.

## Corrective actions completed

- Explicit 45-second provider deadline and one bounded SDK retry.
- Thread-safe circuit breaker with a 30-second cooldown.
- Fallback only for timeout/network, HTTP 429 and HTTP 5xx; never for authentication or invalid requests.
- GPT-5-family fallback parameter adaptation (`max_completion_tokens`, no unsupported temperature).
- Friendly deterministic degraded response with no upstream exception text.
- Prometheus provider-routing counter, alert rule, dashboard panel, and Langfuse route metadata.

## Follow-up before public release

- Run a second drill with a formally approved `public` synthetic payload and a configured secondary provider, then verify a real response and trace route.
- Define the operator who may change data classification/fallback policy and record that change in release metadata.
