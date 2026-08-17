# M3 Creative Intelligence — Implementation Evidence

**Candidate date:** 2026-07-15
**Agent build:** `2026-07-15.1`

## Implemented vertical slice

1. Creative confirmation uploads files before Setup.
2. Mongo-backed jobs are persisted before the API returns.
3. The worker performs real-pixel analysis, then optional Gemma analysis.
4. The Creative UI shows upload, queue, analysis, approval, and review states.
5. A review verdict keeps the workflow on Creative until a human enters an
   override reason.
6. Measured dimensions and explicit intended format feed assignment.
7. The order guard resolves every `analysisId` server-side and rejects missing,
   pending, or unapproved verdicts.
8. Final confirmation no longer starts upload or analysis and only advances
   when the server returns `order_create`.

## Automated evidence

- Python agent suite: 51 tests passing after M3 additions.
- Frontend workflow tests: 2 passing, including the rule that server-side
  validation failures cannot advance a step.
- Frontend production build and backend syntax checks: passing.
- Deterministic creative fixture: 20/20 exact dimensions and 20/20 minimum-size
  checks.
- Optimized live Gemma fixture (20 images):
  - structured success: 95% (one empty structured response failed closed)
  - OCR non-empty on successful calls: 100%
  - brand accuracy: 100%
  - safety accuracy on the safe demo set: 100%
  - brief-match pass: 100%
  - explicit-format routing accuracy: 100%
  - raw VLM skin classification: 73.7% (diagnostic only)
  - p50 latency: 2.106 seconds
  - p95 latency: 3.139 seconds
- Positive runtime control: ELSA creative + ELSA brief → `auto_approved`,
  confidence 1.0, brief match 5/5, four OCR lines.
- Negative runtime control: ELSA creative + ZUMA brief → `needs_review`, brief
  match 1/5.
- Override runtime control: original `needs_review` remained stored and the
  derived status became `approved_override` with actor, reason, timestamp, and
  original reason.
- Restart runtime control: a job interrupted in `analyzing` retained the same
  analysis ID, startup logged `recovered=1`, attempt count increased to two,
  and the job completed `auto_approved`.
- Qwen rejection control: five-case sample passed, but the full fixture reached
  only 40% schema-valid output; Gemma remains primary.
- Safety fixture: 13 labeled safe, unsafe, borderline, and OCR prompt-injection
  creatives. Unsafe direct-classification recall was 90%; operational
  block-or-review recall was 100%; prompt-injection escapes and
  review-required escapes were both zero. One alcohol case timed out and
  correctly failed closed to review.
- HTTP queue load: 20/20 jobs persisted and reached terminal state. With six
  bounded workers, total queue time was 10.285 seconds, end-to-end p95 was
  9.428 seconds, 100% completed within 20 seconds, attempts never exceeded one,
  and no analysis ID was missing.
- Video HTTP smoke: a real 640x360 H.264 MP4 uploaded through the Node backend,
  was probed as a two-second video, and produced `needs_review` with an explicit
  manual-video-review reason.
- Browser override control: the Creative screen displayed `needs_review`, kept
  Setup blocked, accepted a required Vietnamese operator reason, displayed
  `approved_override`, and advanced only after a second confirmation. MongoDB
  retained the original verdict/reasons plus actor, reason, and timestamp.

Reports:

- `eval/reports/creative-v1-deterministic.json`
- `eval/reports/creative-v2-gemma-optimized.json`
- `eval/reports/creative-v1-qwen.json`
- `eval/reports/creative-safety-gemma-v3.json`
- `eval/reports/creative-http-queue-20-v1.json`
- `eval/reports/creative-http-queue-20-v3-concurrency6.json`

## Gate 3 verdict

**Local Gate 3: PASS.** Creative analysis now runs before Setup and order
creation, survives restart, fails closed, handles image and video uploads, and
has measured safety and queue behavior under demo load.

Authenticated user identity is deliberately an M4 security item. Until then,
the local override actor is the explicit `campaign_operator` placeholder; the
reason, timestamp, original status, and original reasons are already durable.
This placeholder is not acceptable for a deployed multi-user release.
