# -*- coding: utf-8 -*-
"""
Validates the golden set (v1 brief_001-040 + v2 brief_041-080): schema keys,
real audience _ids (against the FULL 310-item catalog per AUTHORING-GUIDE.md
Step 0/4), targeting values (against targeting_options.json), and
stratification/quota counts for both the v1 grid and the v2 quota table.

Schema-version aware: briefs without "schema_version" (or with value 1) are
v1 and validated against the original (looser) bounds; briefs with
"schema_version": 2 get the v2 bounds plus optional `targeting` block checks.
"""
import glob
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_FULL = os.path.join(HERE, "catalog_full.json")
OLD_LIB = os.path.join(HERE, "..", "..", "docs", "database-info", "audience_library.json")
TARGETING_OPTIONS = os.path.join(HERE, "targeting_options.json")

with open(CATALOG_FULL, encoding="utf-8") as f:
    _catalog = json.load(f)
valid_ids = {s["_id"] for s in _catalog}

with open(OLD_LIB, encoding="utf-8") as f:
    _old_lib = json.load(f)
old_ids = {s["_id"] for s in _old_lib}

with open(TARGETING_OPTIONS, encoding="utf-8") as f:
    targeting_options = json.load(f)

# Flat, per-dimension set of valid values. `geo` is nested by region in the
# raw options file, so it gets flattened; everything else is already a flat list.
_targeting_valid_values = {}
for dim, val in targeting_options.items():
    if dim == "geo":
        flat = set()
        for region_cities in val.values():
            flat.update(region_cities)
        _targeting_valid_values[dim] = flat
    else:
        _targeting_valid_values[dim] = set(val)

VALID_OBJECTIVES = ("awareness", "consideration", "conversion", "retention")
VALID_LANGS = ("vi", "en")
V2_QUOTA_TAGS = ("full_catalog_only", "targeting_labeled", "primary_secondary", "near_miss", "adversarial")
V2_QUOTA_REQUIRED = {
    "full_catalog_only": 15,
    "targeting_labeled": 12,
    "primary_secondary": 5,
    "near_miss": 5,
    "adversarial": 3,
}

files = sorted(glob.glob(os.path.join(HERE, "brief_*.json")))
assert len(files) == 80, f"expected 80 brief files (v1 001-040 + v2 041-080), found {len(files)}"

obj_c, lang_c, tag_c, v2_quota_c = Counter(), Counter(), Counter(), Counter()
errors = []
old_id_missing_from_full = set()


def _check_targeting_block(name, targeting):
    """Validate an (optional) v2 `targeting` label block."""
    assert isinstance(targeting, dict), f"{name}: targeting must be an object"
    for section in ("expected", "must_not_set"):
        if section not in targeting:
            continue
        block = targeting[section]
        assert isinstance(block, dict), f"{name}: targeting.{section} must be an object"
        for dim, values in block.items():
            assert dim in targeting_options, f"{name}: targeting.{section} has unknown dimension {dim!r}"
            assert isinstance(values, list) and values, f"{name}: targeting.{section}.{dim} must be a non-empty list"
            valid_vals = _targeting_valid_values[dim]
            for v in values:
                if v not in valid_vals:
                    msg = f"{name}: targeting.{section}.{dim} value {v!r} not in targeting_options.json"
                    errors.append(msg)
    assert "expected" in targeting or "must_not_set" in targeting, (
        f"{name}: targeting block has neither 'expected' nor 'must_not_set'"
    )


