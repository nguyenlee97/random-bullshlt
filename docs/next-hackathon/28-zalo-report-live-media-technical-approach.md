# Zalo OA Report and Live Media — Technical Approach

## Outcome

Extend the existing Zalo OA conversational agent so it can present the six synthetic campaign reports and live-ad evidence as native Zalo image messages. The model remains responsible for understanding natural language and choosing tools; ownership, campaign resolution, report data, image generation, delivery limits, and mutations remain server-authoritative.

## Product behavior

### Conversation opening

- A greeting receives a warm, brief introduction instead of campaign data.
- The assistant introduces itself as the campaign companion and offers a natural next step without a long capability dump.

### Report discovery

- A general request such as “cho xem báo cáo” must not silently default to Daily Ops.
- The model calls `list_report_types`, then presents all six choices with short explanations:
  - Daily Ops — daily pacing and operational health.
  - Awareness — reach, frequency, CPM, and viewability.
  - Consideration — clicks, CTR, and engagement quality.
  - Conversion — funnel, conversions, CVR, and CPA.
  - Retention — repeat reach, frequency, and engagement decay.
  - Executive — compact cross-funnel management summary.

### Specific report

- When the user names or clearly implies a report type, the model calls `get_campaign_report` with the ownership-resolved campaign and exact report type.
- The tool reads the existing `analytics_records` and `report_analyses`; it does not create a new analytics agent.
- A `show` request produces a branded JPEG report card based on the same synthetic data shown in the web Report module, then sends the report's generated suggested questions as a text message.
- A later report question calls the same tool with `mode=question`. The tool returns the selected report's cached structured analysis and matching generated answer so the model can rewrite it for plain-text Zalo.
- If report generation is still running, the user receives an honest progress message and can retry. No empty or invented metrics are returned.

### Generation timing

- The shared Node `POST /api/orders` commit boundary starts the existing idempotent report generator, so successful Guided and Autopilot launches use one trigger.
- An idempotent order retry also re-checks the report-generation lease, allowing a failed initial start to recover without creating another order.
- Entering the Report tab may safely call the endpoint again because the backend lease and complete-six-report checks are idempotent. It remains the polling/progress UI, but is no longer the only trigger.
- Legacy sessions and campaigns that predate this change remain lazy-compatible: a Zalo report tool request can still start generation when no report context exists.

### Live evidence

- `get_campaign_live_view` accepts `all`, `baomoi`, `znews`, or `zingmp3`.
- For each requested site that belongs to the campaign, delivery order is:
  1. site heading text;
  2. each captured ad-zone image for that site;
  3. annotated full-site image.
- A request for one site sends only that site. A request for all sends each site group in stable order.
- Raw creative links and staging-site links are not used as the primary answer.

## Zalo image contract

The official Zalo OA image-message documentation specifies a media template with `media_type=image`, JPG/PNG support, and a maximum image size of 1 MB. The current OA adapter already uses the working V3 customer-service media-template endpoint with a public HTTPS URL.

Before an image is queued:

- decode it server-side with Pillow;
- normalize to RGB JPEG;
- reduce quality and dimensions until it is below a 950 KB safety ceiling;
- store only the optimized version as the Zalo image URL;
- preserve the original behind a separate opaque, hashed, expiring media URL;
- when optimization changed the asset, send a short full-resolution fallback link.

No token is put in logs or model context. Media remains short-lived and revocable through expiry.

## Data and API impact

- No destructive migration and no new authentication authority.
- Existing Mongo collections are reused:
  - `analytics_records` for synthetic daily/placement metrics;
  - `report_analyses` for six generated analyses and questions;
  - `zalo_channel_media` for opaque expiring image bytes;
  - `zalo_outbound_messages` for ordered, idempotent delivery.
- Zalo tools are additive:
  - `list_report_types()`;
  - `get_campaign_report(campaign_reference, view, mode, question)`;
  - `get_campaign_live_view(campaign_reference, site)`.

## Verification

- Unit tests for generic report clarification, exact report selection, generated report image, generated-question reuse, ordered site/zone/full images, sub-1 MB optimization, and full-resolution fallback.
- Existing agent test suite and frontend production build.
- Live API checks after deployment for media retrieval and OA delivery records.
- Manual Zalo journeys:
  - greeting;
  - general report request;
  - Awareness report image and suggested question;
  - follow-up report question;
  - BaoMoi-only live capture;
  - all-site live capture;
  - post-launch report readiness without opening the web Report tab.

## Rollback

The slice is additive. Reverting its final commit restores text-only report/live behavior. Existing orders, reports, channel sessions, and account/OA links are not modified or deleted.
