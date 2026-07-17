# Advertising Agent — FE-2B Local Accounts Handoff

Status: ready for a new implementation task  
Prepared: 2026-07-17  
Branch: `revamp/next-hackathon`  
Starting commit: `3eea598` (`fix(frontend): render report analysis answers`)

## 1. Decision: what comes next

The next roadmap item is **FE-2B: local accounts and cross-device conversation ownership**.

The following foundations are already complete:

- anonymous identity in an HttpOnly cookie;
- homepage mode selection;
- same-device conversation history;
- exact conversation/workspace/Autopilot resume;
- archive, individual deletion and delete-all;
- owner checks for conversation-backed sessions;
- Guided and Autopilot campaign creation, upload/AI creative paths and shared reporting.

Do not spend the next task reworking Autopilot UX unless a regression blocks FE-2B. The order after FE-2B is Google OIDC, then Zalo Login/OA identity linking, then the Zalo channel adapter.

## 2. Current verified state

At handoff time:

- all local Compose services are running; application services are healthy;
- agent suite: `234 passed`;
- frontend suite: `52 passed` at commit `3eea598`;
- the production frontend build passes;
- the latest user journey completed campaign creation and opened Result, Setup report and Analysis report successfully;
- the full 128-scenario release suite is still a later FE-5 gate, not a prerequisite for starting FE-2B.

Preserve these user-owned untracked files and do not include them in commits:

- `AGENTS.md`
- `agent/graph/README.md`

## 3. FE-2B outcome

A visitor can still use Advertising Agent anonymously without seeing a login wall. A visitor may register or log in, explicitly attach an anonymous campaign to the account, log in from another browser/device, and resume the exact canonical campaign state.

FE-2B is complete only when all of the following are true:

1. Anonymous Guided and Autopilot journeys still work without an account.
2. A local account can register, log in, log out and query its current identity.
3. Passwords are Argon2id hashes and never appear in responses, logs or traces.
4. Account sessions use an opaque, server-revocable HttpOnly cookie; no account token is stored in `localStorage`.
5. Claiming is explicit. Login must never silently attach device conversations.
6. Claim preserves `conversation_id`, `session_id`, transcript, workspace revision/artifacts, proposals, creative jobs, graph checkpoints and the latest Autopilot run.
7. The old anonymous identity loses access to a claimed conversation after account logout.
8. The account can resume claimed conversations from a second browser.
9. A different account receives a non-enumerating `404` for the conversation and cannot claim or mutate it.
10. Existing anonymous tests, evaluators and campaign flows remain green.

## 4. Scope boundaries

### Implement now

- local email/password registration and login;
- logout and `GET /auth/me`;
- revocable account sessions;
- CSRF protection for browser cookie-authenticated mutations;
- account-owned conversation listing/resume;
- explicit claim of an anonymous conversation;
- cross-device ownership and authorization tests;
- minimal account UI integrated into the existing homepage/history experience;
- indexes, configuration, migration compatibility, documentation and focused evidence.

### Do not implement now

- Google OAuth/OIDC;
- Zalo Login;
- Zalo OA webhook/channel adapter;
- organization membership, tenant RBAC or shared campaigns;
- campaign analytics/optimization agent;
- Qwen reranker enablement;
- automatic claiming of every device conversation;
- a separate auth service in the Node backend;
- destructive migration of existing `anonymous_identities` or `agent_conversations`.

Email verification and password-reset delivery need an outbound email decision. Keep the schema ready for verification/reset, but do not invent a fake production email flow in FE-2B. Record it as the first follow-up before public deployment.

## 5. Architecture decision

Keep identity and conversation ownership in the FastAPI agent service and its Mongo database. That service already owns anonymous identities, conversations, workspaces, proposals, graph checkpoints and Autopilot runs. Building a second account authority in the Node campaign backend would split ownership and create inconsistent authorization.

