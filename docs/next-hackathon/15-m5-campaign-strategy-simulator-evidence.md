# M5 hero feature — Campaign Strategy Simulator

Date: 2026-07-15
Environment: local only

## User story

After the operator submits a brief in Campaign Autopilot, Advertising Agent compares three campaign strategies before audience and placement selection:

1. Balanced allocation.
2. Reach-first allocation.
3. Quality-first allocation.

Each scenario shows directional reach, impressions, CPM, frequency, risk, rationale and budget split. The operator can accept the recommended option or choose another. The selected option and reason become a versioned strategy artifact.

## Technical behavior

- Estimates are deterministic functions of approved budget plus explicit CPM/frequency assumptions. They do not require an LLM and remain available during provider outages.
- The final forecast still uses selected source-catalog placements; simulator values are clearly labeled as directional estimates.
- Strategy selection is validated against generated option IDs and records actor, timestamp and reason.
- A selection made during stage review updates the pending artifact and commits only after approval.
- A selection made later updates the canonical workspace and replans audience, targeting, creative analysis, placement ranking, assignment, forecast and order draft while preserving the simulator task.
- Selection is rejected after order creation, so the hero feature cannot replay an irreversible side effect.
- Reach-first broadens age targeting and favors compatible low-CPM placements. Quality-first favors compatible placements with stronger quality signals. Balanced retains the catalog rank.

## Demo value and metric

Primary metric: the user can compare three grounded scenarios and record one auditable strategy choice before booking.

The default 40-million-VND awareness fixture proves the reach-first option estimates higher reach and lower CPM than quality-first. The comparison is explainable and can be demonstrated in under three minutes.

## UI and observability

- The simulator is embedded inside Campaign Autopilot, not placed on a disconnected page.
- The chosen scenario is visually distinct and its rationale is displayed.
- An expandable operations-evidence section shows trace ID, RAG candidate/reranker status, creative verdicts, order-guard result and idempotency evidence as tasks finish.
- The layout uses the Advertising Agent blue design system and collapses to one column on small screens.

## Fallback

The simulator itself is the deterministic fallback. If the agent service is unreachable, only read-only boot/chat guidance may use the cached demo response, which is visibly labeled “Chế độ demo dự phòng” and cannot produce a workspace mutation. Brief, audience and setup approvals fail visibly until the service recovers.

## Test evidence

- Agent full suite: 167 passed after simulator implementation and privacy-deletion hardening.
- Focused Autopilot/campaign/order suite: 52 passed.
- Frontend tests: 18 passed.
- Frontend production build passes without oversized-chunk warnings.
- Dedicated tests cover three scenarios, metric ordering, pending-review selection, downstream-only replan and post-order rejection.
