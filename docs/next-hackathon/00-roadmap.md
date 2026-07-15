# Next-Hackathon Recovery and Upgrade Roadmap

> Status: proposed roadmap, created 2026-07-14 after a repository and live-system audit.
>
> Purpose: turn the current split state—working older deployment plus unfinished local production upgrade—into one dependable, measurable product that can be adapted for the next hackathon.

> Progress update (2026-07-15): M0-M3 are locally stable. M4.1-M4.4 are also
> complete: transactional Copilot, non-linear artifact recovery, durable
> Campaign Autopilot, the two-mode opening experience, mid-run replanning, and
> an exactly-once creative-to-order run are proven. The 20-brief Autopilot
> orchestration gate passed 20/20 with 5/5 failure drills and zero unauthorized
> launches. The full local Advertising Agent rebrand and accessibility/contrast
> audit are also complete. Remaining work is M4.5 observability/UI evidence,
> M4.6 security and release automation, performance hardening, final screenshot
> capture, and demo rehearsal. External release approval still requires
> human sign-off for golden briefs 041-080.

## 1. Starting point

The project is not starting from zero. It already has:

- A reachable deployed campaign-planning application.
- A deterministic Brief → Audience → Creative → Setup → Result flow.
- Reporting, image generation, email delivery, screenshots, and a guided demo.
- Local implementations of order validation, idempotency, rate limiting, metrics, Langfuse, LangGraph, audience RAG, reranking, and creative VLM analysis.
- An 80-brief evaluation set covering all 310 source-catalog segments and advanced targeting.

But it also has two incompatible realities:

- Production runs agent build `2026-06-25.42`, with 71 audience segments and none of the later production endpoints.
- The local repository is build `2026-07-04.5`, with LangGraph and VLM enabled, RAG disabled, incomplete validation, and uncommitted frontend VLM wiring.

The roadmap therefore begins with recovery and consolidation. New showcase features come later.

## 2. Non-negotiable rules

1. **Keep the deployed demo intact until a replacement release candidate passes every gate.**
2. **Never deploy directly from a dirty working tree.**
3. **Do not claim RAG, LangGraph, VLM, security, or observability is working merely because code exists.** Each capability needs a test and evidence artifact.
4. **LLMs may propose; deterministic code validates; humans approve irreversible actions.**
5. **Order creation remains idempotent and human-confirmed.** No autonomous graph may bypass `order_guard`.
6. **Audience, zone, budget, date, creative, and targeting values must come from server-side catalogs or validated user state—not model invention.**
7. **Do not add a new framework or model unless it removes a measured bottleneck.**
8. **The guided happy path always has a deterministic fallback.**
9. **No real credentials in Git, screenshots, exported logs, prompts, or hackathon submissions. Rotate all credentials previously pasted into chat.**
10. **A feature is done only when code, tests, metrics, documentation, and rollback instructions exist.**

## 3. Target architecture

```text
React workspace + chat
        |
        v
FastAPI agent gateway
  |-- deterministic form handlers
  |-- transactional campaign workspace + dependency graph
  |-- LangGraph Copilot + durable Autopilot runs
  |-- audience RAG orchestrator
  |-- creative analysis orchestrator
  |-- order guard + idempotency
        |
        +--> GreenNode MiniMax: primary generation/tool use
        +--> GreenNode Qwen reranker: audience reranking
        +--> GreenNode Gemma: image understanding
        +--> OpenAI: judge/critic and true provider fallback only
        |
        +--> Qdrant: audience vectors
        +--> MongoDB: sessions, campaigns, checkpoints, verdicts
        +--> Node backend: source-of-truth APIs and order persistence
        |
        +--> Langfuse + Prometheus/Grafana
```

The architecture intentionally keeps deterministic validators, catalog tools, and order safety. LangGraph coordinates Copilot and multi-step Autopilot behavior around those proven capabilities; it does not replace them with prompt-only logic. The detailed interaction and state design is in `04-agentic-campaign-autopilot.md`.

