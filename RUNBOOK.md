# RUNBOOK

## Verified local quick start (2026-07-14)

Prerequisite: Docker Desktop is running. From the repository root:

```powershell
docker compose up -d --build
docker compose ps
```

The first run builds all services and idempotently seeds 310 audience segments,
35 placements, three sample campaigns, and 180 analytics records. Open:

- Application: http://localhost:5175
- Agent health/readiness: http://localhost:8080/health and http://localhost:8080/ready
- Backend health: http://localhost:3000/api/health
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3002
- Qdrant: http://localhost:6333/dashboard

Useful checks:

```powershell
docker compose logs -f agent backend frontend
docker compose exec -T backend node seed/smoke-test.js
cd agent
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pytest tests -q
```

Stop the stack while preserving local data:

```powershell
docker compose down
```

Do not add `-v` unless you intentionally want to delete the local MongoDB,
Qdrant, Prometheus, Grafana, and model-cache volumes.

## Historical production-upgrade execution notes

All commands from the repo root unless noted. Python steps run **from `agent/`** so
`.env` is picked up. Estimated total: ~45 min, mostly waiting on LLM calls.

## 0. Install deps + verify Phase-0 code (5 min)

```powershell
cd agent
.\venv\Scripts\Activate.ps1          # or your python env
pip install langgraph langgraph-checkpoint-mongodb pytest
python -m pytest tests -q            # expect: 23 passed
```

## 1. Probe the MaaS catalog (2 min, ~free)

```powershell
python scripts\probe_maas_catalog.py
```

→ writes `docs/maas-catalog.md`. Look at the table: which non-MiniMax chat models
support **tool calling** and **json_schema**. You'll use them for CRITIC_MODEL (P1)
and the P5 fallback secondary.

## 2. Structured-output spike (5 min, ~50k tokens)

```powershell
python scripts\spike_structured_output.py --n 10
# optionally repeat for a Qwen/GPT-OSS id from the catalog:
python scripts\spike_structured_output.py --model "<qwen-id>" --n 10
```

→ if winner ≠ C, edit `STRUCTURED_OUTPUT_STRATEGY` in `agent\.env`.
→ write the one-paragraph verdict to `docs\adr\005-structured-outputs-minimax.md`.

## 3. Mongo TTL indexes (1 min)

```powershell
python scripts\setup_indexes.py      # idempotent; prints the created indexes
```

## 4. Full catalog + targeting dump for golden-set v2 (2 min)

Per `eval/golden_set/AUTHORING-GUIDE.md` step 0 — from repo root:

```powershell
cd ..
python -c "import httpx, json; d=httpx.get('https://api.pawgrammers.io.vn/api/dmp/attributes', timeout=30).json(); json.dump(d, open('eval/golden_set/catalog_full.json','w',encoding='utf-8'), ensure_ascii=False, indent=1); print(type(d), len(d) if isinstance(d, list) else list(d.keys()))"
python -c "import httpx, json; json.dump(httpx.get('https://api.pawgrammers.io.vn/api/targeting/options', timeout=30).json(), open('eval/golden_set/targeting_options.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)"
```

(If the first returns a dict wrapper, note the actual key — the authoring guide
tells the executing model to adapt.)

### 4b. Fix the 71-vs-310 segment gap (discovered 2026-07-04)

The source sheet has 310 segments but the DB has 71 — the seed's "already
seeded — skip" guard never picked up the sheet's growth. ⛔ Do NOT `--force`
re-seed (that regenerates _ids → breaks existing campaigns' dmp refs and the
golden-set labels). Run the incremental script instead:

```powershell
cd backend
npm install    # if xlsx not installed locally
$env:MONGODB_URI="mongodb://agent_user_1:<pass>@api.pawgrammers.io.vn:27017/adspilot?authSource=admin"
node seed\seed-audience-missing.js      # expect: missing: ~239, total now: 310
```

Then re-run the step-4 catalog dump (expect 310) and note: dmp-recommend now
stuffs 310 segments into the prompt — measurably worse tokens/latency, which is
exactly the Phase 2 RAG baseline story. Capture the before/after in the
baseline eval report.

## 5. Baseline eval run (15–30 min, the big one)

Terminal A — run the agent locally:

```powershell
cd agent
python main.py                        # port 8080 per .env
```

