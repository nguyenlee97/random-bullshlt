# NP-6 Placement Catalog Expansion — Comprehensive Technical Approach

Date: 2026-07-25

Status: approved architecture with a 2026-07-25 scope correction; implemented and deployed to production as Agent version `2026-07-25.2`. Production evidence is recorded in `55-np6-implementation-and-verification.md`.

Scope correction: the original comparison architecture covered ZNews and BaoMoi only. The approved implementation also includes the nine evidence-backed image placements discovered on S-Money, Đi Cùng Con, and Zagoo. House and reserved-layout candidates retain explicit non-commercial provenance.

## 1. Outcome

NP-6 should expand the current 35-placement image catalog into a topic-aware catalog that:

- keeps every existing placement ID and behavior compatible;
- adds non-redundant editorial categories rather than cloning every publisher subcategory;
- gives ZNews and BaoMoi the same canonical topic coverage so placements can be compared meaningfully;
- renders every new category through two generic publisher templates rather than dozens of copied HTML pages;
- adds distinct S-Money finance, Đi Cùng Con parenting, and Zagoo game-discovery mock properties without inventing unobserved native or mobile inventory;
- adds explicit placement topic, keyword, audience-affinity, provenance, lifecycle, and creative-contract metadata;
- retrieves and ranks placements using campaign context before existing performance metrics;
- optionally reranks only the safe candidate set, with deterministic fallback;
- proves Guided, Autopilot, creative generation/upload, assignment, order, preview, and reporting behavior end to end.

The recommended final target is:

| Catalog component | Current | New | Final |
|---|---:|---:|---:|
| Existing ZNews homepage placements | 4 | 0 | 4 |
| Existing ZNews category placements | 24 across 6 topics | 6 category mastheads + 30 placements for 6 new topics | 60 across 12 topics |
| Existing BaoMoi homepage placements | 6 | 0 | 6 |
| BaoMoi category placements | 0 | 60 across 12 topics | 60 |
| ZingMP3 placements | 1 | 0 | 1 |
| S-Money placements | 0 | 4 device-specific placements | 4 |
| Đi Cùng Con placements | 0 | 3 evidence-backed placements | 3 |
| Zagoo placements | 0 | 2 device-specific interstitials | 2 |
| **Total** | **35** | **105** | **140** |

This is a large catalog, but the category layer is built from only two generic renderers and twelve topic fixtures. Three additional single-property renderers cover the distinct finance, parenting, and game-discovery layouts. The number of data records grows without cloning dozens of article pages.

## 2. Revalidated baseline

Current repository and production evidence:

- branch: `revamp/next-hackathon`;
- local HEAD: `238682f`;
- local declared version: `2026-07-25.1`;
- production `https://agent-api.pawgrammers.io.vn/api/version`: `2026-07-25.1`;
- production catalog: 35 placements;
- production channels: 9;
- production groups: 4;
- all current placement performance fields use `metricSource: synthetic_inventory_v2`;
- the 35 current records are physically distributed across:
  - ZNews homepage: 4;
  - six ZNews categories: 4 per category, 24 total;
  - BaoMoi homepage: 6;
  - ZingMP3 homepage: 1.

The six existing ZNews category topics are:

1. Business;
2. Health;
3. Sports;
4. Technology;
5. Entertainment;
6. Lifestyle.

Each existing ZNews category already uses:

- `Background`;
- `SideLeft`;
- `SideRight`;
- `SidebarBox`.

The shared homepage `ZingNews_Masthead` is present in the category HTML, but it is not a topic-specific placement.

### 2.1 Current architectural gaps that NP-6 must address

1. `backend/models/Zone.js` does not model topic context, taxonomy version, provenance, lifecycle, device, page template, catalog version, record revision, renderer contract, or historical snapshot.
2. The seed creates `flexible`, `subFormat`, `mockId`, and notes that are not declared in the strict Mongoose placement schema. Those fields can be lost before reaching consumers.
3. Placement IDs and rendering rules are duplicated or inferred in:
   - `backend/seed/index.js`;
   - `backend/lib/siteUrls.js`;
   - `agent/autopilot/placement_planning.py`;
   - `agent_frontend/src/data/zones.js`;
   - `agent_frontend/src/demo/demoScripts.js`;
   - ZNews and BaoMoi replica JavaScript.
