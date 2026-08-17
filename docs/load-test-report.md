# Advertising Agent local load and performance report

Date: 2026-07-15
Environment: Docker Desktop local Compose
Profile: deterministic Guided control plane only; no model calls, creative uploads, or order creation

## 3× expected demo-load result

Expected interactive demo concurrency is five users; the gate ran 15 concurrent users, each completing ten disposable sessions. Every session performed health, workspace read, experience preference write, stateless boot chat, and session deletion.

| Metric | Result | Gate |
|---|---:|---:|
| Sessions | 150 | — |
| Requests | 750 | — |
| Throughput | 146.84 requests/s | observe |
| p50 latency | 0.0721 s | — |
| p95 latency | 0.2361 s | < 3 s deterministic SLO |
| p99 latency | 0.3221 s | observe |
| HTTP/task errors | 0 | 0 |
| Cross-session leakage | 0 | 0 |

Result: PASS. The reproducible harness is `ops/load_test.py`. Rate limiting is disabled only for the isolated load run and restored immediately afterward; the separate black-box security suite proves the production 30/minute chat limit.

## Measured bottleneck and fix

The initial frontend build emitted one 1.19 MB JavaScript bundle (342.92 KB gzip) and an oversized-chunk warning. Report/email steps and chart rendering were eagerly loaded even before the user selected a workflow.

The fix lazily loads Report, Email, and chart components and separates stable chart/UI/vendor chunks. The resulting build has no oversized or circular-chunk warning:

| Chunk | Minified size | Load behavior |
|---|---:|---|
| Application core | 294.58 KB | initial |
| Shared vendor | 420.84 KB | initial/shared |
| UI vendor | 109.80 KB | initial/shared |
| Chart engine | 361.36 KB | only when a chart/report needs it |
| Report step | 28.06 KB | only on Report |
| Email step | 10.70 KB | only on Email |

The initial application-owned bundle fell by about 75% (1.19 MB → 295 KB), while the largest optional engine no longer blocks the opening selector. The small increase from the first split build is the Campaign Strategy Simulator, its evidence controls, the responsive-selector fixes, and the patched Vite 6 build pipeline.

## Scope limit

This test isolates application and persistence behavior. Model latency/capacity is measured through the online eval and provider metrics, not multiplied in this load test, because doing so would consume external credits and confound local control-plane capacity with provider quotas.

## One-hour session-isolation soak

The sustained gate ran for 3,603.03 seconds with five users per cycle: 360 cycles, 1,800 sessions and 9,000 requests. It completed with zero HTTP/task errors, zero cross-session leaks, p50 0.0254 seconds, p95 0.0785 seconds and p99 0.1024 seconds. Agent memory moved from 157.3 MiB to 170.7 MiB. Result: PASS. Authoritative report: `eval/reports/soak-1h-local.json`.
