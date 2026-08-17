# Zalo OA Report and Live Media — Current State and Evidence

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Starting commit: `a645853` (`fix report metric card flow`)

Build: `2026-07-19.1`

## Delivered behavior

- Zalo greetings now use a warm, natural introduction and do not disclose campaign facts.
- A generic report request calls `list_report_types` and explains all six report views instead of silently defaulting to Daily Ops.
- A specific report request calls `get_campaign_report` with an exact report view and `mode=show`.
- The tool reads the existing synthetic `analytics_records` and `report_analyses`, renders a 1080×1350 branded JPEG report card, then sends the report's six generated follow-up questions.
- A later report question uses `mode=question`, matches the cached generated analysis for that report, and gives the model structured source material to rewrite for plain-text Zalo.
- Successful order creation now acquires the existing report-generation lease in the Node order route. This covers Guided, Autopilot, and idempotent order retries. Opening the Report tab remains a safe generation retry and progress-polling path.
- Live capture accepts `all`, `baomoi`, `znews`, or `zingmp3` and queues each site as heading text, ad-zone crop image(s), then the annotated full-site image.
- Raw staging/creative links are no longer the primary live-view response.

## Official Zalo image contract

The implementation was checked against Zalo's official “Gửi tin nhắn dạng ảnh đến người dùng ẩn danh” documentation:

- media-template element with `media_type=image`;
- JPG and PNG support;
- maximum image size of 1 MB;
- public image URL delivery.

The existing OA adapter already uses the working V3 `message/cs` media-template contract. The new preparation boundary:

- accepts only decodable image bytes;
- retains a valid JPG/PNG already below the threshold;
- otherwise converts to RGB JPEG and iteratively reduces quality/dimensions;
- uses 950,000 bytes as the safety ceiling;
- stores the optimized image behind the existing opaque, hashed, expiring media URL;
- adds a separate expiring full-resolution link only when optimization changed the image;
- rejects any declared outbound image above 1,000,000 bytes before queueing.

No media token, account token, owner ID, or provider credential is sent to the model or written to application logs.

## Report generator compatibility

Production log inspection found an older deployed `reportGenerator.js` still using the unsupported `max_tokens` field for the GPT-5-family model. The deployed generator now:

- uses `max_completion_tokens`;
- omits non-default `temperature` for GPT-5-family models;
- retains configured temperature for older compatible models.

This is required for automatic post-launch report generation to complete rather than leave the six analyses in error.

## APIs and persistence

Additive model tools:

- `list_report_types()`
- `get_campaign_report(campaign_reference, view, mode, question)`
- `get_campaign_live_view(campaign_reference, site)`

Existing HTTP APIs are preserved:

- `POST /api/reports/generate` now delegates to the shared idempotent launcher.
- `POST /api/orders` starts the same launcher after the order is committed.
- `GET /api/reports/status/:campaignId`
- `GET /api/reports/data/:campaignId`
- `GET /api/reports/analysis/:campaignId/:reportType`
- `GET /api/agent/zalo/media/:token`

There is no Mongo schema migration and no new collection. Existing collections are reused:

- `analytics_records`
- `report_analyses`
- `zalo_channel_media`
- `zalo_outbound_messages`

No Mongo data was seeded, cleared, copied, or deleted during deployment.

## Automated verification

Focused Zalo report/media suite:

- `22 passed`
- Covers warm greeting isolation, all six report descriptions, report JPEG rendering, generated-question reuse, similar-question matching, 1 MB optimization, outbound size rejection, and ordered single/all-site capture.

Complete Agent suite:

- `290 passed`
- Two existing non-failing warnings: Starlette/httpx deprecation and FastEmbed pooling guidance.

Backend suite:

- `13 passed`
- Includes GPT-5 report request-contract coverage in addition to existing lease, inventory, security, and route behavior.

Frontend suite and production build:

- `62 passed`
- Vite `6.4.3`
- `2,581` modules transformed
- production build completed successfully.

## Production acceptance

Public health after deployment:

- `/agent/api/version` returned `2026-07-19.1` with all four new feature flags.
- `/agent/ready` returned `ready`; Mongo, backend, creative worker, Autopilot worker, Zalo worker, and Zalo OpenAI were healthy.
- backend `/api/health` returned HTTP 200 with Mongo connected.
- Zalo webhook provider probe returned HTTP 200 with `accepted=false` for the deliberately unsigned empty payload.
- Both PM2 processes remained online after restart.

Report acceptance using existing production campaign `ORD-2026-004`:

- all six reports were ready with zero errors;
- Awareness loaded 84 synthetic analytics rows and six generated questions;
- the production Agent rendered them as JPEG, 1080×1350, 109,135 bytes;
- the image was below the 950,000-byte safety ceiling.

Live capture acceptance using the campaign's real BaoMoi placements:

- captured `BaoMoi_Background` as a 221,992-byte zone image;
- captured the annotated full site as a 224,400-byte image;
- order was zone image followed by full-site image;
- both were below 1 MB.

Real production GPT-5.4-mini model-only probes, with no external Zalo send and no mutation:

1. `chào` returned a warm introduction, disclosed no campaign, and made zero tool calls.
2. `Cho tôi xem báo cáo` selected `list_report_types`, explained all six reports, and asked the user to choose one rather than choosing Daily Ops.

## Deployment and rollback

Updated services:

- Agent API at `/var/www/agent-api`
- AdsPilot backend at `/var/www/backend`

Rollback snapshot:

- `/var/backups/advertising-agent/20260719-zalo-report-media-1`

The snapshot includes the previously deployed files and absence markers for the three new modules. Rollback restores those files, removes modules marked as previously absent, then restarts `adspilot-api` and `agent-api`. No database rollback is required.

## Known follow-ups

- The user should perform the final OA end-to-end delivery check from `chat.zalo.me`: Awareness image plus suggestions, one suggested follow-up question, BaoMoi-only live capture, and all-site capture.
- Zone crops depend on the live replica exposing the requested zone DOM element. In production acceptance BaoMoi Background was present; BaoMoi Masthead was not present in that page render, so the full-site image still provides evidence while missing zones are omitted.
- A multi-site campaign may create several sequential OA messages. The durable outbox already preserves ordering and applies provider retry behavior, but real OA burst behavior should be observed during the manual all-site journey.