4. `agent/tools/zone_ranker.py` ranks objective, reach, VI, CTR, CPM, KPI, and creative size. It does not receive the brief’s product topic, selected DMP segments, family/life-stage relevance, or page context.
5. Autopilot preliminary selection calls the same context-free ranker with no creative. Final ranking adds creative compatibility, but still has no topic relevance.
6. `format_spec_for_zone()` maps every `skin` placement to `znews-Background`. That collapses background skins and left/right side strips even though the demo renderer maps those IDs to different creative formats.
7. The ZNews replica has six copied category HTML files of roughly 220 KB each. Repeating that method for every discovered category would create unnecessary maintenance and regression risk.
8. BaoMoi currently has only a homepage replica. Its category expansion needs a generic category page rather than copies of the 1 MB homepage document.
9. Existing campaigns store placement IDs without a durable catalog-version/snapshot contract.
10. No maintained test currently asserts placement contextual relevance or ZNews/BaoMoi same-topic comparison.

## 3. Topic taxonomy

### 3.1 Categories deliberately excluded

Do not add these as separate NP-6 topics:

- Xuất bản;
- Tác giả;
- Thế giới sách;
- Cuốn sách tôi đọc;
- Nghiên cứu xuất bản;
- Văn hóa đọc;
- Cải chính;
- Podcast/Vodcast;
- Longform;
- Story;
- LENS.

The publishing categories overlap heavily and are too narrow for the intended audience-segment coverage. The special-series surfaces showed no provider frame in the discovery sample. Cải chính is not an advertiser-audience category.

Existing placement records are not deleted merely because a future taxonomy changes. The exclusions above apply to proposed NP-6 additions.

### 3.2 Twelve canonical topic families

Both ZNews and BaoMoi should expose the same twelve canonical topic IDs:

| Canonical ID | User-facing topic | Existing ZNews mapping | Primary coverage |
|---|---|---|---|
| `business_finance` | Business & Finance | Kinh doanh | banking, investing, enterprise, careers, professional services |
| `health_wellness` | Health & Wellness | Sức khỏe | care, wellness, nutrition, fitness, insurance-safe health context |
| `sports_outdoors` | Sports & Outdoors | Thể thao | football, sports, fitness, outdoor activities, fan culture |
| `technology_science` | Technology & Science | Công nghệ | devices, software, AI, telecom, gaming technology, science |
| `entertainment_culture` | Entertainment & Culture | Giải trí | music, film, television, celebrities, arts, events |
| `lifestyle_food_shopping` | Lifestyle, Food & Shopping | Đời sống | food, drink, fashion, beauty, shopping, relationships, consumer life |
| `family_parenting` | Family & Parenting | new | pregnancy-safe context, parents, babies, children, household care |
| `education_careers` | Education & Careers | new | schools, courses, books, exams, study abroad, recruitment |
| `travel_hospitality` | Travel & Hospitality | new | destinations, airlines, hotels, tourism, travel services |
| `automotive_mobility` | Automotive & Mobility | new | cars, motorcycles, EVs, transport, accessories, vehicle finance |
| `home_property_architecture` | Home, Property & Architecture | new | real estate, construction, interiors, home products, architecture |
| `society_news_law` | Society, News & Law | new | public affairs, local news, law, safety, transport policy, environment |

Why twelve:

- the current 310-segment DMP catalog is concentrated in business, entertainment, family, fitness, food/drink, hobbies, shopping/fashion, sports, technology, and travel;
- automotive, property/home, education, health, and public affairs are common advertising briefs that need distinct contextual homes;
- hobbies can map into sports, technology, entertainment, lifestyle, travel, automotive, or home according to the specific segment;
- these categories are broad enough to avoid publishing-style duplication and narrow enough to produce materially different recommendations.

### 3.3 Context is not personal audience truth

`family_parenting` means the page contains family/parenting editorial content. It must not assert that a visitor is pregnant, has a child, or has a particular health status.

Topic affinity:

- may affect relevance ranking;
- may explain why a page suits a brief;
- must not change or inflate canonical audience reach;
- must not be reported as measured demographics;
- must not imply that synthetic inventory metrics are live publisher facts.

## 4. Placement families and IDs

### 4.1 Five category families

Every canonical topic on both publishers should expose:

| Family | Purpose | ZNews contract | BaoMoi contract |
|---|---|---|---|
| `category_masthead` | top banner inside the category page | 1160x250 | 1160x280 |
| `category_background` | desktop page skin/background | explicit background creative contract | explicit background creative contract |
| `category_side_left` | left sliding desktop side ad | explicit left-side contract | explicit left-side contract |
| `category_side_right` | right sliding desktop side ad | explicit right-side contract | explicit right-side contract |
| `category_sidebar` | in-layout side banner | 300x250 | 300x250 |

