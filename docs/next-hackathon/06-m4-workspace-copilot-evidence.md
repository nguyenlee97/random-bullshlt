# M4 Workspace and Campaign Copilot — Implementation Evidence

> Status: M4.1 foundation complete locally; M4.2 in progress. Updated 2026-07-15.

## Implemented

- Canonical versioned campaign workspaces in MongoDB with an in-memory test fallback.
- Optimistic revision checks: stale clients receive a conflict instead of overwriting newer state.
- Idempotent mutations and proposal approvals.
- Durable proposal, approve, and reject records with proposal identity.
- Artifact dependency closure and selective stale-state invalidation.
- Compatibility mirroring between canonical artifacts and the legacy session form state.
- Frontend hydration from the canonical workspace and visible conflict recovery.
- Form and proposal actions routed through the workspace service.
- LangGraph context chooses canonical state when the browser revision is stale.
- A structured intent gate for explicit Vietnamese brief edits.
- Whitelisted brief fields, value validation, partial-brief merge, and clarification for incomplete commands.
- Exact proposal-ID confirmation; chat never applies a structured edit before approval.
- Graceful fallback to ordinary chat when intent classification is unavailable.

## Local verification

Backend suite:

```text
71 passed in 19.31s
```

Frontend suite and production build:

```text
2 tests passed
Vite production build passed
```

Live configured-model proof:

1. Sent: `Hãy đề xuất đổi brand trong workspace thành Thương Hiệu Mới`.
2. The response used `workspace_proposal` and returned a durable `proposal_id`.
3. Canonical workspace remained at revision `0`; no pre-approval mutation occurred.
4. Sent: `đồng ý`.
5. The response used `workspace_confirmed`, applied the same proposal ID, and advanced to revision `1`.
6. Canonical `brief.brand` became `Thương Hiệu Mới`.

Additional concurrency proof completed during M4.1:

- Repeating the same idempotency key returns the original result.
- A different mutation with a stale base revision returns HTTP 409.
- Re-approving an approved proposal is idempotent.
- A rejected proposal cannot be approved.
- Existing deterministic brief and full-campaign flows continue to write canonical state.

## Still required before M4.2 exit

- Expand typed commands beyond brief fields to audience, targeting, creative, placements, assignments, and report context.
- Validate all catalog-backed IDs against authoritative audience, targeting, and zone catalogs.
- Add multiple-pending-proposal selection instead of one compatibility pending slot.
- Add at least 60 Vietnamese multi-turn scenarios, including negation, ambiguity, stale revisions, restart recovery, and injection attempts.
- Prove zero unauthorized mutation across the complete freeform regression set.
- Persist every proactive/visible graph message and decision through one canonical event API.

M4.2 is therefore not marked complete yet. The current slice closes the previously reproduced failure where the model asked for confirmation without creating a proposal.
