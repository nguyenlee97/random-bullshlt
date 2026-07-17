# FE-2B local accounts and cross-device resume — implementation evidence

Date: 2026-07-17

Branch: `revamp/next-hackathon`

Rollback boundary: `3eea598`

Build: `2026-07-17.1`

## Outcome

FE-2B is code-complete and locally verified. Anonymous Campaign Copilot and Campaign Autopilot remain available without login. A visitor may register or log in with a local email/password account, explicitly transfer one device-owned conversation to that account, log out, then resume the same conversation from another cookie jar. Login alone never transfers ownership.

The Agent service remains the only authentication authority. The Node backend was not given account or session logic.

## Security and ownership implementation

- Local passwords are hashed with Argon2id. Passwords and password hashes are excluded from public user/session responses.
- Account cookies contain opaque random tokens. MongoDB stores only SHA-256 token digests. Sessions are expiring and individually revocable.
- `aa_account` and `aa_anonymous` are `HttpOnly`, `SameSite=Lax` cookies. `aa_csrf` is a readable double-submit cookie used only to build the `X-CSRF-Token` header.
- Central CSRF middleware protects browser cookie-authenticated `POST`, `PUT`, `PATCH` and `DELETE` requests under `/api/agent/`. The anonymous bootstrap is the only mutation exemption. Existing evaluator/API calls with no browser identity cookie remain compatible.
- Authentication rate limits use server-observed IP plus a digest of the normalized account key. Login failures return one generic error.
- `resolve_actor()` is the server-side authority for account and anonymous ownership. HTTP handlers never accept a browser-provided user/owner ID.
- Conversation ownership checks return `404` for foreign IDs, so callers cannot distinguish missing from foreign records.
- Claim is an atomic ownership-field update. It preserves `conversation_id`, `session_id`, transcript records, canonical workspace, workspace revision, proposals, creative jobs, Autopilot runs/events/tasks and checkpoints. A same-owner retry is idempotent; competing users cannot both win.
- After claim and account logout, the old anonymous identity cannot list, read or mutate the claimed conversation.

## Additive Mongo model

New collections:

- `users`: `user_id`, display name, status and timestamps.
- `auth_identities`: `user_id`, `provider=local`, normalized provider subject, Argon2id `password_hash`, timestamps.
- `account_sessions`: `session_id`, `user_id`, `token_hash`, expiry/revocation/last-seen timestamps and a bounded user-agent label.
- `auth_rate_limits`: server-side authentication attempt buckets with expiry.
- `auth_audit_events`: registration, login/session and claim audit events without credentials.

Additive conversation fields:

- `owner_user_id` for account ownership.
- `anonymous_id` as the normalized device owner field.
- `claimed_from_anonymous_id` and `claimed_at` for the transfer audit.
- Legacy `identity_id` documents remain readable and are normalized lazily; they are not bulk-rewritten.

Startup creates unique indexes for user IDs, local provider subjects and account token hashes; account-session and auth-rate-limit TTL indexes; account-session user and auth-audit indexes; and account/anonymous/legacy conversation-owner indexes. No collection was dropped, reseeded or bulk-migrated.

## HTTP API

