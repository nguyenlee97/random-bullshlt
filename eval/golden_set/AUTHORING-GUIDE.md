# Golden Set Authoring Guide — for the executing model

> How to expand `eval/golden_set/` correctly. The v1 set (brief_001–040) was drafted against
> the **71-segment dump** in `docs/database-info/audience_library.json`. The live catalog has
> **310+ segments** — v2 briefs must be labeled against the FULL live catalog, and must start
> covering **targeting / advanced targeting**, which v1 does not touch.
> Read `docs/production-plan/07-eval-framework.md` §1–2 first. This guide operationalizes it.

---

## Step 0 — Fetch the full catalog (do this before writing any brief)

The 71-item JSON dump is a subset ⛔. Dump the real thing:

```python
# eval/golden_set/fetch_catalog.py  (write this, run it, commit the output)
import httpx, json
r = httpx.get("https://api.pawgrammers.io.vn/api/dmp/attributes", timeout=30)
items = r.json()          # inspect actual shape; may be {data: [...]} — adapt
json.dump(items, open("eval/golden_set/catalog_full.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(len(items))         # expect 310+
```

Also dump targeting options (for targeting labels):

```python
r = httpx.get("https://api.pawgrammers.io.vn/api/targeting/options", timeout=30)
json.dump(r.json(), open("eval/golden_set/targeting_options.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
```

Rules after fetching:
- ALL audience label `_id`s in new briefs must exist in `catalog_full.json`.
- Update `validate.py` to validate against `catalog_full.json` (keep it passing for
  brief_001–040 too — the 71 dump is a subset of the live catalog, so old IDs remain valid;
  if any old ID is missing from the live catalog, flag it for human review, don't silently edit).
- Explore the full catalog BEFORE labeling: print all categories + counts. The 310+ set has
  categories the 71-dump lacks — coverage quotas below depend on knowing what exists.

## Step 1 — Extended schema (v2)

Same as 07-eval-framework §1 plus an OPTIONAL `targeting` block (v1 briefs stay valid):

```json
{
  "id": "brief_041",
  "lang": "vi",
  "schema_version": 2,
  "brief": { "brand": "...", "objective": "conversion", "kpi": "...", "budget": 300,
             "startDate": "2026-09-01", "endDate": "2026-10-15", "notes": "..." },
  "labels": {
    "audience": { "must_include": ["<_id>"], "acceptable": ["<_id>"], "must_exclude": ["<_id>"] },
    "targeting": {
      "expected": { "geo": ["..."], "age": ["..."], "gender": ["..."] },
      "must_not_set": { "age": ["under-18"] },
      "note": "values MUST come from targeting_options.json — never invent option values"
    },
    "zones": { "expected_top": [], "forbidden": [] },
    "expected_warnings": []
  },
  "tags": ["vi", "conversion", "targeting_labeled"]
}
```

`targeting.expected` = what a correct auto-pick (`handle_targeting_autopick`) should choose
given the brief; `must_not_set` = choices that would be clear errors (e.g. targeting minors
for alcohol/gambling-adjacent brands ⛔ — these double as safety checks). Only label the
dimensions the notes actually imply; leave others out (unlabeled ≠ wrong).

## Step 2 — What to write (quotas for the next 40, brief_041–080)

| Cell | Count | Notes |
|---|---|---|
| Deep-catalog coverage | 15 | Briefs whose correct segments exist ONLY in the full catalog (not in the 71 dump) — this is the point of v2. Tag `full_catalog_only`. |
| Targeting-labeled | 12 | Full `targeting` block. Include ≥3 where notes conflict with defaults (e.g. "chỉ chạy HCM và Đà Nẵng", "chỉ nữ 25-34"). Tag `targeting_labeled`. |
| Multi-segment tension | 5 | Notes implying 2 audiences with different value (primary vs secondary) — tests ranking, not just retrieval. Tag `primary_secondary`. |
| Near-miss traps | 5 | A tempting-but-wrong segment exists (e.g. "Aviation (air travel)" vs actual aviation-industry B2B brief) → put it in `must_exclude`. Tag `near_miss`. |
| Adversarial v2 | 3 | Injection attempts INSIDE structured fields (brand name, kpi) not just notes. Tag `adversarial`. |

Keep the global stratification balance of 07 §1 (objectives ≥8/8/8/4 per 40, ≥70% vi).

## Step 3 — Labeling procedure (per brief, in order)

1. Write the brief first (brand, objective, budget, dates, notes) WITHOUT looking at the catalog
   — realistic briefs don't come pre-fitted to a taxonomy.
2. Search `catalog_full.json` for candidates: match on `name`, `context`, `category`,
   Vietnamese keyword variants. List every plausible segment.
3. Sort into: `must_include` (2–4; removing one would clearly hurt the campaign),
   `acceptable` (0–6 after human review), `must_exclude` (0–3 after human review;
   would be a visible mistake — brand-safety, demographic mismatch, or near-miss
   trap). A machine author may propose a negative for review, but the final bucket
   must be empty when the catalog contains no defensible actively-wrong segment.
   The same rule applies to acceptable alternatives: never add an unrelated label
   merely to fill the bucket. Never invent a demographic proxy or unrelated
   negative merely to satisfy a quota.
4. Targeting (if labeling): open `targeting_options.json`, pick exact option values implied
   by the notes. Copy strings verbatim.
5. Self-check: read the notes as if you were the advertiser — would you accept these labels?
   If a segment feels debatable, move it from `must_include` to `acceptable` (labels must be
   defensible, not exhaustive).
6. Write one sentence in a `"labeler_note"` field explaining any non-obvious call. Human
   review reads these first.

## Step 4 — Validation & handoff (mandatory, in order)

1. Extend `validate.py`: schema-version aware; every `_id` ∈ catalog_full; every targeting value
   ∈ targeting_options; quota table printed; ALL asserts pass for briefs 001–080.
2. Run the deterministic metrics only (`python eval/run_eval.py --no-judge --subset tag=full_catalog_only`)
   against a running agent — not to grade the agent, but to catch YOUR label bugs (a recall of
   0.0 across all new briefs usually means mislabeled IDs, not a broken agent).
3. Update `README.md` stratification table; mark new briefs `DRAFT — needs human review`.
4. ⛔ Never mark labels reviewed yourself. The human pass (07 §1 step 4) is the user's job.

## Known failure modes (from authoring v1 — don't repeat)

- Inventing `_id` values or copying `segmentId` (INT004) instead of `_id` — always `_id`.
- Labels fitted to what the agent currently recommends (label leakage) — label from the brief,
  never from agent output.
- must_exclude used for merely-irrelevant segments — reserve it for actively-wrong ones;
  irrelevant-but-harmless belongs nowhere.
- All-easy briefs. If the correct answer is obvious from the brand name alone, the brief tests
  nothing — the value is in notes that require reading comprehension.
- English briefs that are translations of a Vietnamese brief already in the set — near-duplicates
  inflate n without adding signal.
