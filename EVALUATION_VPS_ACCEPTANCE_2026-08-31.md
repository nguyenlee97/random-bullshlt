# Evaluation production-staging deployment and acceptance

Update: the subsequent L2 patch and its actual acceptance results are recorded in
[`EVALUATION_L2_STABILITY_M3.md`](EVALUATION_L2_STABILITY_M3.md). The results below
remain the original release-2 evidence, not the current release status.

Date: 2026-08-31. This supersedes the **not deployed/not tested with real providers**
status of the earlier local M1/M2 notes; those notes remain historical evidence.

## Deployment outcome

- Branch `codex/v4-live-evaluation`, HEAD `f8e4a41`, existing no-commit merge
  `ad73cc4` preserved. No commit, push, or merge completion in this deployment.
- Deployed the current dirty working tree using a SHA-256 file manifest, not just
  the initial feature commit. Build `2026-08-31.1`.
- Release `20260831-evaluation-m2-2`; 38 runtime files plus changed Agent UI assets.
- VPS hostname verified as `momolita`, reached through `agent.pawgrammers.io.vn`.
  PM2 `agent-api` and `adspilot-api` were restarted; Nginx topology was unchanged.
- Agent UI: https://agent.pawgrammers.io.vn/manage
- Analytics: https://analytics.pawgrammers.io.vn/
- Frozen judge host `zah-4.123c.vn` and its branches were not touched.
- Generated a shared internal report key on the VPS; no secrets were printed or
  downloaded. Existing application settings and provider models were preserved.
- Enabled the L2 background worker with `gpt-5.4-mini`. Periodic L1 scheduling
  remains **off** (`EVALUATION_WORKER_ENABLED=false`). L3 remains disabled.
- Report analysis still uses its existing `gpt-5.6-luna` configuration.

## Test boundary

Created one legitimate QA account without an OA link and one paused QA campaign,
`EVAL-QA-20260831-M2`. Baseline: two placements, ten dates, 20 rows, 100,000
impressions and 1,000 clicks. These are testing records, not paid publisher
execution. Auth, ownership, CSRF, public HTTPS, Mongo and provider calls were real.

QA credentials/cookies remain only in a root-readable server artifact. The QA
campaign is visible in the existing Analytics campaign selector. Its evaluation
policy was disabled after testing. The campaign/data/evidence were retained for
inspection, not deleted. No real publisher request, email, recovery action or OA
notification was sent by these tests.

Browser checks used the existing anonymous browser identity's owned campaign
`ORD-2026-037`, read-only: opened management, Live Evaluation, Analytics, the
Scenario Lab iframe and a preview. **Apply was not clicked on this existing
campaign.** The test did not log the browser into the QA account or claim its
existing campaign history. Preview left its active revision at 1.

## Actual acceptance results

| Check | Result |
| --- | --- |
| Public Agent readiness and backend health | Passed, including final check after QA disable |
| Public deployed version | `2026-08-31.1` |
| Scenario presets available | 12 |
| Owned preview/apply `click_overlay` | Passed: revision 1 to 2, L1 completed |
| L1 result | `ctr_regression`, incident `INC-239833`, scoped to `ZingNews_Masthead` |
| Immutable snapshot consistency | Passed: 20 rows and six ready analyses share the active hash |
| Public report and Analytics readers | Passed: same hash, 20 rows, 700 clicks after scenario |
| Repeated scenario request | Same revision, `replayed=true`, no duplicate dataset |
| Real L2 job | Executed, but **partial**, nine model calls, one attempt |
| Incident Q&A | Real answer with scoped citations; identical request replay reused it; one history item |
| Different user's read/run | Both rejected with 404 |
| Missing CSRF mutation | Rejected with 403 |
| Direct internal backend mutation without key | Rejected with 401 |
| L3 prepare/start/verify/resolve | Rejected with 409 |
| Mongo concurrency | 12 concurrent enqueues produced one job; 12 claims produced one winner |
| Mongo expired lease/new process | Reclaimed in a fresh process; saved task/call budget retained; stale owner could not write |
| Browser UI | Management and Live Evaluation render; Analytics iframe, 12 presets and preview table work |
| Browser width check | No horizontal overflow at the tested default desktop widths |
| QA Zalo notifications | `notification_enqueue_count=0`; no test recipient linked |

The Mongo concurrency test used the deployed queue functions against the **real
Mongo server in a dedicated QA collection**, `evaluation_vps_qa_jobs_20260831`.
It did not inject fake jobs into the live worker collection. Expiry was set on
that isolated test document to exercise reclaim without waiting two minutes.
This proves cross-process persistence/fencing, not a PM2 crash during an actual
paid model call. The completed QA document remains for inspection.

The UI check was desktop/read-only; it does not claim production browser submission
of Q&A, a mobile layout pass, every preset's end-to-end behavior, or OA delivery.