for fp in files:
    name = os.path.basename(fp)
    with open(fp, encoding="utf-8") as f:
        d = json.load(f)

    for k in ("id", "lang", "brief", "labels", "tags"):
        assert k in d, f"{name}: missing key {k}"

    schema_version = d.get("schema_version", 1)
    assert schema_version in (1, 2), f"{name}: unsupported schema_version {schema_version}"
    is_v2 = schema_version == 2

    for k in ("brand", "objective", "kpi", "budget", "startDate", "endDate", "notes"):
        assert k in d["brief"], f"{name}: brief missing {k}"
    assert d["brief"]["objective"] in VALID_OBJECTIVES, f"{name}: bad objective"
    assert d["lang"] in VALID_LANGS, f"{name}: bad lang"
    assert isinstance(d["brief"]["budget"], int), f"{name}: budget not int"

    aud = d["labels"]["audience"]
    for k in ("must_include", "acceptable", "must_exclude"):
        assert k in aud, f"{name}: audience missing {k}"
        for _id in aud[k]:
            if _id not in valid_ids:
                errors.append(f"{name}: unknown _id {_id} in {k} (not in catalog_full.json)")

    assert 2 <= len(aud["must_include"]) <= 4, f"{name}: must_include size"
    if is_v2:
        # Optional alternatives must remain defensible after human review. A
        # lower bound encouraged unrelated labels solely to fill the bucket.
        assert 0 <= len(aud["acceptable"]) <= 6, f"{name}: acceptable size (v2 bound)"
    else:
        assert 2 <= len(aud["acceptable"]) <= 5, f"{name}: acceptable size (v1 bound)"
    # V2 human review may remove a fabricated negative when the catalog has no
    # defensible actively-wrong segment. Requiring one negative per brief caused
    # demographic proxies and quota-shaped labels. Aggregate near-miss and
    # adversarial quotas still provide exclusion coverage across the suite.
    if is_v2:
        assert 0 <= len(aud["must_exclude"]) <= 3, f"{name}: must_exclude size (v2 bound)"
    else:
        assert 1 <= len(aud["must_exclude"]) <= 3, f"{name}: must_exclude size"

    assert "zones" in d["labels"] and "expected_warnings" in d["labels"], f"{name}: missing zones/expected_warnings"
    assert d["labels"].get("labeler_note", "").strip(), f"{name}: missing/empty labeler_note"

    assert d["brief"]["objective"] in d["tags"] and d["lang"] in d["tags"], f"{name}: tags missing objective/lang"

    if "kpi_budget_conflict" in d["tags"]:
        assert "kpi_unrealistic_for_budget" in d["labels"]["expected_warnings"], f"{name}: missing warning"
    if "tiny_budget" in d["tags"]:
        assert d["brief"]["budget"] <= 50, f"{name}: tiny_budget but budget > 50"
    if "empty_notes" in d["tags"]:
        assert d["brief"]["notes"] == "", f"{name}: empty_notes but notes not empty"
    if "long_rambling_notes" in d["tags"]:
        assert len(d["brief"]["notes"].split()) >= 200, f"{name}: rambling notes < 200 words"

    # v2-only checks
    if is_v2:
        v2_tags_present = [t for t in d["tags"] if t in V2_QUOTA_TAGS]
        for t in v2_tags_present:
            v2_quota_c[t] += 1

        if "full_catalog_only" in d["tags"]:
            new_only = [i for i in aud["must_include"] if i not in old_ids]
            if len(new_only) != len(aud["must_include"]):
                bad = [i for i in aud["must_include"] if i in old_ids]
                errors.append(
                    f"{name}: tagged full_catalog_only but must_include contains ids already in the 71-item dump: {bad}"
                )

        targeting = d["labels"].get("targeting")
        if targeting is not None:
            _check_targeting_block(name, targeting)
        if "targeting_labeled" in d["tags"]:
            assert targeting is not None, f"{name}: tagged targeting_labeled but no targeting block present"
    else:
        assert "targeting" not in d["labels"], f"{name}: v1 brief must not have a targeting block"
        v2_only_tags = tuple(t for t in V2_QUOTA_TAGS if t != "adversarial")
        assert not any(t in v2_only_tags for t in d["tags"]), f"{name}: v1 brief must not carry v2-only quota tags"

    obj_c[d["brief"]["objective"]] += 1
    lang_c[d["lang"]] += 1
    for t in d["tags"]:
        if t not in (*VALID_OBJECTIVES, *VALID_LANGS):
            tag_c[t] += 1

# old-id-missing-from-full-catalog check (flag for human review, never auto-fix)
for fp in files:
    with open(fp, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("schema_version", 1) != 1:
        continue
    aud = d["labels"]["audience"]
    for k in ("must_include", "acceptable", "must_exclude"):
        for _id in aud[k]:
            if _id in old_ids and _id not in valid_ids:
                old_id_missing_from_full.add(_id)

if old_id_missing_from_full:
    print("!! HUMAN REVIEW NEEDED: v1 audience _ids present in the old 71-item dump but MISSING from "
          "the live catalog_full.json (flagged per AUTHORING-GUIDE.md Step 0, not silently edited):")
    for _id in sorted(old_id_missing_from_full):
        print("   ", _id)

if errors:
    print("\n".join(errors))
    sys.exit(1)

print(f"All {len(files)} briefs valid. Every audience _id exists in catalog_full.json ({len(valid_ids)} segments).")
print("Objectives:", dict(obj_c))
print("Language:  ", dict(lang_c))
print("All special tags (v1 cells + v2 quota cells; 'adversarial' is shared by both):", dict(tag_c))
print()
print("v2 quota table (brief_041-080):")
for tag, required in V2_QUOTA_REQUIRED.items():
    got = v2_quota_c.get(tag, 0)
    status = "OK" if got >= required else "SHORT"
    print(f"  {tag:22s} required>={required:<3d} got={got:<3d} [{status}]")

assert all(obj_c[o] >= 8 for o in ("awareness", "consideration", "conversion")) and obj_c["retention"] >= 4, (
    f"objective stratification failed: {dict(obj_c)}"
)
assert lang_c["vi"] >= 28 and lang_c["en"] >= 8, f"language stratification failed: {dict(lang_c)}"

# "adversarial" is intentionally used by both v1 (brief_014/027/036) and the v2
# "Adversarial v2" quota cell (AUTHORING-GUIDE.md Step 2) -- tag_c already combines both.
assert all(
    tag_c.get(t, 0) >= 3
    for t in ("ambiguous_notes", "kpi_budget_conflict", "tiny_budget", "empty_notes", "adversarial", "long_rambling_notes")
), f"v1 special-cell stratification failed: {dict(tag_c)}"

for tag, required in V2_QUOTA_REQUIRED.items():
    assert v2_quota_c.get(tag, 0) >= required, f"v2 quota cell '{tag}' short: got {v2_quota_c.get(tag, 0)}, need {required}"

print("\nStratification + quota requirements: PASS")