## 4. Recommended timeline

### Standard six-week plan

| Week | Milestone | Outcome |
|---|---|---|
| 1 | Recovery and reproducibility | One clean branch and one reproducible local stack |
| 2 | Core-flow stabilization | Full local campaign succeeds repeatedly with automated smoke evidence |
| 3 | Audience intelligence | RAG + reranker enabled and measurably better than prompt stuffing |
| 4 | Creative intelligence | VLM runs before assignment/order and enforces review decisions |
| 5 | Copilot, Autopilot, security, and release automation | Transactional workspace, non-linear recovery, durable agent runs, CI, auth, redaction, and failover |
| 6 | New-hackathon adaptation and demo hardening | Theme-specific hero feature plus reliable showcase build |

### Compressed three-week plan

- Week 1: Milestones 0 and 1.
- Week 2: Milestones 2 and 3.
- Week 3: milestone 4 minimum security subset, one hero feature, and demo hardening.

If time becomes tight, cut parallel Autopilot execution, self-hosted Langfuse, Kubernetes, Databricks, and multiple hero features. Keep a sequential order-ready-draft Autopilot. Do not cut transactional workspace safety, final launch approval, order safety, RAG evaluation, VLM gating, smoke tests, or rollback readiness.

## 5. Milestones

## M0 — Repository recovery and baseline preservation

**Goal:** know exactly what can be trusted before changing behavior.

Deliverables:

- Create `revamp-next-hackathon` from current `main`.
- Preserve the current live deployment as `legacy-prod`; record its version and health endpoints.
- Review and commit or discard the two uncommitted creative-analysis frontend changes separately.
- Do not commit generated `dist/` changes until the source build is approved.
- Add `.env.example` entries for every flag without secrets.
- Rotate GreenNode, OpenAI, MongoDB, Langfuse, Resend, and any other exposed credentials.
- Export or snapshot production MongoDB before reseeding or migrating it.
- Record ADR: local Docker, staging, and production environment boundaries.

Definition of done:

- `git status` is clean.
- A fresh clone can identify all required environment variables without seeing secrets.
- The live deployment can be restored without using the local working directory.
- The rollback target/version is documented.

## M1 — Reproducible local stack and core-flow stabilization

**Goal:** a fresh machine can run the same complete application that developers test.

Required work:

- Make local frontend use local services:
  - `VITE_AGENT_URL=http://localhost:8080`
  - `VITE_BACKEND_URL=http://localhost:3000`
- Seed local MongoDB with all 310 audience segments and the complete zone catalog.
- Pin Python dependencies with `uv.lock` or a fully pinned requirements lock.
- Keep Node `package-lock.json` files and use `npm ci`.
- Install missing `pytest-asyncio`, `qdrant-client`, and `fastembed` in the reproducible environment.
- Fix Windows UTF-8 startup logging or make banner logging ASCII-safe.
- Fix setup-entry history persistence (`add_message()` parity with audience-entry).
- Add an end-to-end smoke script that creates a disposable future campaign and cleans it up or uses a dry-run backend.
- Add health checks for MongoDB, backend, Qdrant, model provider, and vector index—not only the HTTP process.
- Confirm order-guard and idempotency behavior against the real backend route.

Definition of done:

- `docker compose up -d --build` starts a healthy stack from a clean machine.
- All unit/parity tests pass in the agent container.
- Backend syntax and frontend production build pass.
- Three consecutive complete campaign flows succeed locally.
- Retrying the same confirmation creates one order, not two.
- Restarting the agent preserves conversation state.
- A smoke-test report is saved under `eval/reports/`.

## M2 — Audience RAG completion and activation

**Goal:** replace the 310-segment prompt dump with a faster, more accurate measured pipeline.

Required work:

- Human-review v2 golden labels before using them for quality claims.
- Build and verify the Qdrant collection against exactly 310 source records.
- Run three comparable evaluations on the same local catalog:
  1. `legacy-310`
  2. `rag-no-rerank`
  3. `rag-reranked`