The 300x250 sidebar is chosen because it matches all six existing ZNews `SidebarBox` records and the existing BaoMoi `Box1`. A future 300x600 family can be added as a separate revision after the first architecture is stable.

All five are desktop placements in NP-6. At mobile widths:

- the desktop background and side strips are not requested;
- the layout has no horizontal overflow;
- the top and sidebar behavior follows an explicit responsive rule or collapses;
- no desktop placement is relabelled as mobile inventory.

### 4.2 Stable ID convention

New IDs should be deterministic:

```text
Znews_<TopicCode>_Masthead
Znews_<TopicCode>_Background
Znews_<TopicCode>_SideLeft
Znews_<TopicCode>_SideRight
Znews_<TopicCode>_SidebarBox

BaoMoi_<TopicCode>_Masthead
BaoMoi_<TopicCode>_Background
BaoMoi_<TopicCode>_SideLeft
BaoMoi_<TopicCode>_SideRight
BaoMoi_<TopicCode>_SidebarBox
```

Examples:

```text
Znews_FamilyParenting_Masthead
Znews_FamilyParenting_Background
BaoMoi_FamilyParenting_Masthead
BaoMoi_FamilyParenting_Background
```

Existing IDs are preserved exactly. The importer maps them to canonical topic and family metadata without renaming them.

### 4.3 Comparison identity

Every category placement gets:

```json
{
  "topicId": "family_parenting",
  "placementFamily": "category_sidebar",
  "comparisonGroupId": "family_parenting:category_sidebar"
}
```

This lets the UI and ranker compare:

- ZNews Family & Parenting sidebar;
- BaoMoi Family & Parenting sidebar;

without pretending that the two publishers have identical performance or commercial availability.

## 5. Generic replicated-site architecture

### 5.1 Do not clone category HTML

Replace future category copies with:

```text
topic fixture JSON
       +
publisher category template
       +
publisher theme/layout CSS
       +
generic five-zone ad controller
```

Suggested source layout:

```text
test-site-fixtures/
  topics/
    business_finance.json
    health_wellness.json
    ...
  assets/
    business_finance/
    ...

znews_replicate/
  category.html
  category-template.js
  category-style.css

baomoi_replicate/
  category.html
  category-template.js
  category-style.css
```

Stable URLs can be exposed through static route files or Nginx rewrites:

```text
/category/business-finance.html
/category/family-parenting.html
```

The renderer resolves the topic fixture from a controlled route map. It must not accept an arbitrary path or arbitrary HTML from the query string.

### 5.2 Fixture content

AI-generated content should be generated once and committed as deterministic fixtures. It must not be generated at page request time.

Each topic fixture should include:

- page title and navigation label;
- one hero story;
- at least twelve supporting headlines;
- short summaries;
- local image asset references;
- alt text;
- topic keywords;
- publisher-specific ordering hints;
- a visible test-fixture marker in metadata, not necessarily in the reader-facing layout.

Validation rules:

- no copied publisher article text;
- no remote image hotlinks;
- no real-person defamation or fabricated current-event claims;
- no medical, legal, financial, or safety instruction presented as fact;
- no duplicate headline within a topic;
- no same hero image across unrelated topics;
- all files local and loadable;
- content is visually credible enough to test layout but explicitly classified `demo_fixture`.

### 5.3 Five-zone controller

One generic controller receives:

```json
{
  "publisher": "znews",
  "topicCode": "FamilyParenting",
  "zones": {
    "masthead": "Znews_FamilyParenting_Masthead",
    "background": "Znews_FamilyParenting_Background",
    "sideLeft": "Znews_FamilyParenting_SideLeft",
    "sideRight": "Znews_FamilyParenting_SideRight",
    "sidebar": "Znews_FamilyParenting_SidebarBox"
  }
}
```

It must:

- initialize each zone independently;
- request each placement ID once;
- track an impression only after a successful ad render;
- isolate timeout/failure/close behavior to one zone;
- prevent duplicate initialization on navigation or rerender;
- preserve publisher-specific styling;
- expose `data-zone`, `data-topic`, `data-family`, and rendered-state attributes for tests and screenshots.

The new BaoMoi category controller must not inherit the homepage rule that hides the masthead whenever a background is active. The category template must reserve independent geometry so all five requested families can be tested together.

## 6. Canonical catalog contract

The migration should be additive. Existing fields remain available while new consumers adopt the richer contract.

