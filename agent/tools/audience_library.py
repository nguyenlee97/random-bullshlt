"""DMP audience library — GET /api/dmp/attributes"""
import httpx
from config import config

_client = httpx.AsyncClient(base_url=config.BACKEND_URL, timeout=10.0)


async def search_audience(query: str = "", type_filter: str | None = None, limit: int = 20) -> list[dict]:
    """Search DMP segments. Returns list with _id, fullLabel, sizeMin, sizeMax."""
    params: dict = {"limit": str(limit)}
    if query:
        params["q"] = query
    if type_filter:
        params["type"] = type_filter
    try:
        resp = await _client.get("/api/dmp/attributes", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", [])
    except Exception:
        return []


async def get_all_segments(limit: int = 400) -> list[dict]:
    """Fetch full DMP library (used for context window in audience handler)."""
    return await search_audience(limit=limit)
