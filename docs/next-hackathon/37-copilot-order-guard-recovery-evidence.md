# Campaign Copilot order-guard recovery evidence

Date: 2026-07-19

Branch: `revamp/next-hackathon`

Production build: `2026-07-19.6`

## Outcome

Campaign Copilot now explains commit-time placement conflicts instead of
showing the generic `Order guard từ chối tạo chiến dịch` message. The guard
remains fail-closed, refreshes current placement availability, and gives the
operator a direct path back to choose another zone.

Audience records without catalog size fields are now represented as unknown.
The workspace, chat block, model context and Setup confirmation no longer turn
missing data into `0 người` or invite the model to diagnose a false empty
audience.

No Mongo schema, stored campaign, ownership rule, Zalo behavior, Node order
authority or booking rule changed. Mongo was not reseeded, deleted or migrated.

## Production diagnosis

The signed-in production campaign was inspected without creating or modifying
an order. It contained six valid catalog-grounded audience segments whose size
fields were absent, plus one selected placement: `BaoMoi_Box2`.

The latest server audit event for the same attempt recorded:

`Zone đã bị đặt trong khoảng thời gian này: BaoMoi_Box2 (đã đặt bởi ORD-2026-006)`

The guard was therefore correct. The UI lost the reason because
`createCampaignOrder` returned raw FastAPI `{text, meta}` while
`ConfirmPhase` consumed normalized frontend `{content, metadata}`.

## Repair

- Route Setup order creation through the shared chat response adapter.
- Keep the same idempotency key after guard rejection; reset it only after a
  normalized `order_create` success.
- Surface the full guard message with preserved line breaks.
- Refresh live zone conflicts after rejection and offer `Chọn zone khác`.
- Preserve the booking guard and Node backend as the only order authority.
- Add explicit `sizeKnown` / `size_known` semantics while retaining numeric
  `size: 0` for migration compatibility with older stored workspaces.
- Tell the audience reasoning model that missing size is unknown, not evidence
  that a segment is broken or empty.
- Render unknown size as `— · Catalog chưa cung cấp size` in Guided surfaces.

## Verification

### Automated

- Agent suite: **305 passed**, 0 failed, 2 existing warnings.
- Frontend suite: **69 passed**, 0 failed.
- Node backend suite: **15 passed**, 0 failed.
- Focused order/audience regression checks: **33 passed**, 0 failed.
- Production Vite build: passed; 2,582 modules transformed.

Two standalone screenshot utilities in the `agent/` root match pytest's file
naming convention but require command-line parameters. The authoritative suite
is `pytest tests`, which passed completely; these utilities were not changed.

### Production acceptance

- `GET /api/version` returned `2026-07-19.6` with the three recovery features.
- `GET /ready` reported Mongo, Node backend, creative worker, Autopilot worker,
  Zalo worker and Zalo OpenAI ready.
- Resuming the affected campaign displayed `Chưa có size` for the audience,
  rather than `0 người`.
- Opening Setup refreshed live availability. The conflicted `BaoMoi_Box2` zone
  was excluded and six currently available alternatives were offered.
- The final order-creation click was deliberately left to the operator; the
  deployment acceptance journey did not create a campaign.

## Migration and rollback

The change is additive and read-compatible. Existing workspaces without
`sizeKnown` infer known size only when their numeric size is positive. Existing
`size: 0` records with no catalog estimate render as unknown. No backfill is
required.

Rollback archives:

- `/var/backups/agent-api-setup-guard-20260719-221045.tar.gz`
- `/var/backups/agent-frontend-setup-guard-20260719-221045.tar.gz`

Restoring both archives returns production to build `2026-07-19.5`.
