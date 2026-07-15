# M4.5–M4.6 security, observability, CI and performance evidence

Date: 2026-07-15
Environment: local Docker Compose only; no deployment performed

## Security boundaries

- Browser uses same-origin `/agent`; no static agent credential is present in source or built JavaScript.
- Nginx injects the internal key server-side; direct unauthenticated agent request returns 401 while the same request through the frontend proxy returns 200.
- Agent and Nginx reject payloads above 2 MiB with 413.
- Untrusted CORS origin receives no allow-origin header; tunnel origins require an explicit flag.
- The 31st rapid chat request is throttled with 429.
- All published Compose ports bind to `127.0.0.1`; containers use the private Compose network.
- Session deletion was proven against MongoDB and removes workspace data while preserving business orders.
- Current-tree and Git-history credential-shape scans pass with values never printed.

## Privacy

- Python agent logs, Mongo events and Langfuse inputs/outputs use recursive redaction.
- Node API logs use equivalent redaction and a 30-day TTL.
- Live seeded email, Vietnamese phone and password values were absent from persisted API-log JSON.
- Email, phone, 12-digit citizen IDs, bearer/token/key shapes, database credentials, and sensitive keys are covered by tests.
- The opening selector and boot response disclose AI processing and ask users not to enter unnecessary personal/secret data.
- Data inventory and a non-claiming legal checklist are in `docs/privacy/`.

## Prompt-injection defense

- Direct chat, brief/form data, and workspace events are screened before any model or mutation handler.
- System prompt treats user text, OCR, tool output, workspace events and catalog content as untrusted data.
- OCR uses the same deterministic injection detector in addition to VLM instructions.
- Offline suite: 60 cases; 45 attacks, 15 benign; 0% attack success and 0% false positives.
- Live injected chat returned `meta.tool=prompt_guard`; workspace revision, brief and audience remained unchanged.
- Existing order guard, creative review gate and final human launch approval remain the irreversible-action boundary.

## Provider resilience

- Explicit timeout, one bounded retry, transient-only fallback, circuit breaker and cooldown.
- Cross-provider generation fallback is off by default and classification-gated.
- Simulated outage: first failure 0.367 s, second request rejected by open circuit in 0.000 s.
- Safe graph fallback never exposes upstream exception text.
- Drill: `docs/postmortems/001-simulated-llm-outage.md`.

## Observability

- Prometheus: two local scrape targets healthy and one SLO rule group loaded.
- Grafana: Agent Ops dashboard provisioned with HTTP, LLM, provider, RAG, reranker, VLM, fallback and order panels.
- Correlation ID appears in HTTP response, agent logs, Langfuse metadata, outbound order calls, Express logs and persisted API logs.
- SLOs and alert response are documented in `docs/slo.md`.

## CI and supply chain

- Pull-request workflow runs locked Python install + all tests, golden validation, offline red-team gate, frontend tests/build/audit, backend tests/syntax/audit, credential scan, and all three container builds.
- Online model evaluation is manual-only and stores its report artifact.
- Candidate images are tagged with commit SHA and their immutable image IDs are printed.
- `xlsx` (unpatched high advisories) was removed. Portable seed workbooks now use ExcelJS; Multer resolved to the patched 2.2.0 line. High-severity npm audit gates pass.
- The frontend build tool was moved to patched Vite 6.4.3; both frontend and backend now report zero npm audit findings.

## Test summary

- Agent: 167 passed.
- Frontend: 18 passed; production build passes without chunk warning.
- Backend: 2 passed; 33 JavaScript files parse.
- Golden set: 80/80 schema/catalog/quota validation passes.
- Prompt injection: 60/60 classification gate passes.
- 3× load: 150 sessions, 750 requests, 0 errors/leaks, p95 0.2361 s.
- Full one-hour session-isolation soak: 3,603.03 seconds, 1,800 sessions, 9,000 requests, zero errors/leaks, p95 0.0785 seconds, agent memory 157.3 MiB to 170.7 MiB. Report: `eval/reports/soak-1h-local.json`.
