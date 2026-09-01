# L2 evidence relations, resumable investigation and UI — 2026-09-01

## Scope and release

Implemented the next L2 slice, not a complete L3 recovery system.

- Branch: `codex/v4-live-evaluation`, HEAD `f8e4a41`.
- Existing merge (`MERGE_HEAD=ad73cc4`), staged changes and unrelated files preserved.
- Staging release: `20260901-evaluation-m3-3`, build `2026-09-01.3`.
- Eleven Agent runtime files changed; 41-file runtime snapshot and 100 frontend
  files verified. Backend, environment, API keys and model unchanged.
- Engine identity is now `multi-agent-v5`; old investigation history remains.
- Model: `gpt-5.4-mini`. Periodic scheduler remains off; L3 remains blocked.
- No commit/push/merge completion, judge-host changes, or real OA send.

## Evidence and causal scope

Each observation is related independently to each supported hypothesis using
`supports`, `contradicts`, `context`, or `unavailable`. Server rules derive these
relations from read-only observations. The model may propose links, but invented
IDs or incorrect links are rejected within the existing one-repair allowance.

For example, a clear Chromium hit-test can oppose an overlay hypothesis in the
isolated document. It does not oppose a metadata size mismatch. Stable delivery
is contextual measurement, not proof that configuration drift is absent.
Conflicting direct observations remain ambiguous even when the model omits them.

The three currently typed hypotheses are click obstruction, creative/catalog
mismatch and order/baseline configuration drift. They are NOT an exhaustive
root-cause catalogue. A scoped supported observation does not prove KPI causality
or validate publisher runtime. No probability percentage is invented.

Published typed summaries/limitations are server-derived, rather than unvalidated
model causal prose. Incident Q&A uses the same relation validation, bound to the
current bundle/revision; the model selects relevant citations, while public
explanation uses scoped findings and probe summaries. Legacy bundles retain their
old contract. Config comparison now lists only actually compared fields and
explicitly records missing fields, instead of describing untested fields as matching.

OpenAI structured-output guidance informed the nested strict relation schema:
https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas
Schema validation does not replace semantic server checks or ownership.

Creative Inspector now has a minimum evidence contract: both `inspect_render`
and `creative_compatibility` must be collected before finishing, even when one
looks healthy or enough. Remaining tool slots are reserved for required probes;
the three-tool ceiling is unchanged. Missing observations stay explicitly
unavailable. This was added after the first live suite exposed omitted metadata
inspection (see below), not by weakening the grader or forcing an expected cause.

## Resume and interruption semantics

An input fingerprint covers engine/model/provider, policy/revision, sanitized
report facts, baseline/order/catalog, date window and isolated document fixture.
Only matching campaign/scope/revision/tool-version observations are reused.
Changed inputs invalidate cached evidence. Transient tool errors are not reused;
the factual absence of a fixture remains unavailable, never healthy.

Completed specialists are retained. Failed specialists continue with collected
evidence rather than repeating successful tools. A crash during a read-only tool
can replay that pending tool without purchasing its model decision a second time.
Model reservations still count across restarts: 24 calls, up to three attempts,
three tools per specialist per input attempt, two coordinator delegations, and
one shared protocol/provider repair per role/attempt.

Worker publication and cached-bundle retry recheck the input fingerprint. Q&A
also checks it before answering/replaying. A stale job may be explicitly requeued
within its existing budget; automatic triggers do not revive stale results.

Progress records distinguish model/tool time, completed/unavailable/interrupted
steps, safe error codes, attempt and reused evidence. Completion counts are not
diagnostic confidence or a safety pass rate.

## UI

The existing Campaign Management / Live Evaluation page now shows:

1. Specialist/coordinator progress, safe errors, timing details, attempt and budget.
2. Independent hypothesis cards with scope, direct support/opposition and gaps.
3. Expandable evidence source, observation time, ID, screenshot and bounded raw facts.
4. Resume instead of duplicate submission; disabled controls for active/exhausted
   or completed current-revision jobs, preserving new engine/revision eligibility.

Card layout responds to content width, not just browser width, because management
has both navigation and a Campaign Agent sidebar. The mobile view remains inside
the existing Campaign/Agent navigation. Polling clears recovered connection
errors separately from action errors. Historical investigation display is retained.

Scenario Lab stays in Analytics; this slice did not add presets or rebuild any
existing production campaign report. Its existing scenario -> L1 -> L2 path was
used in local verification.

## Validation

- Focused Evaluation/investigation/evidence/Q&A/Zalo: **245 passed**.
- Frontend: **209 passed**, production build passed (existing chunk-size warning).
- Full Agent regression: **794 passed, 6 known baseline failures** (old Brief/Order
  date fixtures, Responses mocks, audience NameError and reasoning ordering).
