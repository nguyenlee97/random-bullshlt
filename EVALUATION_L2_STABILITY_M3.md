# L2 stability and evidence-scope patch — 2026-08-31

## Outcome and boundary

The scoped patch is deployed to the production VPS used as staging. L2 is safer
and more observable, but its real-model quality gate is **not fully passed**.
Do not describe the evaluation loop as production-ready or enable L3 on this basis.

- Branch: `codex/v4-live-evaluation`, HEAD `f8e4a41`.
- Existing uncommitted merge (`MERGE_HEAD=ad73cc4`) and unrelated changes preserved.
- No commit, push, merge completion, or judge-host changes in this work.
- Current release: `20260831-evaluation-m2-4`, build `2026-08-31.3`.
- Engine identity: `multi-agent-v2`; existing v1 investigation history retained.
- Model remains `gpt-5.4-mini`; API keys, environment and Node backend unchanged.
- Periodic L1 scheduler remains off. L2 jobs run on explicit/manual triggers.
- No actual Zalo OA recipient was linked to the QA account; no QA OA send or
  publisher mutation. L3 remains blocked.

## Changes

### Completion and bounded recovery from model errors

The server exposes at most three evidence tools per specialist, then removes all
tools for a reserved synthesis decision. A fourth tool cannot execute even if
the model asks for it. The coordinator has at most two additional delegations
and its own terminal decision.

Each role gets one shared repair/retry allowance: invalid protocol/citation, or
transient provider timeout/unavailability/incomplete output. Retrying a decision
does not repeat a collected tool. Refusals and unauthorized tools are terminal.
The existing persisted ceiling of 24 calls per investigation still applies,
including repair and crash/restart attempts. A role can still fail after its
allowance is exhausted; there is no silent deterministic success fallback.

Creative specialists must collect `inspect_render` before finishing. An
unavailable fixture is a recorded limitation, not evidence of healthy rendering.

Safe error codes distinguish invalid schema, invalid/unauthorized/duplicate tool,
unknown citation, unsupported cause, required evidence, forced finish, refusal,
incomplete response, provider timeout/unavailability and tool failure. The audit
stores code/phase/retry usage rather than raw provider error text.

### Causal scope and channels

The output separates the L1 symptom from `cause_code`, `cause_status`,
`claim_scope` and explicit limitations. Server validation requires cited evidence
appropriate to the selected cause:

| Cause | Required evidence | Maximum claim scope |
| --- | --- | --- |
| Click obstruction | Independently observed blocked center hit target and zero local click events | Isolated test document |
| Creative contract mismatch | Derived size/format mismatch against catalog | Creative metadata |
| Configuration drift | Derived order/baseline field change | Baseline/order comparison, not signed approval |
| None | Metrics may establish symptoms, not a cause | Unknown |

Missing publisher validation is always a limitation. The server does not infer
publisher causality from a screenshot, local click, metadata mismatch or CTR loss.
Actual opposing evidence prevents a supported assessment; current validation is
still conservative when the model incorrectly labels an unrelated observation
as counterevidence (see the remaining failure below).

Incident Q&A is bound to the current dataset/bundle and cannot introduce a new
cause beyond the investigation. Web displays scope, limitations and partial/error
states. Zalo alert/Q&A formatting carries the same scope limitations. Existing
incident correlation, active campaign and pending-action routing were not changed.

The OpenAI structured-output guidance informed distinct refusal/incomplete/schema
handling. Structured output is not treated as semantic proof: server evidence
validation remains mandatory.

## Real-model counterfactual suite

The suite uses the deployed orchestrator, real model and real Chromium with
identical low-CTR measurements. Only the isolated document/metadata changes.
Scenario labels and expected answers are not supplied to the model. Persistence
and ownership are tested separately through public HTTP/Mongo, not mocked into
this model-quality suite. Each case runs twice, at concurrency two.

First pass (release 3): **4/8**, 65 model calls. This exposed premature creative
completion, provider timeouts and confusion between counterevidence against the
selected hypothesis versus evidence against a different hypothesis.

After the bounded retry, mandatory render and prompt-contract patch, release 4:
**7/8**, 69 model calls, unchanged model and grading criteria.

| Case | Repetition 1 | Repetition 2 |
| --- | --- | --- |
| Overlay, matching metadata | Pass, 7 calls, scoped click-obstruction hypothesis | Pass, 8 calls |
| Clear document, same CTR loss | Pass, 9 calls, unknown cause; recovered one timeout | Pass, 8 calls, unknown cause |
| No document available | Pass, 10 calls, explicitly partial/unknown; recovered one timeout | Safety gate pass, 9 calls; performance specialist failed after two timeouts |
| Metadata mismatch, clear document | Pass, 8 calls, metadata-scoped hypothesis | **Fail**, 10 calls; correct cause/scope but ambiguous assessment |