Terminal B — deterministic metrics first (free), then with judge:

```powershell
cd agent                              # so .env loads for the judge
python ..\eval\run_eval.py --agent-url http://localhost:8080 --no-judge --label baseline-nojudge
python ..\eval\run_eval.py --agent-url http://localhost:8080 --label baseline --concurrency 2
```

→ commit `eval/reports/baseline*.json`. **This is the number every later change
must beat.** Expect imperfect recall — that's the point of a baseline.
Judge cost: ~40 briefs × 3 samples on gpt-4o-mini ≈ well under $1.

## 6. Deploy Phase-0 safety code to the VPS (10 min)

```powershell
scp agent/validation/*.py  root@<VPS>:/var/www/agent-api/validation/
scp agent/middleware/*.py  root@<VPS>:/var/www/agent-api/middleware/
scp agent/main.py agent/config.py agent/models.py agent/version.py agent/llm.py `
    agent/ratelimit.py agent/metrics.py agent/router.py agent/requirements.txt root@<VPS>:/var/www/agent-api/
scp agent/handlers/setup.py agent/handlers/freeform.py agent/handlers/boot.py root@<VPS>:/var/www/agent-api/handlers/
scp agent/tools/order_api.py agent/tools/registry.py root@<VPS>:/var/www/agent-api/tools/
ssh root@<VPS> "cd /var/www/agent-api && pip install -r requirements.txt"   # slowapi, prometheus, langfuse
scp backend/models/Campaign.js backend/routes/orders.js root@<VPS>:/var/www/backend/...   # match your backend layout
# rebuild frontend (idempotency key in agentApi.js):
cd agent_frontend; npm run build; scp -r dist/* root@<VPS>:/var/www/agent/
ssh root@<VPS> "pm2 restart agent-api backend-api"
curl https://agent-api.pawgrammers.io.vn/api/version    # expect 2026-07-04.1
```

Smoke test: create one campaign through the UI end-to-end (order_guard must not
block a legitimate order). Auth stays dormant (AGENT_API_KEY empty) until the
frontend sends X-API-Key.

## 7. Hand off to the executing model

> Status 2026-07-04: Phase 0 Parts A+B fully executed and verified end-to-end
> (order_guard+tests, idempotency, auth+rate limiting, metrics, Langfuse,
> Compose stack). The old prompt #3 is obsolete. None of the remaining handoffs
> block Phase 1 — only trusting eval COMPARISONS requires the label review.

Remaining prompts, in order of value:

1. **Label review helper** (before trusting any eval delta):
   "Read every brief in `eval/golden_set/brief_*.json`. Produce a markdown review
   table: id | brand | objective | notes (1-line) | must_include resolved to
   fullLabels | must_exclude resolved to fullLabels | labeler_note. Flag any
   label you disagree with and say why. Do NOT edit the briefs."
   → then **you** approve/fix; mark reviewed in the golden_set README.

2. **Golden set v2** (parallel, independent):
   "Follow `eval/golden_set/AUTHORING-GUIDE.md` exactly to create
   brief_041–080. The full catalog is now live (310 segments) — re-run the
   Step-0 fetch first. All quotas and validation in the guide are mandatory."

3. **Phase 1 wiring** (the next build; can also be done in the planning chat
   with Claude instead): "Execute `agent/graph/README.md` steps 3–8 in order:
   config flags, router flag wiring, parity run of the golden set through both
   freeform paths (diff and fix graph-side only), MongoDB checkpointer,
   Langfuse node spans, then the auto-mode planner→executor→critic subgraph
   per `docs/production-plan/02` §5. Respect every ⛔ in the README. Do not
   modify handlers/freeform.py."

4. **Judge calibration** (after #1; mostly you): have the model prepare 30
   outputs per `docs/production-plan/07` §4, you score them, model computes
   agreement (ρ ≥ 0.7 required) and commits the calibration report.

## Security debt (do before any public exposure)

- [ ] Rotate the OpenAI key and Mongo password (both were pasted in chat).
- [ ] Mongo is internet-exposed on :27017 with password auth — restrict to VPS-local
      + SSH tunnel, or at minimum firewall the port to known IPs (Phase 5 formalizes).
- [ ] Set AGENT_API_KEY once the frontend header lands.
