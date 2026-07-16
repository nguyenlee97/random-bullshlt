# Advertising Agent — Current System Walkthrough and Next Roadmap

Date: 2026-07-16
Purpose: handoff for the next hackathon revamp. This document describes what exists now, how to test it, and what remains. It does not claim unverified production readiness.

## 1. Current product shape

Advertising Agent has two sibling modes:

- **Traditional Guided Workflow**: the operator controls Brief → Audience → Creative → Setup → Result. Freeform chat acts as a workspace-aware Copilot and changes state through durable proposals.
- **Campaign Autopilot**: the operator supplies an approved brief, chooses an approval policy and creative source, then watches a durable capability plan execute. The run pauses on review boundaries and always pauses before order creation.

MongoDB is the canonical workspace. The browser renders it; it is not a second source of truth. Each artifact has a revision and status. Approved mutations increment the workspace revision and deterministically invalidate only downstream artifacts.

## 2. What is implemented

| Area | Current implementation |
|---|---|
| Hygiene | Docker Compose, API proxy auth, rate limiting, readiness, metrics, Grafana, Langfuse integration |
| Freeform | LangGraph strangler path, structured intent/tool output, proposal IDs, confirmation guards |
| Non-linear work | Artifact dependency graph, stale markers, recompute plan, optimistic concurrency |
| Audience | Query rewrite, dense + BM25 Qdrant retrieval, RRF/merge, optional reranker, critic selector, deterministic exclusion guard |
| Creative | Deterministic media checks, async VLM analysis, manual-review fallback, zone compatibility |
| Autopilot | Durable runs/tasks/events, fixed capability allowlist, leases + heartbeat, bounded retries, pause/resume/cancel/replan |
| Side effects | Order guard, stable idempotency key, explicit launch approval, post-create verification |
| UX | Vietnamese Guided and Autopilot sibling canvases with plan, evidence, trace and review cards |

## 3. Creative-source contract

Autopilot cannot start until the operator chooses one of:

1. `upload`: the run waits at `prepare_creatives` until at least one canonical file exists. Retry reuses the file; it does not generate one.
2. `ai_generate`: the worker generates one `zuma-box` 300×250 creative using `openai/gpt-image-1`, crops/resizes it server-side, persists it through the backend, commits it to the creative artifact and automatically submits it for the same creative-intelligence checks as uploads.

AI assets use an idempotency key containing run ID, format and brief revision. The deterministic backend filename is a recovery checkpoint: a worker retry after successful upload reuses the stored file instead of paying for a second generation. Prompt version, prompt fingerprint, provider, model and format are persisted as provenance.

This first slice intentionally generates one exact-size format. Multi-format variants are a later milestone. AI generation never bypasses VLM/manual review and never bypasses final launch approval.

## 4. How audience selection works without reranking

When `RAG_USE_RERANK=false` or the reranker is unavailable, selection still has these ranking stages:

1. Preserve raw brief signals and explicit exclusions.
2. Rewrite into coverage-preserving aspect queries.
3. Retrieve each query with multilingual dense embeddings and sparse BM25.
4. Fuse dense/sparse rankings in Qdrant with reciprocal-rank fusion.
5. Merge and deduplicate multi-query candidates. Best per-query rank is primary; query agreement breaks ties.
6. Keep a bounded top-25 candidate pool.
7. Remove deterministic taxonomy conflicts with explicit negative intent.
8. Let the structured critic select exactly six IDs from the candidate whitelist.
9. Reject unknown IDs and attach catalog/source evidence.

Therefore the reranker is an optional improvement stage, not the only ranking mechanism. The latest complete post-fix evaluation reported recall@15 `0.819`, MRR `0.851`, p95 `5.51s`, and zero exclusion/unknown/grounding violations. These are regression results, not a universal quality guarantee.

## 5. Local walkthrough

```powershell
docker compose up -d --build
docker compose ps

docker compose exec agent python -m pytest tests -q
npm test --prefix agent_frontend
npm test --prefix backend
```

Open:

- UI: `http://localhost:5175`
- Agent health: `http://localhost:8080/health`
- Metrics: `http://localhost:8080/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3002`

