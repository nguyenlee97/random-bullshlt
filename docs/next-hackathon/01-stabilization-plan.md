# Stabilization Implementation Plan

> This is the execution guide for M0 and M1 of `00-roadmap.md`.
> Do not begin RAG/VLM enhancement work until this checklist is green.

## A. Preserve the current state

1. Record live versions and health output in `docs/release/live-baseline.md`.
2. Create a production database backup.
3. Create branch `revamp-next-hackathon`.
4. Review the current working tree:
   - Source changes in `agent_frontend/src/api/agentApi.js`.
   - Source changes in `agent_frontend/src/steps/setup/ConfirmPhase.jsx`.
   - Generated `agent_frontend/dist` changes.
   - Untracked roadmap/runbook files.
5. Commit source and documentation separately from generated bundles.
6. Tag the current rollback commit as `legacy-prod-2026-06-25` after confirming it matches production.

⛔ Do not reseed, migrate, or deploy to the live database during this step.

## B. Rotate and reorganize secrets

Rotate every credential that has appeared in chat or local files:

- GreenNode MaaS key.
- OpenAI key.
- MongoDB password.
- Langfuse secret/public pair.
- Resend key.
- Any VPS or storage credential used by scripts.

Then:

- Keep real values only in ignored `.env` files or deployment secret storage.
- Put names and safe defaults in `.env.example`.
- Add a secret scan to CI.
- Verify Git history does not contain secrets before publishing the next-hackathon repository.

## C. Establish clean environment profiles

Create explicit profiles:

```text
dev-local    frontend → local agent → local backend → local Mongo/Qdrant
staging      staging frontend → staging agent/backend/data
production   production frontend → production agent/backend/data
```

Required variables:

```dotenv
# agent_frontend/.env.local
VITE_AGENT_URL=http://localhost:8080
VITE_BACKEND_URL=http://localhost:3000

# agent/.env.local
BACKEND_URL=http://backend:3000
MONGODB_URI=mongodb://mongo:27017/camp_ads
QDRANT_URL=http://qdrant:6333
```

Do not let local frontend silently call the production backend.

## D. Rebuild the local stack

From a clean clone:

```powershell
docker compose build --no-cache agent backend
docker compose up -d
docker compose exec backend node seed/index.js
docker compose exec agent python scripts/setup_indexes.py
```

Verify:

- Agent `/health` returns 200.
- Backend `/api/health` returns 200.
- Audience endpoint returns 310 records.
- Zone endpoint returns the expected catalog count.
- Qdrant responds and collection count is correct after indexing.
- Prometheus scrapes the agent.
- Grafana loads the Agent Ops dashboard.
- Langfuse receives a trace after one chat turn.

## E. Repair dependency reproducibility

1. Choose `uv` for Python dependency locking.
2. Convert broad minimum versions into tested pins.
3. Rebuild `agent/venv` from the lock instead of patching it manually.
4. Verify these imports explicitly:
   - `pytest_asyncio`
   - `langgraph`
   - `langgraph.checkpoint.mongodb`
   - `qdrant_client`
   - `fastembed`
   - `langfuse`
   - `slowapi`
5. Continue using `npm ci` for Node projects.

## F. Fix currently known core defects

### F1. Setup-entry history gap

`handle_setup_entry()` must store the proactive assistant message in MongoDB before returning, using the same pattern as audience-entry. Add a regression test asserting that the next freeform turn can see the recommendation.

### F2. Windows startup encoding

Do not let emoji banner output stop local startup. Configure UTF-8 output or replace startup banner characters with ASCII-safe logging. Test `python main.py` in PowerShell and Docker.

### F3. LangGraph environment and parity

- Restore `pytest-asyncio`.
- Run all existing graph tests.
- Run `scripts/parity_check.py`.
- Add a two-turn and ten-turn replay test with checkpointing.
- Add restart persistence test against MongoDBSaver.

### F4. Source/build consistency

- Commit the creative-analysis frontend source changes only after the flow is redesigned under M3.
- Regenerate `dist/` from committed source.
- Do not hand-edit hashed bundle files.

## G. Add a reproducible smoke test

Add `eval/smoke/full_campaign.py` or an equivalent test driver that:

1. Creates a unique session.
2. Submits a future-dated brief.
3. Fetches audience recommendations.
4. Confirms audience/targeting.
5. Uploads a safe fixture creative.
6. Gets zones and assignments.
7. Creates an order with a fixed idempotency key.
8. Retries the same order and verifies the same ID returns.
9. Fetches the result/report.
10. Cleans up only the disposable test order or runs against a dry-run backend.

The smoke report must include durations, trace IDs, selected segment IDs, selected zone IDs, order ID, and cleanup result.

## H. Stabilization acceptance checklist

- [ ] Repository clean and recovery tag exists.
- [ ] All exposed credentials rotated.
- [ ] Local frontend uses only local agent/backend.
- [ ] Local database has 310 audience records.
- [ ] Python lockfile exists.
- [ ] All agent tests pass.
- [ ] Backend syntax checks pass.
- [ ] Frontend production build passes.
- [ ] Golden-set validator passes all 80 briefs.
- [ ] Three complete manual flows pass.
- [ ] Automated smoke test passes.
- [ ] Duplicate-order retry test passes.
- [ ] Agent restart persistence test passes.
- [ ] Prometheus/Grafana/Langfuse evidence captured.
- [ ] Rollback instructions tested.

Only after every applicable box is green should M2 audience RAG become the default workstream.
