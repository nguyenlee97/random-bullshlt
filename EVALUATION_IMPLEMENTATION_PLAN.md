# Evaluation loop: deterministic L2 foundation and Analytics Scenario Lab

Date: 2026-08-31. Branch: `codex/v4-live-evaluation`.
This describes the original local slice. No commit, push or hackathon changes.
Subsequent production-staging deployment and live acceptance findings are in
[VPS acceptance on 2026-08-31](EVALUATION_VPS_ACCEPTANCE_2026-08-31.md).

## Multi-agent follow-up (2026-08-31)

The checked T1-T9 below describe the earlier **deterministic playbook** slice,
not completion of the original multi-agent L2 requirement. The next implementation
is documented in [EVALUATION_MULTI_AGENT_M1.md](EVALUATION_MULTI_AGENT_M1.md).
It adds an opt-in, durable specialist/coordinator queue, independently rendered
click-overlay evidence, UI progress, and asynchronous Web/Zalo integration.
Live provider quality, real Mongo concurrency and OA delivery are still separate
validation gates; L3 remains disabled.

## Scope and task list

- [x] T1 Integrate the committed V4 Campaign Management foundation without committing.
- [x] T2 Make report scenario apply idempotent, revision-checked and serialized; expose an immutable active snapshot to readers.
- [x] T3 Fix policy cache invalidation, run completion/retry, incident recurrence and data-quality resolution safeguards.
- [x] T4 Complete L2 playbooks for all L1 issue types; distinguish insufficient evidence and ambiguity from a supported hypothesis.
- [x] T5 Persist full investigation history; scope manual investigation by policy, ownership and dataset revision.
- [x] T6 Keep Zalo correlation independent; display honest L2 results, retry notifications and block incomplete recovery executors.
- [x] T7 Build Scenario Lab on the Report/Analytics site (campaign only), with preview, explicit apply, baseline reset, history and evaluation feedback.
- [x] T8 Mount Evaluation in Campaign Management; display policy, incidents, evidence, hypotheses and history; link to Analytics for scenarios.
- [x] T9 Verify actual JavaScript scenarios through Python L1/L2, authorization, stale revisions, retries and UI/build regressions.

## Technical approach

### Report facts

Preserve legacy readers and generation. Scenario revisions hold both records and all six analyses. Build the revision before publishing it, then atomically compare-and-set the campaign active revision. Readers of scenario-managed reports use that immutable snapshot. A per-campaign lease serializes applies; a caller request ID plus payload hash deduplicates retries and rejects key reuse with different parameters. Expected revision prevents overwriting a newer scenario. No browser receives an internal backend key.

### Evaluation lifecycle

Hash effective policy content to invalidate cached runs. Mark runs complete only after incident persistence, investigation and notification enqueue have succeeded; failed stages stay retryable. Serialize campaign evaluation with a lease, while external notification delivery remains the existing durable outbox's responsibility. Reopen recurring resolved incidents, retain dismissed decisions, and do not resolve performance incidents just because data is missing. Register evaluation when a user first opens campaign management/evaluation; background worker remains opt-in.

### L2

Cover delivery, CTR, creative, tracking, configuration, pacing, trend and data-quality incidents. Rules rank hypotheses rather than claim causal probabilities. Missing required evidence yields `insufficient_evidence`; close competing scores yield `ambiguous`. Technical scenario signals retain provenance. Catalog alternatives remain unverified candidates until booking/creative checks. Full immutable bundles are stored separately with dataset/policy/engine version and input fingerprints; stale investigations cannot overwrite newer evidence. L2 performs no campaign or report mutation.

### Safety boundary

Ownership is checked on every Agent API access. Unsafe cookie requests use existing CSRF protection. Evaluation policy bounds investigation authority. L3 state-only actions and the incomplete legacy Zalo baseline recovery are disabled until a common approved executor is implemented. Baseline reset remains an explicit Scenario Lab operation, not automatic remediation. No OA messages are sent in verification; use mocked transport.

### UI and session boundary

