# NP-6 Placement Catalog Expansion — Implementation and Verification

Date: 2026-07-25  
Status: implemented, deployed, and production verified  
Scope: placement catalog, mock publishers, placement recommendation, creative contracts, setup UI, and order evidence

## Outcome

NP-6 is additive:

- legacy catalog: 35 placements, with the same IDs and inventory metrics;
- new topic-aware category placements: 96;
- new observed-property placements: 9;
- new total: 140 unique placements;
- publishers with comparable category inventory: ZNews and BaoMoi;
- additional contextual properties: S-Money, Đi Cùng Con, and Zagoo;
- topic taxonomy: 12 non-redundant audience contexts;
- category placement families per topic: masthead, background, side-left, side-right, and 300×250 sidebar.

The 105-placement expansion arithmetic is:

- ZNews: six mastheads for the six existing category topics;
- ZNews: five families for each of six new topics;
- BaoMoi: five families for each of all 12 topics.
- S-Money: four device-specific finance placements.
- Đi Cùng Con: two device-specific content bridges and one desktop reserved-layout rail.
- Zagoo: two device-specific game interstitials.

The category layer remains `6 + (6 × 5) + (12 × 5) = 96`; the three additional properties add `4 + 3 + 2 = 9`, producing `35 + 96 + 9 = 140`.

## Topic taxonomy

1. Business & Finance
2. Health & Wellness
3. Sports & Outdoors
4. Technology & Science
5. Entertainment & Culture
6. Lifestyle, Food & Shopping
7. Family & Parenting
8. Education & Careers
9. Travel & Hospitality
10. Automotive & Mobility
11. Home, Property & Architecture
12. Society, News & Law

The taxonomy excludes the redundant publishing/book categories and special editorial products identified during discovery.

## Catalog and API

The seed now builds the unchanged 35-placement legacy catalog first and applies the versioned NP-6 extension afterward.

Catalog metadata includes:

- `catalogVersion = np6-2026-01`;
- `taxonomyVersion = placement-topics-v1`;
- record revision and lifecycle status;
- publisher, page template, topic, placement family, comparison group, device, and renderer metadata;
- explicit creative contract;
- audience-context keywords and DMP category affinities;
- provenance and synthetic inventory source.

The zone API remains backward compatible:

- `/api/zones` still returns groups, channels, and placements and now also returns catalog/taxonomy metadata;
- `/api/zones/placements` still returns the flat list and optionally filters by topic, publisher, family, or device;
- existing single-placement lookup is unchanged.

Local preview URLs preserve the `category.html?topic=...` route for both publishers.

## Mock publisher implementation

ZNews and BaoMoi each use one reusable `category.html` renderer rather than copied article pages.

Each renderer:

- supports all 12 deterministic topics;
- mounts five independent ad zones;
- creates topic-specific Vietnamese fixture copy;
- creates deterministic local SVG editorial illustrations;
- contains no copied article text or remote editorial images;
- is responsive and does not require a separate HTML file for each category.

BaoMoi category background and masthead are independent. The homepage behavior that hides masthead when a background campaign exists is not used on category pages.

Three additional responsive mock publishers are now included:

- S-Money exposes separate desktop/mobile top promotions and separate desktop/mobile stock-screener units;
- Đi Cùng Con exposes separate desktop/mobile content bridges plus a desktop-only 300×600 rail;
- Zagoo exposes separate desktop/mobile game interstitial contracts with an independent close control.

Each page requests only the inventory for its active device after page load. Desktop units are not requested on mobile, and mobile units are not requested on desktop.

Commercial truth remains explicit:

- S-Money stock-screener units: `observed_filled`;
- S-Money top promos, Đi Cùng Con bridges, and Zagoo interstitials: `observed_house`;
- Đi Cùng Con rail: `reserved_layout` and `proposed_mock_only`.

The unconfirmed DCC mobile in-feed and Zagoo sponsored-native ideas were deliberately not implemented.

## Recommendation architecture

The existing performance score remains intact and visible as a score component.

