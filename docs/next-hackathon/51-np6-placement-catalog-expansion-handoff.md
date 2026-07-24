# NP-6 Placement Catalog Expansion — Technical Handoff

Date: 2026-07-24

Status: ready for a new implementation task. Start with a read-only audit and technical plan; do not edit catalog data until the product owner confirms the initial placement set and provenance policy.

## 1. Objective

Expand the current placement catalog into a larger, more realistic, versioned source of truth that all campaign surfaces can consume safely.

NP-6 must improve:

- placement discovery and comparison;
- preliminary and final placement ranking;
- live inventory availability checks;
- creative format planning and exact-format compatibility;
- reach/cost forecasting;
- order validation and historical reproducibility;
- Copilot, Autopilot, FAQ/live-data tools, Zalo OA, AdsPilot, and public test-site behavior.

The expansion must not create a second placement catalog for any one interface.

## 2. Why this is a separate task

Placement data currently affects multiple layers:

```text
Seed/source data
  -> Node backend zone model and APIs
  -> Python Agent zone catalog and ranking
  -> FAQ/live availability tools
  -> placement intent
  -> creative format plan
  -> creative analysis and assignment
  -> forecast and order guard
  -> frontend setup/result/report views
  -> test-site rendering and Zalo explanations
```

A zone added only to the UI or only to the Agent would create inconsistent availability, pricing, creative compatibility, and order behavior. NP-6 therefore needs a schema-first migration and compatibility program rather than a larger hardcoded list.

## 3. Current verified baseline

At handoff creation:

- Repository: `random-bullshlt`
- Branch: `revamp/next-hackathon`
- Local HEAD: `6ba340c`
- Declared build version: `2026-07-24.1`
- Production was last verified on `2026-07-24.1`; recheck before implementation or deployment.
- NP-1 through NP-5 are implemented:
  - independent OpenAI campaign engine alongside unchanged GreenNode;
  - canonical audience reach contract;
  - GPT Image 2 Creative Studio, named assets, and durable 20-output daily quota;
  - semantic FAQ/action coordination with allowlisted read tools;
  - evidence-grounded report generation and Q&A.
- Zalo OA is a channel adapter over server-owned campaign/workflow services. Do not create Zalo-specific placement truth.

The knowledge-base architecture documents under `docs/knowledge base` are older than the current implementation. Read them for orientation, then verify every important claim against current source and tests.

## 4. Existing placement surfaces to audit

Begin by tracing these files and their callers:

- `backend/seed/data/Ads Zone.xlsx`
- `backend/models/Zone.js`
- `backend/routes/zones.js`
- `backend/middleware/zoneValidator.js`
- `backend/tests/inventory-metrics.test.js`
- `agent/tools/zone_catalog.py`
- `agent/tools/zone_ranker.py`
- `agent/autopilot/placement_planning.py`
- `agent/openai_campaign/knowledge.py`
- `agent/openai_campaign/read_tools.py`
- `agent/order_guard.py`
- `agent/tests/test_autopilot_placement_planning.py`
- `agent/tests/test_autopilot_service.py`
- `agent/tests/test_openai_knowledge_tools.py`
- `agent_frontend/src/data/zones.js`
- `agent_frontend/src/steps/setup/ZoneSelectionPhase.jsx`
- the ZNews, BaoMoi, and ZingMP3 replicated test sites;
- AdsPilot order and placement views.

Search for duplicated placement IDs, dimensions, CPMs, site URLs, media types, and compatibility rules before deciding which file is authoritative.

## 5. Required scope

### 5.1 Versioned placement schema

Define one canonical schema with, at minimum:

- immutable `placement_id`;
- catalog version and record revision;
- lifecycle state: draft, active, inactive, or retired;
- effective start/end dates;
- publisher, property/site, channel, and environment;
- device and responsive behavior;
- media types supported;
- placement family and human-readable name;
- exact width/height or an explicitly modelled responsive size contract;
- aspect ratio;
- safe-area and crop constraints;
- image MIME/file-size restrictions;
- pricing unit and price/CPM metadata;
- inventory source and availability capability;
- reach/traffic metadata with source date and confidence;
- test-site/rendering capability;
- source/provenance classification;
- source URL/reference and last verification date;
- compatibility metadata used by creative planning and order validation.

