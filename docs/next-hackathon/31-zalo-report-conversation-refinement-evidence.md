# Zalo OA Report Conversation Refinement — Current State and Evidence

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Starting commit: `c30518b053154c173a4fdd62841704df2744f867`

Build: `2026-07-19.2`

## Delivered behavior

- The warm introduction includes: `Nếu bạn muốn được hướng dẫn kỹ hơn, hãy nói
  với mình nhé.`
- Detailed guidance uses only neutral examples such as `campaign A`; it does not
  use an owned campaign name, ID, metric, or account fact as sample content.
- A new specific report request cannot silently fall back to the active campaign
  or the only owned campaign. It asks which campaign and preserves the requested
  report view for a follow-up.
- Explicit references by owned name/ID, ordinal, or contextual phrase remain
  supported.
- Report questions and PDF requests reuse only the ownership-checked active
  report context.
- User-facing report output no longer exposes internal data-source labels such
  as demo, mock, or forecast.
- A full Zalo report now contains three ordered images rather than one abbreviated
  card.
- Suggested questions plus the PDF invitation are queued once and removed from
  the model-visible tool result, preventing duplicate delivery.
- PDF intent accepts natural variants and small typos, including `pfd`; it queues
  an opaque, hashed, expiring download link to the existing full report PDF.
- Existing live-view behavior was not changed.

## Report page coverage

Awareness delivery now covers the same core information shown by the web report:

1. overall analysis, impressions, clicks, CTR, spend, reach, viewability, and
   daily reach/impression trend;
2. CPM trend and viewability by placement;
3. daily impression distribution and the zone-performance table with
   impressions, CTR, viewability, CPM, and conversions.

The other five report types use the same three-page structure with view-specific
primary, secondary, and placement metrics.

## APIs and additive persistence

Updated model tool:

```text
get_campaign_report(campaign_reference, view, mode, question)
mode = show | question | pdf
```

Existing HTTP route, extended compatibly:

```text
GET /api/agent/zalo/media/:token
```

When an optional filename exists, the route returns
`Content-Disposition: attachment`; older image documents have no filename and
retain their previous behavior.

Additive Zalo thread fields:

- `active_report_campaign_id`
- `active_report_view`
- `pending_report_request`

Additive optional `zalo_channel_media` field:

- `filename`

There is no destructive migration, no collection replacement, and no Mongo
seed, clear, copy, or delete. Older thread and media documents remain readable.
The single acceptance PDF-media document uses the existing TTL and expires
automatically.

## Automated verification

Focused report/media suite:

- `12 passed`
- Covers all six report types, three-page JPEG rendering, 1 MB safety,
  explicit-campaign enforcement, active-report PDF continuation, opaque filename
  preservation, duplicate suggestion prevention, typo-PDF contract, and live
  capture regression.

Complete Agent suite:

- `294 passed`
- Two existing non-failing warnings: Starlette/httpx deprecation and FastEmbed
  pooling guidance.

Backend suite:

- `13 passed`

Frontend suite:

- `63 passed`

Frontend production build:

- Vite `6.4.3`
- `2,582` modules transformed
- build completed successfully.

## Production acceptance

Public/current service checks after deployment:

- Agent build: `2026-07-19.2`
- `/agent/ready`: `ready`
- Mongo: healthy
- backend dependency: healthy
- creative, Autopilot, and Zalo workers: healthy
- Zalo OpenAI: healthy
- backend `/api/health`: HTTP 200, database connected
- PM2: both `agent-api` and `adspilot-api` online

Model-only probes used the deployed GPT-5.4-mini path and did not send external
Zalo messages or perform campaign mutations:

1. `chào` produced a warm introduction containing the requested guidance
   sentence, no campaign facts, and zero tool calls.
2. `hướng dẫn kĩ hơn` produced generic Campaign A/B/C examples and zero tool
   calls.
3. `cho xin report awareness` asked which campaign instead of selecting the
   active campaign.
4. A follow-up `Campaign A` invoked `get_campaign_report`, queued exactly three
   images and one suggestion message, and did not repeat suggested questions in
   assistant text.
5. `toi muon file report pfd` invoked `get_campaign_report` with the active
   report context and queued one PDF delivery link.

Real production-report acceptance used existing campaign `ORD-2026-004`:

- 84 analytics rows;
- six generated Awareness questions;
- three JPEG pages at 108,816, 83,322, and 95,579 bytes;
- every page was far below the 950,000-byte safety ceiling;
- existing exporter returned a valid `%PDF` file of 14,265 bytes;
- opaque download returned HTTP 200 and identical bytes;
- response type was `application/pdf`;
- attachment filename was `report-ORD-2026-004.pdf`.

No external OA message was sent during automated acceptance. The user can now
perform the final visual journey in `chat.zalo.me` with their linked account.

## Deployment and rollback

Updated service:

- Agent API at `/var/www/agent-api`

Rollback snapshot:

- `/var/backups/advertising-agent/20260719-zalo-report-refinement-2`

The snapshot contains the six previously deployed Agent files. Rollback copies
them back to `/var/www/agent-api` and restarts `agent-api`. The backend and
frontend were verified but did not require deployment for this slice. No database
rollback is needed.

## Known follow-ups

- Perform the final real OA visual check from `chat.zalo.me`: new greeting,
  neutral detailed guidance, missing-campaign clarification, three Awareness
  images, one suggestions/PDF invitation message, typo-PDF download, and the
  already-working live-view flow.
- The opaque PDF link intentionally expires after 15 minutes; the user can ask
  for the PDF again to receive a new link.
- Long zone names are truncated in the Zalo table for readability; the full PDF
  remains the complete downloadable representation.
