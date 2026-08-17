# FE-3/FE-4 Zalo OA Campaign Agent — Current State and Evidence

Date: 2026-07-18

Status: implemented, regression-tested and deployed to
`https://agent.pawgrammers.io.vn` as Agent build `2026-07-18.14`.

## 1. Delivered outcome

Zalo OA is now a durable conversational adapter over the existing Advertising
Agent services. It does not create a second authentication authority, campaign
database, report engine or workflow graph.

An unlinked OA sender can chat anonymously. A linked sender resolves to the
same internal account used by the web application. Linking claims the existing
channel-anonymous conversation in place, preserving its conversation/session
IDs and any canonical workspace, Autopilot run and campaign artifacts. Zalo
Login itself never claims conversations.

The channel supports:

- actor-owned campaign list, deterministic selection and remembered active
  campaign context;
- campaign status and canonical setup inspection;
- questions over the existing synthetic Daily Ops, Awareness, Consideration,
  Conversion, Retention and Executive report views;
- existing live-site links, creative preview and a screenshot delivered through
  a short-lived opaque media URL;
- explicit, expiring and ownership-rechecked pause/resume;
- new Campaign Autopilot runs in exactly two modes: fully automatic
  (`auto_build_draft`) and semi automatic (`critical_only`);
- persisted progress at meaningful run/review/launch/terminal milestones;
- same-origin web workspace deep links for unsupported edits or richer review.

Natural-language turn planning now uses the official OpenAI Responses API with
`gpt-5.4-mini`. The planner receives a bounded recent transcript, summaries of
campaigns already proven to be actor-owned, the active campaign and the type of
pending action. Structured output selects an intent, campaign reference,
report view or clarification question. The model never supplies an owner and
never executes tools or mutations. Server code still resolves the campaign,
fetches report/setup/live data and enforces every confirmation and ownership
check. This follows the model's supported Responses API and Structured Outputs
contract: <https://developers.openai.com/api/docs/models/gpt-5.4-mini>.

New campaigns do not use Guided Workflow over Zalo. Existing campaigns cannot
be edited in chat except for pause/resume.

## 2. Server-side ownership and resolution

The signed OA sender UID is the only channel identity input. The resolver first
loads `channel_identities` and then constructs either an account actor or a
channel-only anonymous actor. Browser/message-provided `user_id`, owner ID,
conversation ID or arbitrary order ID never grants access.

Campaign candidates come only from conversations owned by that resolved actor.
Order IDs are read from those conversations' canonical session artifacts and
then fetched from AdsPilot. Resolution is deterministic:

1. exact campaign/order ID;
2. exact normalized brand/campaign name;
3. unique partial/token match;
4. remembered active campaign for contextual references;
5. the only owned campaign;
6. otherwise a numbered selection prompt with no side effect.

Pause/resume stores campaign/session/conversation, requested target state,
nonce and expiry. Confirmation re-runs ownership resolution and fetches the
current order state before the idempotent backend mutation.

The contextual planner cannot expand this candidate set. A campaign index or
reference returned by the model is resolved again only inside the ordered list
of account-owned candidates that the server supplied. Ambiguity produces a
question; an OpenAI planner failure produces a no-mutation retry response.

## 3. Durable schemas and indexes

All Mongo changes are additive. Existing documents remain readable; worker
queries accept legacy event records without `next_attempt_at`. No collection was
dropped, rewritten, reseeded or bulk migrated.

### `channel_threads`

Stores the OA-scoped sender, resolved account or channel anonymous identity,
stable controller conversation/session, active campaign context, pending
selection/confirmation/Autopilot intake and optimistic revision. Indexes:

- `channel_thread_external_unique` on channel/OA/external UID;
- `channel_thread_account_time` on account and update time.

### `channel_events`

The signed webhook queue now carries additive status, attempt, retry, lease,
result, processed and error fields. Indexes:

- `channel_event_key_unique` for provider replay idempotency;
- `channel_event_queue` and `channel_event_worker_queue` for restart-safe claims.

### `channel_outbound_messages`

Stores hashed deterministic idempotency key, text or image URL, sender/thread,
event/run correlation, category, attempts, retry/lease state and provider
receipt. It never stores account cookies, passwords or OA access tokens.
Indexes:

- `channel_outbound_idempotency_unique`;
- `channel_outbound_worker_queue`.

### `channel_run_subscriptions`

Stores one thread/run cursor and delivered milestone state. Indexes:

- `channel_run_subscription_unique`;
- `channel_run_subscription_queue`.

### `channel_media`

Stores screenshot bytes behind a SHA-256 hash of a random opaque URL token.
The raw token exists only in the returned short-lived URL. Indexes:

- `channel_media_token_unique`;
- `channel_media_expiry_ttl` (`expireAfterSeconds=0`).

Local live-index creation succeeded against the existing Compose MongoDB. The
media collection reported `_id_`, `channel_media_token_unique` and
`channel_media_expiry_ttl` without destructive migration.

## 4. APIs and runtime

Existing Zalo Login and channel-link APIs remain the identity surface:

```text
POST   /api/agent/auth/zalo/start
GET    /api/agent/auth/zalo/callback
POST   /api/agent/channel-links/zalo
GET    /api/agent/channel-links/zalo/{attempt_id}
DELETE /api/agent/channel-links/zalo
```

Channel runtime endpoints:

```text
GET  /api/agent/zalo/webhook          # health/configuration contract
POST /api/agent/zalo/webhook          # signed, immediate durable acknowledgement
GET  /api/agent/zalo/media/{token}    # short-lived screenshot fetch
GET  /ready                           # includes zalo_worker readiness
```

