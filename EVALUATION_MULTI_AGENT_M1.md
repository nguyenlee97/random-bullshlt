# Evaluation L2 multi-agent — milestone 1

2026-08-31. Local, uncommitted work on `codex/v4-live-evaluation` (HEAD `f8e4a41`).
The pre-existing no-commit merge of V4 and earlier feature changes are preserved.
At this local milestone no push, deployment, real OA message, or campaign mutation was performed.

Later deployment and real-provider acceptance results are recorded in
[VPS acceptance on 2026-08-31](EVALUATION_VPS_ACCEPTANCE_2026-08-31.md).
In particular, real-model L2 quality is not yet accepted.

Continuation: incident Q&A and additional Zalo isolation are implemented in
`EVALUATION_INCIDENT_QA_M2.md`. The boundaries below describe milestone 1;
the continuation document records the latest validation totals.

## Scope delivered in code

L1 detects a performance symptom, queues an incident-scoped investigation and
enqueues the initial Zalo alert without waiting for model work. A separate worker
runs specialist model loops, collects read-only evidence, lets a coordinator
commission additional specialists and review their results, attaches a versioned
bundle, then enqueues the investigation update. L3 is not part of this milestone.

This is not renaming deterministic probes into agents: each specialist makes
bounded structured model decisions to choose a tool, inspect its results, choose
another tool or finish. The deterministic probes remain tools and the explicitly
labelled fallback when multi-agent is disabled. No new campaign-creation run or
conversation is created for an investigation.

### Runtime and authority

- `agent/evaluation/agent_model.py`: isolated Responses structured-decision adapter,
  `store=False`, no shared campaign conversation, no automatic SDK retries; existing
  metrics record provider calls/tokens. The model is configured independently.
- `multi_agent.py`: initial issue-specific specialist assignment, parallel loops,
  coordinator with at most two additional delegations. Registry: Performance,
  Creative/Interaction, Setup, Placement. Four decisions per specialist; three
  coordinator decisions; 24 model-call reservations total, including restart attempts.
- `evidence_tools.py`: fixed campaign/scope/revision context. Model cannot provide a
  URL, actor, order ID, SQL, or mutation. Measurement rows use an allowlist and strip
  scenario/preset/flags before the model sees any tool results. Source text/images
  are untrusted data. Evidence carries ID, source, scope, revision and observation time.
- `investigation_jobs.py`: Mongo queue, `_id` dedup on incident/revision/policy/engine/model;
  atomic claims, 120-second token-fenced renewable lease, three processing attempts.
  Budget is reserved before API requests. No production in-memory fallback.
- `investigation_worker.py`: separate from the opt-in periodic L1 scheduler; starts
  when multi-agent is enabled. Rejects changed/disabled policy, changed model,
  closed incidents and stale dataset revisions before publication. Worker shutdown
  cancels children; expired jobs can be reclaimed with completed tasks retained.

Missing/failed tools are visible as unavailable, not healthy. Partial tasks can be
retried explicitly from Web/Zalo without resetting budget; completed tasks are
reused. Forged citation IDs are rejected. A supported coordinator hypothesis needs
at least two cited tool types and an observed anomaly; contradictions downgrade
certainty. This is a safety check, not proof that the model's causal reasoning is
correct. Live model evaluation remains required.

### Independent scenario evidence

`click_overlay` is preset 12. It lowers recent clicks/outcomes while preserving
impressions and spend, and sets no positive technical answer flag. L1 therefore
detects CTR regression, not a pre-labelled creative/tracking fault.

`backend/lib/investigationFixtures.js` creates bounded, self-contained test HTML
alongside dataset records. `runtimeFixture` publishes with the same immutable
revision as the six report analyses. Scenario labels never enter the page or
model's evidence. Healthy/reset fixtures make the overlay non-intercepting.

The Creative tool renders that HTML in isolated Chromium with external requests
blocked. It checks five hit-test points, tests the local in-memory click handler,
and captures a screenshot. It does not click a real ad or send publisher tracking.
Screenshot plus DOM observations can be passed to the creative model; browser
observations, not screenshot interpretation alone, establish the local hit target.

The remaining eleven presets retain their previous semantics. They have NOT all
been upgraded to independent runtime/config/telemetry environments. Missing runtime
fixtures are reported explicitly; no healthy publisher state is invented.

### UI, API and Zalo

- Existing owned `POST .../incidents/{id}/actions` with `action=investigate` returns
  202 + `investigation_job` in multi-agent mode; legacy mode remains synchronous.
