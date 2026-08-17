# Advertising Agent — Zalo Login and OA Link Foundation Evidence

Date: 2026-07-18

Branch: `revamp/next-hackathon`

Pre-slice rollback commit: `ebfaac58c5dd4aa80f16306ba5d54ca3f1f4fdac`

## Outcome

Zalo is now the primary account-login experience in code. Local email/password remains available inside a clearly labelled testing fallback and still uses the FE-2B account authority. Google login was not added.

The slice also establishes the server-side OA identity link without assuming that Zalo Login profile IDs and OA-scoped sender IDs are interchangeable:

1. An authenticated account requests a short-lived OA link.
2. The UI identifies `IOT Generation`, embeds Zalo's official follow widget and links directly to that OA.
3. The browser widget callback is UX-only; it never supplies an owner/user ID to the Agent API.
4. A signed `follow` webhook may consume only the newest pending attempt belonging to the account whose Zalo Login subject matches signed `user_id_by_app`.
5. A one-time `LINK <code>` message remains available when the user already follows the OA or the widget is unavailable; the server stores only the code's SHA-256 digest.
6. Either proof atomically attaches the verified OA-scoped sender to the internal `user_id`.

Anonymous web use remains available. Zalo login creates the same opaque, hashed, revocable `aa_account` session as local login. It never automatically claims an anonymous conversation.

## Architecture and security decisions

- The FastAPI Agent service remains the only account/session authority. No auth logic was added to the Node campaign backend.
- Social OAuth v4 uses PKCE S256, high-entropy state, a short Mongo TTL, one-time atomic consumption and browser/account-session binding.
- A Zalo access token exists only in callback request memory while fetching the profile. It is not stored in Mongo, cookies, responses, browser storage, logs or traces.
- Existing local users may select `Kết nối đăng nhập Zalo`. The callback attaches the new provider identity only when the same account session that started the attempt is still valid.
- Provider identities are uniquely keyed by `(provider, provider_subject)`. A Zalo identity already attached to a different account is never merged by name or email.
- OA webhook event processing fails closed when OA configuration or the secret is missing. Invalid or unsigned POSTs receive Zalo's provider-required HTTP 200 transport acknowledgement but are explicitly `accepted: false` and are never normalized, persisted or processed. There is no production “skip signature” mode.
- Verification uses the exact raw request body, configured App ID, provider timestamp and OA secret; App/OA mismatches and stale timestamps are rejected.
- Durable event deduplication uses a one-way event key derived from channel, OA and provider event/message ID. Replays do not consume a second link code or create a second identity.
- OA link codes expire, are superseded when a new code is created, are stored hashed and are single-use.
- A follow never links by itself: it must match an existing Zalo Login identity and an explicit, unexpired account-owned link attempt. A mismatched app-scoped ID leaves the attempt pending.
- Legacy Mongo datetimes without timezone metadata remain readable by link-status polling; no existing record needs rewriting.
- Unlinking the OA revokes only the channel identity. It does not delete the account, web conversations or campaign artifacts.

## Additive Mongo models and indexes

Existing:

- `auth_identities`: now supports `provider: "zalo"`, profile subject/name/avatar, while retaining the existing unique `(provider, provider_subject)` index.
- `users` and `account_sessions`: unchanged ownership and session semantics.

New additive collections:

- `oauth_login_attempts`
  - state digest as `_id`, provider, intent, PKCE verifier, browser/account binding, safe return path, timestamps;
  - TTL `oauth_attempt_expiry_ttl`;
  - provider/time lookup index.
- `channel_link_attempts`
  - attempt ID, account, OA, hashed one-time code, status and expiration;
  - unique code digest, TTL expiration and user/time indexes.
- `channel_identities`
  - `channel`, `oa_id`, OA-scoped `external_uid`, optional separately observed `app_scoped_uid`, internal `user_id`, status and audit timestamps;
  - unique `(channel, oa_id, external_uid)` and user/channel/OA lookup indexes.
