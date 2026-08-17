# M4.4 Autopilot Creative-to-Order End-to-End Evidence

> Status: complete for the live creative-to-order and exactly-once launch gate.
> The 20-brief evaluation and failure-drill gate remains.

## Clean local run

- Session: `live_exact_1784074712`
- Run: `run_b9859d0baea046ac876b66e28d178ce5`
- Order: `ORD-2026-022`
- Policy: `auto_build_draft`
- Creative: `zuma-zmp3-masthead.png`, measured at exactly `2032x528`
- VLM: auto-approved, brief-match score `5/5`, no manual override
- Placement: `ZingMP3_Masthead`
- Budget: 40,000,000 VND

Observed durable path:

1. Brief normalization and deterministic validation.
2. Strategy generation.
3. Audience RAG retrieval and ranking.
4. Catalog-validated targeting.
5. Creative deterministic analysis and Gemma VLM verdict.
6. Exact-size placement filtering and live conflict check.
7. Creative assignment.
8. Reach/cost forecast.
9. Order-draft construction.
10. Live order guard.
11. Mandatory human launch approval.
12. Idempotent local order creation.
13. Order fetch/verification.
14. Setup-report creation.

Final state:

- Run: `completed`
- Create task: `succeeded`
- Verify task: `succeeded`, `verified=true`
- Report task: `succeeded`, `kind=setup_report`
- Backend placement warnings: **0**

## Exactly-once evidence

- The first launch approval released the create-order task.
- An immediate replay of the same approval returned HTTP **409** because the
  launch task was no longer reviewable.
- The stable idempotency key was
  `autopilot:run_b9859d0baea046ac876b66e28d178ce5:launch`.
- The backend contained exactly **1** order for that key.
- A direct duplicate POST with the same payload returned `deduplicated=true`
  and the existing order ID.
- The backend still contained exactly **1** order for the key afterward.

## Defects discovered and fixed by the drill

### Stale creative verdict after strategy creation

Run `run_09d75d7eaaeb4a399f900c30c331bb83` failed closed because strategy
creation correctly invalidated a precomputed creative verdict, but the
Autopilot capability incorrectly treated the stale verdict as current.

Fix: reuse the expensive VLM evidence but recommit the verdict through the
revision-checked workspace boundary against the current brief, strategy, and
creative revisions.

### Non-BSON assignment score keys

Run `run_9d2ec1ec0ddc4cd1aa2297e209496ba1` reached assignment but MongoDB rejected
integer keys in the nested score map.

Fix: normalize score-map keys to strings at the assignment source, matching
the JSON representation already observed by clients.

### Incompatible creative-placement launch

An intermediate test run proved that the previous planner could assign one
creative to incompatible skin and sidebar placements and rely on backend
warnings.

Fixes:

- Creative is now a declared input to placement planning.
- Creative edits replan both verdict and placement branches.
- Ranking uses measured creative-intel dimensions and intended format.
- Automatic placement selection requires exact pixels or an explicit skin
  match; same-ratio assets are not treated as launch-ready because the current
  backend does not resize them.
- Weak assignments become a retry/input review instead of silently advancing.

## Automated evidence

- Focused creative, nonlinear-workspace, and Autopilot tests: **47 passed**.
- Full agent regression: **133 passed**.
- Source whitespace validation: **passed**.

## Remaining M4.4 gate

Run the 20-brief Autopilot evaluation and documented failure drills before
marking the complete Campaign Autopilot milestone done.