Proposed placement shape:

```json
{
  "id": "Znews_FamilyParenting_SidebarBox",
  "catalogVersion": "np6-2026-01",
  "recordRevision": 1,
  "lifecycle": {
    "status": "active",
    "effectiveFrom": "2026-08-01",
    "effectiveTo": null
  },
  "publisher": "ZNews",
  "siteId": "znews",
  "channel": "znews-family-parenting",
  "pageTemplate": "category",
  "topicId": "family_parenting",
  "placementFamily": "category_sidebar",
  "comparisonGroupId": "family_parenting:category_sidebar",
  "device": ["desktop"],
  "format": "banner",
  "size": "300x250",
  "creativeContractId": "display-box-300x250-v1",
  "renderer": {
    "templateId": "znews-category-v2",
    "renderZoneId": "Znews_FamilyParenting_SidebarBox",
    "previewSupported": true,
    "siteUrl": "https://znews-stg.pawgrammers.io.vn/category/family-parenting.html"
  },
  "audienceContext": {
    "taxonomyVersion": "placement-topics-v1",
    "primaryTopics": ["family_parenting"],
    "secondaryTopics": ["health_wellness", "education_careers"],
    "keywordsVi": ["gia đình", "cha mẹ", "trẻ em", "chăm sóc"],
    "keywordsEn": ["family", "parenting", "children", "household care"],
    "dmpCategoryAffinities": ["Family and relationships"],
    "dmpSegmentAffinities": [],
    "intentSignals": ["family_purchase", "household_care"],
    "exclusions": ["infer_personal_parental_status"],
    "confidence": 0.9
  },
  "metrics": {
    "reach": 120000,
    "vi": 62,
    "ctr": 0.45,
    "cpm": 25000,
    "metricSource": "synthetic_inventory_v3",
    "inventoryTier": "standard-box"
  },
  "provenance": {
    "classification": "demo_fixture",
    "sourceType": "live_layout_observation_plus_synthetic_fixture",
    "evidenceIds": ["np6-category-census-2026-07-25"],
    "verifiedAt": "2026-07-25"
  }
}
```

### 6.1 Explicit creative contracts

Stop using placement ID substrings and `size: "skin"` as the primary format contract.

Define reusable creative contracts:

- `znews-category-masthead-1160x250-v1`;
- `baomoi-category-masthead-1160x280-v1`;
- `category-background-v1`;
- `category-side-left-v1`;
- `category-side-right-v1`;
- `display-box-300x250-v1`;
- existing ZingMP3 and homepage contracts.

Each contract contains:

- exact source width/height;
- displayed geometry;
- media type;
- aspect ratio;
- safe area;
- crop behavior;
- maximum bytes;
- supported MIME types;
- renderer key;
- AI-generation format key.

`format_spec_for_zone()` should resolve `creativeContractId`. Legacy size/ID inference remains only as a compatibility fallback for the original 35 records.

### 6.2 Metric policy

New metrics remain demo data:

- use `synthetic_inventory_v3`;
- derive values deterministically by publisher and placement family;
- do not invent topic superiority without evidence;
- keep values within channel reach;
- show the synthetic label in setup/review/report surfaces;
- never use topic affinity to modify canonical audience reach.

Using equal family-level metric profiles within a publisher makes topic relevance—not invented performance—the primary difference between category records.

## 7. Catalog versioning and migration

### 7.1 Compatibility requirements

The original 35 records form a locked baseline fixture. NP-6 tests should snapshot:

- ID;
- channel;
- format;
- size;
- metrics;
- site ID/URL;
- existing renderer mapping.

NP-6 may enrich these records, but must not silently change their historical meaning.

### 7.2 Version behavior

Add to the top-level catalog:

```json
{
  "catalogVersion": "np6-2026-01",
  "taxonomyVersion": "placement-topics-v1",
  "revision": 1,
  "publishedAt": "...",
  "previousVersion": "legacy-35"
}
```

At order creation, store:

- `placementCatalogVersion`;
- `placementSnapshots[]` containing the fields necessary for price, format, topic, provenance, and renderer meaning;
- the existing placement IDs.

Legacy campaigns without snapshots resolve through a documented `legacy-35` compatibility view and receive no destructive rewrite.

### 7.3 Import

Replace a destructive reseed as the normal delivery mechanism with:

1. schema validation;
2. dry-run diff;
3. unique-ID and comparison-group validation;
4. additive upsert by catalog version;
5. publish/activate transaction;
6. previous-version retention.

