# M4.4 Autopilot Replan and Launch-Boundary Evidence

> Status: complete for mid-run replanning. The remaining M4.4 exit work is the
> full creative-to-order live drill and the 20-brief evaluation.

## Implemented behavior

- The Autopilot worker detects canonical workspace revisions created outside
  the current Autopilot run.
- A changed artifact maps to an explicit plan task; that task and only its
  downstream dependants are reset.
- Unrelated succeeded tasks and their evidence remain reusable.
- Replans increment `plan_revision`, record `last_replan`, and emit a durable
  `run_replanned` event.
- Edits that arrive while a relevant task is running are deferred until the
  task reaches its revision-checked commit boundary.
- Waiting reviews are superseded when their inputs changed. Reviews on an
  unaffected branch remain valid.
- Missing-input retry is idempotent when the worker already observed the new
  input and replanned the task.
- The UI displays the plan revision and explains which artifacts triggered a
  replan and how many tasks were affected.

## Launch safety

- A brief, audience, targeting, creative, placement, assignment, forecast, or
  draft edit before launch resets the launch approval and order-creation path.
- Launch approval records the exact approved `order_draft` revision.
- The create-order capability rejects a stale/missing draft or an approval for
  an older draft before calling the order API.
- If an order has already been created, an upstream edit pauses and blocks the
  run instead of replaying the side effect.
- A blocked run cannot be resumed; the UI directs the operator to start a new
  campaign run.

## Automated evidence

- Focused Autopilot tests: **16 passed**.
- Full agent regression: **130 passed**.
- Frontend behavior tests: **6 passed**.
- Frontend production build: **passed**.
- Source whitespace validation: **passed**.

Covered cases include full brief replan, selective creative-branch replan,
stale launch-review rejection, post-order side-effect blocking, stale draft
rejection, mismatched approval revision rejection, and retry-review races.

## Live local Compose smoke

Run: `run_a3d99d3cbfa6464f91a70eb11602f3e4`

1. The run reached `analyze_creatives` and waited for the missing creative.
2. The canonical brief budget was edited from 40 to 55 million VND.
3. The worker preserved the run ID and advanced `plan_revision` from 1 to 2.
4. `last_replan.changed_artifacts` contained only `brief`.
5. The run recomputed from brief normalization and returned to the expected
   creative-review checkpoint.
6. The SSE backlog contained `run_replanned`.
7. `create_order` remained `pending`; no order side effect was released.

## Remaining M4.4 gates

1. Complete one live run with uploaded creative through VLM analysis,
   placement, assignment, forecast, order draft, guard, final approval,
   idempotent creation, verification, and setup report.
2. Repeat launch approval and prove exactly one order exists.
3. Run the 20-brief Autopilot evaluation and documented failure drills.
