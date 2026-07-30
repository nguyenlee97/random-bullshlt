# Production-to-hackathon handoff — 2026-07-30

## Purpose and source of truth

This document is the durable starting point for the next task. It records the
state observed on 2026-07-30 before any further feature work or hackathon
promotion.

The three states must not be conflated:

1. **Production live baseline:** commit
   `16992b7752ebcf5e9fd0bd2db64ba4aeb6824e17`, build
   `2026-07-30.10`.
2. **Hackathon live baseline:** release artifact
   `20260730-004731-brief-date-normalization-2026-07-30.8`, build
   `2026-07-30.8`. The artifact has no `.git` directory, so its source commit
   cannot be proven from the VPS.
3. **Next production candidate:** local build number `2026-07-30.11` in the
   current working tree. It is staged for a future commit but has not been
   committed, pushed, deployed, or browser-accepted.

No password, token, API key, OAuth secret, or private key is recorded here.

## 1. Non-negotiable deployment strategy

Production is currently the acceptance and testing environment.

The required sequence is:

1. Finish the current fixes locally.
2. Deploy the candidate to production only.
3. Verify the complete acceptance set on production, including the affected
   browser flows.
4. Commit and push the exact production-tested source. Record the full commit
   SHA and final `BUILD_VERSION`.
5. Create the hackathon release from that exact commit. Do not rebuild from a
   dirty tree and do not manually copy a different collection of files.
6. Apply only the documented environment substitutions in this handoff.
7. Rebuild the hackathon RAG index and verify persistent-data steps.
8. Verify hackathon `/agent/health` and `/agent/ready`.
9. Activate and validate Zalo incrementally.
10. Produce the final production-versus-hackathon parity table.

The hackathon VPS must reach code and build parity with the accepted production
release. Permitted differences are limited to domain/service routing, isolated
persistent data, Zalo OA/App identity and credentials, secret storage, and the
intentional absence of Langfuse. Agent logic, behavior flags, backend behavior,
publisher behavior, UI behavior, reports, screenshots, and Zalo conversation
behavior must otherwise be the same.

## 2. Environment matrix

### Runtime topology and URLs

| Concern | Production | Hackathon | Classification |
|---|---|---|---|
| Public UI | `https://agent.pawgrammers.io.vn/` and `/agent` | `https://zah-4.123c.vn/` and `/agent` | Intentional domain difference |
| Agent API | Direct: `https://agent-api.pawgrammers.io.vn`; browser proxy: `https://agent.pawgrammers.io.vn/agent/` | Browser proxy: `https://zah-4.123c.vn/agent/`; Compose service `http://agent:8080` | Intentional route difference |
| Backend API | `https://api.pawgrammers.io.vn` | Browser proxy `/backend/` and `/api/`; Compose service `http://backend:3000` | Intentional route difference |
| Adspilot | `https://adspilot.pawgrammers.io.vn` | `https://zah-4.123c.vn/adspilot/` | Intentional route difference |
| Analytics | `https://analytics.pawgrammers.io.vn` | `https://zah-4.123c.vn/analytics/` | Intentional route difference |
| Publisher sites | Production ZNews, BaoMoi, ZingMP3, SMoney, DiCungCon and Zagoo hosts | `/znews/`, `/baomoi/`, `/zingmp3/`, `/smoney/`, `/dicungcon/`, `/zagoo/` on `zah-4.123c.vn` | Intentional route difference; behavior must match |
| Frontend hosting | Nginx static files under `/var/www/agent` | `frontend` container, exposed only at `127.0.0.1:5175`, then host Nginx TLS proxy | Intentional deployment difference |
| Agent service | PM2 process `agent-api`; cwd `/var/www/agent-api`; Uvicorn on `127.0.0.1:8000` | Compose service `agent`; Uvicorn on container port `8080` | Intentional deployment difference |
| Backend service | PM2 process `adspilot-api`; cwd `/var/www/backend` | Compose service `backend`; Node on container port `3000` | Intentional deployment difference |
| Mongo | Production Mongo URI is secret-backed; Agent database `camp_ads` | One private `mongo:8` container with separate `camp_ads` and `adspilot` databases; named volume `advertising-agent-hackathon_mongo_data`; no public port | Intentional data isolation |
| Qdrant | `http://127.0.0.1:6333`; collection `dmp_segments` | `http://qdrant:6333`; dedicated volume `advertising-agent-hackathon_qdrant_data`; no public port | Intentional data isolation |
| Uploads | Production backend storage | `advertising-agent-hackathon_backend_uploads` | Intentional data isolation |
| Model caches | Production host caches | `advertising-agent-hackathon_hf_cache` and `advertising-agent-hackathon_fastembed_cache` | Intentional data isolation |
| Zalo tokens | `/var/lib/advertising-agent/zalo-oa-token.json` | `/app/data/zalo/tokens.json` on `advertising-agent-hackathon_zalo_tokens` | Intentional credential isolation |
| Namespace | `local-demo` | `zah4-hackathon` | Intentional environment difference |
| Observability | Langfuse enabled; credentials present in production secret store | Langfuse variables deliberately empty | Approved exception |