Importing the same package twice must produce no data change.

Rollback activates the previous catalog version. It does not delete campaign history or new fixture files.

## 8. Topic-aware recommendation architecture

### 8.1 Input

Build a normalized `placement_query` from approved campaign data:

```json
{
  "briefText": "launch family health insurance for young parents",
  "brandCategory": "insurance",
  "objective": "consideration",
  "kpi": "qualified traffic",
  "selectedSegmentIds": ["..."],
  "selectedDmpCategories": ["Family and relationships"],
  "normalizedTopics": ["family_parenting", "health_wellness"],
  "negativeTopics": [],
  "dateRange": {"start": "...", "end": "..."},
  "device": ["desktop"]
}
```

Only normalized campaign context and public catalog metadata enter placement retrieval. Do not send account identity, contact information, raw ownership records, or unrelated conversation history.

### 8.2 Hard filters first

No model can override:

- active lifecycle/effective dates;
- image-only NP-6 media support;
- requested device;
- publisher/site enablement;
- date-range conflict availability;
- renderer availability when preview is required;
- creative contract compatibility during final ranking;
- explicit exclusion or safety rules.

### 8.3 Placement RAG

Use the existing multilingual dense/sparse embedding infrastructure as a pattern, but create a separate placement collection and configuration:

```text
audience RAG collection       unchanged
placement-context collection new, keyed by catalog version
```

Placement document text:

```text
publisher | page topic | primary topics | secondary topics |
Vietnamese keywords | English keywords | DMP affinities |
placement family | objective suitability | provenance
```

Index fingerprint includes:

- catalog version;
- taxonomy version;
- placement IDs;
- contextual metadata;
- embedding model version.

Retrieval:

1. exact canonical-topic lookup;
2. sparse/BM25 retrieval;
3. dense multilingual retrieval;
4. reciprocal-rank fusion;
5. deterministic topic/DMP overlap score;
6. top 24 safe candidates.

If Qdrant or embeddings are unavailable, fall back to canonical topic and keyword overlap. Placement setup must remain usable.

### 8.4 Deterministic score

Normalize every component to 0–1 before blending:

```text
preliminary score =
  0.50 contextual relevance
  0.30 current objective/performance score
  0.10 provenance/evidence confidence
  0.10 comparison/diversity utility
```

After creative analysis:

```text
final score =
  0.40 contextual relevance
  0.25 objective/performance
  0.25 creative compatibility
  0.10 comparison/diversity utility
```

Weights are initial hypotheses and must be tuned on the golden set. They are not production facts.

### 8.5 Diversity and comparison

After scoring:

- maximum two results from one `comparisonGroupId`;
- maximum four results from one publisher in a six-result shortlist when another relevant publisher is available;
- if ZNews and BaoMoi placements in the same comparison group are within an approved score margin, retain the pair;
- do not add a low-relevance publisher merely to force symmetry.

The UI can show:

```text
Family & Parenting · Sidebar
  ZNews  — context 0.91, current demo metrics...
  BaoMoi — context 0.89, current demo metrics...
```

### 8.6 Explanations

Reasons are assembled from scored evidence, not free-form invention:

> Recommended ZNews Family & Parenting sidebar because the brief maps to family and household-care context, the selected DMP category overlaps this page topic, the 300x250 creative contract is supported, and the placement is available for the requested dates. Reach and CPM shown are synthetic demo inventory metrics.

Every reason should expose:

- matched brief topic;
- matched DMP category/segment when applicable;
- objective/performance component;
- publisher/placement family;
- creative compatibility status;
- availability freshness;
- metric/provenance label.

## 9. GPT-5.4-nano reranking experiment

OpenAI’s current official model page describes `gpt-5.4-nano` as intended for simple high-volume tasks including classification, extraction, and ranking, with Structured Outputs support:

`https://developers.openai.com/api/docs/models/gpt-5.4-nano`

That makes it a valid experiment candidate. It should not become the production ranker merely because it is inexpensive.

### 9.1 Separate placement reranker

Do not reuse or alter the audience RAG reranker configuration during NP-6.

Add placement-specific configuration:

```text
PLACEMENT_RERANK_MODE=off|greennode|openai
PLACEMENT_RERANK_MODEL=gpt-5.4-nano
PLACEMENT_RERANK_TIMEOUT_SECONDS=...
PLACEMENT_RERANK_TOP_N=...
```

This component is not the conversation engine and does not change GreenNode/OpenAI campaign-engine model locking.

### 9.2 Candidate-only structured request