```text
Browser
  |-- aa_anonymous: HttpOnly device credential
  |-- aa_account:   HttpOnly account-session credential
  |-- aa_csrf:      readable double-submit CSRF value
  v
Frontend nginx BFF (/agent)
  v
FastAPI actor resolver
  |-- account session -> user_id
  |-- anonymous cookie -> anonymous_id
  v
Conversation authorization
  |-- owner_user_id matches authenticated user
  |-- otherwise anonymous_id matches current device identity
  |-- legacy evaluator session with no conversation owner remains compatible
```

The account session is preferred for account-owned conversations. The anonymous credential remains present so the same browser can list and explicitly claim device-only conversations.

## 6. Mongo model

Use opaque IDs; do not expose Mongo ObjectIds as credentials.

### `users`

```text
_id/user_id       usr_<random>
display_name      sanitized, 1..80 characters
status            active | disabled
created_at
updated_at
last_seen_at
```

### `auth_identities`

```text
_id
user_id
provider          local (Google/Zalo will reuse this collection later)
provider_subject  normalized email for local provider
email_normalized
email_verified    false initially
password_hash     Argon2id only
created_at
updated_at
```

Required unique index: `(provider, provider_subject)`.

### `account_sessions`

```text
_id/session_id
user_id
token_hash        SHA-256 of a high-entropy random token
created_at
last_seen_at
expires_at
revoked_at?
user_agent_label? non-sensitive display metadata only
```

Required indexes: unique `token_hash`, `user_id`, and TTL `expires_at`. Store only the token hash. Rotate the cookie on successful login.

### Existing `anonymous_identities`

Keep existing fields and add nullable audit/link fields only if needed:

```text
claimed_by_user_id?
claimed_at?
```

This field does not automatically transfer all conversations. Conversation ownership remains authoritative.

### Existing `agent_conversations`

Migrate additively:

```text
owner_user_id?             account owner
anonymous_id?              existing identity_id normalized/aliased
claimed_from_anonymous_id? audit only
claimed_at?
```

Existing `identity_id` documents must continue to work during migration. A claimed conversation has exactly one active owner: `owner_user_id`. Do not change its conversation/session IDs.

## 7. Actor and authorization rules

Introduce one server-side actor resolver. Do not accept `user_id`, `anonymous_id`, conversation owner or workspace owner from a browser payload.

Suggested actor shape:

```python
{
    "user_id": "usr_..." | None,
    "anonymous_id": "anon_..." | None,
    "account_session_id": "ase_..." | None,
}
```

Authorization rules:

- account-owned conversation: require matching `actor.user_id`;
- unclaimed anonymous conversation: require matching `actor.anonymous_id`;
- claim: require both a valid account session and the anonymous credential that owns the unclaimed conversation;
- claim update must be conditional/atomic so two accounts cannot race;
- repeated claim by the same account may return the current resource idempotently;
- claim by another account or device returns `404`, not ownership details;
- conversation-backed workspace/run/proposal/creative endpoints continue using the shared session-access guard;
- legacy evaluator sessions without a conversation record retain current migration compatibility.

## 8. Cookie and CSRF policy

Suggested names:

- `aa_anonymous`: existing anonymous credential, HttpOnly;
- `aa_account`: account-session credential, HttpOnly;
- `aa_csrf`: random double-submit value, readable by the frontend.

All cookies use `Path=/`, `SameSite=Lax`, configured `Secure`, and explicit expiration. Account logout revokes the server-side session and clears `aa_account`; it does not delete the anonymous cookie.

For cookie-authenticated `POST`, `PUT`, `PATCH` and `DELETE` requests, compare `aa_csrf` with `X-CSRF-Token` using constant-time comparison. Exempt only the initial anonymous bootstrap and endpoints that cannot mutate state. API/evaluator calls with no browser credential cookie remain governed by the existing API-key/migration rules.

Update the shared `agentFetch` helper once so every browser mutation sends the CSRF header. Do not sprinkle token handling through feature components.

## 9. API contract