The hackathon Compose project is named `advertising-agent-hackathon` and
contains:

- `frontend`
- `agent`
- `backend`
- one-shot `seed`
- `mongo`
- `qdrant`
- `adspilot`
- `analytics`
- `znews`
- `baomoi`
- `zingmp3`
- `smoney`
- `dicungcon`
- `zagoo`

All hackathon stateful services use dedicated named volumes and do not publish
Mongo or Qdrant to the public network.

### Shared behavior flags

The following values must be identical in production and hackathon. These
effective values were verified for production and, where listed in the running
container environment, for hackathon:

| Flag | Required value |
|---|---|
| `GREENNODE_CAMPAIGN_ENABLED` | `false` |
| `OPENAI_CAMPAIGN_ENABLED` | `true` |
| `USE_CAMPAIGN_AUTOPILOT` | `true` |
| `USE_RAG_AUDIENCE` | `true` |
| `AUDIENCE_RAG_RETRIEVAL_MODE` | `hybrid_dense_bm25` |
| `AUDIENCE_RERANK_MODE` | `openai_nano` |
| `PLACEMENT_RAG_ENABLED` | `true` |
| `PLACEMENT_RERANK_ENABLED` | `true` |
| `RAG_QUERY_REWRITE` | `false` |
| `RAG_USE_CRITIC_SELECTOR` | `false` |
| `USE_LANGGRAPH_FREEFORM` | `false` |
| `USE_VLM_CREATIVE` | `true` |
| `ACCOUNT_COOKIE_SECURE` | `true` |
| `ANONYMOUS_COOKIE_SECURE` | `true` |
| `GUARDRAIL_MODE` | `enforce` |
| `ZALO_AUTOPILOT_CONVERSATION_MODEL` | `openai_gpt_5_4_mini` |

Production also reported:

- `OPENAI_CAMPAIGN_MODEL=gpt-5.4-mini`
- `OPENAI_CAMPAIGN_REASONING_EFFORT=low`
- `OPENAI_CAMPAIGN_MAX_OUTPUT_TOKENS=2000`
- `OPENAI_CAMPAIGN_TIMEOUT_SECONDS=45`
- `OPENAI_IMAGE_ENABLED=true`
- `OPENAI_IMAGE_MODEL=gpt-image-2`
- `QUALITY_DATA_ENABLED=true`
- `RAG_COLLECTION=dmp_segments`

Before promotion, print the effective runtime values from both running
containers/processes again. A checked-in example file is not evidence of the
effective environment.

### Zalo configuration

| Setting | Production | Hackathon |
|---|---|---|
| Zalo App ID | `990183335072014581` | `669472079566550173` |
| OA ID | `2224936774907333597` | `847163434345003951` |
| OA name | `IOT Generation` | `Advertising Agent` |
| Login callback | `https://agent.pawgrammers.io.vn/agent/api/agent/auth/zalo/callback` | `https://zah-4.123c.vn/agent/api/agent/auth/zalo/callback` |
| Workspace URL | `https://agent.pawgrammers.io.vn` | `https://zah-4.123c.vn` |
| Token persistence | Production root-owned token file | Dedicated Compose token volume |

Effective production Zalo switches were all enabled:

- `ZALO_LOGIN_ENABLED=true`
- `ZALO_OA_ENABLED=true`
- `ZALO_AGENT_WORKER_ENABLED=true`
- `ZALO_OUTBOUND_ENABLED=true`
- `ZALO_OPENAI_ENABLED=true`

The running hackathon `.8` container also currently has all five switches set
to `true`. This is the current state, not the safe activation sequence. For a
fresh or replaced hackathon release, start all five at `false`, verify the
independent stack and callbacks, then enable them in the order described in
section 5.

### Secret names and storage only

Never commit actual values. Relevant secret names include:

- `AI_PLATFORM_API_KEY`
- `LLM_API_KEY`
- `OPENAI_API_KEY`
- `AGENT_API_KEY`
- `ZALO_APP_SECRET`
- `ZALO_OA_SECRET`
- `ZALO_OA_ACCESS_TOKEN`
- `ZALO_OA_REFRESH_TOKEN`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `RESEND_API_KEY`

Storage:

- Production Agent secrets: `/var/www/agent-api/.env`.
- Production rotated OA tokens:
  `/var/lib/advertising-agent/zalo-oa-token.json`.
- Production backend secrets: `/var/www/backend/.env`.
- Hackathon deployment secrets:
  `/opt/advertising-agent/current/deploy/hackathon/stack.env`,
  `agent.env`, and `backend.env`, plus the dedicated `zalo_tokens` volume.
- Hackathon env files must be mode `0600` and must not be committed.
- TLS private keys remain under host Nginx certificate storage and are not
  copied into the repository.

Production Agent `.env` and the OA token store were observed mode `0600`.
Production `/var/www/backend/.env` was observed mode `0666`; this is a security
finding to remediate separately because this handoff did not change production
permissions.

## 3. Release ledger

### Releases and candidates

| State | Branch / source | Git commit | `BUILD_VERSION` | Deployment evidence |
|---|---|---|---|---|
| Production live | `revamp/next-hackathon` | `16992b7752ebcf5e9fd0bd2db64ba4aeb6824e17` | `2026-07-30.10` | Agent PM2 process created `2026-07-30T08:43:47.599Z`; frontend last modified `2026-07-30T08:41:52Z`; live endpoints report `.10` |
| Previous production feature release | same branch | `5a2e3fcce712783aea8f7cd7e888d1805c2e5a25` | `2026-07-30.9` | Release directory `/var/www/agent-releases/5a2e3fc`; included Autopilot creative workflow hardening |
| Hackathon live | release artifact without Git metadata | **unknown from VPS** | `2026-07-30.8` | `/opt/advertising-agent/releases/20260730-004731-brief-date-normalization-2026-07-30.8`; `/opt/advertising-agent/current` resolves there |
| Next production candidate | current staged working tree on `revamp/next-hackathon` | **not committed** | `2026-07-30.11` | Local tests only; not pushed, deployed, or browser-accepted |

Do not assign commit `16992b7…` to the hackathon `.8` release. The VPS release
has no Git metadata and predates production `.9` and `.10`.

### What production `.9` and `.10` contain

Commit `5a2e3fc…` (`.9`) contains the large Autopilot creative workflow batch,
including:

- stable review-artifact navigation
- creative-source and approval-policy workflow controls
- generative creative prompt and asset handling improvements
- skip/start creative analysis controls and inline analysis evidence
- assignment-map visibility and creative mapping improvements
- campaign/report chat milestone signaling
- ratio-aware creative preparation
- Zalo live-site screenshot route selection
- PDF export fixes and local deployment routing changes

Commit `16992b7…` (`.10`) adds:

- mobile bottom-clearance helper
- removal of the destructive Adspilot reset/reseed API and documentation/UI
  surface

### Current `.11` candidate

The current candidate addresses the two newest reported production issues:

1. Lock **Chọn cách Agent xin duyệt** until the user chooses the creative
   approach, and guide the user through brief confirmation → creative approach
   → approval policy in chat.
2. Preserve a trusted server-side “skip creative analysis” verdict through
   order-draft construction and both safety gates, including hydration of
   pre-fix drafts, without trusting client-supplied override flags.

Tracked modified files:

- `agent/autopilot/capabilities.py`
- `agent/tests/test_autopilot_service.py`
- `agent/tests/test_order_guard.py`
- `agent/validation/order_guard.py`
- `agent/version.py`
- `agent_frontend/src/App.jsx`
- `agent_frontend/src/components/AutopilotPanel.jsx`
- `agent_frontend/tests/autopilotStateSafety.test.mjs`

New candidate test:

- `agent_frontend/tests/autopilotPreferenceSequence.test.mjs`

Deployment/promotion support files that must be versioned with the release:

- `docker-compose.hackathon.yml`
- `deploy/hackathon/README.md`
- `deploy/hackathon/agent.env.example`
- `deploy/hackathon/backend.env.example`
- `deploy/hackathon/stack.env.example`
- `deploy/hackathon/nginx-zah-4.conf`
- `agent_frontend/public/zalo-oa-qr-hackathon.png`
- `agent_frontend/public/zalo_verifierFO-V5yExAJyIhuu5-Aeb93lRyW3NhIXTEJ4p.html`
- `docs/handoffs/2026-07-30-production-to-hackathon.md`

