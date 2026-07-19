# Copilot audience sizing and creative recovery evidence

Date: 2026-07-20

Branch: `revamp/next-hackathon`

Production build: `2026-07-20.1`

## Product behavior

- Existing publisher-provided DMP sizes remain unchanged.
- Catalog rows without a size receive a deterministic Vietnam-scale range.
  Modeled values are stable per segment and explicitly carry
  `sizeSource=modeled_estimate`; they are not represented as delivery truth.
- Campaign Copilot keeps Creative Intelligence evidence visible after the
  Creative step is complete: deterministic dimensions, VLM subject and brand,
  Brief-match score/reasons, confidence, safety flags and OCR.
- A `needs_review` creative exposes the existing audited override endpoint and
  requires an operator reason. Copilot and Autopilot therefore share the same
  creative-analysis authority.
- Missing, stale, unapproved or URL-less creative assignments render as an
  actionable warning rather than a generic thrown zone error. The operator can
  reassign, open Creative review, or explicitly remove only invalid zones.
- The order guard remains fail-closed. A warning never makes an unapproved or
  nonexistent creative valid and never creates an order by itself.

## Migration

`backend/seed/backfill-audience-sizes.js` is additive and idempotent. It updates
only documents where both `sizeMin` and `sizeMax` are absent/non-positive. It
does not delete, reseed, replace `_id`, or modify an existing positive size.

The DMP read API also applies the same deterministic fallback, so older or
partially migrated environments do not return blank size cells. The Mongo
backfill makes those values durable and auditable through `sizeSource`,
`sizeEstimateVersion`, and `sizeEstimatedAt`.

## Verification

### Automated checks

- Focused Agent tests: **16 passed**.
- Full Agent suite: **318 passed** with two pre-existing warnings.
- Backend suite: **18 passed**.
- Frontend suite: **73 passed**.
- Vite production build: **passed** across 2,583 transformed modules.

### Production migration

- Pre-migration dry run: 303 candidates out of 310 audience documents.
- Applied migration: 303 documents modified; no documents deleted or reseeded.
- Post-migration dry run: 0 candidates.
- Live `/api/dmp/attributes?limit=1000` response: 310 rows, 0 rows with a
  missing size, 303 `modeled_estimate` rows and 7 publisher/catalog rows.
- Representative VNG audience ranges after migration:
  - Action games: 2.70M-3.79M
  - Live events: 6.13M-8.50M
  - Massively multiplayer online games: 5.14M-7.24M
  - Online games: 6.33M-8.14M
  - Video games: 6.16M-8.78M
  - Sports: 3.42M-4.22M

### Production browser acceptance

Using the existing account-owned VNG Campaign Copilot workspace:

- History restored the same workspace at revision 5.
- Completed Audience showed a 19.7M union and the disclosure that some
  segments use modeled Vietnam catalog estimates.
- Completed Creative showed the saved image and the full Creative Intelligence
  result: VNG brand, subject description, 5/5 Brief match, 95% confidence,
  match reasons, safety result and OCR summary.
- Setup remained reachable. The existing campaign had no invalid-assignment
  alert to exercise, so the actionable warning/recovery branch is covered by
  focused component and helper tests rather than by corrupting production
  workspace data.
- No zone proposal was approved and no order was created during acceptance.

### Rollback evidence

- `/var/backups/adspilot-api-audience-creative-20260719T173013Z.tar.gz`
- `/var/backups/agent-api-audience-creative-20260719T173013Z.tar.gz`
- `/var/backups/agent-frontend-audience-creative-20260719T173013Z.tar.gz`
- `/var/backups/audience-library-before-size-backfill-20260719T173013Z.json`
- Previous frontend directory:
  `/var/www/agent.prev-20260719T173013Z`

## Known follow-up

Modeled audience ranges are labeled planning estimates for the hackathon demo,
not measured delivery data. Replace them with publisher/DMP-provided segment
counts when that source becomes available; existing positive catalog values are
already preserved by both the read fallback and backfill.