Input:

- normalized brief;
- at most 16 already-safe placement documents;
- placement IDs;
- contextual fields;
- no raw reach arithmetic instructions;
- no account/user identity.

Structured output:

```json
{
  "ranking": [
    {
      "placementId": "...",
      "contextScore": 0.0,
      "matchedTopics": ["..."],
      "reasonCodes": ["primary_topic_match", "dmp_category_match"]
    }
  ]
}
```

Validation:

- every returned ID must be in the candidate set;
- no duplicates;
- scores bounded 0–1;
- omitted candidates retain deterministic order;
- model output affects contextual relevance only;
- hard filters and creative compatibility are reapplied after reranking.

Start with `reasoning.effort: none` as the latency baseline and compare `low`. Use `store: false` if supported by the existing OpenAI request boundary.

### 9.3 Experiment arms

| Arm | Retrieval | Rerank |
|---|---|---|
| A | deterministic topic + hybrid RRF | none |
| B | deterministic topic + hybrid RRF | existing GreenNode Qwen reranker, only if its endpoint is made operational |
| C | deterministic topic + hybrid RRF | `gpt-5.4-nano` Structured Outputs |

The existing GreenNode probe currently reports no working rerank endpoint. That arm is optional until an official endpoint is available.

### 9.4 Promotion gate

Proposed minimums:

- zero hard-filter violations;
- zero invented placement IDs;
- NDCG@6 at least 0.85;
- expected-topic Recall@6 at least 0.90;
- publisher-comparison coverage at least 0.80 for eligible same-topic cases;
- paraphrase Jaccard@6 at least 0.80;
- reason-code faithfulness at least 0.95;
- p95 latency and per-request cost within the owner-approved budget;
- statistically meaningful improvement over Arm A on the same labeled set.

If nano does not beat deterministic retrieval materially, keep it off. The placement pipeline still gains topic awareness without an LLM reranker.

Using the winning reranker for audience segments is a later separately gated change. It must not modify audience reach estimation or the independent engine/model-locking contract.

## 10. Setup and UI approach

### 10.1 Avoid a 140-card flat list

`ZoneSelectionPhase.jsx` currently renders recommended cards and a flat “other zones” list. With 140 records, add generic grouping:

```text
Publisher
  Topic
    Placement family
```

Controls:

- topic filter;
- publisher filter;
- placement-family filter;
- format/device filter;
- “compare same topic across publishers” toggle;
- synthetic/demo provenance badge;
- catalog-version/freshness details.

Recommended results remain six by default.

### 10.2 Comparison card

A comparison group should display:

- ZNews and BaoMoi side by side;
- topic match reason;
- physical family and creative contract;
- synthetic reach/CPM/VI/CTR;
- availability/conflict state;
- preview link;
- compatible creative state.

Selecting one publisher must not implicitly select the other.

### 10.3 Creative planning

Use `creativeContractId` to deduplicate formats.

Keep:

- the 20-output daily image quota unchanged;
- the current Autopilot maximum generated-assets cap unchanged initially;
- explicit operator review and creative-recovery flow;
- upload support.

A large number of placements does not mean generating one image per placement. One exact-format asset can cover many topic/publisher records when the creative contract permits it.

## 11. Test strategy

### 11.1 Catalog and migration tests

Automated checks:

- original 35 baseline snapshot unchanged;
- final count 140 for the approved twelve-topic plus property plan;
- 105 new IDs, all unique;
- every active new record has lifecycle, version, topic, family, comparison group, device, contract, renderer, provenance, and metric source;
- exactly five placement families for every publisher/topic pair;
- exactly two publishers in every ZNews/BaoMoi category comparison group; property-specific placements have no forced comparison group;
- excluded redundant topics absent;
- no video/audio format in new records;
- metrics bounded by channel reach and labelled `synthetic_inventory_v3`;
- import dry-run is human-readable;
- second import is a no-op;
- previous catalog version remains resolvable;
- legacy campaigns resolve the original 35 meanings;
- new orders store catalog version and snapshots.

### 11.2 Renderer contract tests

Run the same test suite against 24 pages:

```text
12 topics × 2 publishers
```

For each page:

- fixture schema valid;
- title, hero, at least twelve stories, and local images render;
- five expected zone IDs exist once;
- each placement makes one `/api/ads/check` request;
- successful render produces the correct creative;
- no-ad response collapses only that zone;
- one timeout does not block the other four;
- closing left does not close right/background/sidebar/masthead;
- impression fires once after render;
- click fires once with the same placement ID;
- navigation between topics does not leave stale zone IDs or ads;
- no copied/remote editorial content is required.