- Existing campaign evaluation GET includes `investigation_mode`, job summaries
  and storage errors. Owned `GET .../investigations/{job_id}` returns job details.
- Campaign Management polls while mounted, ignores stale campaign responses, and
  shows per-specialist status/tools/results, coordinator review, budget/retries,
  evidence IDs/source/time and the captured screenshot. Reloading does not restart work.
- Zalo `2 INC-*` uses the same queue; initial detection and result notifications use
  distinct existing outbox keys (pending vs bundle ID). Alert/reply does not change
  `active_campaign_id` or unrelated `pending_action`. Notification retry reuses the
  stored bundle and stable outbox key, avoiding another model investigation.
- No incident free-form Q&A, generalized concurrent approval namespace, delivery
  receipt monitor, recovery approval or executor is claimed here.

## Configuration (not enabled in this checkout)

Agent `.env.example` documents:

```dotenv
EVALUATION_MULTI_AGENT_ENABLED=false
EVALUATION_AGENT_MODEL=gpt-5.4-mini
```

To exercise the actual provider path, enable the flag in an authorized environment
with existing `OPENAI_API_KEY`, working Mongo, Chromium installed via Playwright,
and matching Agent/backend `REPORT_INTERNAL_API_KEY`. Enable L2 on the owned
campaign. This permits scoped investigation evidence/screenshots to reach OpenAI.
The periodic L1 scheduler still separately requires `EVALUATION_WORKER_ENABLED`.
No real environment file or deployment config was changed in this milestone.

The structured decision implementation follows the existing Responses/Pydantic
pattern in the repo and the [official tool-loop guidance](https://developers.openai.com/api/docs/guides/function-calling).
Strict structure does not replace server-side authorization or tool allowlists.

## Validation

- 27 new Agent tests: actual JavaScript scenario, real headless Chromium observation,
  counterfactual healthy document with unchanged low metrics, hidden ground-truth,
  role tool isolation, invalid citations, partial/provider failure, delegation,
  persisted budget, resumed tasks, queue dedup/fencing/retry, API ownership, Zalo
  context separation, immediate L1 enqueue and mid-investigation revision change.
- Provider adapter tested with mocked structured responses; **no live model calls**.
- Queue tests use an in-memory Mongo-shaped adapter; **not real Mongo/multi-process validation**.
- Backend: 87 passed. Agent UI: 203 passed; Vite production build passed with existing
  >500 KB chunk warning. Analytics: 8 passed.
- Full Agent: 735 passed, 6 failed. Same six failures recorded by the previous slice:
  expired ZPlay intake date, two mocks lacking `responses.parse`, undefined audience
  `proposal`, targeting reasoning-order assertion, expired order-guard date.
- Browser QA: real Agent UI with loopback fixture API, scripted model, real queue
  functions/orchestrator/Chromium; preview 100,000 impressions and clicks 1,000 -> 700,
  apply revision 2, CTR incident, specialist/coordinator result and screenshot visible.
  A second apply advanced to revision 3; the management poll displayed the new job
  without reloading, and reload preserved completed job results and model-call counts.
  This does not validate deployed authentication, Mongo, publisher runtime, or OA delivery.

### Reproduce UI check without external services

From `agent/`: `python -m tests.manual_multi_agent_server` (127.0.0.1:18766).
Start Agent Vite on port 5176 with process-local `VITE_AGENT_URL` and
`VITE_BACKEND_URL` both `http://localhost:18766`. Open
`http://localhost:5176/evaluation/scenarios?campaignId=ORD-2026-001`, choose the new
click-overlay preset, preview/apply, then open `/manage/campaigns/ORD-2026-001`.

This harness intentionally replaces identity, model, persistence and OA with test
adapters. Never deploy it. It is separate from the actual application entry point.

## Next gates and remaining work

1. Run labelled positive/negative/missing-evidence cases against the real configured
   model with bounded cost; verify citation relevance and causal overclaim rates.
2. Real Mongo index/claim/crash concurrency and deployed cookie/CSRF integration.
3. Extend independent evidence to configuration drift, telemetry delay, alternative
   booking and creative compatibility; connect authorized publisher read-only tools.
4. Incident-grounded Q&A, stage-specific notification preferences/receipts and
   approved test-account OA smoke check.
5. L3 shared proposal/approval/executor/verification over genuinely new measurement
   windows. Baseline reset stays a Scenario Lab action, not remediation.

Other previously listed gaps (automatic monitoring registration on every order,
snooze/cooldown, root-incident grouping and snapshot scale) remain separate tasks.
