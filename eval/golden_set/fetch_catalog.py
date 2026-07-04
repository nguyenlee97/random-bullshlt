# -*- coding: utf-8 -*-
"""
Step 0 of AUTHORING-GUIDE.md — fetch the full live DMP catalog + targeting options.

Run this from a machine with network access to the backend
(https://api.pawgrammers.io.vn). The sandbox this was authored in only has
allowlisted egress on its raw shell, so the actual v2 fetch (2026-07-04) was
performed via paginated per-category GETs through an HTTP-fetch tool instead of
this script; that fetch is what produced the committed catalog_full.json (310
items) and targeting_options.json. This script is kept so the fetch is
reproducible from a normal dev/CI machine — running it end-to-end should
reproduce byte-identical *content* (order may differ; validate.py sorts before
comparing _id sets, so that's fine).

    python eval/golden_set/fetch_catalog.py
"""
import json
import os

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("DMP_BACKEND_URL", "https://api.pawgrammers.io.vn")


def fetch_catalog() -> list[dict]:
    """GET /api/dmp/attributes — full segment catalog (Interest + Behavior).

    NOTE: the endpoint's regex-based `category` query param does a *substring*
    match (Mongo `new RegExp(q, 'i')`, unanchored), so categories like
    "Food and drink" vs "Food and drink (consumables)" collide unless you
    anchor with ^...$ and escape any literal parens in the category name
    (parens are regex metacharacters). limit=1000 alone is simplest and is
    what this script uses; the per-category anchored fetch is only needed
    when a single response would be too large for the calling tool.
    """
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{BASE}/api/dmp/attributes", params={"limit": 1000})
        r.raise_for_status()
        items = r.json()
    if isinstance(items, dict):
        items = items.get("data", items.get("items", []))
    return items


def fetch_targeting_options() -> dict:
    """GET /api/targeting/options — geo/age/gender/... option values."""
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{BASE}/api/targeting/options")
        r.raise_for_status()
        return r.json()


def main() -> None:
    items = fetch_catalog()
    print(f"catalog: {len(items)} segments")
    assert len(items) >= 310, f"expected 310+ segments, got {len(items)} — check BASE/endpoint"
    ids = {i["_id"] for i in items}
    assert len(ids) == len(items), "duplicate _id in catalog fetch"

    out_path = os.path.join(HERE, "catalog_full.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    print(f"wrote {out_path}")

    options = fetch_targeting_options()
    opt_path = os.path.join(HERE, "targeting_options.json")
    with open(opt_path, "w", encoding="utf-8") as f:
        json.dump(options, f, ensure_ascii=False, indent=1)
    print(f"wrote {opt_path}")


if __name__ == "__main__":
    main()
