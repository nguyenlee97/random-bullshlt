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

- Python agent suite: 48 tests passing after M3 additions.
- Frontend production build: passing.
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

Reports:

- `eval/reports/creative-v1-deterministic.json`
- `eval/reports/creative-v2-gemma-optimized.json`
- `eval/reports/creative-v1-qwen.json`

## Remaining before calling Gate 3 fully closed

- Add unsafe and borderline-safety labeled images; the current 20-image set is
  a safe demo set and cannot establish safety recall.
- Add video metadata extraction with ffprobe or keep video as mandatory review.
- Add a browser-level test for the override UI.
- Complete a 20-image demo-load run through the HTTP queue; the model fixture
  and single-job HTTP restart drill are complete.
- Replace the local actor label with authenticated user identity during M4.