NP-6 adds a deterministic placement-context score based on:

- approved brief fields;
- selected/recommended DMP labels and categories;
- catalog-authored placement keywords;
- catalog-authored topic and DMP affinities.

DMP category names are scored only against explicit placement category affinities. They do not participate in keyword/topic matching; this prevents a broad label such as `Business and industry` from overpowering a specific education or property brief.

Every result contains:

- performance, KPI, creative, and topic-relevance components;
- matched topic/keyword/category evidence;
- a user-facing reason;
- publisher comparison metadata.

Audience RAG is unchanged. Placement relevance is implemented in a separate module.

## Optional GPT-5.4-nano reranker

The optional reranker is:

- default-off;
- model-configured separately as `gpt-5.4-nano`;
- limited to a bounded deterministic shortlist;
- structured-output only;
- prohibited from adding, removing, or duplicating placement IDs;
- `store=false`;
- fail-open to the original deterministic order on any provider, schema, or validation failure.

The component does not select or change a campaign conversation engine and does not affect model locking.

A real provider comparison was not executed because this checkout has no OpenAI API key. Unit tests cover valid reorder, invalid candidate-set rejection, default-off behavior, and `store=false`.

## Creative routing

Placement families now resolve through explicit creative contracts.

This fixes the prior ambiguity where every `skin` placement planned the ZNews background format. Background, ZNews side banners, BaoMoi left/right units, mastheads, sidebar boxes, halfpages, inline banners, and ZingMP3 masthead now resolve to their own known generation format.

Creative compatibility uses the same contract during final placement ranking and auto-assignment. A valid side-banner creative is preferred over a background skin even when both placements retain legacy `skin` inventory labels.

The existing 20-output image quota is unchanged.

## Setup UI and historical evidence

The Guided setup panel now:

- preserves all topic and contract metadata returned by the API;
- groups the catalog by the 12 topics;
- filters by publisher and search text;
- labels cross-publisher comparison placements;
- shows topic-match evidence;
- links to the exact mock page;
- retains the existing conflict disclosure contract.

Campaigns now retain:

- the catalog version used at creation;
- a compact snapshot of every selected placement, including topic, family, contract, metrics, and preview URL.

Idempotent retries return the already-created campaign and its original snapshot.

## Verification evidence

Automated:

- backend maintained suite: 35/35 tests passed;
- Agent maintained `agent/tests/` suite: 448/448 tests passed;
- agent frontend: 107/107 tests passed;
- frontend production build passed;
- catalog invariant: 35 legacy + 96 category + 9 property records = 140 unique;
- cross-publisher invariant: every topic/family has both ZNews and BaoMoi;
- deterministic relevance evaluation: 12/12 topic cases, 100% top-topic accuracy;
- JavaScript and Python syntax checks passed;
- Docker Compose configuration validation passed;
- repository diff whitespace check passed.

The repository-root Agent command also collects two pre-existing manual browser scripts (`agent/test_screenshot_baomoi_category.py` and `agent/test_znews_category_only.py`) as pytest tests and reports missing `label` fixtures. The maintained `agent/tests/` suite is clean; those manual scripts were not changed in NP-6.

Browser:

- ZNews family desktop: all five slots mounted; side units visible at wide viewport; no broken images; no horizontal overflow;
- BaoMoi family desktop: all five slots mounted concurrently; background and masthead both visible; no broken images; no horizontal overflow;
- ZNews technology mobile: page refreshed after viewport change; all five slots mounted, desktop side units hidden by responsive CSS, no overflow;
- BaoMoi travel mobile: page refreshed after viewport change; all five slots mounted, desktop side units hidden by responsive CSS, no overflow.
- S-Money desktop/mobile: page loaded after each viewport change; only the two device-matching placements were filled, with zero overflow and zero broken images;
- Đi Cùng Con desktop/mobile: desktop bridge and rail rendered at 966×249 and 300×600; the refreshed mobile page rendered only the 343×88 bridge, with zero overflow and zero broken images;
- Zagoo desktop/mobile: the refreshed page rendered only the matching 512×512 or 350×470 interstitial; close control dismissed the overlay independently; zero overflow and zero broken images.