The last case incorrectly used a healthy render observation as counterevidence
against a metadata mismatch. The conservative server downgrade retained
`ambiguous`. It did not falsely claim publisher causality, but the classification
is inconsistent with the fixture's scoped expectation. A future typed relation
contract should separate support, contradiction and exclusion of alternative
hypotheses, instead of depending on prose instructions alone.

The no-document safety gate intentionally expects a partial result. Its passing
grade must **not** hide the remaining specialist/provider reliability failure.
Eight cases are a small acceptance sample, not a measured production success rate.
Neither failed run was erased or retried until it happened to pass.

Server-only artifacts (mode 0600):

- `/var/backups/advertising-agent/evaluation/20260831-evaluation-m2-3/model-suite-initial.json`
- `/var/backups/advertising-agent/evaluation/20260831-evaluation-m2-4/model-suite-initial.json`
- `/var/backups/advertising-agent/evaluation/20260831-evaluation-m2-4/http-stability.json`

## Local and browser validation

- Focused Agent evaluation/investigation/incident/Zalo suite: **230 passed**.
- Frontend suite: **205 passed**; production build passed (existing chunk-size warning).
- Python compile and `git diff --check` passed.
- Final full Agent regression: **779 passed, 6 failed**. These are the same
  pre-existing unrelated failures: expired Brief/Order date fixtures, two SDK
  mocks without `responses.parse`, an undefined audience proposal, and targeting
  reasoning ordering. The full suite is not green; they were not changed here.
- Browser: deployed Management/Live Evaluation renders in the existing anonymous
  identity, read-only; no existing campaign's policy or data was changed.
- Browser: local loopback fixture exercised scenario apply -> L1 -> L2 -> rendered
  uncertainty/scope/limitations, then a Q&A submission with citations/limitations.
  It uses a scripted model and memory persistence, not production auth/provider
  evidence. Desktop width 1280 showed no horizontal document overflow. No mobile
  coverage or full production-browser Q&A submission is claimed.

## Deployment and rollback

Release 3 changed eight Agent runtime files and frontend assets. Release 4 changed
four Agent runtime files. Both preflights verified hostname `momolita`, no queued
or running Autopilot/L2 work, exact prior hashes and the prior frontend symlink.
Only `agent-api` was restarted. `adspilot-api`, Nginx and environment stayed intact.
Release 4 verified four changed files, the full 39-file runtime snapshot and all
100 frontend files; manifests
retain a full runtime snapshot for safe subsequent delta packaging.

Rollback to release 3:

```sh
python3 /tmp/evaluation_vps_release.py rollback /tmp/20260831-evaluation-m2-4.tar.gz
```

Rollback to the prior release-2 baseline then requires the release-3 rollback,
in reverse deployment order. Backups are server-only under the corresponding
release directories. Rollback does not delete the QA campaign, datasets or evidence.

## Next work (not shipped here)

1. Typed evidence relationships and broader blinded L2 acceptance, including
   multiple simultaneous causes and interruptions/timeouts. Keep safe uncertainty.
2. Investigate the report model fallback observed in the prior release; report
   facts/analysis hash consistency is not proof that all six AI analyses succeeded.
3. Named, explicitly authorized Zalo QA recipient for actual delivery/reply/FAQ/
   campaign-creation collision tests. Unit tests and zero sends are not OA E2E.
4. Only then implement/reopen L3 proposals, approval, execution and verification.

## Final HTTP/runtime completion record

- Reused the isolated paused QA campaign `EVAL-QA-20260831-M2`, existing revision 2
  and incident `INC-239833`. No new scenario/data revision or order mutation.
- Public authenticated investigate returned 202 and persisted job
  `IVR-a4f58c85d5c2909386ba27db` in Mongo. All three roles completed, one attempt,
  seven model calls, one bounded timeout retry, zero QA notification enqueues.
- Result: `click_obstruction`, `isolated_document`, `supported_hypothesis`, with
  explicit publisher/causality limitations. This campaign retains the earlier
  metadata confound; this result does not prove exclusion of all alternative causes.
- Replaying investigate returned the same completed job/call count.
- A real-model question returned citations and scoped limitations; identical
  request replay returned the stored answer. This verifies transport/provenance,
  not unrestricted semantic correctness of every sentence. In particular, one
  limitation said stable delivery "loại trừ drift cấu hình rõ ràng"; stable metrics
  alone cannot exclude configuration drift. Typed evidence relationships should
  also prevent this kind of unsupported exclusion in future synthesis.
- L3 prepare/start/verify/resolve each returned 409.
- Public report and Analytics readers still returned 20 rows, 700 clicks and six
  analyses with a single active input hash. Report AI fallback was not fixed here.
- QA campaign evaluation disabled again after the test. Test data/evidence retained
  for inspection. No OA delivery test and no real publisher interaction.
- Final Agent readiness and backend database health passed after cleanup.