### Tests and browser scenarios

Production `.10` verification already completed during its deployment:

- 181 frontend tests passed.
- 53 focused backend tests passed.
- The production mobile bottom-clearance helper was verified in the browser.
- Production destructive endpoints `/api/admin/reset` and
  `/api/admin/reseed-zones` returned `404`.

Current `.11` local verification:

- 184 frontend tests passed.
- 101 focused backend tests passed.
- Vite transformed 2,601 modules and emitted the complete production build.
- The final frontend asset is `/assets/index-eGhitnR1.js`.

Completed `.11` production acceptance:

- Production conversation
  `conv_83af8ea6ec044da684fb407771867a77` passed **Kiểm tra an toàn** after
  the worker-authored skip verdicts were re-evaluated.
- The run advanced to **Duyệt launch** without creating an order.
- Approval-policy cards stayed disabled until a creative source was selected.
- Creative-source A → B → A changes persisted after each distinct operator
  action; the QA campaign was restored to its original upload preference.
- The browser loaded Agent `v2026-07-30.11` from
  `/assets/index-eGhitnR1.js`.

Known incomplete acceptance:

- The full `.9` bug batch needs a final acceptance pass before any promotion:
  review-anchor navigation, creative-source gating, generated/upload paths,
  analysis start/skip/flag/approve branches, assignment visibility, chat
  milestones, creative ratio behavior, correct publisher screenshot route, UI
  PDF export and Zalo PDF export.
- No hackathon parity verification has been run against `.9`, `.10`, or `.11`.

### Database, index and persistent-data ledger

- `.11` introduces no Mongo migration, index, RAG corpus change, or persistent
  data mutation.
- `.10` introduces no Mongo migration, index, or RAG change.
- Hackathon bootstrap seeds backend data with:
  `node seed/index.js`,
  `node seed/seed-audience-missing.js`, and
  `node seed/migrate-np6-catalog.js --apply
  --deployment-id=zah4-hackathon-np6`.
- The one-shot hackathon `seed` container currently shows `Exited (0)`.
- Qdrant data is environment-specific. Every promoted release must run
  `python scripts/build_rag_index.py --force` in the hackathon Agent container
  and then pass `/agent/ready`.
- Do not copy production Mongo, Qdrant, upload, cache, or Zalo token volumes to
  the hackathon environment.

## 4. Current production state

### Live evidence

Observed on 2026-07-30:

| Check | Result |
|---|---|
| `https://agent-api.pawgrammers.io.vn/health` | `200`, `{"status":"ok","version":"2026-07-30.11"}` |
| `https://agent-api.pawgrammers.io.vn/ready` | `200`, `status=ready`; Mongo, backend, RAG index/runtime, creative worker, Autopilot worker, Zalo worker and Zalo OpenAI all `true` |
| `https://agent-api.pawgrammers.io.vn/api/version` | `200`, version `.11` |
| `https://agent.pawgrammers.io.vn/agent/health` | `200`, version `.11` |
| `https://agent.pawgrammers.io.vn/agent/ready` | `200`, all readiness checks `true` |
| `https://api.pawgrammers.io.vn/api/health` | `200`, database connected, environment `production` |
| Frontend | `200`; asset `/assets/index-eGhitnR1.js`; browser UI reported Agent `v2026-07-30.11` |

PM2 reported both `agent-api` and `adspilot-api` online. The current affected
browser flow loads correctly and shows:

- Campaign Autopilot, Plan v1
- 3/3 brief stages
- 2/2 audience stages
- 6/6 placement/creative stages
- 3/3 forecast/safety stages
- 0/4 launch stages
- three generated creatives
- “Đã bỏ qua Creative Intelligence”
- a four-zone creative assignment map
- launch approval available, with no order created during validation

### Effective production environment, redacted

The effective non-secret values are recorded in section 2. Secret presence was
confirmed for the production AI provider, OpenAI, Zalo App, Zalo OA and
Langfuse credentials, but values were not read into this document.

The legacy `DEFAULT_CONVERSATION_MODEL` is `greennode_minimax`; this does not
mean the current Zalo Autopilot path uses GreenNode. New Zalo Autopilot
conversations are explicitly locked to
`ZALO_AUTOPILOT_CONVERSATION_MODEL=openai_gpt_5_4_mini`, and
`GREENNODE_CAMPAIGN_ENABLED=false`.