Scenario controls live in Analytics, enabled only for one selected campaign. Use an Agent-origin embedded controller so HttpOnly identity/CSRF cookies and anonymous ownership do not need cross-site copying. The controller validates parent origin; only a successful apply notification crosses the frame boundary, causing charts to reload. No token or data is accepted from arbitrary postMessage origins. The Agent Campaign Management page owns policy, incidents and L2 investigation, linking to Analytics for scenario editing.

### Verification and limits

Use the real JS preset engine as test input, not a Python reimplementation. Test missing sources, recurring incidents, policy changes, failed notification retries, disabled recovery, ownership and optimistic concurrency. Run backend/Analytics/Agent UI tests and builds; browser-check local UI with fixture services if live services are unavailable. Simulated data remains simulated internally; no claim of measured publisher effectiveness. Record remaining integration/environment blockers explicitly.

## Result and entry points

- Working branch remains `codex/v4-live-evaluation`, HEAD `f8e4a41`.
- Incorporated committed V4 foundation `ad73cc4` with a no-commit merge. Conflict in `agentApi.js` is resolved, but `MERGE_HEAD` intentionally remains. Incoming V4 files are staged; current feature edits are unstaged/untracked. Do not assume the branch was committed or pushed.
- Preserved the stale Git lock as `index.lock.stale-20260831` in this worktree's Git metadata after checking there was no active Git process.
- Analytics: select a campaign -> **Giả lập tình huống** -> preset/placement/parameters -> **Xem trước** -> **Áp dụng & chạy Evaluation**.
- Reset: **Chọn khôi phục baseline**, then preview and apply. This creates a new dataset revision; it is not an approved L3 recovery.
- Agent: `/manage/campaigns/:id` -> **Live Evaluation**. L1 is the default. Choose L2 and run evaluation to collect investigation evidence. Report tab links to Analytics; overview and directory show evaluation health.
- Scenario controller: Agent UI `/evaluation/scenarios?campaignId=...`, embedded from Analytics. It uses the same owned Agent API as the main UI.

### Core files

- `backend/services/reportDatasets.js`: baseline migration, lease, optimistic revision, request replay, six-analysis publication, active snapshot readers.
- `backend/routes/analytics.js`: aggregate/campaign readers overlay scenario snapshots without duplicate legacy rows.
- `agent/evaluation/engine.py`: L1 recent-window CTR, duplicate-row aggregation and data-quality guards.
- `agent/evaluation/probes.py`, `playbooks.py`, `investigator.py`: read-only evidence, eight issue-type playbooks, rule-weight ranking and versioned bundles.
- `agent/evaluation/service.py`, `store.py`: lifecycle, policy hashes, leases, retries, history, recurrence and summary.
- `agent/zalo_incidents.py`: independent incident context, L2 replies and disabled legacy recovery.
- `analytics_frontend/scenario-lab.js`, `agent_frontend/src/components/ScenarioLabPage.jsx`: embedded controller and exact-origin message boundary.
- `CampaignEvaluationWorkspace.jsx`: Scenario Lab and Evaluation controls, evidence/history UI.

### Actual Agent API surface

All paths below have prefix `/api/agent/evaluation/campaigns/{campaign_id}`; ownership is checked before data access.

| Method | Suffix | Purpose |
| --- | --- | --- |
| GET | empty | policy, incidents, latest run, summary, worker configuration |
| PUT | /policy | level, enabled flag, schedule and thresholds |
| POST | /runs | manual evaluation; optional force |
| GET | /scenarios | presets, placements and revision history |
| POST | /scenarios/preview | baseline-derived preview and expected current revision |
| POST | /scenarios/apply | requestId + expectedRevision; returns separate scenario/evaluation outcomes |
| GET | /incidents/{id} | current incident and full investigation history |
| POST | /incidents/{id}/actions | investigate, dismiss, false_positive; incomplete L3 actions return 409 |

## Validation performed on 2026-08-31

- Backend: **85/85 passed**, including nine new dataset lifecycle/reader tests.
- Agent UI: **200/200 passed**, production Vite build successful. Existing >500 KB bundle-size warning remains.
- Analytics: **8/8 passed**, including URL and exact-origin/frame/campaign message checks.
- Focused Agent (evaluation, L2, Zalo, campaign directory): **165 passed**.
- Full Agent: **709 passed, 6 failed**. Re-ran the same six failures against a clean archive of HEAD `f8e4a41`; all six reproduce there:
  - expired ZPlay brief date fixture;
  - two OpenAI proposal tests whose mock lacks `responses.parse`;
  - existing undefined `proposal` in the later audience-approval path;
  - targeting reasoning-order expectation;
  - order-guard fixture end date 2026-08-10 is in the past.
