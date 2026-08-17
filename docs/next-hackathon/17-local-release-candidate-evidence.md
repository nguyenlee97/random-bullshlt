# Local release candidate evidence

Date: 2026-07-15
Scope: local Docker Compose only; no deployment performed

## Result

The local Advertising Agent roadmap is complete through M6. Guided Workflow,
Campaign Autopilot, transactional non-linear workspace updates, measured
audience RAG, Gemma creative analysis, order safety, observability, the Campaign
Strategy Simulator, and the blue Advertising Agent interface are integrated in
one reproducible stack.

## Final automated gates

- Agent: 167 passed.
- Frontend: 18 passed; Vite 6.4.3 production build passed without an oversized-chunk warning.
- Backend: 2 passed; 33 JavaScript files passed syntax checks.
- Frontend and backend dependency audits: 0 vulnerabilities.
- Golden set: 80/80 valid against the 310-segment catalog.
- Prompt-injection set: 60/60 passed; 0% attack success and 0% false positives.
- Five live demo rehearsals: 5/5 passed after 47 offline recovery tests.
- Prometheus: 2/2 targets healthy, one rule group and four alert rules loaded.
- Grafana database health: `ok`.
- Black-box auth, CORS, request-size, deletion, event-deletion and rate-limit suite: passed.

## Performance and recovery

- 3x demo load: 150 sessions, 750 requests, zero errors or session leaks, p95 0.2361 seconds.
- One-hour soak: 1,800 sessions, 9,000 requests, zero errors or session leaks, p95 0.0785 seconds.
- Agent memory during soak: 157.3 MiB to 170.7 MiB.
- Offline and online prewarm passed; online audience prewarm returned six grounded recommendations.
- A persisted fixture survived an agent-container rebuild.
- The rollback branch `archive/pre-revival-2026-07-14` resolves to `bd9a057`.

## Final browser gates

The rebuilt stack at `http://localhost:5175` was tested in the local browser:

- Vietnamese opening selector exposes Guided Workflow and Campaign Autopilot.
- A full Vietnamese brief entered through chat creates one durable proposal.
- Approving the proposal preserves Autopilot mode and does not enter the Guided step machine.
- Audience, geo and interest text is preserved in canonical `brief.notes` even when the model omits that tool argument.
- Proposal controls become immutable after approval.
- Strategy Simulator units are readable (`nghìn`, `triệu`) and quality-first selection is recorded.
- The Autopilot event stream produced normal `200` completions and zero `499` reconnect storms.
- Cancelled runs expose no stale review controls.
- At 390x844, horizontal overflow is zero and the selector scrolls to both mode cards and the privacy notice.
- Browser warning/error log is empty.

Screenshots:

- `docs/next-hackathon/screenshots/01-opening-selector.png`
- `docs/next-hackathon/screenshots/02-autopilot-strategy.png`
- `docs/next-hackathon/screenshots/03-mobile-mode-selector.png`

## Release limits

- No deployment was performed.
- Qwen reranking remains integrated but disabled because it regressed measured catalog ranking quality.
- Briefs 041-080 remain machine-authored and require human sign-off before they support an external quality claim.
- Credential rotation was explicitly deferred by the project owner for this local hackathon cycle. External release remains blocked until rotation and secret-store migration are complete.