### 11.3 Layout and styling tests

Playwright viewports:

- 1440x900;
- 1280x800;
- 1024x768;
- 390x844.

Assertions:

- masthead stays inside the content frame;
- background click area does not cover content;
- left and right side ads do not overlap the page;
- sidebar does not cover headlines;
- all five desktop zones can render concurrently;
- z-index order is deterministic;
- one zone’s close/collapse does not shift another into an invalid position;
- desktop-only zones are not requested on mobile;
- mobile has zero horizontal overflow;
- page remains readable when every zone is empty;
- page remains readable when every zone is filled;
- screenshots exist for all-filled, all-empty, and one-failure states.

Use screenshot baselines by template/topic representative, not 24 full-page pixel baselines. DOM/geometry assertions run across all 24 pages; visual baselines cover:

- one existing topic;
- one new family topic;
- one dense business topic;
- one mobile page;
- both publishers.

### 11.4 Backend and inventory tests

- `/api/zones` returns catalog version and all active records;
- filters by publisher/topic/family/device/status work;
- single-placement detail includes context/provenance/contract;
- local/public site URL mapping supports generic category routes;
- conflict checks recognize every new placement ID;
- `/api/ads/check` selects an explicitly assigned creative before size/format fallback;
- cross-topic campaigns never serve into another topic’s placement ID;
- unknown/retired placement behavior is explicit;
- analytics event keeps the exact new placement ID;
- no raw Mongo access is exposed to an LLM.

### 11.5 Guided setup tests

For representative briefs:

- correct topic families appear in top six;
- irrelevant topics do not appear solely because their synthetic reach is larger;
- same-topic ZNews/BaoMoi comparison appears when both are eligible;
- conflicted placement is excluded;
- selected placement survives refresh/resume;
- grouping/filtering works with 140 records;
- creative upload/generation maps by explicit contract;
- invalid creative produces a warning/recovery path;
- order creation preserves confirmation and idempotency;
- result page preview opens the correct category URL and zone.

### 11.6 Autopilot tests

- preliminary intent is creative-agnostic but topic-aware;
- placement artifact records query topics, catalog version, score components, and evidence;
- review shortlist remains operator-editable;
- creative-format plan deduplicates explicit contracts;
- side strips no longer collapse to the background format;
- final rank reapplies context, availability, and creative compatibility;
- no-compatible-creative and no-availability recovery remain separate;
- reranker error/timeout/malformed output falls back deterministically;
- conversation model provenance remains unchanged;
- review/confirmation gates remain unchanged;
- image quota remains 20 outputs per actor/day.

### 11.7 Recommendation golden set

Create at least 72 labeled briefs:

- 4 single-topic briefs per canonical topic: 48;
- 12 multi-topic briefs;
- 6 ambiguous briefs;
- 6 negative/exclusion briefs.

Cover:

- all four campaign objectives;
- upload and AI-generation flows;
- exact, same-ratio, and incompatible creatives;
- date conflicts;
- paraphrases in Vietnamese and English;
- briefs that should compare publishers;
- briefs where one publisher should not be forced into the result.

Store expected:

- relevant topic IDs;
- acceptable secondary topics;
- prohibited topics;
- expected comparison groups;
- reason codes;
- hard constraints.

Report each experiment arm’s:

- Recall@6;
- Precision@6;
- NDCG@6;
- MRR;
- publisher diversity;
- paired comparison coverage;
- constraint violations;
- paraphrase stability;
- latency;
- token/cost;
- fallback/error rate.

### 11.8 Data-quality tests

- every topic fixture has valid UTF-8;
- no missing local asset;
- no duplicate content IDs;
- no external editorial image URL;
- basic spelling/length rules;
- alt text present;
- sensitive topics carry safe fixture language;
- each page’s content matches its canonical topic;
- a reviewer approves a contact sheet for all 24 pages.

### 11.9 Regression suites

Run focused suites first, then maintained full suites:

- backend unit/integration tests;
- Agent unit/integration tests;
- frontend tests and production build;
- ZNews/BaoMoi replica tests;
- Guided campaign smoke;
- Autopilot full run;
- FAQ catalog and date-specific availability;
- report evidence;
- read-only Zalo placement discovery/comparison;
- existing OpenAI and GreenNode engine-purity tests;
- ownership, confirmation, security, quota, audience-reach, and order-idempotency tests.

