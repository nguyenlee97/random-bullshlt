# M4.4 Durable Campaign Autopilot — Foundation Evidence

> Status: in progress. This checkpoint proves the durable orchestration
> foundation and the brief-to-creative-review path. It does not yet close the
> full M4.4 order-launch exit gate.

## Implemented

- Persisted `experience_mode` and `approval_policy` on the canonical workspace.
- Explicit `POST /api/agent/autopilot/runs` start API; phrase triggers are no
  longer required to create a run.
- Fixed allowlisted campaign capability graph. A model cannot invent tools.
- Durable `agent_runs`, `agent_tasks`, and `agent_run_events` collections.
- Idempotent run start, bounded task attempts, worker leases, expired-lease
  recovery, pause, resume, cancel, and task review.
- Three approval policies:
  - `review_every_stage`
  - `critical_only`
  - `auto_build_draft`
- Final launch review is mandatory under every policy.
- Artifact output is withheld from the canonical workspace until required
  review is approved.
- SSE event replay/live stream at
  `/api/agent/autopilot/runs/{run_id}/events`.
- Background worker readiness is included in `/ready`.
- Initial real capabilities: brief normalization and validation, deterministic
  strategy options, audience RAG, catalog-validated targeting, creative review
  checkpoint, zone ranking/conflict check, creative assignment, forecast,
  order draft, order guard, idempotent create, verification, and setup report.

## Automated evidence

- Focused Autopilot state/worker tests: **9 passed**.
- Full agent regression after the final policy adjustment: **123 passed**.

Covered invariants include:

- Missing brief cannot start a run.
- Duplicate start key returns the same run.
- Preferences increment the workspace revision without invalidating artifacts.
- Pause/resume/cancel preserve durable state.
- Review interrupts queue the correct dependency after approval.
- `auto_build_draft` still cannot auto-approve launch.
- Expired worker lease is returned to the queue.
- Auto-approved artifact output is committed through the transactional
  workspace service.
- Review-required output remains outside canonical workspace until approval.

## Live local Compose smoke

Run: `run_15038390b48541b19f6f17e61bc8bd1a`

Policy: `critical_only`

Observed task state:

| Task | Status |
|---|---|
| normalize brief | succeeded |
| validate brief | succeeded |
| generate strategy | succeeded |
| retrieve audience | succeeded |
| derive targeting | succeeded |
| analyze creatives | waiting review (`missing_creative`) |
| downstream placement/order tasks | queued or pending |

The agent container was restarted while the run waited for review. The same
run ID, current task, and `waiting_review` status were restored from MongoDB.
The event stream replayed every run/task event after restart. `/ready` reported
MongoDB, backend, RAG index, creative worker, and Autopilot worker healthy.

## Safety behavior proven

- A brief without creative does not fabricate a file or bypass the VLM gate.
- The run pauses with a resumable input request.
- Reviewed artifact values are committed only through revision-checked
  workspace operations.
- Launch remains a dedicated human-only checkpoint.
- Order creation uses a stable run-derived idempotency key and re-runs the live
  order guard immediately before the side effect.

## Remaining before M4.4 can close

1. Add the frontend opening mode selector and Autopilot intake.
2. Add plan/progress/review UI and SSE subscription.
3. Exercise creative upload, VLM completion, placement, forecast, order draft,
   final approval, create, verify, and report as one live end-to-end run.
4. Prove repeated launch approval creates exactly one order.
5. Add replan behavior for mid-run workspace edits and stale queued tasks.
6. Run the 20-brief Autopilot evaluation plus failure drills.
