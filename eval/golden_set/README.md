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
2. ⛔ **Blocked in this environment**: `python eval/run_eval.py --no-judge --subset
   tag=full_catalog_only` requires a running agent that itself calls the live backend
   (`api.pawgrammers.io.vn`) and the LLM (`maas-llm-aiplatform-hcm.api.vngcloud.vn`). The
   sandbox this batch was authored in has network egress restricted to an allowlist that does
   not include those hosts (confirmed: direct `curl`/`httpx` to both return no route even
   though credentials in `agent/.env` are present and valid). `run_eval.py`'s own
   `fullLabel → _id` map was also still pointing at the old 71-item dump — fixed to read
   `catalog_full.json` so the run will work correctly once someone runs it in an environment
   with real network access. **Action needed from a human with agent access**: run the command
   above (and ideally the full `--subset tag=targeting_labeled` and `tag=near_miss` cells too)
   against a live agent before trusting these labels — a recall of 0.0 across the new briefs
   would flag a label bug, not necessarily an agent bug.
3. This README is updated; all v2 briefs are tagged for human review per the note above.
4. ⛔ No labels in `brief_041.json`–`brief_080.json` have been marked reviewed by this pass —
   that is explicitly the next human's job, not the authoring model's.