## Findings: L2 quality gate is not passed

### 1. Specialist completion budget is not reliably enforced

The real campaign's performance specialist selected four tools, then exhausted
its four decision iterations without producing a final result. The prompt says
at most three tools, but the dispatcher still offers the fourth tool. The job
correctly surfaced `partial` rather than claiming complete investigation.

Next fix: reserve a final synthesis decision deterministically; stop offering
tools after the allowed count and test the terminal behavior with real responses.
Do not simply raise an unbounded model-call budget.

### 2. The initial QA campaign contains a confound

Its creative metadata is 600x180 while the real masthead catalog expects 1160x250.
Chromium independently observed five hit targets landing on the overlay and zero
local click events, but the model emphasized the size mismatch. This initial run
does not prove it reliably isolated overlay as the root cause.

An additional bounded real-model pair used **identical low-CTR rows and matching
600x180 creative/catalog metadata**, changing only the isolated DOM. These are
in-memory model-quality fixtures using the deployed orchestrator, not two more
production campaign runs. No preset label was sent to the model.

| Case | Browser observation | Actual model outcome |
| --- | --- | --- |
| A: overlay | Hit-target mismatch, zero local clicks | Six calls, partial; both specialists hit `ValueError` before requesting render evidence; coordinator stayed ambiguous |
| B: clear DOM | Creative reachable, one local click | Eight calls, all tasks completed; summary explicitly left root cause unknown, but assessment was `supported_hypothesis` |

The A/B pair therefore **does not pass the diagnostic-quality gate**. Case A's
sanitized errors do not retain enough detail to distinguish invalid tool choice
from an invalid evidence reference; targeted safe error diagnostics are needed.
Case B shows that completed orchestration and valid citation IDs do not guarantee
a semantically appropriate assessment label.

Next fix: explicit tool-selection/citation failure codes, bounded repair where
safe, and a separate distinction between "symptom supported" and "cause supported".
Repeat the paired test; do not treat unknown cause as a supported causal finding.

### 3. Q&A is provenance-bound, not semantically verified

The answer used current incident evidence and retained the ambiguous assessment,
but connected size mismatch with the hit-target observation and did not fully
explain what remains unproven. Citation validation alone cannot validate the
causal explanation. Add evaluation criteria for limitations and confounding.

### 4. Report analysis frequently falls back

All six reports were ready, but readiness includes deterministic fallback.
Baseline generation logged rejection of an unknown finding ID,
`action_preserve_winner`; 4/6 baseline analyses used fallback. At active revision 2,
5/6 analyses had provider `deterministic_fallback` and reason
`model_unavailable_or_invalid`; only retention retained provider `openai`.
Do not infer that every revision-2 fallback had the same underlying cause.

Next fix: inspect typed report validation failures and align model finding/action
references with the report contract. Preserve safe fallback while improving
acceptance; do not remove citation checks merely to make reports look successful.

## Remaining unverified or disabled

- Live OA send, delivery receipt, reply correlation and interaction with FAQ/new
  campaign flows still need a user-designated Zalo test account. No arbitrary
  existing OA recipient was chosen. Local routing regressions are not live proof.
- L3 approval/execution/rollback/verification remains out of service.
- Periodic enrollment, all-preset independent evidence, mobile interaction and
  broad concurrent worker failure/recovery tests are not accepted by this run.
- Existing report/Analytics read endpoints remain public as before; new scenario
  mutations and Agent evaluation APIs are ownership/key/CSRF protected. This
  deployment is not a general backend authorization remediation.

## Release artifacts and rollback

Active frontend: `/var/www/evaluation-releases/20260831-evaluation-m2-2/frontend`.
Server backup: `/var/backups/advertising-agent/evaluation/20260831-evaluation-m2-2`.
It contains the manifest, previous runtime files, restricted env backups and
root-only QA artifacts. Do not copy those secret artifacts into Git or reports.

Rollback command on this verified VPS:

```sh
python3 /tmp/evaluation_vps_release.py rollback /tmp/20260831-evaluation-m2-2.tar.gz
```

Rollback restores runtime/env files and the prior frontend symlink and restarts
the two PM2 services. Newly added runtime files are moved to backup quarantine,
not deleted. **It does not delete QA accounts, datasets or new Mongo collections.**
The restore procedure is implemented and backup presence checked; a disruptive
rollback rehearsal was not performed.

The abandoned `20260831-evaluation-m2-1` upload was not deployed. Release 2 is the
only applied release. No broad cleanup or removal of prior releases was performed.

Local operational helpers: `ops/package_evaluation_release.py`,
`ops/evaluation_vps_release.py`, `ops/evaluation_vps_smoke.py`,
`ops/evaluation_vps_mongo_test.py`, `ops/evaluation_vps_model_pair.py`.
These are scoped one-off acceptance/release tools, not public app endpoints.
