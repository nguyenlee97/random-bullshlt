# FE-3/FE-4 Zalo OA Campaign Agent — Implementation Plan

Date: 2026-07-18

Status: implemented, regression-tested and deployed on 2026-07-18; production
campaign-specific manual acceptance remains dependent on a linked account that
owns at least one campaign

## 1. Product contract

Zalo OA is a conversational control surface over the existing account,
conversation, canonical-workspace, Autopilot and report services. It is not a
second authentication authority, campaign database, workflow engine, analytics
agent or optimization agent.

Anonymous OA chat remains available. Linking the OA sender to a Zalo-login
account transfers the channel conversations to that account without changing
their session, run or artifact identifiers.

### Existing campaigns

Supported:

- list and select campaigns owned by the resolved account or anonymous channel
  identity;
- remember one active campaign in the server-side Zalo thread;
- show status and canonical setup configuration;
- answer questions from the existing six-view synthetic report module;
- show live-site links and creative previews when present;
- pause or resume after an explicit, expiring confirmation.

Not supported:

- edits to budget, dates, audience, targeting, placements or creative;
- optimization of an existing campaign;
- free-form changes to an active Autopilot run.

### New campaigns

Zalo creates new campaigns through the existing Campaign Autopilot capability
graph. It exposes exactly two channel modes:

- `fully_automatic` maps to `auto_build_draft`: report milestone progress but
  stop only at the mandatory final launch approval;
- `semi_automatic` maps to `critical_only`: report milestone progress and stop
  at important safety/review boundaries, including final launch approval.

The channel may continue, cancel or deep-link to the web workspace. It does not
patch an in-progress run.

## 2. Durable data model

All additions are migration-compatible Mongo collections/indexes. No existing
collection is rewritten or reseeded.

### `channel_threads`

- key: `(channel, oa_id, external_uid)`;
- resolved `user_id` or channel-only `anonymous_id`;
- stable controller `conversation_id` and `session_id`;
- `active_campaign_id`, `active_campaign_conversation_id` and
  `active_campaign_session_id`;
- pending campaign selection, pause/resume confirmation, new-campaign intake or
  Autopilot confirmation;
- last inbound/outbound timestamps and optimistic `revision`.

### `channel_events`

The existing collection becomes the durable inbound queue. Additive processing
fields include lease owner/expiry, attempts, next attempt time, normalized
result, failure and processed timestamps. The webhook still acknowledges after
signature verification and idempotent insertion; it never waits for the model
or OA send.

### `channel_outbound_messages`

- deterministic idempotency key per inbound event and rendered part;
- text/image payload without account secrets;
- send category, campaign/run correlation and reply eligibility;
- queued/sending/sent/retry/failed status, lease, provider receipt and error.

### `channel_run_subscriptions`

- one row per Zalo thread and Autopilot run;
- last delivered run-event cursor;
- milestone/review/final state deduplication;
- notification policy and delivery status.

## 3. Server-side ownership and campaign resolution

The signed OA sender ID is resolved through `channel_identities`. A linked
sender becomes an account actor. An unlinked sender receives a channel-only
anonymous actor. Browser-provided owner/user identifiers are never accepted.

The campaign catalog is built only from conversations owned by that actor and
the order IDs stored in those conversations' canonical sessions. Each backend
order is fetched by an ID already proven to belong to an owned conversation.

Resolution order:

1. Exact order ID.
2. Exact normalized campaign/brand name.
3. Unique partial-name match.
4. The thread's active campaign for pronouns such as `campaign này`.
5. The only owned campaign, while explicitly echoing its name.
6. Otherwise return a numbered selection prompt; never guess.

Every operation re-fetches the owned campaign and current backend state. A
pause/resume confirmation records campaign ID, conversation/session, current
state, requested action, nonce and expiry. Execution re-resolves ownership and
state before calling the idempotent lifecycle endpoint.

## 4. Inbound command routing

The deterministic channel router handles, in priority order:

1. one-time account-link messages;
2. pending numbered campaign selection;
3. pending pause/resume or launch confirmations;
4. Autopilot review decisions;
5. campaign list/select/status/setup/live/report/lifecycle commands;
6. new-Autopilot intake and mode selection;
7. safe help/fallback response.

An LLM may extract a structured brief or summarize already-fetched structured
data. It never selects an owner, invents a campaign ID, authorizes a mutation or
supplies a backend URL.

## 5. Synthetic report contract

For a selected campaign, the channel initializes the existing report context
for that campaign session and calls the shared report handler. Questions can
target `daily_ops`, `awareness`, `consideration`, `conversion`, `retention` or
`executive`. Answers come only from the cached synthetic dataset already shown
by the web report module. No new analytics or optimization agent is introduced.

## 6. Autopilot progress contract

The worker subscribes a Zalo thread to the run and renders deduplicated updates
at these operator-relevant milestones:

1. brief accepted/run started;
2. audience and targeting ready;
3. creative plan/assets ready;
4. placements, assignment, forecast and guard ready;
5. review required;
6. final launch approval required;
7. completed, failed or cancelled.

Fully automatic mode does not stop at ordinary or critical stages; semi
automatic stops only where the existing `critical_only` policy requires. Both
always stop before launch.

## 7. Outbound delivery and recovery

The OA client uses the server-only rotating token manager. Text and image parts
are separate idempotent outbox records. Transient provider/network failures use
bounded exponential retry. Permanent provider errors remain visible in the
outbox and do not replay the agent turn.

Worker leases make inbound processing and outbound sending restart-safe. A
replayed webhook event creates neither a second agent turn nor a second send.

## 8. UX and deep links

Text output is concise Vietnamese and always repeats the selected campaign for
mutations. Unsupported rich content is rendered as text plus a same-origin web
workspace deep link containing only the public conversation ID. No password,
account token, anonymous token or OA token appears in a response, log or trace.

## 9. Acceptance matrix

- invalid webhook: provider-compatible HTTP 200, no persisted work;
- duplicate valid webhook: one event, one turn, one outbound delivery;
- process restart: expired event/outbox leases resume;
- unlinked sender: anonymous help/conversation works;
- link after anonymous chat: same channel thread/session and artifacts become
  account-owned;
- ambiguous campaign: numbered prompt and zero backend calls;
- selected campaign: context survives later pronoun-based questions;
- foreign campaign ID/name: not disclosed and not mutable;
- report questions: use all six existing synthetic report types;
- pause/resume: explicit confirmation, ownership/status recheck, idempotent
  already-paused/already-active response;
- existing campaign configuration edits: rejected with web-workspace guidance;
- fully automatic: milestone updates and only final launch stop;
- semi automatic: important review stops and final launch stop;
- repeated launch approval: exactly one order;
- full backend/frontend suites and production build pass;
- production signed-webhook, linked-user, campaign-selection, report and
  pause/resume journeys are recorded without deleting/reseeding MongoDB.

## 10. Rollback

Code rollback is one application release/commit. New collections and fields are
additive and may remain dormant. Disable the Zalo worker/send flags before a
rollback if the OA webhook must continue accepting link events without agent
turns. Never drop or reseed MongoDB as part of rollback.
