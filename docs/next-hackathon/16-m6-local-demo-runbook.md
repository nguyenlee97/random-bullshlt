# M6 local demo runbook

Date: 2026-07-15
Scope: local Docker Compose only; no deployment

## Namespace

Set `DEMO_NAMESPACE` before building the stack. The local default is `local-demo`.

- Browser sessions use `sess_<namespace>_...`.
- Guided and Autopilot idempotency keys include the namespace.
- Autopilot order drafts include `demoNamespace`.
- The reset tool only matches the exact sanitized session prefix and performs a dry run unless `--apply` is present.

## Before a demo

From the repository root:

```powershell
docker compose up -d --build
agent\venv\Scripts\python.exe scripts\demo\prewarm_demo.py
```

Use `--online` only when external model credits and connectivity are available. It additionally warms the full audience RAG/reranker/generator path and then deletes its disposable session.

The prewarm checks frontend assets, technical docs, dependency readiness, backend catalog, Qdrant and deterministic boot.

## Reset

Preview what would be removed:

```powershell
agent\venv\Scripts\python.exe scripts\demo\reset_demo.py --namespace local-demo
```

Apply the namespaced reset:

```powershell
agent\venv\Scripts\python.exe scripts\demo\reset_demo.py --namespace local-demo --apply
```

Orders remain untouched by default. Add `--include-orders` only for an isolated local demo database. Creative files are deleted only when their basename resolves directly inside `backend/uploads`; arbitrary or parent paths are rejected.

Legacy append-only workspace events can be audited without deletion using `scripts\privacy\cleanup_orphan_workspace_events.py`. It also requires explicit `--apply` before removing orphan rows.

## Automated rehearsal gate

```powershell
agent\venv\Scripts\python.exe scripts\demo\run_rehearsal.py --runs 5
```

The gate runs the offline campaign/order/injection/provider recovery suite and then five isolated HTTP rehearsals. Each rehearsal proves:

- local readiness;
- Autopilot preference persistence;
- brief mutation and duplicate-mutation idempotency;
- prompt-injection rejection without workspace revision change;
- a real durable Autopilot run through brief validation and the three-option Strategy Simulator review checkpoint, followed by safe cancellation before online stages;
- session cleanup.

Evidence is written to `eval/reports/demo-rehearsal.json`.

Final local RC evidence: the offline suite passed 47 tests and all five HTTP
rehearsals passed on 2026-07-15. Offline and online prewarm both passed; the
online path returned six grounded audience recommendations. The final browser
run also verified lossless freeform brief context, stable event streaming,
terminal review cleanup and a scrollable 390x844 selector. See
`17-local-release-candidate-evidence.md` and `screenshots/`.

## Three recovery stories

1. Model timeout: run `agent\venv\Scripts\python.exe scripts\drills\provider_outage.py`. The first transient failure opens the breaker; the next call fails fast. The UI never exposes provider exception text.
2. Unsafe creative: use a known unsafe or prompt-injection fixture. Creative analysis enters review and final order remains blocked until a reasoned human override or replacement.
3. Duplicate retry: repeat the same confirmation. The same namespaced idempotency key returns the existing order and does not create a second one.

## Judge-facing happy path

1. Open Advertising Agent and choose Campaign Autopilot.
2. Enter a Vietnamese campaign brief and choose the review policy.
3. Start Autopilot and compare the three Strategy Simulator scenarios.
4. Choose a scenario and explain the downstream replan.
5. Expand “Bằng chứng vận hành” to show trace, RAG/rerank, creative verdict, guard and idempotency evidence.
6. Upload creative, resolve any review, inspect the order-ready draft and explicitly approve launch.
7. Show the result/report and repeat confirmation to demonstrate exactly-once behavior.

The Guided Workflow remains the deterministic backup path. No local rehearsal or screenshot step authorizes deployment.