### Rollback

Known production static snapshots:

- `/var/www/agent-releases/16992b7-hotfix`
- `/var/www/agent-releases/5a2e3fc`

Rollback procedure:

1. Identify the last accepted full commit and release snapshot.
2. Restore the matching Agent/backend source from that commit or its deployment
   backup; do not combine source from different builds.
3. Atomically restore the matching frontend static directory to
   `/var/www/agent`.
4. Restart `agent-api` and `adspilot-api` with PM2.
5. Verify direct and proxied `/health`, `/ready`, `/api/version`, frontend asset
   version, and the affected browser flow.

Accepted `.11` frontend snapshot:

- `/var/www/agent-releases/20260730-230036-2026-07-30.11-precommit`

The matching Agent source has a pre-deployment backup at:

- `/var/www/agent-api/backups/20260730-230036-pre-2026-07-30.11`

## 5. Current hackathon state

### Connectivity and installed state

SSH connectivity succeeded to the supplied VPS IP on port `2222` as the
hackathon user. Observed software:

- Docker `29.6.2`
- Docker Compose `v5.3.1`
- Nginx `1.20.1`
- Git `2.43.5`

The full Compose stack is installed and running. Agent, frontend, backend and
all publisher/static services were up; Mongo was healthy; Qdrant was up; the
one-shot seed exited successfully.

Live evidence:

| Check | Result |
|---|---|
| `https://zah-4.123c.vn/agent/health` | `200`, build `2026-07-30.8` |
| `https://zah-4.123c.vn/agent/ready` | `200`; Mongo, backend, RAG index/runtime, creative worker, Autopilot worker, Zalo worker and Zalo OpenAI all `true` |
| Frontend | `200`; last modified `2026-07-30T04:17:52Z`; asset `/assets/index-CHVH-_l1.js` |
| Current release | `/opt/advertising-agent/releases/20260730-004731-brief-date-normalization-2026-07-30.8` |
| Current symlink | `/opt/advertising-agent/current` resolves to the `.8` release |

What has **not** been deployed:

- production `.9` / commit `5a2e3fc…`
- production `.10` / commit `16992b7…`
- local candidate `.11`

The current hackathon artifact has no Git metadata. A final parity claim is
therefore impossible for `.8`; the next promotion must embed or retain the
source commit identifier.

### Required deployment files and commands

Required versioned files:

- `docker-compose.hackathon.yml`
- `deploy/hackathon/README.md`
- `deploy/hackathon/nginx-zah-4.conf`
- the three `*.env.example` files
- the two hackathon Zalo public assets

Required uncommitted, server-only files:

- `deploy/hackathon/stack.env`
- `deploy/hackathon/agent.env`
- `deploy/hackathon/backend.env`

From the release root:

```sh
docker compose \
  --env-file deploy/hackathon/stack.env \
  -f docker-compose.hackathon.yml \
  up -d --build

docker compose \
  --env-file deploy/hackathon/stack.env \
  -f docker-compose.hackathon.yml \
  exec agent python scripts/build_rag_index.py --force
```

The Agent container intentionally uses `/health` while bootstrapping. Promotion
is not accepted until `/agent/ready` is green after the forced RAG build.

Host Nginx uses `zah-4.123c.vn` and proxies to
`http://127.0.0.1:5175`. TLS certificate and private-key files remain on the
host and are not part of the source release.

### Zalo activation order

Current `.8` state is all five switches enabled. For a new release:

1. Start with `ZALO_LOGIN_ENABLED=false`,
   `ZALO_OA_ENABLED=false`, `ZALO_AGENT_WORKER_ENABLED=false`,
   `ZALO_OUTBOUND_ENABLED=false`, and `ZALO_OPENAI_ENABLED=false`.
2. Verify the independent stack, TLS domain, callback URL and webhook URL.
3. Configure the hackathon App/OA secrets and token store.
4. Verify webhook signature rejection/acceptance and replay protection.
5. Enable Zalo login and OA webhook reception.
6. Enable the Agent worker and verify inbound processing without outbound sends.
7. Enable Zalo OpenAI and verify the intended model policy.
8. Enable outbound delivery last.
9. Run a real inbound → Agent → outbound smoke test and confirm the message
   stays in the hackathon workspace and links only to `zah-4.123c.vn`.

## 6. Promotion checklist

