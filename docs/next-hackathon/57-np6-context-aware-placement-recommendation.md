# NP-6 Context-Aware Placement Recommendation

Date: 2026-07-26  
Status: implemented, deployed, and production verified  
Production Agent: `2026-07-26.3`  
Production catalog: `np6-2026-03` / `placement-topics-v2`

## Outcome

Ad-zone recommendation now treats documented brief/audience relevance as the
retrieval stage. Price, availability, reach, viewability, CTR, campaign
objective, KPI, creative compatibility, and the selected strategy remain
important, but they optimize inside the context-matching tier instead of
allowing unrelated high-performance inventory to displace it.

If the brief and audience contain no usable topic signal, recommendation
explicitly uses `performance_fallback` and preserves the previous behavior.

## Production gap found

Before this change, 247 of 258 production placements had topic/audience
metadata, but the ranking algorithm used relevance only as an additive bonus of
at most 25 points. A generic homepage masthead could score about 69 performance
points and outrank a family category placement even when the campaign was
explicitly about mothers, babies, and parents.

Controlled pre-change family result:

| Rank | Placement | Topic |
|---:|---|---|
| 1 | `ZingNews_Masthead` | none |
| 2 | `BaoMoi_Masthead` | none |
| 3 | `ZingNews_Masthead_Inline_1` | none |
| 4 | `BaoMoi_Background` | none |
| 5 | `BaoMoi_FamilyParenting_Masthead` | `family_parenting` |
| 6 | `Znews_FamilyParenting_Masthead` | `family_parenting` |

Autopilot then had a second issue: its reach-first and quality-first strategy
sorts could overwrite the contextual order.

## Metadata completeness

All 250 active placements now have:

- `topicId`;
- `audienceContext.primaryTopics`;
- Vietnamese and English topic keywords;
- DMP category, subcategory, and segment affinities where available;
- confidence and provenance;
- publisher, page template, placement family, device, creative contract, and
  catalog revision metadata.

The eleven previously unclassified active legacy units were enriched:

- broad ZNews and BaoMoi homepage inventory uses
  `society_news_law` with `contextScope = broad_news_homepage` and reduced
  confidence `0.55`, so it remains fallback inventory rather than pretending
  to be a specialist category page;
- `ZingMP3_Masthead` uses `music_live_events` with
  `contextScope = publisher_vertical`.

The 35 legacy IDs and their original inventory metrics remain unchanged.

## Ranking contract

1. Build an explainable query from approved brief fields and selected DMP
   category/subcategory/segment labels.
2. Score catalog-authored topic, keyword, category, subcategory, and segment
   evidence.
3. Enter `audience_context` mode when at least one placement reaches the
   deterministic relevance threshold `0.15`.
4. Put context matches ahead of non-matches.
5. Within each tier, use the existing objective/performance/KPI/creative score.
6. Remove booked placements using the existing availability contract.
7. Apply reach-first or quality-first strategy only inside the context tier.
8. Allow the optional default-off `gpt-5.4-nano` reranker to reorder only the
   bounded known candidate set; it cannot move a non-match above a deterministic
   match.
9. If no match reaches the threshold, use `performance_fallback`.

Each result now exposes:

- `ranking_mode`;
- `recommendation_basis.mode`;
- `recommendation_basis.context_match`;
- the relevance threshold and approved brief source fields;
- matched topics, keywords, DMP categories, subcategories, and segments;
- performance, KPI, creative, and topic score components;
- optional reranker evidence.

## Guided setup UI

Recommended cards now show:

- a human-readable Vietnamese topic label for all 25 taxonomy topics;
- `Khớp nội dung brief/audience` for context-driven recommendations;
- relevance percentage and up to three matched evidence labels;
- `Xếp hạng theo hiệu suất dự phòng` when no usable context exists;
- the existing reach, viewability, CTR, CPM, conflict, publisher-comparison,
  creative, and preview information.

## Production evidence

The same controlled family brief after deployment returns:

| Rank | Placement | Topic | Mode | Relevance |
|---:|---|---|---|---:|
| 1 | `DiCungCon_ContentBridge_Mobile` | `family_parenting` | `audience_context` | 0.46 |
| 2 | `DiCungCon_ContentBridge_Desktop` | `family_parenting` | `audience_context` | 0.46 |
| 3 | `DiCungCon_SidebarRail_Desktop` | `family_parenting` | `audience_context` | 0.46 |
| 4 | `BaoMoi_FamilyParenting_Masthead` | `family_parenting` | `audience_context` | 0.45 |
| 5 | `Znews_FamilyParenting_Masthead` | `family_parenting` | `audience_context` | 0.45 |
| 6 | `BaoMoi_FamilyParenting_Background` | `family_parenting` | `audience_context` | 0.45 |

Production catalog audit:

- 258 total placements;
- 250 active placements;
- 250/250 active placements enriched;
- 23 active topics;
- 35 legacy IDs preserved;
- catalog migration `np6-2026-02` → `np6-2026-03`;
- migration snapshot recorded in `zone_catalog_revisions`;
- pre-change archive:
  `/var/backups/np6-2026-07-26.3/adspilot-before.archive.gz`.

Production recommendation eval:

- 23/23 expected top topics;
- 100% full-ranking accuracy;
- every case used `audience_context`;
- evaluated against `https://api.pawgrammers.io.vn`;
- all 258 placements carried topic metadata after migration.

Production health:

- Agent `2026-07-26.3`;
- feature `np6-context-first-zone-ranking`;
- Agent status `ok`;
- readiness `ready`;
- MongoDB, backend, creative worker, Autopilot worker, Zalo worker, and Zalo
  OpenAI checks all ready;
- backend database connected;
- production frontend and all referenced hashed assets returned HTTP 200;
- browser render completed with no console errors.

## Automated verification

- backend maintained suite: 44/44 passed;
- Agent placement/Autopilot slice: 63/63 passed;
- focused placement tests: 12/12 passed;
- agent frontend: 107/107 passed;
- frontend production build passed;
- repository full-ranking evaluation: 23/23 passed;
- production full-ranking evaluation: 23/23 passed;
- catalog migration dry-run and activation hashes matched.

## Protected contracts

This change does not alter:

- NP-7 video;
- independent OpenAI/GreenNode engines;
- model locking;
- image quota;
- canonical audience reach;
- FAQ/action coordination;
- report evidence;
- ownership;
- creative confirmation;
- order idempotency.