When enabled, webhook health exposes only the planner enabled/configured state
and model name. Readiness fails if the server-side OpenAI key is missing; the
key is never returned. Requests use `store=false` and a one-way hashed safety
identifier rather than the raw OA/thread identity.

The webhook acknowledges after verification and idempotent persistence. It
does not wait for agent execution or provider delivery. The inbound worker and
outbox use expiring leases and bounded exponential retry. OA tokens remain in
the root-owned rotating token store; they are not sent to browsers, Mongo
outbox records, logs or traces. Mongo readiness logging was also changed to
avoid printing credential-bearing connection URIs.

## 5. Report and Autopilot behavior

Report commands initialize the selected campaign's existing report context and
call the same report entry/chat handlers used by the web module. Answers are
therefore grounded in the hackathon synthetic dataset already visible in the
report UI. This slice adds no analytics, anomaly-detection or optimization
agent.

Autopilot uses the existing `create_run` and review-chat services:

- fully automatic maps to `auto_build_draft` and stops only at mandatory final
  launch approval;
- semi automatic maps to `critical_only` and stops at important existing review
  gates plus final launch approval;
- run subscriptions deliver deduplicated milestone messages instead of every
  internal task event;
- launch still uses the existing guard, approval and order idempotency path.

## 6. Automated verification

Commands executed after the contextual OpenAI planner change:

- focused OpenAI planner and Zalo campaign-agent tests: **14 passed**;
- complete Agent test suite: **275 passed**, 2 warnings;
- Agent container production image build: **passed**;
- Python compilation of all changed runtime modules: **passed**;
- provider-backed production structured-plan and grounded-render probes:
  **passed**.

The unchanged frontend, AdsPilot backend and additive-index evidence from build
`.13` remains applicable because `.14` changes only the Agent conversational
planner/router, configuration, health metadata and tests.

Focused coverage includes campaign ambiguity and active context, foreign-owner
denial, explicit lifecycle confirmation and recheck, both Autopilot mode
mappings, milestone filtering, webhook replay, channel linking and opaque media
retrieval. The new tests also cover natural active-campaign list intent,
pronoun/ordinal selection restricted to the offered owned list, bounded and
privacy-minimized model input, grounded reply rendering and fail-closed model
outage behavior.

## 7. Production and browser evidence

Production configuration enables the Zalo agent worker and outbound delivery.
After the `2026-07-18.14` deployment:

- `/agent/api/version` returned `2026-07-18.14` with
  `zalo-openai-context-planner`;
- `/agent/ready` returned Mongo, backend, creative worker, Autopilot worker and
  Zalo worker all ready, plus `zalo_openai: true`;
- `/agent/api/agent/zalo/webhook` reported the OA configured and both worker and
  outbound delivery running, and the `gpt-5.4-mini` planner enabled/configured;
- a provider-backed production diagnostic using the deployed planner classified
  `đang có chiến dịch gì đang chạy` as `list_campaigns` with the `active`
  filter, then rendered only the server-provided Doraemon result;
- a controlled valid signed event for the linked test user was acknowledged,
  processed once and sent once; the actual OA reply was the account-owned
  campaign-list result;
- replay of that event was deduplicated;
- an opaque production media URL returned HTTP 200, `image/png`, 68 bytes and a
  bounded cache lifetime;
- startup logs after the final restart contain `MongoDB OK` without the Mongo
  URI or credentials.

In the signed-in production browser, account history displayed **Trợ lý Zalo
OA**, resumed the same controller conversation and showed the real OA reply.
The account-safe `?conversation=<public-id>` deep link resumes the owned
workspace without exposing a user ID or session credential. A frontend
initialization-order defect found during this journey was fixed, rebuilt and
redeployed; the fixed build renders the signed-in homepage/history/workspace
without new console errors.

The earlier FE-2B evidence retains the independent-cookie-jar journeys for
explicit anonymous claim, old-device denial after claim/logout, cross-device
account resume, foreign-account isolation and anonymous use after logout.

## 8. Migration and rollback

Deployment copied application files and added environment flags only. It did
not delete/reseed MongoDB or alter existing campaign orders. New collections,
indexes and optional document fields may safely remain if the feature is
disabled.

Production rollback snapshot:

```text
/var/backups/advertising-agent/20260718-zalo-openai-14
```

For a transport-only rollback, first disable `ZALO_AGENT_WORKER_ENABLED` and
`ZALO_OUTBOUND_ENABLED`; the signed webhook/link foundation can continue to
acknowledge events without running campaign turns. A code rollback restores the
Agent/frontend snapshot. Do not drop the additive Mongo collections.

## 9. Known follow-ups

- The linked production account now owns a Doraemon campaign and exposed the
  former keyword-router defect: a natural active-campaign question returned the
  generic capability menu while an explicit report keyword happened to work.
  Build `.14` fixes that routing path. A fresh human OA journey should now
  exercise natural follow-ups, report/live, confirmed pause/resume and both
  complete Autopilot modes against production data.
- Native inbound Zalo creative-image ingestion is deferred. Current inbound
  images direct the user to the authenticated web upload workspace.
- Rich cards/buttons, voice, ZBS proactive templates and broad notification
  policy automation remain later work. Current progress sends are limited to
  the eligible conversational OA path and persisted delivery evidence.
- FE-0 truth closeout, the full 128-scenario release report and five consecutive
  demo rehearsals remain FE-5 release work.
- Google login, organization RBAC, Qwen reranking experiments and the future
  analytics/optimization agent remain out of this slice.