### Production acceptance

- [x] Deploy `.11` to production only.
- [x] Confirm live `/health`, `/ready`, `/api/version` and frontend version all
      report the same build.
- [x] Re-run the broken skip-analysis conversation or a clean equivalent
      through safety and up to Launching without launching.
- [x] Verify approval-policy cards stay locked until creative approach is
      chosen.
- [x] Verify chat guides brief confirmation → creative approach → approval
      policy.
- [ ] Run upload and AI-generated creative paths.
- [ ] Run analysis start, analysis skip, flagged/manual approve and successful
      approval branches.
- [ ] Verify review-anchor navigation does not create or switch conversations.
- [ ] Verify assignment map before and after approval.
- [ ] Verify chat milestone signals.
- [ ] Verify ratio-aware creative output.
- [ ] Verify correct category-page screenshot routing.
- [ ] Verify PDF export in UI and Zalo.
- [ ] Re-check mobile clearance and destructive endpoints.

### Freeze exact tested source

- [x] Run all release tests and a clean production frontend build.
- [x] Record all database/index/persistent-data steps.
- [x] Confirm the staged tree contains only intended release files; preserve
      the unrelated untracked files listed below.
- [ ] Commit the exact production-tested tree.
- [ ] Push the branch and record the full remote commit SHA.
- [ ] Confirm the committed `agent/version.py` matches the live production
      version.
- [ ] Create a source artifact from that exact commit and include the commit SHA
      in release metadata.

### Promote to hackathon

- [ ] Copy/extract the exact committed artifact to a new
      `/opt/advertising-agent/releases/<timestamp>-<version>` directory.
- [ ] Apply only documented hackathon domain, Compose, isolated data, secret
      location, Zalo identity and Langfuse substitutions.
- [ ] Keep Mongo, Qdrant, uploads, caches and Zalo tokens on their dedicated
      volumes.
- [ ] Start Compose with all Zalo switches off.
- [ ] Confirm the one-shot seed/migration completes successfully.
- [ ] Force-build the hackathon RAG index.
- [ ] Verify `/agent/health` reports the exact production build.
- [ ] Verify `/agent/ready` is green.
- [ ] Activate Zalo incrementally in the order above.
- [ ] Run the production acceptance scenarios on hackathon.

### Final parity table to produce

| Check | Production evidence | Hackathon evidence | Parity |
|---|---|---|---|
| Full source commit |  |  |  |
| `BUILD_VERSION` |  |  |  |
| Frontend asset/build |  |  |  |
| Shared behavior flags |  |  |  |
| Agent `/health` |  |  |  |
| Agent `/ready` |  |  |  |
| Backend health |  |  |  |
| Mongo seed/migrations |  |  |  |
| Qdrant collection/build |  |  |  |
| Copilot walkthrough |  |  |  |
| Autopilot walkthrough |  |  |  |
| Creative analysis and skip |  |  |  |
| Creative assignment |  |  |  |
| Publisher screenshots |  |  |  |
| UI PDF export |  |  |  |
| Zalo PDF export |  |  |  |
| Zalo inbound/outbound |  |  |  |
| Intentional differences only |  |  |  |

## 7. Working-tree handoff

Branch:

```text
revamp/next-hackathon
```

Parent commit at handoff intake:

```text
16992b7752ebcf5e9fd0bd2db64ba4aeb6824e17
```

The release source is the commit containing this document. Obtain and verify
its immutable identifier with `git rev-parse HEAD`; production and hackathon
release metadata must record that same full SHA.

Intentionally preserved unrelated untracked files:

- `AGENTS.md`
- `DEMO-VIDEO-PRODUCTION-GUIDE.md`
- `DEMO-VIDEO-REHEARSAL-CUE-CARD.md`
- `agent/graph/README.md`
- `docs/copy-review/01-public-and-homepage.md`
- `docs/copy-review/02-workspace-and-workflows.md`
- `docs/copy-review/03-tours-and-walkthroughs.md`
- `docs/copy-review/04-agent-messages.md`
- `docs/copy-review/05-raw-source-literals.md`
- `docs/copy-review/06-raw-agent-literals.md`
- `docs/copy-review/README.md`

Commit/push status:

- No `.11` commit exists.
- No `.11` push has occurred.
- This is not an authentication or remote rejection claim; commit/push were
  deliberately not attempted because production acceptance has not happened.
- Do not claim `.11` is a release until it is deployed and accepted on
  production, committed, and pushed.