- The L2 test helper now invokes the real Node `reportScenarios.js` engine via JSON, replacing the previous Python mirror.
- Real-preset integration caught a whole-flight CTR averaging bug in `multiple_issues`. L1 now uses recent policy windows; L2 metric probes receive the same dates.
- Browser QA used the real Analytics/Agent frontends with a loopback-only fixture API and real Python L1/L2 (not a live DB/OA):
  - campaign selection enabled Scenario Lab; aggregate mode disabled it;
  - preview showed before/after data; apply created revision 2;
  - Multiple issues changed chart totals from 100,000/1,000 impressions/clicks to 77,500/724 and created delivery + CTR incidents;
  - switching policy L1 -> L2 ran investigation and rendered evidence/uncertainty in Campaign Management;
  - baseline reset created revision 3, restored charts, and left zero open incidents after evaluation;
  - inspected the default desktop layout visually; no claim of mobile or production browser validation.
- `git diff --check` and staged diff checks passed (line-ending conversion warnings only).
- No live Zalo messages, production writes, deployment, push or commit.

### Reproduce UI QA locally

From `agent/`: `python -m tests.manual_evaluation_server` (binds only 127.0.0.1:18765).

Start the Agent UI with process-local `VITE_AGENT_URL=http://localhost:18765` and `VITE_BACKEND_URL=http://localhost:18765`, then `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5175 --strictPort`.

Serve `analytics_frontend/` with `python -m http.server 5174 --bind 127.0.0.1`.
Open `http://localhost:5174/?apiBase=http://localhost:18765/api&campaignId=ORD-2026-001`.

The fixture bypasses real authentication for its single hard-coded test campaign and mocks report persistence/analysis generation. It must never be used as a deployable API. Its purpose is UI testing only.

## Remaining work / explicit limitations

1. **Staging integration gate:** actual Mongo index creation and multi-process concurrency, old-dataset migration on a backup, Agent cookie/CSRF across the deployed Analytics iframe, proxy timeouts and OA delivery receipts still require a staging smoke test. Local model adapters are not a substitute for that check.
2. **L2 evidence depth:** no publisher runtime screenshots/VLM, live inventory/booking checks or creative experiment outcomes. Catalog alternatives are candidates, not validated substitutes. Rule scores are not calibrated causal probabilities. Full-flight trend/fatigue probes remain heuristic; the recent-window metric evidence is recorded separately.
3. **L3:** action registry/proposal model, owner-bound expiring approval nonce, shared Web/Zalo executor, audit/rollback and post-change verification windows remain unimplemented. Legacy Zalo baseline-recovery and Web state-only recovery actions are blocked. Scenario recovery presets do not prove a real recovery succeeded.
4. **Notification UI:** shows enqueue-request count, not provider delivery confirmation. Existing OA outbox handles dedup/retry; no new end-to-end delivery monitor or notification preference UI is included.
5. **Product follow-ups:** snooze/cooldown policy, incident Q&A chat, root-incident grouping across multiple issues, automatic evaluation registration for every order at creation, and cross-session history UI polish remain follow-ups.
6. **Scale:** snapshot documents embed records and six analyses, subject to Mongo's document-size limit. Analytics overlay currently aggregates records in application memory. Validate expected campaign volume before a broader rollout; chunk large snapshots and move aggregation server-side if needed.
7. **Runtime configuration:** Agent and backend must share `REPORT_INTERNAL_API_KEY`; automatic scheduling additionally requires `EVALUATION_WORKER_ENABLED=true`. It remains opt-in and was not enabled here. Agent `VITE_ANALYTICS_URL` must match the Analytics origin. Analytics defaults to `https://agent.pawgrammers.io.vn/`; custom installs must set `window.__ADSTACK_CONFIG__.agentUiBase` before the app module loads. Existing CSP/frame policies must permit the intended embedding, not arbitrary origins.
