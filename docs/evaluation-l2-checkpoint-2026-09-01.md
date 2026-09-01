# Live Evaluation L2 checkpoint — 2026-09-01

## Scope and safety boundary

- Branch: `codex/v4-live-evaluation`.
- Staging host: `*.pawgrammers.io.vn`; the frozen judge host was not touched.
- Deployed release chain: `20260901-evaluation-m5-1` → `m5-2` → `m5-3`.
- Agent build: `2026-09-01.4`; investigation engine: `multi-agent-v6`;
  evidence relationship contract: `evidence-relations-v3`.
- Periodic Evaluation worker remains disabled. L2 runs only from an explicit
  investigation request. L2 does not mutate campaign/report data or enqueue a
  Zalo notification. L3 actions remain fail-closed with HTTP 409.

## Implemented flow

Scenario Lab is hosted in Analytics and is linked from Campaign Management.
Each of the 12 presets exposes a minimum acceptance contract containing the L1
incident types, expected L2 hypotheses and evidence classes. Preview always
starts from the immutable baseline. Apply creates a new report dataset revision,
rebuilds active analytics and six analyses from the same facts, then runs L1.
The expectation contract is used by the UI and acceptance checks only; it is not
included in L2 model context.

L2 runs resumable specialist tasks with a bounded model-call budget:

1. Performance Analyst collects metric windows, delivery pattern and report
   completeness.
2. Creative Inspector checks creative compatibility and an isolated render;
   click telemetry is requested when the issue requires it.
3. Placement Investigator compares the observed placement with the real catalog,
   checks creative-compatible alternatives and explicitly reports booking and
   inventory availability as unverified.
4. Setup Auditor compares report-baseline and current configuration where the
   issue requires it.
5. Coordinator produces independent hypotheses with typed support, contradiction,
   context or unavailable relations. Invalid relations are repaired once and
   deterministic validation is applied before persistence.

The v3 relation contract permits only scoped claims. In particular, a measured
zero-click gap is not proof that a click handler or telemetry service failed;
catalog alternatives are not proof of bookable inventory; and report
completeness does not prove publisher correctness.

## Acceptance evidence

Local regression at the implementation checkpoint:

- Backend: 87 passed.
- Agent frontend: 210 passed and production build succeeded.
- Evaluation/Zalo-focused Agent tests: 237 passed.
- Full Agent suite: 800 passed, 6 pre-existing unrelated failures in dated
  fixtures/OpenAI mocks/guided-targeting ordering.
- Analytics frontend after the responsive patch: 9 passed.

The production Node scenario transformer was tested against Python L1 for all 12
presets. This exposed and fixed an ineffective-recovery fixture whose rounded CTR
did not reliably cross the z-score threshold.

The bounded real-model suite ran four counterfactual cases twice on staging
(`gpt-5.4-mini`, 80 calls total). The original grader reported 7/8 because the
unavailable-render case required `cause=none`. The failing output remained
partial and ambiguous but selected the independently supported
`click_measurement_gap`. The acceptance contract was corrected to allow that
narrow claim, and the saved artifact was regraded offline to 8/8 with zero extra
provider calls. Execution and typed-evidence gates were 8/8 in the original run.

Public HTTP acceptance then verified ownership, Mongo persistence, background
worker execution, replay idempotency, evidence-grounded Q&A, consistent report
revision/hash, zero notification enqueue, and all four L3 transitions returning
409. The job completed as `partial` because placement booking availability is not
available from the current catalog; this is an explicit limitation, not a failed
specialist.

Browser acceptance on staging verified Campaign Management, the Report link,
Scenario Lab, the Live Evaluation L1/L2-only control surface, and no console
errors. A mobile test found Analytics horizontal overflow caused by the campaign
select. The CSS was fixed and cache-busted as Analytics `v1.1.5`; at a 390 px
viewport the final document scroll width is 375 px.

Server artifacts are stored under:

`/var/backups/advertising-agent/evaluation/20260901-evaluation-m5-1/`

including the original model journal, offline regrade and HTTP acceptance result.
Every deployed patch has its own rollback backup and verified manifest.

## Remaining gates

1. Real Zalo OA E2E with a designated test user: alert delivery, reply-to and
   explicit incident-code routing, coexistence with FAQ/report/create-campaign
   flows, duplicate webhook/outbox handling, and confirmation isolation. This
   requires a user-controlled Zalo chat and must not use a production customer.
2. Decide whether and how to enable the periodic worker after measuring real
   investigation cost and cooldown behavior. It remains off for now.
3. Design and implement L3 proposal/action registry, risk/approval policy,
   idempotent execution, verification windows and rollback. No L3 executor should
   be enabled before those controls and Zalo correlation pass acceptance.