All routes are mounted under `/api/agent`:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /auth/sessions`
- `DELETE /auth/sessions/{session_id}`
- `POST /auth/anonymous` (existing, retained)
- `POST /conversations/{conversation_id}/claim`
- Existing conversation list/create/get/archive/delete and all session-scoped workspace, proposal, creative and Autopilot routes now use the shared actor resolver.

## User experience

- Homepage, history and workspace expose login/account controls while keeping the two anonymous campaign entrances unchanged.
- Registration and login are one dialog with browser password-manager hints and no token storage.
- Account history is labelled `Tài khoản`; device history is labelled `Trên thiết bị`.
- After login during a device conversation, a non-blocking offer opens an explicit claim confirmation. The confirmation explains that state is transferred, not copied.
- Claim success keeps the current workspace open and updates history ownership in place.
- Logout closes an account-owned open workspace and returns to the anonymous homepage. Device-owned history remains available.
- Guided cross-device resume derives the first incomplete step from the canonical workspace instead of defaulting to Brief.
- The account menu lists the current and other sessions and can revoke another session.

## Verification

- Backend: `242 passed`, with two existing dependency deprecation/runtime warnings.
- Frontend: `58 passed`.
- Production frontend: Vite build passed; 2,579 modules transformed.
- Live Compose: agent and frontend rebuilt; `/ready` reported MongoDB, backend, RAG, creative intelligence and Autopilot ready; `/api/version` reported `2026-07-17.1` with the five FE-2B feature flags.
- Live Mongo: all additive indexes were observed. Existing records were retained.

Browser A/B acceptance used two independent host-scoped cookie jars (`localhost` and `127.0.0.1`) so device and account cookies could not bleed between the journeys:

1. Browser A created an anonymous Campaign Copilot campaign, committed a complete brief, and reached canonical workspace revision 1.
2. Browser A registered an account. The campaign remained device-owned and displayed an explicit claim offer, proving registration/login did not auto-claim it.
3. Browser A confirmed claim. The campaign and session IDs remained unchanged, workspace revision stayed 1, and the current campaign stayed open.
4. Browser A logged out. The claimed campaign disappeared from the old anonymous history, while an unrelated pre-existing device campaign remained.
5. Browser B began with zero device campaigns, logged in to the first account, listed the claimed account campaign, and resumed Campaign Copilot with the confirmed brief, revision 1 and stored transcript.
6. Browser B switched to a second local account. The claimed campaign was absent; focused ownership tests also verified foreign read, mutation and claim return not-found behavior.
7. Browser B logged out and successfully started a fresh anonymous Campaign Copilot workspace.

## Production VPS deployment evidence

FE-2B application commit `275c0e42151b662658b564735545a0d03037d709` was deployed to the playground VPS on 2026-07-17 under release ID `fe2b-275c0e4-20260717T155848Z`.

- The frontend was rebuilt with `VITE_AGENT_URL=/agent`. Nginx now proxies `/agent/` to the Agent API on `127.0.0.1:8000`, so the browser-facing account, anonymous and CSRF cookies remain host-scoped to the HTTPS frontend.
- Production sets `ANONYMOUS_COOKIE_SECURE=true` and `ACCOUNT_COOKIE_SECURE=true`. The deployed bundle contains no direct `agent-api.pawgrammers.io.vn` endpoint.
- Before reset, both PM2 writers were stopped. Compressed `mongodump` archives for `camp_ads` and `adspilot` passed `gzip -t` and `mongorestore --dryRun`; SHA-256 sums are stored with the release.
- Per the playground reset request, only collections inside `camp_ads` and `adspilot` were cleared. MongoDB `admin`, `config`, `local`, and the unrelated `kfc` database were not modified.
- The current seed recreated 1 zone catalog, 310 audience segments, 3 seed campaigns and 156 analytics records.
- Startup created the additive FE-2B collections and indexes. Live inspection confirmed Argon2id password hashes in `auth_identities`, hash-only opaque account sessions, no plaintext password/token fields, session/rate-limit TTL indexes, and account/anonymous/legacy conversation-owner indexes.
- HTTPS acceptance with independent device cookie jars verified registration, login without automatic claim, centralized CSRF rejection, explicit claim with unchanged conversation/session IDs, denial to the old anonymous identity after logout, account history on a second device, cross-device resume and individual session revocation.
- Visible browser acceptance verified homepage registration, account controls, account-owned Guided workspace, history labels, session management, logout returning to zero anonymous campaigns, login restoring the account campaign and workspace resume.
- PM2, public Node health, direct Agent health and same-origin proxied Agent health were healthy after the swap. Nginx configuration validation passed before reload.

The complete rollback set is retained at `/var/backups/advertising-agent/fe2b-275c0e4-20260717T155848Z`, including the two database archives, prior live application trees, Nginx/PM2 configuration copies, pre-reset counts, checksums and the release manifest.

## Migration and rollback

The release is additive. Existing anonymous cookies, legacy `identity_id` conversation records and evaluator sessions without a conversation record continue to work. Old documents gain normalized ownership fields only when touched by the new flow. Account/session TTL cleanup affects only expired authentication records.

Code rollback is `3eea598`. Rolling back code leaves the new collections and optional fields unused; no destructive database rollback is required. Do not drop the new collections during rollback because doing so would destroy newly created accounts and ownership audit history.

## Deferred by scope

Email verification/reset, Google OIDC, Zalo Login, Zalo OA linking, organization RBAC, Qwen reranking and the analytics agent remain future work. Production deployment must set `ACCOUNT_COOKIE_SECURE=true` behind HTTPS and define the final retention policy for dormant accounts and audit events.
