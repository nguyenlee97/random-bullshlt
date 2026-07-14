# Golden set v1 + v2 — DRAFT (machine-authored, pending human review)

These 40 briefs (`brief_001.json` … `brief_040.json`) are **draft, machine-authored labels** and must NOT be treated as shipped ground truth. Per `docs/production-plan/07-eval-framework.md` §1 step 4, a mandatory human review pass is required before use: the labeler browses the segment catalog (`docs/database-info/audience_library.json`) to confirm each pick, and a second pass on a different day sanity-checks **100% of `must_exclude`** and **30% of the rest**, recording labeler notes. All audience `_id` values reference real segments in the catalog (verified by `validate.py` in this directory); `zones` labels are intentionally left empty for v1 and will be filled in P2.

## Achieved stratification (validated by `validate.py`)

| Cell | Requirement | Achieved |
|---|---|---|
| Objective: awareness | ≥ 8 | 11 |
| Objective: consideration | ≥ 8 | 10 |
| Objective: conversion | ≥ 8 | 12 |
| Objective: retention | ≥ 4 | 7 |
| Language: vi | ≥ 28 | 30 |
| Language: en | ≥ 8 | 10 |
| Special: ambiguous_notes | ≥ 3 | 3 |
| Special: kpi_budget_conflict | ≥ 3 | 3 (each carries `kpi_unrealistic_for_budget` in `expected_warnings`) |
| Special: tiny_budget (≤ 50 triệu) | ≥ 3 | 3 |
| Special: empty_notes | ≥ 3 | 3 |
| Special: adversarial (prompt injection in notes; labels reflect legitimate audience) | ≥ 3 | 3 |
| Special: long_rambling_notes (200+ words, buried requirements) | ≥ 3 | 3 |
| **Total briefs** | 40 | **40** |

---

## Golden set v2 — DRAFT (machine-authored, pending human review)

`brief_041.json` … `brief_080.json` follow `AUTHORING-GUIDE.md` and extend the schema with
`"schema_version": 2` and an optional `labels.targeting` block. Like v1, these are
**machine-authored draft labels** — not shipped ground truth. The same mandatory human review
(100% of `must_exclude`, 30% of the rest, second pass on a different day) still applies before
these are trusted for grading. `labeler_note` on every brief documents non-obvious calls for the
reviewer to check first.

### Step 0 — catalog re-fetch

The live DMP catalog was re-fetched on 2026-07-04: **310 segments** (12 Behavior + 298 Interest),
replacing the 71-segment subset v1 was labeled against. `catalog_full.json` and
`targeting_options.json` in this directory are the refreshed dumps; `fetch_catalog.py` documents
the reproducible fetch. Confirmed: all 71 old-dump `_id`s are present in the new 310-item catalog
(a true subset relationship) — `validate.py` checks this on every run and would print a
human-review flag if that ever regresses, rather than silently patching v1 labels.

### v2 quota table (achieved, validated by `validate.py`)

| Cell | Requirement | Achieved | Tag |
|---|---|---|---|
| Deep-catalog coverage (`must_include` only uses `_id`s absent from the old 71-dump) | ≥ 15 | 15 | `full_catalog_only` |
| Targeting-labeled (full `targeting` block; ≥ 3 with notes conflicting with naive defaults) | ≥ 12 | 12 (5 conflicting) | `targeting_labeled` |
| Multi-segment tension (stated primary vs. secondary audience) | ≥ 5 | 5 | `primary_secondary` |
| Near-miss traps (tempting-but-wrong segment in `must_exclude`) | ≥ 5 | 5 | `near_miss` |
| Adversarial v2 (injection inside `brand`/`kpi` fields, not just `notes`) | ≥ 3 | 3 | `adversarial` |
| **Total v2 briefs** | 40 | **40** | |

### Combined stratification (brief_001–080, validated by `validate.py`)

| Cell | Requirement | Achieved |
|---|---|---|
| Objective: awareness | ≥ 8 | 22 |
| Objective: consideration | ≥ 8 | 21 |
| Objective: conversion | ≥ 8 | 26 |
| Objective: retention | ≥ 4 | 11 |
| Language: vi | ≥ 28 | 62 |
| Language: en | ≥ 8 | 18 |
| Special: adversarial (v1 + v2 combined; tag is shared across both eras) | ≥ 3 | 6 |
| (all other v1 special cells — see table above) | ≥ 3 each | unchanged |
| **Total briefs** | 80 | **80** |

### Step 4 — validation & handoff status

1. ✅ `validate.py` is schema-version aware, checks every `_id` against `catalog_full.json`
   (not the old 71-dump), checks every `targeting` value against `targeting_options.json`,
   prints the v2 quota table, and passes for all 80 briefs.
2. ✅ The local agent evaluation is operational. The final 100-request grounded soak completed
   without errors, fallback, exclusions, unknown IDs, or source-citation violations; see
   `../reports/rag-soak-100-grounded.json`.
3. ✅ The 12 targeting-labeled cases have a dedicated gate. The structured critic candidate
   reached 95.8% expected-value recall with zero forbidden or out-of-catalog values and p95
   3.99 seconds; see `../reports/targeting-critic-v2.json`.
4. ✅ Run `python eval/golden_set/build_v2_review_packet.py` to refresh
   `V2-HUMAN-REVIEW-PACKET.md`. It preserves an existing `v2_review_status.json` so reviewer
   decisions are never overwritten.
5. ⛔ No labels in `brief_041.json`–`brief_080.json` are human-approved yet. A reviewer must
   fill `v2_review_status.json`; `python eval/golden_set/check_v2_review.py` intentionally
   fails until all 40 cases have a reviewer, timestamp, and `approved` or `edited` status.
