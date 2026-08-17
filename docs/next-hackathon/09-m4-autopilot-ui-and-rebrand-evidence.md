# M4.4 Autopilot UI and Advertising Agent Rebrand — Checkpoint Evidence

> Status: in progress. This checkpoint proves the two-mode opening experience,
> the local Autopilot control surface, and the first user-facing rebrand slice.
> It does not yet close the full M4.4 launch and replan exit gates.

## Implemented

- Added a Vietnamese opening selector with two explicit experiences:
  - Guided Workflow
  - Campaign Autopilot
- Persisted the selected experience mode through the workspace preference API.
- Added an Autopilot panel with approval-policy selection, run start, task
  progress, pause, resume, cancel, ordinary review, missing-input recovery, and
  a visually stronger final launch review.
- Connected Autopilot progress to SSE event updates with polling as a local
  resilience fallback.
- Renamed core user-facing identity and boot copy to **Advertising Agent**.
- Replaced the primary green brand palette with centralized blue brand tokens.
- Updated the application metadata, top bar, opening experience, and core
  surfaces to use the new blue visual direction.
- Fixed rapid brief-field updates to use functional state updates so one field
  cannot overwrite a sibling field from a stale browser render.

## Automated evidence

- Full agent regression: **123 passed**.
- Frontend behavior tests: **6 passed**.
- Frontend production build: **passed**.
- Source whitespace validation: **passed**.
- Local `/ready`: MongoDB, backend, RAG index, creative worker, and Autopilot
  worker all healthy.

The production build still reports a JavaScript bundle of approximately
1.19 MB before gzip. This is accepted only for this functional checkpoint and
remains an explicit performance task; it is not a closed production gate.

## Browser evidence

Verified against the local Compose frontend:

- The initial screen identifies the product as Advertising Agent and presents
  both modes in Vietnamese.
- Choosing Campaign Autopilot opens the Autopilot policy and run controls while
  preserving chat and workspace access.
- Choosing Guided Workflow opens the existing step-by-step workspace.
- The top bar displays the selected mode in both experiences.
- The boot greeting uses the Advertising Agent identity.
- No visible application error appeared during either opening flow.

The in-app browser could not reliably synthesize React change events for its
native date input. Full Autopilot start and persistence have therefore been
proven independently through the live API and worker smoke recorded in the
previous checkpoint, while this checkpoint covers the user-facing entry and
control surfaces.

## Remaining before M4.4 can close

1. Detect relevant mid-run workspace edits and replan only affected queued or
   completed tasks.
2. Complete one live creative-to-order-ready run, including VLM analysis,
   placement, assignment, forecast, order guard, final approval, create,
   verification, and report.
3. Prove repeated launch approval creates exactly one order.
4. Run the 20-brief Autopilot evaluation and failure drills.
5. Finish the complete old-name, old-copy, primary-green, responsive,
   accessibility, and exported-report rebrand audit.
6. Split the oversized frontend bundle before the final performance gate.
