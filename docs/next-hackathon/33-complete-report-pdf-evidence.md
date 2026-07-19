# Complete Report PDF - Current State and Evidence

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Starting commit: `99379ebe57311c59f69fc7e6a34a858461a62c0c`

Build: `2026-07-19.3`

## Delivered behavior

- Vietnamese text renders through embedded Unicode fonts instead of PDFKit's
  built-in Helvetica/Symbol fonts.
- The export contains all six report types, charts, KPIs, all generated Q&A,
  analysis/recommendation sections, and zone/daily appendices.
- Non-finite values cannot emit `NaN` PDF operators.
- Guided/Copilot and Autopilot show one shared full-PDF download action when all
  six report analyses are ready.
- Browser and email PDF requests return `409 Conflict` until the complete
  package is ready.
- Zalo does not create or expose a partial PDF. It asks the user to retry while
  the remaining report types finish, then uses the existing opaque download
  delivery.

## Automated verification

- Backend: `15 passed`.
- Agent canonical suite: `295 passed`, with the two existing warnings for
  Starlette/httpx deprecation and FastEmbed pooling guidance.
- Zalo report/media focused suite: `13 passed`.
- Frontend: `63 passed`.
- Frontend production build: Vite 6.4.3, 2,582 modules transformed, successful.

Unrestricted `pytest` discovery also sees two pre-existing root-level
interactive screenshot utilities as tests and reports their command parameters
as missing fixtures. They were not changed. The maintained `agent/tests` suite
is fully green.

## PDF acceptance

The supplied broken PDF was rendered with Poppler and reproduced:

- missing Symbol/ArialUnicode display fonts;
- invalid `NaN` drawing operators;
- Vietnamese mojibake;
- malformed textual sparklines;
- only a partial representation of generated analysis.

A production-shaped local render using the existing `ORD-2026-004` data had 84
analytics rows and six ready analysis documents. The completed local PDF was 25
A4 pages. Poppler rendered every page without a font or operator warning, and a
full contact-sheet review confirmed all sections and appendices.

The actual VPS-generated artifact was separately downloaded and rendered after
deployment:

- HTTP 200;
- `Content-Type: application/pdf`;
- `Content-Disposition: attachment; filename="report_ORD-2026-004.pdf"`;
- `Cache-Control: no-store`;
- 156,980 bytes;
- 27 A4 pages using Linux DejaVu font metrics;
- six colored analytics sections, complete Q&A continuation pages, and both
  appendices visible in the production contact-sheet review.

## Public browser journey

Using the signed-in production account:

1. restored the existing Doraemon Autopilot campaign from account history;
2. confirmed the run was complete at 18/18 tasks;
3. opened `Kết quả & báo cáo campaign` -> `Báo cáo phân tích`;
4. confirmed 84 records and six AI analyses were ready;
5. confirmed exactly one visible link named `Tải PDF đầy đủ gồm 6 báo cáo`;
6. confirmed its target was
   `https://api.pawgrammers.io.vn/api/reports/export/ORD-2026-004/pdf`;
7. confirmed the page reported no browser console errors.

This is the shared `ReportStep` rendered inside the completed Autopilot outcome,
which is direct evidence that Autopilot now exposes the same export action as
Copilot.

## Production state and rollback

- Agent build: `2026-07-19.3`.
- Agent readiness: ready.
- Mongo, backend, creative worker, Autopilot worker, Zalo worker, and Zalo OpenAI:
  healthy.
- Backend health: HTTP 200 and database connected.
- PM2: `agent-api` and `adspilot-api` online.
- Frontend assets: the new production build is served from `/var/www/agent`.

Rollback snapshot:

`/var/backups/advertising-agent/20260719-complete-report-pdf-3`

The snapshot contains the previous backend generator/route, Agent Zalo/version
files, and complete frontend tree. Mongo was not modified, so rollback is
file-only.

## Known follow-ups

- Perform the user-facing Zalo OA check by asking for the full PDF after a newly
  launched campaign finishes all six reports; the deterministic readiness gate
  and opaque delivery path are covered automatically, but this final external
  message is intentionally left to the linked user's manual journey.
- A future polish pass could add a table of contents with internal PDF links and
  stronger PDF accessibility tagging. Neither is required for this slice.
