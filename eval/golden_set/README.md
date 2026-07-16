# Golden set v1 + v2 — review status

The legacy 40 briefs (`brief_001.json` … `brief_040.json`) were reviewed and
corrected in the earlier human-directed label pass recorded in `LABEL-REVIEW.md`.
They predate the per-case status ledger used by v2. All audience `_id` values
reference real segments in the catalog (verified by `validate.py`); `zones`
labels remain intentionally empty for v1.

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

## Golden set v2 — HUMAN REVIEW COMPLETE (2026-07-16)

`brief_041.json` … `brief_080.json` follow `AUTHORING-GUIDE.md` and extend the schema with
`"schema_version": 2` and an optional `labels.targeting` block. An independent AI
audit reviewed all labels, and the project owner accepted its recommendations on
2026-07-16. The accepted operations were applied to the source briefs: 12 cases
were approved unchanged, 28 were marked edited, and 6 of those edited cases retain
an explicit `catalog_gap` instead of an invented substitute. The human-owned status
ledger is `v2_review_status.json`.

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
| Multi-segment tension (stated primary vs. secondary audience) | ≥ 5 | 6 | `primary_secondary` |
| Near-miss traps (tempting-but-wrong segment in `must_exclude`) | ≥ 5 | 6 | `near_miss` |
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
5. ✅ Human review is recorded for all 40 v2 cases. `python
   eval/golden_set/check_v2_review.py` passes only when every case has a reviewer,
   timestamp, and `approved` or `edited` status.
6. ✅ Optional `acceptable` and `must_exclude` buckets may be empty after human
   review. This prevents demographic proxies or unrelated labels from being added
   only to meet a per-brief lower bound; aggregate near-miss/adversarial quotas
   still preserve exclusion coverage.
