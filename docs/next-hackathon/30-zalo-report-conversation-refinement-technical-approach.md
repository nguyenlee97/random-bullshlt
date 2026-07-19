# Zalo OA Report Conversation Refinement — Technical Approach

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Starting commit: `c30518b053154c173a4fdd62841704df2744f867`

## Product outcomes

This slice refines the existing Zalo OA campaign assistant without changing the
working live-view behavior:

- a warmer introduction points users to detailed guidance;
- detailed-guidance examples use neutral placeholders and never expose an owned
  campaign merely as an example;
- a new report request must name or explicitly refer to a campaign;
- report data is presented as the campaign report, without internal data-source
  labels;
- the Zalo report covers the same core information as the web report module;
- suggested questions are delivered once;
- the user is offered a typo-tolerant path to the existing full PDF export.

## Server-authoritative campaign resolution

The model can request a tool, but it cannot choose ownership or make a supplied
campaign reference authoritative. The report tool checks the actual current OA
message against the server-fetched owned campaign set.

A new `mode=show` request is accepted only when the current message contains one
of these signals:

- an owned campaign name or ID;
- an ordinal such as `số 2`, `thứ hai`, or `đầu tiên`;
- an explicit contextual reference such as `campaign này`, `chiến dịch đó`, or
  `của nó`, with an active server-side campaign context.

If the signal is absent, the server stores `pending_report_request` and returns
owned candidates. It never falls back to the active or only campaign. A later
campaign-name reply can continue the pending report.

Report follow-up questions and PDF requests may reuse
`active_report_campaign_id` plus `active_report_view`, because those values were
created only after an ownership-checked report tool call.

## Complete Zalo report delivery

The renderer reads the same existing analytics records and generated report
analysis used by the web module, then creates three 1080×1350 JPEG pages:

1. overall analysis, six KPIs, and the report's primary daily trend;
2. the secondary quality/cost trend and placement comparison;
3. daily distribution and the zone-performance table.

For Awareness this includes impressions, clicks, CTR, spend, reach,
viewability, daily reach/impression trend, CPM trend, viewability by placement,
daily impression distribution, and zone impressions/CTR/viewability/CPM/
conversions.

Every page passes through the existing Zalo image preparation boundary. Images
are compressed only when needed and must remain below the provider limit before
they enter the durable outbound queue.

## Duplicate-safe suggestions

Generated questions are removed from the tool result before it is returned to
the model. The server queues one deterministic suggestion message after the
three images, including the PDF invitation. The model receives only a delivery
marker instructing it not to reproduce queued content or URLs.

## PDF delivery

`get_campaign_report` adds `mode=pdf`. After the same ownership and active-report
checks, it fetches the existing backend PDF exporter. The bytes are stored in
`zalo_channel_media` using:

- a random opaque URL token;
- only the SHA-256 token digest at rest;
- the existing expiry/TTL behavior;
- `application/pdf` and a sanitized download filename.

The media route adds `Content-Disposition: attachment` for files. The raw PDF
URL is queued directly to the OA response and is never included in model tool
output, logs, account state, or browser storage.

## Compatibility and migration

- No Mongo collection or destructive migration is introduced.
- Older `zalo_channel_media` documents remain valid because `filename` is
  optional.
- Existing thread documents remain valid because report-context fields are
  additive and nullable.
- Live capture, local accounts, Zalo Login/OA linking, Guided workflow,
  Autopilot, report generation, and the backend PDF exporter keep their existing
  authority boundaries.
- No Mongo data is seeded, cleared, copied, or deleted.

## Verification plan

- focused report selection, rendering, suggestion, PDF, and media tests;
- complete Agent, backend, and frontend test suites;
- frontend production build;
- production health/readiness checks;
- model-only greeting, guidance, missing-campaign, and typo-PDF probes;
- production rendering against an existing ready campaign;
- opaque PDF response verification including content type and attachment header;
- manual final OA journey from `chat.zalo.me`.