Keep routes under the current agent BFF boundary for this slice:

```text
POST   /api/agent/auth/register
POST   /api/agent/auth/login
POST   /api/agent/auth/logout
GET    /api/agent/auth/me
GET    /api/agent/auth/sessions
DELETE /api/agent/auth/sessions/:session_id
POST   /api/agent/conversations/:conversation_id/claim
```

### Register

Request:

```json
{"email":"user@example.com","password":"...","display_name":"Nguyen An"}
```

Response sets `aa_account` and returns only public user/session data. Normalize email with `strip + casefold`; validate before storing. Duplicate local identity returns `409`. Apply a strict registration rate limit.

### Login

Request:

```json
{"email":"user@example.com","password":"..."}
```

Invalid email/password returns the same generic `401` response. Apply per-IP and account-key rate limits. Successful login rotates the account session and returns public user data plus `has_claimable_conversations`.

### Current identity

`GET /auth/me` returns:

```json
{
  "authenticated": true,
  "user": {"user_id":"usr_...","display_name":"Nguyen An","email":"user@example.com"},
  "anonymous_identity_present": true
}
```

Anonymous response is `200` with `authenticated: false`; page boot must not fail because the visitor is logged out.

### Claim

`POST /conversations/:id/claim` has no owner ID in its body. It atomically changes only the ownership fields and returns the same conversation/session IDs. It must not copy or recreate campaign artifacts.

### Conversation listing

When authenticated, return:

- account-owned conversations;
- unclaimed conversations from the current anonymous cookie, marked `ownership: "device"` and `can_claim: true`.

Account-owned items use `ownership: "account"`. Keep one chronological list in the API; the UI can label ownership without duplicating history state.

## 10. Frontend experience

Integrate with the current Zalo-blue homepage; do not introduce a separate app shell.

### Logged out

- Homepage remains immediately usable.
- Add a quiet `Đăng nhập` action near the Advertising Agent identity.
- Login/register opens a focused dialog or sheet.
- History continues to show device campaigns.

### After login

- Replace `Đăng nhập` with the display name/account menu.
- Refresh history from the server.
- Account campaigns are labeled `Tài khoản`; device-only campaigns are labeled `Trên thiết bị`.
- Device campaigns expose `Lưu vào tài khoản`.
- If login occurs while an anonymous campaign is open, offer to claim that campaign; do not interrupt an active Autopilot review with a forced modal.

### After claim

- Keep the current chat/workspace/run open without resetting React state.
- Update the history ownership badge in place.
- Show a concise success message.

### Logout

- Revoke the account session.
- Return to anonymous mode without deleting or resetting the current device identity.
- Claimed account campaigns disappear from history until login; unclaimed device campaigns remain.

Recommended new components:

- `components/AuthDialog.jsx`
- `components/AccountMenu.jsx`
- `components/ClaimConversationDialog.jsx`

Keep auth API/state in a small hook such as `hooks/useIdentity.js`; do not add Redux/Zustand for this slice.

## 11. Likely file map

Backend:

- `agent/identity.py` — split/refactor anonymous storage and conversation ownership carefully;
- `agent/auth.py` or `agent/accounts/service.py` — password, account and session operations;
- `agent/router.py` — public routes and shared actor dependency;
- `agent/config.py`, `agent/.env.example` — cookie/session/password settings;
- `agent/main.py` — identity indexes/lifespan and optional CSRF middleware;
- `agent/requirements.txt`, `agent/requirements.lock` — pinned Argon2 dependency;
- `agent/tests/test_identity_conversations.py` — preserve existing behavior;
- new focused tests such as `agent/tests/test_account_auth.py`.

Frontend:

- `agent_frontend/src/api/agentApi.js` — auth/claim methods and shared CSRF header;
- `agent_frontend/src/App.jsx` — top-level identity state and history refresh;
- `agent_frontend/src/components/ExperienceSelector.jsx` — login/account entry and ownership badges;
- `agent_frontend/src/components/ConversationHistory.jsx` — account/device ownership and claim action;
- `agent_frontend/src/components/TopBar.jsx` — account menu in workspace;
- focused frontend tests under `agent_frontend/tests/`.

