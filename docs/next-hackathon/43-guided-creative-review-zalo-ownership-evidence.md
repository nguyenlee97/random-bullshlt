# Guided creative review and durable Zalo campaign ownership evidence

Date: 2026-07-20

Branch: `revamp/next-hackathon`

Production build: `2026-07-20.3`

## Outcome

- Campaign Copilot waits for every Creative Intelligence verdict, keeps the
  completed analysis visible, and no longer navigates to Setup automatically.
- The operator explicitly selects **Xác nhận & sang Setup** after reading the
  analysis. That checkpoint is stored server-side and survives history resume
  and another browser/device.
- Manual-review verdicts remain blocked until an audited override exists.
- Autopilot artifact repair retains its existing single explicit save/review
  boundary and does not inherit an unnecessary second click.
- Zalo campaign discovery now uses a durable, server-owned campaign reference
  rather than treating conversation history as the ownership database.
- Deleting one or all conversations first preserves campaign references, then
  removes the transcript, workspace, jobs and run artifacts as before. The Node
  campaign order remains discoverable to its owner through Zalo.

## Additive data model

Collection: `account_campaign_ownership`

Each record contains:

- unique `order_id`;
- exactly one server-derived owner (`owner_user_id` or `anonymous_id`);
- original `conversation_id` and `session_id` as provenance;
- optional `experience_mode` and `conversation_title` display metadata;
- `created_at`, `updated_at`, and claim metadata when applicable.

Indexes are created additively at Agent startup:

- unique `order_id`;
- account owner plus recency;
- anonymous owner plus recency;
- session plus recency.

No existing collection is rewritten or reseeded. Surviving conversations are
backfilled lazily when Zalo lists campaigns. New Guided and Autopilot orders are
registered at the successful order-commit boundary. Anonymous-to-account claims
transfer the registry only after the existing server-side claim authority has
proved both owners.

## API additions

`POST /api/agent/workflow/steps/{step}/confirm`

```json
{
  "session_id": "server-issued-session-id"
}
```

The endpoint uses the existing actor/session authorization and centralized CSRF
middleware. The browser cannot submit a user or owner ID.

`GET /api/agent/conversations/{conversationId}` now includes additive progress:

```json
{
  "workflow_progress": {
    "confirmed_steps": [2],
    "creative_review_confirmed": true
  }
}
```

Legacy campaigns that already reached Setup, Result or Report remain resumable
without a new confirmation record. Legacy creative snapshots without analysis
status also preserve their previous resume behavior.

## Production data migration

Before deployment, production inspection found one linked account with four
surviving campaign sessions:

- `ORD-2026-004`
- `ORD-2026-005`
- `ORD-2026-007`
- `ORD-2026-008`

`ORD-2026-006` was the only additional app-created order and had no surviving
session, matching the reported deleted-history reproduction. It was backfilled
once through an operator migration to the same server-resolved linked account.
Legacy/seed orders `001` through `003` were not assigned.

## Verification

- Focused Agent ownership/identity checks: **28 passed**.
- Complete Agent suite: **322 passed**, with the two existing warnings.
- Complete frontend suite: **76 passed**.
- Vite production build: **passed**, 2,583 modules transformed.
- Production health reports `2026-07-20.3`.
- Production readiness reports Mongo, Node backend, Creative worker, Autopilot
  worker, Zalo worker and Zalo OpenAI ready.
- PM2 reports `agent-api` and `adspilot-api` online.
- The deployed frontend serves `assets/index-DjSaYQSd.js`, which contains the
  explicit Creative review state.
- An unauthenticated workflow-confirmation probe returns **401** and creates no
  session record.
- The server-side Zalo resolver returns exactly `ORD-2026-004` through
  `ORD-2026-008`; registry count is **5**. No OA message was sent for this test.

## Rollback

Rollback bundle:

`/var/backups/advertising-agent/20260719T183407Z-creative-review-zalo-owner`

The prior frontend also remains at `/var/www/agent-prev-20260720-3`. Database
rollback is additive: the new collection can remain unused by the previous
build. Schema setup rewrites no existing order, conversation or session. The
only data migration was the explicit ownership reference for the already
orphaned `ORD-2026-006`; legacy seed orders were not assigned or modified.