### Guided smoke

1. Select Traditional Guided Workflow.
2. Enter a valid Vietnamese brief.
3. Ask chat to change budget. Verify it produces a reviewable proposal and does not mutate before approval.
4. Approve it, retrieve audience, and inspect catalog IDs/source evidence.
5. Change an earlier input after later artifacts exist. Verify the UI marks only affected artifacts stale.

### Autopilot upload smoke

1. Select Campaign Autopilot and approve a brief.
2. Select upload, choose a policy, start.
3. Verify `prepare_creatives` waits if no file exists.
4. Upload a file and retry. Verify analysis either passes or routes to human review.

### Autopilot AI-generation smoke

1. Select AI generation and start.
2. Verify a 300×250 file appears in the creative artifact with `source=ai_generated` and generation provenance.
3. Verify VLM timeout, safety warning or low confidence pauses for review.
4. Verify all policies still stop at final launch approval.

## 6. Comprehensive test handoff

The AI-executable suite is defined by:

- `docs/testing/COMPREHENSIVE-TEST-PLAN.md`
- `docs/testing/SCENARIO-CATALOG.md`
- `docs/testing/scenario-manifest.json`
- `docs/testing/AI-TEST-EXECUTOR-PROMPT.md`

The current manifest contains 128 unique scenarios spanning UI/UX, workspace proposals, nonlinear recomputation, RAG safety, creative intelligence, Autopilot recovery, security, observability and full journeys. The executor must return the repository's structured report format so another model can validate coverage and diagnose failures without relying on prose alone.

## 7. Independent label review

An independent AI audit reviewed briefs 041–080 and every audience-label bucket:

- 12 pass
- 22 change recommended
- 6 catalog gaps
- 0 invalid catalog IDs

High-risk issues include demographic interests used as age/gender proxies, fabricated `must_exclude` labels, and examples shaped around `full_catalog_only` rather than the strongest labels. This is advisory AI review, not human sign-off. The audit did not edit briefs or `v2_review_status.json`.

Review artifacts:

- `eval/golden_set/LABEL-REVIEW-041-080-20260716.md`
- `eval/golden_set/LABEL-REVIEW-041-080-20260716.json`

## 8. Remaining roadmap

The detailed continuation is now defined in `19-final-enhancement-phase-roadmap.md`.
It prioritizes placement-aware multi-format generation, followed by anonymous/account
identity with conversation history, then a channel-agnostic Zalo OA integration.

The user has accepted the independent golden-label recommendations. This is
authorization to apply the proposed edits and record human-owned review statuses;
it does not make the current unedited 041–080 files correct by declaration.

### P0 — closeout and truth gates

- Apply the accepted golden-label audit; rerun validators and RAG safety gates.
- Execute changed-journey browser/API scenarios. The 128-case manifest exists but has not all been executed.
- Keep only minimal restart/retry checks around generated-image cost and exactly-once order creation; defer broad chaos work.
- Run a complete campaign smoke through final launch approval and verified order using a known-safe creative.

### P1 — final enhancement product work

- Add two-pass placement planning and generate exact creative formats/variants with cost and quality budgets.
- Add anonymous-first accounts, login identities, conversation history and cross-device resume.
- Add Zalo OA as a channel adapter for Autopilot, simplified Guided flow, campaign status/modification and live notifications.
- Keep Qwen reranking disabled and defer the post-launch analytics/report agent.

### P2 — later hardening

- Extend owner authorization into organization RBAC and tenant isolation after account ownership is stable.
- Horizontal-worker concurrency tests and operational SLO/error-budget dashboards.
- Data retention/deletion policy, backup/restore drills and formal incident runbooks.

## 9. Recommended sequence

1. Apply the accepted golden-label changes and pass focused safety validation.
2. Implement placement-aware multi-format generation.
3. Perform one upload and one real AI-generation full journey.
4. Add anonymous/account identity and resumable conversation history.
5. Add the Zalo OA channel foundation, campaign operations and notifications.
6. Execute the complete release suite after the changed journeys stabilize.
