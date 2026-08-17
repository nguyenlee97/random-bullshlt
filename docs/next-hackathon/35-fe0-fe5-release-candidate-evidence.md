# FE-0 and FE-5 release-candidate evidence

- Date: 2026-07-19
- Branch: `revamp/next-hackathon`
- Starting/tested commit: `99618a2df0dca4163e84bc818007f64291eda6c4`
- Run: `20260719T115522Z-fe5-rc`

## Outcome

FE-0 is complete. The complete FE-5 manifest was executed and the report contract validates with **127 pass, 0 fail, 1 blocked and 0 not-run**. There are no blocker or major defects. The release gate is `incomplete`, solely because `REP-004` requires a project-owner-authorized test email address; no address was supplied and no external message was sent.

The project owner separately confirmed these campaign-bearing journeys passed:

- Zalo OA manual flow;
- FE-1 real upload flow;
- FE-1 real provider-backed AI creative generation flow.

Machine-readable artifacts are under `eval/external-reports/20260719T115522Z-fe5-rc/`: `report.json`, `summary.md` and `evidence/index.json`. `python scripts/validate_external_test_report.py .../report.json` reports a complete manifest inventory.

## FE-0 closeout

- Golden validation: 80/80 valid.
- Independent v2 review checker: 40/40 resolved; 12 approved and 28 edited, with six catalog gaps documented instead of invented labels.
- Final-output audience safety: 80 cases, zero errors, 0.806 mean recall, 0.854 MRR, zero exclusion violations, zero unknown IDs, zero source-grounding violations and zero RAG fallbacks.
- Creative recovery: persisted upload reused; the provider was not called.
- Launch recovery: three successful launches, three idempotency checks, three unique orders and three cleanups; p95 9.91 seconds.

## Deterministic and evaluator evidence

- Python: **299 passed**, two dependency deprecation/model-pooling warnings.
- Node backend: **15 passed**.
- Frontend: **63 passed**.
- Production frontend build: passed.
- Autopilot: **20/20 passed** across all policies; five failure drills passed; launch-without-approval count was zero.
- Demo rehearsal: **5/5 passed**, including review gates, idempotency, prompt-injection safety and cleanup.
- Nonlinear: **30/30 passed**, with zero unaffected-value discards.
- Creative queue: **20/20 completed**, 100% within 20 seconds, p95 19.43 seconds.
- Creative safety: unsafe block-or-review recall 100%, zero review escapes and zero prompt-injection escapes.
- Prompt injection: 45 attack and 15 benign cases, zero attack success and zero false positives.
- Targeting: 12 cases, zero forbidden, catalog or contract violations.
- Default retrieval: 80 cases, zero errors; must-recall@25 0.840; production metadata/index count of 310 matched the expected fingerprint and runtime.
- Qwen A/B: the fixed ten-case reranker-on run regressed relevance and latency versus off; production remains disabled.

The P1 100-case RAG soak and P2 one-hour mixed soak are pre-existing committed artifacts, clearly labeled as reused. They report zero RAG errors/violations/fallbacks and, respectively, 9000 mixed requests with zero errors or session leaks. Fresh 80-case safety/retrieval and 299-test regressions corroborate the tested commit; the report does not mislabel those long-duration artifacts as freshly rerun.

## Failure and recovery checks

- Slow LLM: two simultaneous 15-second blocking calls while 20 workspaces were polled for 15 rounds; 300 polls remained responsive and both chats failed safely.
- Provider outage: configured circuit opened after three failures; the next call failed fast with fallback disabled.
- Qdrant: readiness failed closed during outage, one request used the safe fallback, and normal retrieval resumed after restart.
- Agent restart: the same durable run/task remained at its waiting-review boundary after restart.
- Mongo interruption: readiness and approval failed closed; the same review state survived and approval succeeded after recovery.
- Backend interruption: agent readiness returned 503, the initial order connection failed, recovery created one order, and retry returned HTTP 200 with the same order ID and `deduplicated=true`.

No Mongo volume was deleted or reseeded during these drills.

## Production browser matrix

The signed-in production workspace was inspected without mutating its campaign:

| Viewport | Journey | Result |
|---|---|---|
| 1440×900 | Homepage/account/mode/history | Passed; no horizontal overflow |
| 1280×720 | Resumed completed Autopilot workspace | Passed; 18/18 tasks and outcome tabs visible |
| 390×844 | Homepage and resumed campaign | Passed; account/history/result/report controls reachable |
| 375×667 | Narrow-phone homepage/history controls | Passed; no horizontal overflow |

The resumed production campaign retained the AI-generated creative source, generated assets, Plan v2 artifacts, verified order data, report entry and live placement links.

## Observability, secrets and rollback

- Prometheus readiness passed and scraped the agent metrics target; Grafana database/provisioning health passed.
- Tracked-secret scan passed.
- Built frontend bundles contained none of the checked VPS/Zalo secrets or `sk-*` token patterns.
- Tested/rollback commit: `99618a2df0dca4163e84bc818007f64291eda6c4`.
- Production build observed: `2026-07-19.4`.
- Recorded image digests: agent `sha256:a6583093...`, frontend `sha256:404f28ff...`, backend `sha256:ffba0586...` (complete values are in `evidence/rollback-manifest.json`).

The reset dry-run found exactly two namespaced local test sessions. The scoped apply removed only test namespace records (including two sessions, four logs, two workspaces, one run and 18 tasks); no orders or creative files were in scope. A post-check found zero remaining namespaced sessions. Recovery would require the normal Mongo backup; user campaign data and the persistent Mongo volume were untouched.

## Migration behavior

This verification slice changes no application collection schema and runs no data migration. The local Mongo volume was preserved. The only source changes align evaluation/rehearsal fixtures with the already-deployed placement-aware graph and add reusable non-destructive recovery/report tooling.

## Remaining release action

`REP-004` can be completed only after the project owner supplies or explicitly authorizes one test recipient. Until then, preserve the truthful `blocked` result and `incomplete` release gate. Qwen reranking and the post-launch optimization/analytics agent remain deferred roadmap work.