Do not add video-only duration, codec, audio, or caption behavior as an incidental extension. Those belong to NP-7 after its discovery spike.

### 5.2 Provenance policy

Every placement must be classified clearly:

- `authoritative`: verified against an official/current source;
- `partner_fixture`: supplied by a known partner or internal dataset;
- `demo_fixture`: intentionally synthetic for the hackathon.

Do not combine synthetic price, reach, or availability with a real publisher name in a way that implies live commercial inventory.

Current external publisher specifications are time-sensitive. If new real placements are proposed, verify them against official primary sources during the new task and record the verification date.

### 5.3 Historical reproducibility

Existing campaigns and reports must retain their original meaning when the catalog changes.

Required behavior:

- version or retire placements instead of rewriting their historical definition;
- preserve a catalog snapshot/version on placement-intent, format-plan, final-placement, forecast, and order artifacts;
- define how legacy orders with only a placement ID resolve their historical metadata;
- avoid destructive migration of existing campaigns;
- make catalog seeding/import idempotent.

### 5.4 Generic consumers

Adding an image placement should normally require catalog data and generic renderer support, not a new hardcoded branch in every frontend.

Consumers must handle:

- unknown or retired placements;
- missing reach/pricing values;
- unsupported test-site preview;
- availability service degradation;
- several placements sharing one exact creative format;
- one placement accepting multiple image formats;
- responsive placements whose constraints cannot be represented as a fabricated exact size.

### 5.5 Inventory and FAQ integration

Reuse the NP-4 read boundary:

- catalog questions use versioned catalog snapshots;
- date-specific availability uses the live inventory/conflict service;
- the model never receives raw Mongo access;
- answers include source/version/freshness;
- unavailable or demo-only inventory is labelled honestly.

### 5.6 Creative compatibility

For each new image placement, verify the complete path:

1. placement intent can rank it;
2. format planning derives a supported exact format;
3. GPT Image 2 generation or upload can supply that format;
4. deterministic composition respects the safe area;
5. VLM/creative intelligence evaluates the correct intended format;
6. final placement ranking filters incompatible assets;
7. creative assignment maps a valid asset;
8. order guard accepts the valid mapping and rejects invalid mappings.

## 6. Explicit non-goals

Do not include these in NP-6:

- video generation, transcoding, thumbnails, audio, captions, or video moderation;
- a video quota or reuse of the 20-image daily quota;
- replacing the GreenNode or OpenAI campaign engines;
- changing the immutable per-run model selection;
- arbitrary database/query tools for the Agent;
- redesigning audience reach;
- creating a second report pipeline;
- Zalo-specific placement storage;
- silently presenting demo fixtures as live inventory.

NP-7 begins only after NP-6 is stable and will start with a separate provider/specification/cost spike.

## 7. Recommended delivery slices

### Slice 0 — Read-only inventory and decision record

- Map every current source and consumer.
- Export the current catalog with IDs, dimensions, CPM, reach, source, and duplicates.
- Identify which source currently wins when values disagree.
- Propose the initial expansion set with evidence and provenance.
- Present product decisions before editing.

Exit: the product owner approves the initial publishers/properties, number of zones, provenance labels, and demo-versus-authoritative policy.

### Slice 1 — Canonical schema and versioning

- Add schema validation and catalog-version contracts.
- Add additive persistence/index changes if required.
- Define legacy resolution and retirement behavior.
- Build an idempotent import/seed path.

Exit: current placements round-trip through the new contract without behavior changes.

### Slice 2 — Expanded catalog data

- Add only approved placements.
- Store source/freshness/provenance for every record.
- Validate IDs, dimensions, prices, lifecycle dates, and duplicate families.
- Generate a human-reviewable catalog diff.

Exit: every new placement passes schema and provenance validation.

### Slice 3 — Backend and inventory services

- Update list/search/detail APIs and availability/conflict checks.
- Preserve stable response contracts or version them explicitly.
- Add catalog-version and freshness metadata.
- Add cache invalidation tied to catalog revision.

Exit: live and demo inventory behavior is distinguishable and testable.

### Slice 4 — Agent planning and creative compatibility

- Update zone discovery/ranking.
- Update preliminary placement intent.
- Update format-family planning and deduplication.
- Update final placement, forecasting, assignment, and order guard.
- Update FAQ/live-data tools without adding raw DB access.

