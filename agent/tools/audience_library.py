"""DMP audience library — GET /api/dmp/attributes with fuzzy fallback."""
import httpx
from config import config

_client = httpx.AsyncClient(base_url=config.BACKEND_URL, timeout=10.0)

# In-process cache of all segments (avoids repeated full fetches per session)
_all_segments_cache: list[dict] | None = None


async def _fetch_all_segments() -> list[dict]:
    """Fetch and cache all DMP segments from backend."""
    global _all_segments_cache
    if _all_segments_cache is not None:
        return _all_segments_cache

    segments: list[dict] = []
    try:
        # Primary: bulk fetch with high limit (avoids broken pagination)
        resp = await _client.get("/api/dmp/attributes", params={"limit": "500"})
        resp.raise_for_status()
        data = resp.json()
        bulk = data if isinstance(data, list) else data.get("data", [])
        if bulk:
            segments = bulk

        # Fallback: paginated fetch if bulk returned nothing or very few
        if len(segments) < 50:
            segments = []
            seen_ids: set = set()
            for page in range(1, 15):  # max 14 pages × 100 = 1400 segments
                resp = await _client.get(
                    "/api/dmp/attributes",
                    params={"limit": "100", "page": str(page)},
                )
                resp.raise_for_status()
                data = resp.json()
                items = data if isinstance(data, list) else data.get("data", [])
                if not items:
                    break
                # Deduplication by _id to detect broken pagination
                new_items = []
                for item in items:
                    uid = str(item.get("_id") or item.get("segmentId") or item.get("fullLabel", ""))
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        new_items.append(item)
                if not new_items:
                    break  # All items already seen — pagination is broken, stop
                segments.extend(new_items)
                if len(items) < 100:
                    break  # Last page

    except Exception as e:
        print(f"[audience_library] Failed to fetch all segments: {e}")

    # Final deduplication by _id
    seen: set = set()
    deduped: list[dict] = []
    for s in segments:
        uid = str(s.get("_id") or s.get("segmentId") or s.get("fullLabel", ""))
        if uid not in seen:
            seen.add(uid)
            deduped.append(s)

    _all_segments_cache = deduped
    print(f"[audience_library] Loaded {len(deduped)} unique segments")
    return deduped


def _fuzzy_match(query: str, segments: list[dict], limit: int = 10) -> list[dict]:
    """
    Client-side fuzzy text match.
    Searches across fullLabel, name, category, type, segment_category fields.
    Supports multi-keyword input (comma or space separated).
    """
    if not query or not segments:
        return []

    # Split into individual terms, minimum 2 chars each
    raw_terms = query.replace(",", " ").split()
    terms = [t.strip().lower() for t in raw_terms if len(t.strip()) >= 2]
    if not terms:
        return []

    scored: list[tuple[int, dict]] = []
    for seg in segments:
        haystack = " ".join(filter(None, [
            seg.get("fullLabel", ""),
            seg.get("name", ""),
            seg.get("category", ""),
            seg.get("type", ""),
            seg.get("segment_category", ""),
            seg.get("label", ""),
        ])).lower()

        score = 0
        for term in terms:
            if term in haystack:
                score += len(term)          # Full substring match — score by length
            elif len(term) >= 4 and term[:4] in haystack:
                score += 1                  # Prefix partial match

        if score > 0:
            scored.append((score, seg))

    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:limit]]


async def search_audience(
    query: str = "",
    type_filter: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Search DMP segments by query.
    1. Tries backend ?q= search first.
    2. Falls back to client-side fuzzy match against full segment cache if empty.
    """
    params: dict = {"limit": str(limit)}
    if query:
        params["q"] = query
    if type_filter:
        params["type"] = type_filter

    results: list[dict] = []
    try:
        resp = await _client.get("/api/dmp/attributes", params=params)
        resp.raise_for_status()
        data = resp.json()
        results = data if isinstance(data, list) else data.get("data", [])
    except Exception:
        pass  # Fall through to fuzzy

    # Fuzzy fallback if API returned nothing and we have a query
    if not results and query:
        all_segs = await _fetch_all_segments()
        results = _fuzzy_match(query, all_segs, limit)

    # Apply type filter locally if provided (fuzzy results may not be filtered)
    if type_filter and results:
        results = [
            r for r in results
            if r.get("type", "").lower() == type_filter.lower()
        ]

    return results[:limit]


async def get_all_segments(limit: int = 400) -> list[dict]:
    """Fetch full DMP library (used for context window in audience handler)."""
    all_segs = await _fetch_all_segments()
    return all_segs[:limit]