- `channel_events`
  - normalized event metadata, payload digest, text where applicable, queue status and receipt time;
  - unique event key and status/receipt queue indexes.

Startup created all indexes additively against the existing local Mongo database. No collection was dropped, rewritten, deleted or reseeded.

## API surface

```text
POST   /api/agent/auth/zalo/start
GET    /api/agent/auth/zalo/callback

POST   /api/agent/channel-links/zalo
GET    /api/agent/channel-links/zalo/:attempt_id
DELETE /api/agent/channel-links/zalo

GET    /api/agent/zalo/webhook
POST   /api/agent/zalo/webhook
```

`GET /api/agent/auth/me` now includes provider capabilities, the public list of identities attached to the user, an optional Zalo avatar, and non-secret OA link status.

The public VPS/BFF paths are expected to be:

```text
https://agent.pawgrammers.io.vn/agent/api/agent/auth/zalo/callback
https://agent.pawgrammers.io.vn/agent/api/agent/zalo/webhook
```

## Automated verification

Commands:

```powershell
docker compose run --rm --no-deps agent python -m pytest tests -q

cd agent_frontend
npm test
npm run build
```

Results:

- Backend: `250 passed`, including eight focused Zalo tests.
- Frontend: `59 passed`.
- Vite production build: passed, 2,578 modules transformed.
- Focused Zalo coverage includes PKCE/state storage, state replay, browser binding, explicit provider attachment, cross-account conflict, no provider-token persistence, CSRF on OAuth start, opaque HttpOnly callback session, provider-compatible acknowledgement with fail-closed webhook processing, durable unlinked event, one-time OA link and replay deduplication, signed-follow identity matching, rejection of mismatched app-scoped identity, and legacy naive Mongo datetime compatibility.

## Live runtime and browser evidence

- Production version `2026-07-18.3` is healthy and advertises `zalo-oa-signed-follow-link`.
- Webhook health reports `configured: true`, OA ID `2224936774907333597`, and OA name `IOT Generation`.
- The Zalo developer console points to `https://agent.pawgrammers.io.vn/agent/api/agent/zalo/webhook`; `user_send_text` and `follow` delivery are enabled.
- The production browser retained the authenticated Zalo account `Lê Nguyên` and its account-owned campaign history after deployment.
- The OA-link dialog rendered the official widget as `Đã quan tâm`, the exact OA name, direct `zalo.me` link, status polling, and the expandable one-time message fallback.
- Because this acceptance account already followed the OA, Zalo emitted no new real-user follow event during this browser pass. The automatic signed-follow path is covered by focused tests; final real-provider proof requires an unfollow/refollow or a second Zalo account. The signed text-code path remains the expected fallback for an existing follower.
- Rollback snapshot: `/var/backups/advertising-agent/20260718-zalo-follow-3`; no Mongo data was deleted, reseeded or migrated in place.

## Live activation state

Required secrets/configuration:

- `ZALO_APP_ID`
- `ZALO_APP_SECRET`
- registered `ZALO_LOGIN_REDIRECT_URI`
- `ZALO_OA_ID`
- `ZALO_OA_SECRET`

Defaults remain off in the repository, while the VPS service environment explicitly enables the configured Zalo Login and OA integration:

```env
ZALO_LOGIN_ENABLED=false
ZALO_OA_ENABLED=false
```

Secrets exist only in the Agent service environment and are not committed. The shared webhook has been cut over from the retired KFC integration to Advertising Agent.

## Remaining FE-3 work

- OA admin consent and rotating access/refresh-token manager for outbound sends.
- Durable worker/lease that converts `channel_events` into the same Guided/Autopilot commands used by web.
- Account-owned Zalo conversation creation/resume and preservation when an anonymous OA sender links later.
- Text/image rendering, outbound idempotency, delivery receipts and transient retry.
- Approval ambiguity rules, campaign-operation policy and deep links.
- Real-provider signed-follow acceptance using a Zalo account that is not already following the OA.
