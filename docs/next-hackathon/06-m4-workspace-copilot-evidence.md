# M4 Workspace and Campaign Copilot — Implementation Evidence

> Status: M4.1 and M4.2 complete in the local environment. Updated 2026-07-15.

## Implemented foundation (M4.1)

- Canonical versioned campaign workspaces in MongoDB with an in-memory test fallback.
- Optimistic revision checks: stale clients receive a conflict instead of overwriting newer state.
- Idempotent mutations and proposal approvals.
- Durable proposal, approve, reject, supersede, and audit records with proposal identity.
- Artifact dependency closure and selective stale-state invalidation.
- Compatibility mirroring between canonical artifacts and the legacy session form state.
- Frontend hydration from canonical state and visible conflict recovery.
- Form and proposal actions routed through the workspace service.
- LangGraph context uses canonical state when the browser revision is stale.

## Reliable Campaign Copilot (M4.2)

- Structured Vietnamese intent classification plus deterministic typed commands for:
  - one or many brief fields;
  - authoritative DMP audience segments;
  - catalog-backed targeting dimensions and values;
  - available placement zones and booking conflicts;
  - already-uploaded creative files;
  - zone-to-creative assignments.
- Report output, order state, and creative uploads remain generated/read-only artifacts. Chat can inspect them but cannot fabricate or overwrite them through a proposal.
- Exact catalog resolution rebuilds model references from server data. Unknown or ambiguous segment, targeting, zone, creative, and assignment references are rejected.
- Every proposal path uses the same validation firewall, including the legacy `update_workspace` tool and the generic proposal HTTP endpoint.
- Creative chat commands can retain or remove existing files but cannot synthesize an upload.
- Confirmation is proposal-ID based. A plain confirmation cannot choose between multiple pending proposals.
- Explicit rejection is deterministic and never reaches the model.
- Approval-bypass phrases still create a reviewable proposal; they never mutate state directly.
- Every successful mutation supersedes proposals based on an older workspace revision.
- Proposal creation, clarification, approval, rejection, and conflict messages are persisted in conversation history; decisions are also stored in proposal/audit records.
- The compatibility pending slot is retained only for old clients; durable proposal records are authoritative.

## Local verification

Backend suite in the rebuilt Compose agent image:

```text
96 passed in 15.97s
```

Frontend verification from the M4.1 checkpoint:

```text
2 tests passed
Vite production build passed
```

Full configured-model Vietnamese Copilot evaluation:

```json
{
  "cases": 60,
  "passed": 60,
  "failed": 0,
  "turns": 65,
  "mean_latency_s": 2.953,
  "p95_latency_s": 13.793,
  "unauthorized_mutations": 0
}
```

Evidence files:

- `eval/golden_set/copilot_multiturn_vi.json`
- `eval/run_copilot_eval.py`
- `eval/reports/copilot-v2-full60-final.json`

The 60 scenarios cover all editable artifact classes, normal questions, incomplete edits, negation, ambiguous catalog labels, multiple pending proposals, exact approval, stale revision conflicts, rejection followed by confirmation, and attempts to bypass approval.

## End-to-end safety probes

Configured-model proposal flow:

1. An explicit edit creates a durable `workspace_proposal` with a proposal ID.
2. Canonical workspace revision does not change before approval.
3. Approval applies that exact proposal and advances revision by one.
4. A stale competing proposal cannot overwrite the result.

Shared HTTP proposal boundary:

1. Posted a proposal containing segment ID `FAKE-999` to `/api/agent/workspace/proposals`.
2. The rebuilt service returned HTTP 422: the segment was absent from the authoritative catalog.
3. Pending proposal count for the probe session remained zero.
4. The same rejection behavior is covered for invented creative files and invalid command shapes in unit tests.

## M4.2 exit decision

M4.2 passes locally:

- editable campaign artifacts are changed only through validated proposals;
- the complete 60-scenario set has zero unauthorized mutations;
- stale revisions and ambiguous confirmations cannot silently overwrite state;
- the legacy model tool no longer provides a bypass around catalog validation.

The next implementation slice is M4.3: non-linear edit/jump/recompute behavior, stale-result rejection, plan-diff evidence, stale-state UI, and a 30-scenario regression suite.
