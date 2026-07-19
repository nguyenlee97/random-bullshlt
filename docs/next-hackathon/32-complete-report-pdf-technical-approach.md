# Complete Report PDF - Technical Approach

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Starting commit: `99379ebe57311c59f69fc7e6a34a858461a62c0c`

## Problem

The previous PDFKit export used built-in Helvetica/Symbol behavior and Unicode
sparkline glyphs. Vietnamese text was corrupted, the VND symbol was rendered as
the wrong character, charts became malformed text, and non-finite layout values
could be written as invalid PDF operators. The export also omitted most of the
current structured analysis because it expected legacy section names.

Autopilot reused the web report module but did not expose the existing PDF
export action. Zalo could request a PDF as soon as one selected report was ready,
even though the desired artifact is a complete six-report package.

## Design

### One complete server-side package

`backend/services/reportPDFGenerator.js` remains the single PDF authority for
browser download, email, and Zalo. It now requires:

- analytics records;
- all six ready analyses: Daily Ops, Awareness, Consideration, Conversion,
  Retention, and Executive;
- campaign metadata when available.

An incomplete package raises `REPORT_NOT_READY`. The HTTP routes translate this
to `409 Conflict` with additive `missingTypes` metadata.

### Unicode and layout safety

The generator embeds a regular and bold Unicode TrueType font. Resolution order
is:

1. `REPORT_PDF_FONT_REGULAR` / `REPORT_PDF_FONT_BOLD`;
2. optional `backend/assets/fonts/DejaVuSans*.ttf`;
3. standard Linux DejaVu locations;
4. Windows Arial fallback locations.

All numeric drawing inputs pass through a finite-number guard. Unsupported dash
characters and control characters are normalized. Flowing content reserves a
footer band, Q&A metric boxes calculate their own height, and long headers use a
bounded size.

### Report contents

The package contains:

- campaign cover and performance scorecard;
- one analytics page for each of the six report types;
- six view-specific KPIs per report;
- two vector trend charts and one placement chart per report;
- every generated Q&A item and all supported `summary`, `metrics`, `insight`,
  `recommendation`, and legacy sections;
- zone-performance and daily-performance appendices.

### Shared web and Zalo behavior

The ready state in `ReportStep.jsx` exposes `Tải PDF đầy đủ (6 báo cáo)`. The
same component is used by Guided/Copilot and `AutopilotOutcome`, so both modes
receive the action without a second report implementation.

Zalo checks the status of all six report types before requesting the PDF. A
partial package returns a natural generating response and lists the remaining
reports internally. Once ready, the existing opaque, hashed, expiring Zalo
media link serves the same backend PDF.

## Compatibility and migration

- No Mongo schema migration is required.
- No data is copied, reseeded, cleared, or deleted.
- Existing analytics and report-analysis documents are read in place.
- Existing PDF, email, CSV, JSON, Guided, Autopilot, and Zalo routes remain.
- The only HTTP behavior change is an additive `409` response while a complete
  PDF package is not ready, plus `Cache-Control: no-store` on PDF downloads.

## Rollback

Restore the four changed runtime files and the previous frontend snapshot, then
restart `adspilot-api` and `agent-api`. No database rollback is required.