Exit: each new placement works through a complete image campaign path.

### Slice 5 — Generic UI and test-site presentation

- Render catalog-provided details generically in Guided and Autopilot.
- Update AdsPilot and result/report views as required.
- Add previews only where a real replicated renderer exists.
- Show a clear unavailable-preview state otherwise.
- Remove newly discovered duplicated static placement data where safe.

Exit: adding a standard image placement does not require placement-specific UI code.

### Slice 6 — Migration, regression, and production release

- Validate existing campaign/history behavior.
- Run focused catalog, inventory, placement, creative, forecast, order, FAQ, Zalo, backend, and frontend tests.
- Run full maintained backend/frontend suites.
- Perform production browser scenarios for Copilot and Autopilot.
- Verify Zalo read questions for new placements without performing unauthorized mutations.
- Commit, push, back up production, deploy, and verify readiness/version.

Exit: old campaigns remain reproducible and all approved new placements are usable end to end.

## 8. Product decisions required in the new task

Do not guess these:

1. Which publishers/properties should be included in the first expansion?
2. How many new placements are wanted in the first release?
3. Which records have authoritative specs versus demo-fixture values?
4. May real publisher names be paired with synthetic reach/pricing, or should demo publishers be clearly fictionalized?
5. What inventory semantics are real: static availability, conflict-based availability, or partner API?
6. Which placements must have working replicated-site previews?
7. Should inactive/retired placements remain searchable for historical campaigns?
8. What is the intended initial image-format coverage?

Recommended approach: propose a small representative first tranche, validate the architecture, then expand the data. Do not migrate dozens of zones before the versioning and generic-consumer contracts are proven.

## 9. Acceptance matrix

At minimum, acceptance must cover:

- schema validation for every record;
- globally unique stable placement IDs;
- explicit provenance and freshness;
- versioned historical lookup;
- idempotent import/seed;
- search/filter by publisher, property, device, format, and objective;
- date-range availability/conflict behavior;
- no fabricated availability when the service is unavailable;
- placement-intent ranking;
- exact-format family planning and deduplication;
- safe-area-aware generation/composition;
- upload compatibility;
- VLM intended-format checks;
- final ranking and assignment;
- forecast pricing-unit correctness;
- order guard and idempotent order creation;
- FAQ catalog and availability answers with citations;
- Guided and Autopilot end-to-end scenarios;
- Zalo read-only discovery/comparison;
- unchanged OpenAI/GreenNode component isolation;
- unchanged image quota semantics;
- no video behavior introduced.

## 10. Workspace and operational safeguards

- Read `AGENTS.md` and `docs/knowledge base` before acting.
- The workspace is shared and may be dirty. Recheck `git status` immediately.
- At handoff creation, known user-owned changes included:
  - `agent/README.md`;
  - `agent/tests/test_autopilot_creative_generation.py`;
  - untracked `AGENTS.md`;
  - untracked `agent/graph/README.md`;
  - untracked `output/`.
- Preserve unrelated changes and stage only files owned by NP-6.
- Never copy credentials into documentation, logs, commits, or prompts.
- Use production as the acceptance environment for identity/Zalo-dependent flows.
- Back up exact production targets before overwriting them.
- Report manual or blocked checks honestly.

## 11. Source documents

Read these first:

1. `AGENTS.md`
2. `docs/knowledge base/`
3. `docs/next-hackathon/45-openai-creative-knowledge-roadmap.md`
4. `docs/next-hackathon/47-np2-np5-delivery-and-manual-acceptance.md`
5. `docs/next-hackathon/46-openai-engine-technical-implementation-plan.md`
6. `docs/next-hackathon/51-np6-placement-catalog-expansion-handoff.md`

Use current code and tests as authority when older documentation disagrees.

## 12. Completion deliverables

The NP-6 task is complete only when it leaves:

- an approved placement-source and provenance decision record;
- canonical versioned placement schema documentation;
- validated catalog source/import artifacts;
- additive migration and rollback instructions;
- implementation across all affected consumers;
- focused and full-suite test evidence;
- manual Guided, Autopilot, FAQ, Zalo, and historical-campaign evidence;
- production deployment/rollback evidence;
- a final catalog inventory showing active, inactive, retired, and demo placements;
- an explicit handoff boundary to NP-7 video discovery.
