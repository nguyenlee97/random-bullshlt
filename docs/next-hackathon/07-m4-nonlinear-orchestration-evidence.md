# M4.3 Non-linear Orchestration — Local Evidence

> Status: complete in the local environment. Updated 2026-07-15.

## Implemented

- Added direct artifact-input definitions alongside the existing transitive dependency graph.
- Canonical mutations retain affected values and mark only existing dependent artifacts stale.
- Added a deterministic recompute-plan API with:
  - ordered affected artifacts;
  - ready versus blocked recompute work;
  - explicit reusable-artifact evidence and revisions;
  - stale reasons and previous-value availability.
- Added task-context snapshots containing input artifact revisions and the target artifact revision.
- Added atomic artifact-result commits that:
  - allow unrelated global workspace changes;
  - reject changed or stale inputs;
  - reject a second worker attempting to overwrite a newer result on the same inputs;
  - remain idempotent for a retried task ID;
  - invalidate only downstream artifacts after a valid commit.
- Added HTTP endpoints for recompute plans, task contexts, and artifact-result commits.
- Wired the creative-intelligence worker to the task contract:
  - uploaded files are committed before analysis starts;
  - all files in one analysis batch share one revision snapshot;
  - terminal verdicts are committed as one aggregate artifact;
  - a creative edit during analysis marks the late verdict stale instead of accepting it;
  - final creative confirmation republishes the reviewed verdict against the final file revision.
- Fixed browser handling for typed proposals so targeting, creative files, placements, and assignments are all persisted and mapped to the correct UI state.
- Replaced destructive “reset all later steps” editing with non-linear editing that retains data until a confirmed mutation determines the real invalidation set.
- Brief, Audience, Creative, and Setup are directly reachable in any order. Result, Report, and Email remain gated by campaign completion.
- Added stale-step badges, workspace revision display, recompute/reuse banner, and navigation to the first affected step.

## Regression evidence

Backend image:

```text
114 passed in 18.19s
```

Frontend policy tests:

```text
6 passed
```

Frontend production build:

```text
Vite build passed (2748 modules transformed)
```

Non-linear golden set:

```json
{
  "cases": 30,
  "passed": 30,
  "failed": 0,
  "discarded_unaffected_values": 0
}
```

Evidence files:

- `eval/golden_set/nonlinear_workflows.json`
- `eval/run_nonlinear_eval.py`
- `eval/reports/nonlinear-v1.json`

The scenarios cover every artifact as a change source, complete and sparse workspaces, creative-before-audience, late brand/date changes, audience removal after draft creation, placement conflicts, order/report refreshes, and unaffected artifact reuse.

## Live API proof

1. Committed a creative and captured a `creative_verdict` task context.
2. Committed a valid verdict and assignments.
3. Replaced the creative before submitting another result from the old context.
4. `/workspace/artifact-results` returned HTTP 409 with `stale_task_result`.
5. Workspace revision did not advance for the rejected result.
6. `/workspace/recompute-plan` returned exactly `creative_verdict → assignments` and identified `creative` as reusable.

## Visual local proof

The rebuilt Compose UI was exercised in the in-app browser:

- Creative and Setup were reachable from an empty workflow without completing Brief or Audience.
- A typed brief proposal showed its exact impact before approval.
- After approval, canonical revision advanced from 4 to 5.
- Creative and Setup displayed **Cần xem lại** while the replacement creative remained visible.
- The banner showed two affected artifacts, two reusable artifacts, and the order `creative_verdict → assignments`.
- **Xử lý** opened Creative, the first affected workspace step.
- No browser console warnings or errors were emitted during the flow.

## M4.3 exit decision

M4.3 passes locally:

- non-linear edits do not force a full reset;
- affected artifacts are invalidated deterministically;
- unaffected values are retained and accompanied by reuse evidence;
- late and competing task results cannot overwrite current workspace state;
- the browser exposes stale state and directs the operator to the earliest required recompute step.

The next slice is M4.4: durable Campaign Autopilot runs, tasks, worker leases, pause/resume/cancel, approval policies, restart recovery, and SSE progress.