The local browser audit used fallback creatives because no local campaign/backend was running. The mock sites correctly attempted the real ad endpoint first.

Implementation screenshots:

| Placement | Desktop evidence | Mobile evidence |
|---|---|---|
| S-Money top promo | [desktop](assets/np6-placement-evidence/smoney-mock-desktop-implemented.png) | [mobile](assets/np6-placement-evidence/smoney-mock-mobile-implemented.png) |
| S-Money stock screener | [desktop](assets/np6-placement-evidence/smoney-screener-desktop-implemented.png) | [mobile](assets/np6-placement-evidence/smoney-screener-mobile-implemented.png) |
| Đi Cùng Con content bridge | [desktop](assets/np6-placement-evidence/dicungcon-mock-desktop-implemented.png) | [mobile](assets/np6-placement-evidence/dicungcon-mock-mobile-implemented.png) |
| Đi Cùng Con sidebar rail | [desktop](assets/np6-placement-evidence/dicungcon-rail-desktop-implemented.png) | not applicable |
| Zagoo interstitial | [desktop](assets/np6-placement-evidence/zagoo-mock-desktop-implemented.png) | [mobile](assets/np6-placement-evidence/zagoo-mock-mobile-implemented.png) |

## Protected contracts

NP-6 does not modify:

- NP-7 video;
- GreenNode or OpenAI campaign-engine independence;
- immutable conversation model locking;
- image quota;
- canonical audience reach;
- FAQ/action coordination;
- report evidence;
- account/campaign ownership;
- creative confirmation;
- order idempotency.

## Production state

NP-6 was deployed and accepted in production on 2026-07-25:

- Agent version: `2026-07-25.2`;
- advertised feature: `np6-placement-catalog`;
- catalog version: `np6-2026-01`;
- production catalog: 140 placements, seven publisher groups, and twelve topics;
- property counts: S-Money 4, Đi Cùng Con 3, and Zagoo 2;
- deterministic live recommendation evaluation: 12/12 briefs passed, with 129 topic-aware candidate placements;
- backend health: healthy with MongoDB connected;
- Agent readiness: MongoDB, backend, creative worker, autopilot worker, Zalo worker, and Zalo OpenAI all ready;
- process state: backend and Agent online under PM2;
- Nginx configuration validation passed.

The catalog migration preserved all 35 legacy placement contracts, created a pre-change revision snapshot, updated the single catalog document in place, and was re-run successfully as an idempotent `already-current` operation. The pre-deployment database archive is stored at:

- `/var/backups/np6-2026-07-25.2/zones-before.archive.gz`.

Public mock sites:

- [S-Money](https://smoney-stg.pawgrammers.io.vn);
- [Đi Cùng Con](https://dicungcon-stg.pawgrammers.io.vn);
- [Zagoo](https://zagoo-stg.pawgrammers.io.vn).

All three hosts return HTTPS 200 and redirect HTTP to HTTPS. Their Let's Encrypt certificate is valid through 2026-10-23, with automated renewal scheduled.

Production browser acceptance repeated the desktop/mobile checks with a page reload after every viewport change:

- S-Money: desktop and mobile top/screener placements switched independently; zero overflow and broken images;
- Đi Cùng Con: desktop bridge and rail rendered, while refreshed mobile rendered the mobile bridge and hid desktop inventory; zero overflow and broken images;
- Zagoo: desktop and mobile interstitials switched independently; the close control dismissed the overlay; zero overflow and broken images;
- ZNews and BaoMoi category templates: all five placement mounts were present; wide desktop showed side units; refreshed mobile hid the side units; zero overflow and broken images;
- Advertising Agent: production frontend rendered successfully with zero horizontal overflow and broken images.

Production API spot checks confirmed publisher, topic, and device filters, including five technology/science placements for each of ZNews and BaoMoi, four S-Money placements, and four mobile placements.