- Python compilation and whitespace checks passed.
- Browser loopback fixture: real Chromium observations with a scripted model and
  memory persistence. Scenario applied, L1 opened an incident, two injected model
  timeouts produced a partial investigation. Resume went from 6 to 8 calls of 24
  on attempt two, retaining both evidence observations, then completed.
- Evidence disclosure and Q&A citations/limitations rendered. Desktop 1280px and
  mobile 390px had no horizontal document overflow, including expanded evidence.
- Browser test identity was not replaced by the QA production account.

### Real-model acceptance, retained first pass

Release 1 / engine v3: **5/8 complete gates**, 60 calls. Diagnostic classification
passed 6/8, role execution 7/8, and evidence contract checks 8/8. Both metadata
cases were inconclusive because Creative Inspector never collected the metadata
probe; one unavailable-document case also failed after a timeout and invalid
action exhausted its shared repair allowance. All failures are retained in
`20260901-evaluation-m3-1/model-suite-initial.json` on the server.

This first pass motivated the minimum two-probe coverage above. Release 2 / v4
used the same model, same fixtures, same two repetitions per case, same maximum
budget and the same stricter diagnostic/execution/relation gates. It achieved
**7/8 complete gates**, 66 calls: diagnostic classification 7/8, role execution
7/8 and evidence contract 8/8. Both metadata cases collected the required probe
and were classified with metadata scope; the only failed gate had correct scoped
evidence but a Creative specialist failed after provider unavailable + timeout,
so the run remained partial/ambiguous. This is not a percentage estimate of
production reliability and the failed run was not erased or retried to get a pass.

Release-1 public HTTP QA passed: durable job completed after eight calls and one
recovered timeout; Q&A plus same-request replay passed; L3 actions returned 409;
report/analytics facts and six analysis hashes stayed consistent. No OA messages
were enqueued and the isolated QA policy was disabled afterward. This is not
evidence that all six report AI analyses avoided fallback.

Release-2 public HTTP investigation completed with all three roles after eight
calls. Its first Q&A call failed closed on a provider error. The same-request
retry then exposed a false stale check: toggling the QA policy changed scheduler
timestamps, although the semantic policy version and all evidence inputs stayed
the same. Engine v5 removes scheduler/lease timestamps from the fingerprint while
still hashing every effective policy field. A focused regression proves timestamp
changes keep the signature stable and threshold changes invalidate it. Final v5
HTTP acceptance is recorded below.

Release 3 / engine v5 public HTTP acceptance passed. The durable investigation
completed on its first attempt after eight model calls, with Performance,
Creative and Coordinator roles all complete and no worker errors. It produced
typed, independently scoped hypothesis cards and selected
`creative_contract_mismatch` from cited metadata evidence. The fixture also
contained click-overlay evidence, so this validates multi-hypothesis handling,
not proof of a single isolated root cause. Q&A passed and an identical request
replayed the stored response without another model call; the answer remained
conservative and included citations and limitations. Analytics/report facts
matched across 20 records and all six analyses shared the active input hash.
Every L3 mutation endpoint returned 409, no Zalo OA message was enqueued, and the
QA policy was disabled after the run.

## Deployment and rollback

Preflight confirmed host `momolita`, zero queued/running Autopilot and L2 jobs,
unchanged previous file hashes, scheduler off and unchanged model. Only
`agent-api` restarted. Immutable frontend release link switched after runtime
copy, backups and checks. Node `adspilot-api` was not restarted.

Server artifacts are private under:
`/var/backups/advertising-agent/evaluation/20260901-evaluation-m3-3/`.

Rollback (on the verified staging host only):

```sh
cd /var/www/agent-api
venv/bin/python /tmp/evaluation_vps_release.py rollback /tmp/20260901-evaluation-m3-3.tar.gz
```

Rollback restores the prior runtime/frontend and quarantines new runtime files;
it does not delete campaign reports, QA data or investigation history.
Release 3 is an Agent-only delta over release 2. Rolling back farther requires
release-2 then release-1 rollback, in reverse order.

## Remaining work

- Broader blinded scenarios, simultaneous causes, provider reliability and true
  publisher/runtime evidence. Three typed hypotheses do not complete L2.
- Report AI fallback investigation and full Scenario Lab acceptance matrix.
- A named authorized OA QA recipient for actual notification/reply/FAQ/create
  collision tests; unit routing tests and zero sends are not real OA acceptance.
- L3 proposal/approval/execution/verification remains closed until these gates pass.
