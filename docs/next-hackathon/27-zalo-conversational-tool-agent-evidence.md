# Zalo OA Conversational Tool Agent — Current State and Evidence

Date: 2026-07-18

Branch: `revamp/next-hackathon`

Build: `2026-07-18.15`

## Delivered behavior

- GPT-5.4 mini now runs a bounded Responses API function-calling loop for Zalo OA instead of choosing one fixed intent for a server `if/elif` router.
- The model can answer directly, ask a clarification question, or call multiple strict tools in sequence.
- Tool schemas contain no user, owner, anonymous identity, or account-session arguments. The server supplies the linked thread actor and resolves campaigns only from its owned conversations.
- Greetings and small talk do not fetch or disclose campaign data.
- Existing campaign reads cover list, status, setup, all six existing synthetic report views, live view, and Autopilot progress.
- Existing campaign mutations remain limited to pause/resume proposals followed by the existing expiring exact-confirmation gate and a second ownership check.
- New campaigns continue through the existing two-mode Campaign Autopilot workflow. Existing campaign configuration cannot be edited through Zalo.

## Context and memory

- One permanent OA thread is organized into additive time-based chat sessions.
- A session has a 60-minute hard limit and a 20-minute idle limit.
- Model context contains at most the newest 30 messages, with a 24,000-token total budget and reserved space for instructions, tools, and summaries.
- Individual messages and tool results are bounded.
- Rolling structured summaries are queued every eight new messages or about 4,000 unsummarized tokens, and when a session closes.
- The existing Zalo worker claims summary work with a lease. Summarization never blocks the first message of a new session.
- A completed previous-session summary can bridge a new session. Operational facts are always refreshed through tools.
- Pending confirmations are cleared at a session boundary. Autopilot run subscriptions and the active campaign remain thread state.

## Mongo migration evidence

New collection: `channel_chat_sessions`.

Indexes created successfully in production:

- `_id_`
- `channel_chat_session_one_open`
- `channel_chat_session_sequence_unique`
- `channel_chat_session_thread_time`
- `channel_chat_summary_queue`

Immediately after deploy the collection count was `0`, demonstrating that deployment/index creation did not seed, copy, rewrite, or delete campaign/session data. Documents are created lazily on the next real OA message. All existing channel, identity, conversation, workspace, order, report, and Autopilot collections are unchanged.

## Automated verification

Focused Zalo suite:

- `35 passed`
- Covers session rollover, token/message context, async summary persistence, function-call round trips, strict/no-owner schemas, greeting isolation, campaign resolution, ownership loss, explicit lifecycle confirmation, Autopilot mode behavior, media URLs, webhook/link behavior, and fail-closed OpenAI handling.

Complete Agent suite:

- `282 passed`
- Two non-failing existing warnings: Starlette/httpx deprecation and FastEmbed pooling guidance.

Frontend production build:

- Vite `6.4.3`
- `2,581` modules transformed
- Build completed successfully in `21.68s`

## Production acceptance

Public stack after restart:

- `/agent/api/version` returned `2026-07-18.15`.
- `/agent/ready` returned `ready` with Mongo, backend, creative worker, Autopilot worker, Zalo worker, and Zalo OpenAI all healthy.
- `/agent/api/agent/zalo/webhook` continued returning HTTP `200` for the provider verification route.
- PM2 `agent-api` returned online and startup logs showed Mongo connected and the new feature flags.

Real GPT-5.4-mini probe on the deployed server, using `store=false`:

1. Input `chào` returned a natural Vietnamese greeting, made zero tool calls, and disclosed no campaign.
2. Input `Tôi có những chiến dịch nào?` selected `list_campaigns` itself, completed the function-call/output round trip, and correctly answered that the deliberately ownerless acceptance context had no campaigns.

The acceptance probe did not send an external Zalo message and did not create a channel chat-session document. End-user OA rendering remains available for the user's ongoing manual chat test.

## Deployment and rollback

- Backend files deployed to `/var/www/agent-api` and compiled before restart.
- PM2 process restarted with the existing environment; no secret values were printed or changed.
- Rollback snapshot: `/var/backups/advertising-agent/20260718-zalo-tool-agent-15`
- Rollback restores that directory to `/var/www/agent-api` and restarts `agent-api`. The additive collection/indexes can safely remain because the previous build does not use them.

## Known follow-ups

- Validate longer, real OA conversations across an actual 20-minute idle boundary; unit coverage already exercises the clock deterministically.
- Tune model instructions and tool-result presentation from real chat transcripts, without adding keyword intent routing.
- Direct Zalo creative-image upload remains outside this slice; live-view image delivery is supported.
- The existing local email/password UI remains temporary as previously agreed. Google Login remains out of scope.