- Add retrieval metrics: Recall@15, MRR@15, exclusion violations, targeting exact/F1, p50/p95 latency, model tokens, and fallback rate.
- Verify every returned recommendation contains a valid source segment ID and citation metadata.
- Add index version metadata and rebuild on catalog version changes, not only count changes.
- Add a startup/readiness check that detects missing or stale indexes.
- Tune query rewrite, retrieval K, and rerank K using the validation split—not the final test split.
- Enable `USE_RAG_AUDIENCE=true` only after acceptance targets pass.

Initial acceptance targets:

- Recall@15 improves by at least 15 percentage points over `legacy-310`, or reaches at least 0.75.
- Exclusion violations remain zero.
- p95 recommendation latency is below 20 seconds; stretch target below 10 seconds.
- RAG fallback rate is below 2% in a 100-request soak.
- No recommendation can escape the retrieved candidate set.

Definition of done:

- `USE_RAG_AUDIENCE=true` is the tested default in staging.
- `eval/reports/SCOREBOARD.md` contains the three-way comparison.
- Grafana shows retrieval, rerank, fallback, latency, and token metrics.

## M3 — Creative intelligence moved before booking

**Goal:** make VLM analysis operationally meaningful rather than post-order telemetry.

Current defect to remove:

- Creative assignment runs before files receive URLs.
- Analysis is started asynchronously only in final confirmation.
- Order creation starts immediately without waiting for the verdict.

Required redesign:

1. Upload files when the Creative step is confirmed, not during order confirmation.
2. Start deterministic and VLM analysis immediately after upload.
3. Persist `analysis_id`, status, measured dimensions, OCR, safety flags, and confidence in workspace state.
4. Display `analyzing`, `approved`, and `needs_review` states in the Creative UI.
5. Do not permit Setup assignment until required analysis completes or a documented timeout policy applies.
6. Feed measured dimensions/layout into `creative_match.py` before auto-assignment.
7. Block order creation for `needs_review` creatives unless an authorized human override includes a reason.
8. Store override actor, reason, timestamp, and original verdict.
9. Replace process-local fire-and-forget jobs with an explicit job record and recoverable worker loop; Redis/Celery is optional at hackathon scale.

Acceptance targets:

- 100% of uploaded images receive deterministic analysis.
- At least 95% receive VLM verdicts within 20 seconds under demo load.
- Unsafe/low-confidence files cannot silently create orders.
- Measured dimensions override filenames and browser metadata in assignment tests.
- Restarting the agent does not lose queued or completed verdicts.

Definition of done:

- The order guard checks creative verdict IDs server-side.
- The UI visibly explains why a file was approved or needs review.
- A 20-image fixture set passes deterministic and VLM regression tests.

## M4 — Reliable Copilot, non-linear workspace, and Campaign Autopilot

**Goal:** make chat a safe control surface for the workspace and let one brief drive a durable, inspectable, human-gated campaign run.

Workspace and freeform foundation:

- Make a versioned MongoDB campaign workspace the source of truth instead of splitting authority between React, session form state, and graph checkpoints.
- Replace unrestricted chat writes with typed proposals, domain validation, proposal IDs, approval records, and atomic revision checks.
- Add dependency-aware invalidation so users can work non-linearly and recompute only affected artifacts.
- Persist every visible message, proactive event, proposal, decision, and task result.
- Expand freeform coverage to at least 60 Vietnamese multi-turn scenarios and 30 non-linear workflow scenarios.
- Retain keyword intercepts only as unambiguous fast paths; structured intent and proposal identity govern mutations.

Campaign Autopilot:

- Add an opening mode selector before campaign work begins: Traditional Guided Workflow or Campaign Autopilot.
- Preserve the existing step-by-step experience as Guided Workflow, with reliable Copilot chat available inside it.
- Give Autopilot a separate brief-first intake and explicit start action; phrase triggers may remain as convenience aliases, not the only entry point.
- Keep experience mode separate from the Autopilot approval policy: first choose the workflow, then choose how much reversible work may be auto-approved.
- Convert Auto mode from an ephemeral summary into durable run/task records with plan revisions, worker leases, pause/resume/cancel, bounded retries, and restart recovery.
- Support three approval policies: review every stage, review critical stages, and auto-build draft.
- Run brief validation, strategy, RAG audience, targeting, creative analysis, placement ranking, assignment, forecast, order draft, guard, final approval, idempotent creation, verification, and report preparation.
- Stream plan and task progress to the UI and expose evidence for each decision.
- Replan after mid-run edits, reuse unaffected artifacts, and reject results computed from stale workspace revisions.
- Never let policy auto-approve a creative safety override or final order launch.

Detailed implementation slices, schemas, invariants, and eval targets are in `04-agentic-campaign-autopilot.md`.

Security/reliability minimum:

- Replace empty API-key auth with short-lived session tokens or a backend-for-frontend flow.
- Add PII redaction before logs and Langfuse traces.
- Add input size/content limits to all agent endpoints.
- Add direct and indirect prompt-injection tests, including OCR-borne injection.
- Add provider timeout, bounded retry, circuit breaker, and GreenNode → OpenAI fallback policy.
- Disable offshore fallback when the data-classification policy forbids it.
- Stop exposing unauthenticated MongoDB outside the Compose network.
- Rotate secrets and use deployment secret storage.
- Add data-retention and session-deletion operations.

Release automation:

- Add CI for Python tests, backend checks, frontend build, golden-set validation, dependency audit, and container build.
- Add a small offline eval gate for every pull request and a full online eval before release.
- Build immutable images tagged with commit SHA.
- Deploy to staging first; production promotion requires explicit approval and rollback metadata.

Definition of done:

- Chat can safely inspect and propose changes to every supported campaign artifact with zero unauthorized or stale mutations in the regression suite.
- Thirty non-linear scenarios preserve unaffected work and invalidate every affected artifact correctly.
- A one-brief Autopilot run can survive restart, reach an order-ready draft, pause for final approval, and create exactly one order.
- The UI shows plan, progress, evidence, review requests, blocked reasons, and replan impact.
- CI passes on a clean clone.
- No static credential is present in the browser bundle.
- A red-team report and load-test report exist.
- The upgraded staging agent survives a one-hour soak without state leakage or duplicate orders.

## M5 — Next-hackathon product enhancement

**Goal:** add one memorable capability that demonstrates business value, not a pile of disconnected AI features.

Campaign Autopilot is the core interaction model delivered in M4, not the M5 hero feature. The selected hero feature should appear as a high-value capability or artifact inside an Autopilot run.

### Product identity revamp — Advertising Agent

Before final demo polish:

- Rename the user-facing product to **Advertising Agent**.
- Replace the current green brand theme with a blue, conversational visual system inspired by the familiarity of Zalo while retaining an original identity.
- Add centralized semantic design tokens; keep green only for success and retain amber/red for review, warning, blocked, and danger states.
- Apply the identity consistently to the opening mode selector, Guided Workflow, Copilot chat, Campaign Autopilot, creative review, reports, result screens, exports, and demo assets.
- Keep API paths, Docker services, database collections, environment variables, and other internal identifiers unchanged during the visual rebrand.
- Meet accessibility and visual-regression requirements in `05-advertising-agent-rebrand.md`.

Select exactly one primary hero feature after the new hackathon theme is known:

### Option A — Campaign strategy simulator (recommended default)

- Generate 2–3 audience/zone/budget strategies.
- Estimate reach, cost, risk, and rationale for each.
- Let the user compare scenarios and choose one.
- Record why the selected strategy won.

### Option B — Closed-loop optimization agent

