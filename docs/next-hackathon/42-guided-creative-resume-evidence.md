# Guided creative terminal gate and report resume evidence

Date: 2026-07-20

Branch: `revamp/next-hackathon`

Production build: `2026-07-20.2`

## Outcome

- Campaign Copilot no longer marks Creative complete when uploaded files are
  merely `queued`, `uploading` or still being analyzed.
- The completed Creative copy and Setup navigation become available only after
  every current file has a terminal Creative Intelligence verdict:
  `auto_approved`, `needs_review` or `approved_override`.
- Historical creative records created before Creative Intelligence remain
  resumable when they contain no analysis-status field.
- Guided history resume now uses a small server-derived progress snapshot from
  the owned session. A created order completes Setup and Result for navigation;
  a started report restores Report and its campaign ID.
- Restoring a started report seeds the existing report-entry guard, so resume
  polls the existing package rather than triggering generation again.

## API compatibility

`GET /api/agent/conversations/{conversationId}` adds:

```json
{
  "workflow_progress": {
    "order_created": true,
    "report_started": true,
    "report_campaign_id": "ORD-2026-007"
  }
}
```

The values are resolved server-side from the authorized campaign session and
canonical workspace. The browser cannot submit an owner, order or campaign ID
to influence resume routing. Existing clients can ignore this additive field.

No Mongo schema migration, reseed, deletion or record rewrite is required.
Existing `created_order_ids`, `form_state.report_context` and canonical
artifacts remain the durable compatibility sources.

## Verification

- Focused frontend/state and identity checks: 17 frontend tests and 22 Agent
  tests passed.
- Complete Agent suite: **319 passed**, with the two existing warnings.
- Complete frontend suite: **75 passed**.
- Vite production build: **passed**, 2,583 modules transformed.
- Production version: `2026-07-20.2`.
- Production readiness: Mongo, Node backend, creative worker, Autopilot worker,
  Zalo worker and Zalo OpenAI all ready.
- PM2: `agent-api` and `adspilot-api` online.

## Production browser acceptance

From the signed-in homepage history, the existing account-owned VNG Campaign
Copilot campaign was opened after deployment. It restored directly to Report,
not Setup, with:

- campaign `ORD-2026-007`;
- 14 report records;
- all 6 AI analyses;
- the complete six-report PDF action.

The Creative in-flight condition is covered by the focused state-machine test
instead of creating another production campaign or analysis batch. No order,
workspace or campaign data was mutated during browser acceptance.

## Rollback

`/var/backups/advertising-agent/20260719T175903Z-guided-resume`

The directory contains the previous `identity.py`, `version.py` and a complete
frontend archive. No database rollback is required.