## 12. Manual acceptance matrix

For at least six briefs—family, business, sports, technology, travel, and automotive—capture:

1. approved brief and selected DMP segments;
2. topic-aware recommendation screen;
3. ZNews/BaoMoi comparison;
4. selection and creative assignment;
5. all relevant ad zones on the replicated sites;
6. empty and conflict behavior;
7. confirmation and created order;
8. result/report evidence;
9. catalog version and provenance labels.

For the family case, verify the reason uses contextual wording and does not claim the visitor is a parent.

## 13. Delivery slices

### Slice 0 — Freeze decisions and baselines

- approve twelve topics;
- approve five families;
- export the exact production 35-record baseline;
- approve synthetic metric policy;
- approve `gpt-5.4-nano` as an experiment, not a committed production dependency.

Exit: signed decision record and baseline hash.

### Slice 1 — Schema, contracts, and version compatibility

- declare currently dropped fields;
- add catalog/taxonomy versioning;
- add audience context, provenance, renderer, and creative contracts;
- add legacy resolution and order snapshots;
- add idempotent dry-run import.

Exit: original 35 round-trip with no behavioral change.

### Slice 2 — Two-topic vertical slice

Implement:

- `business_finance`: existing ZNews + new BaoMoi category;
- `family_parenting`: new ZNews + new BaoMoi category;
- five families per publisher;
- generic template/controller;
- explicit creative contracts;
- topic-aware deterministic retrieval.

This adds 16 records:

- one new masthead for existing ZNews Business;
- five BaoMoi Business records;
- five ZNews Family records;
- five BaoMoi Family records.

Exit: both publishers complete one existing and one new topic end to end.

### Slice 3 — Recommendation evaluation

- build placement-context index;
- add deterministic contextual score;
- build 72-case golden set;
- run no-rerank baseline;
- run GreenNode arm if endpoint exists;
- run `gpt-5.4-nano` arm;
- choose `off`, `greennode`, or `openai` only from measured results.

Exit: evaluation report and promotion decision.

### Slice 4 — Complete twelve-topic expansion

- add the remaining topic fixtures;
- add remaining ZNews category mastheads/new categories;
- add remaining BaoMoi categories;
- validate final 140-record catalog;
- generate contact sheet and catalog diff.

Exit: 24 category pages and 120 category placements work.

### Slice 5 — Guided, Autopilot, UI, and generic consumers

- grouped zone UI and comparison view;
- explicit creative-contract planning;
- context-aware Guided and Autopilot ranking;
- FAQ/catalog exposure with provenance;
- report/result/preview compatibility;
- AdsPilot display.

Exit: both campaign modes complete a new topic campaign.

### Slice 6 — Full regression and production

- full automated suites;
- manual acceptance matrix;
- production backup;
- deploy backend, Agent, frontend, and two replica sites;
- activate NP-6 catalog version;
- verify version/readiness;
- run production Guided, Autopilot, FAQ, preview, report, and read-only Zalo checks.

Exit: evidence bundle and rollback-ready production release.

## 14. Rollback

Rollback order:

1. disable placement reranker;
2. activate previous catalog version;
3. keep new records inactive rather than delete them;
4. restore previous Agent/backend/frontend/test-site artifacts from backups;
5. verify original 35 catalog and existing campaigns;
6. leave historical snapshots and event logs intact.

The deterministic ranker must always work with the previous catalog. A reranker failure alone must never require a deployment rollback.

## 15. Protected contracts

NP-6 must not alter:

- NP-7 video behavior or add video assets/quotas;
- independent OpenAI and GreenNode campaign engines;
- immutable conversation model selection;
- the 20-output GPT Image 2 daily quota;
- canonical audience reach estimation;
- FAQ/action authorization;
- report evidence contracts;
- account/campaign ownership;
- confirmation checkpoints;
- order idempotency;
- Zalo as a channel adapter over server-owned state.

The placement reranker is a new bounded relevance component. It does not select the campaign engine or conversation model.

## 16. Approval requested

Before implementation, approve:

1. the twelve canonical topics;
2. the five category placement families;
3. final target of 105 new records / 140 total;
4. desktop-first category inventory and explicit mobile collapse;
5. committed AI-generated fixture content and local images;
6. `synthetic_inventory_v3` family-level metric policy;
7. two-topic vertical slice before bulk expansion;
8. `gpt-5.4-nano` as an offline/feature-flagged experiment only;
9. proposed recommendation-eval gates;
10. catalog versioning and historical snapshot migration.