Documentation:

- update `19-final-enhancement-phase-roadmap.md` with implementation evidence only after tests pass;
- update `18-current-system-walkthrough-and-roadmap.md` and `agent_frontend/public/tech-docs.html` after behavior exists;
- create an FE-2B evidence note with commands, test counts and browser results.

## 12. Implementation sequence

1. Add data models, indexes, password hashing and account-session primitives.
2. Add actor resolution while preserving anonymous and legacy behavior.
3. Add register/login/logout/me and focused API tests.
4. Add CSRF centrally and update the shared frontend fetch helper.
5. Add atomic conversation claim and cross-owner tests.
6. Update account-aware conversation list/resume and claim tests.
7. Add the homepage, history and workspace account UI.
8. Run all backend/frontend suites and production build.
9. Rebuild only affected Compose services.
10. Run two-browser claim/resume and authorization journeys.
11. Update evidence/current-state docs and commit the completed slice.

Do not begin UI work before the actor/claim API tests prove the ownership model.

## 13. Required tests

### Backend/API

- registration stores Argon2id, never plaintext;
- duplicate normalized email is rejected;
- valid login issues a hashed/revocable session;
- invalid email and invalid password are indistinguishable;
- disabled user cannot log in;
- logout revokes the current session;
- second session can be listed/revoked;
- expired/revoked cookie cannot access account history;
- missing/mismatched CSRF rejects mutation without side effects;
- anonymous campaign still creates/resumes;
- explicit claim preserves all IDs and artifacts;
- claim is atomic/idempotent for the owner;
- foreign account/device cannot claim/read/mutate;
- logout removes access to claimed history while preserving unclaimed device history;
- legacy evaluator sessions still pass.

### Frontend

- boot succeeds while logged out;
- registration/login errors are rendered without blanking/resetting the workspace;
- login refreshes history;
- claim action appears only for claimable device conversations;
- claim does not recreate or reset the active conversation;
- logout returns to anonymous history;
- credentials never enter local storage;
- existing mode, history, deletion, Guided and Autopilot source tests remain green.

### Browser acceptance

Use Browser A and Browser B with separate cookie jars:

1. Browser A, logged out: create an anonymous campaign and commit at least one Brief revision.
2. Register/login in Browser A; choose `Lưu vào tài khoản` for that campaign.
3. Confirm the open workspace revision, messages, mode and run state do not change.
4. Log out: the claimed campaign is no longer available anonymously.
5. Browser B: log in to the same account; list and resume the campaign.
6. Confirm exact transcript/workspace/run restoration.
7. A second account cannot open the captured conversation ID.
8. Create a new anonymous campaign after logout to prove anonymous-first usage remains intact.

## 14. Verification commands

```powershell
docker compose exec -T agent python -m pytest tests -q

cd agent_frontend
npm test
npm run build
cd ..

docker compose up -d --build --no-deps agent frontend
docker compose ps
```

Do not report success from targeted auth tests alone. The full existing agent and frontend suites must remain green.

## 15. Release/rollback rules

- Work only on `revamp/next-hackathon` unless the user explicitly chooses another branch.
- Keep `3eea598` as the pre-FE-2B rollback point.
- Do not delete or reseed local Mongo conversation data while implementing migration logic.
- Do not commit `.env`, credentials, cookies, Mongo exports or browser storage.
- Use additive fields and indexes; no destructive migration.
- Commit only after focused tests, full suites, build and browser acceptance pass.

## 16. Definition of done

FE-2B can be marked complete when code, tests, browser evidence and current-state docs all prove:

> An anonymous user can become an account user without losing campaign state, explicitly transfer ownership of a campaign, and resume it from another browser, while every unowned/foreign access is rejected server-side and the original anonymous experience remains fully functional.