- Read campaign performance.
- Detect underperformance against KPI.
- Propose budget, audience, creative, or zone changes.
- Simulate impact and request approval before applying.

### Option C — Creative compliance copilot

- Inspect creative, OCR copy, brand alignment, placement compatibility, and policy risk.
- Produce actionable corrections and regenerate safe variants.

### Option D — Natural-language campaign operations

- Answer performance questions using grounded analytics.
- Create auditable change proposals.
- Execute only through validated tools and approval gates.

Selection criteria:

- Directly matches hackathon judging criteria.
- Reuses existing campaign data and infrastructure.
- Can be demonstrated in under three minutes.
- Produces measurable before/after value.
- Has a deterministic fallback if an AI provider fails.

Definition of done:

- The hero feature has one clear user story, one metric, one demo script, and one fallback.
- It is integrated into the existing workflow instead of being a disconnected page.

## M6 — Demo and release hardening

**Goal:** make the showcase reliable under poor network conditions and judge interaction.

Required work:

- Capture final Advertising Agent screenshots and verify no old user-facing name or primary green branding remains.
- Prewarm embeddings, Qdrant, model connections, Playwright, and demo assets.
- Maintain a deterministic guided path with no hidden production mutations.
- Add a demo/staging namespace so judge orders cannot conflict with real data.
- Add a reset script for demo sessions, zones, generated creatives, and reports.
- Cache safe demo responses for external provider outages while clearly labeling fallback mode.
- Show live observability: trace ID, retrieval candidates, reranker effect, guard decision, and order idempotency.
- Prepare one happy-path demo and three recovery demos: model timeout, unsafe creative, and duplicate order retry.
- Freeze features 72 hours before judging; only P0 fixes afterward.

Final release gate:

- Clean Git state and immutable release tag.
- All automated tests and eval gates pass.
- Five complete demo rehearsals succeed consecutively.
- No critical/high security finding remains.
- Rollback tested.
- Secrets rotated.

## 6. Priority backlog

### P0 — start here

1. Clean and branch the repository.
2. Rotate credentials.
3. Start Docker and make frontend fully local.
4. Rebuild dependencies and make all tests pass.
5. Add the end-to-end smoke test.
6. Fix setup-entry history.
7. Run three complete local campaign flows.

### P1 — needed before feature claims

1. Human-review the 80-brief golden set.
2. Enable, evaluate, and tune RAG.
3. Move VLM analysis before assignment and order creation.
4. Stabilize LangGraph with multi-turn parity tests.
5. Add CI and staging.

### P2 — needed before public deployment

1. Session auth/JWT or BFF.
2. PII redaction and privacy controls.
3. Prompt-injection red-team suite.
4. Circuit breaker and provider failover.
5. Load/soak testing.

### P3 — optional sophistication

- Kubernetes.
- Self-hosted model serving.
- Databricks/MLflow.
- Multi-agent decomposition beyond planner/executor/critic.
- Self-hosted Langfuse.

These are portfolio enhancements, not prerequisites for a strong hackathon product.

## 7. Success scoreboard

Track these values in `eval/reports/SCOREBOARD.md` for every release candidate:

| Dimension | Metric |
|---|---|
| Audience quality | Recall@15, MRR@15, exclusion violations |
| Targeting quality | Exact match/F1 per targeting group |
| Agent reliability | Task success, tool error, fallback, stale-state incidents |
| Latency | p50/p95 request, retrieval, rerank, LLM, VLM |
| Cost | Tokens and estimated cost per completed campaign |
| Safety | Order-guard rejection correctness, injection success rate, unsafe-creative escape rate |
| Operations | Duplicate-order rate, recovery time, error rate |
| Demo | Successful consecutive rehearsals |

## 8. First decision checkpoint

Do not choose the new hero feature yet. First complete M0 and M1 and produce a working release candidate. At that point, use the new hackathon problem statement and judging rubric to select one M5 option. This prevents another technically impressive branch from diverging from the application that actually works.
