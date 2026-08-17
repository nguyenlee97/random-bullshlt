# Zalo Workspace Continuity - Current State and Evidence

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Starting commit: `5e4fabff4a101e6bbc37ac780b676b99feca34d8`

Build: `2026-07-19.4`

## Delivered behavior

- The Zalo GPT controller has a strict `get_workspace_link` tool for requests
  such as "give me workspace link", "open this in the browser", or equivalent
  Vietnamese requests.
- The tool resolves the server-owned Zalo actor, rechecks conversation
  ownership, and returns a URL containing only the public conversation ID. It
  never accepts or returns a browser-provided owner/user ID or a session ID.
- The current in-progress Zalo Autopilot run works before an order/campaign ID
  exists. Existing owned campaigns can also be selected by name, ID, ordinal,
  or explicit conversational context. Ambiguous requests ask the user to choose.
- A Zalo-created Autopilot run continues to use the canonical
  `agent_conversations`, `campaign_workspaces`, `agent_runs`, and `agent_tasks`
  records. There is no Zalo-only campaign history or second run engine.
- Account history includes a bounded latest-run summary: status, approval
  policy, completed/total tasks, current task, and last run update time.
- While the history drawer is open, these summaries refresh every four seconds.
  Resuming the campaign still loads the complete canonical workspace and run,
  after which the existing event stream and three-second poll keep the full
  Autopilot canvas synchronized.
- Run status transitions touch conversation activity time without fabricating a
  browser chat message, so an advancing Zalo run returns to the top of history.

## APIs and persistence

No new public route was required.

- `GET /api/agent/conversations` now adds `latest_run_summary` when a
  conversation has an Autopilot run.
- `GET /api/agent/conversations/{conversation_id}` remains the full resume
  source and continues to return `latest_run` with complete task state.
- `GET /api/agent/autopilot/runs/{run_id}` and its event stream remain the live
  synchronization authority after resume.
- The Zalo model receives `get_workspace_link(campaign_reference)`; the
  function executes inside the server-resolved thread actor boundary.

Additive startup indexes:

- `agent_runs`: `{session_id: 1, created_at: -1}`
- `agent_tasks`: `{run_id: 1, plan_index: 1}`
- `agent_run_events`: `{run_id: 1, created_at: 1}`

Existing documents need no rewrite or backfill. Conversations without a run
simply omit `latest_run_summary`. Legacy evaluator sessions are unchanged.

## Automated verification

- Focused backend identity/Zalo/tool suites: `31 passed`.
- Full canonical backend suite: `298 passed`, with the two existing warnings
  for Starlette/httpx deprecation and FastEmbed pooling guidance.
- Frontend suite: `63 passed`.
- Frontend production build: Vite 6.4.3, 2,582 modules transformed, successful.
- Ownership tests prove a foreign active conversation cannot be converted into
  a workspace URL and that the URL never contains the internal session ID.
- History tests prove Zalo-originated run activity reorders the canonical
  account conversation and exposes only the bounded summary, not full tasks.

## Production and rollback

- Production build: `2026-07-19.4`.
- `GET /agent/health`: HTTP 200 and build `2026-07-19.4`.
- `GET /agent/ready`: ready; Mongo, backend, creative worker, Autopilot worker,
  Zalo worker, and Zalo OpenAI all healthy.
- PM2 `agent-api`: online after restart.
- Production frontend asset: `index-DIsCcE-t.js`.
- Signed-in browser acceptance showed the account-owned Doraemon Autopilot card
  on the homepage with `Hoàn tất` and `18/18 bước`.
- Resuming that card loaded the same canonical Autopilot canvas at 100%, with
  five stages and all 18 persisted tasks complete.
- Browser console errors during the homepage and resume journey: zero.

The existing campaign is browser-originated, so it proves the shared history
and resume rendering against canonical records. Creation of a fresh Zalo-origin
run is covered by the server integration tests and remains the recommended
user-facing OA acceptance journey below.

Rollback snapshot:

`/var/backups/advertising-agent/20260719-zalo-workspace-continuity-4`

It contains the previous Agent Python files, the full pre-release frontend, and
the intermediate frontend before homepage progress was added. Mongo data was
not rewritten, deleted, reseeded, or backfilled; rollback is file-only.

## Known follow-ups

- The first user-facing acceptance should ask the OA in Vietnamese and English
  for the workspace link during an in-progress Autopilot run, then sign in with
  the same linked Zalo account in a second browser/device and confirm the live
  task count matches.
- A later UX polish can show the human-readable current task label in the
  history card. The current card deliberately keeps the summary compact.
