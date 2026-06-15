"""
Zone catalog — fetches GET /api/zones and caches for 5 minutes.
Real schema: id, channel, format, size ("NxM" or "skin"), reach (raw), vi, ctr, cpm, obj, siteId
"""
import time
import httpx
from config import config

_cache: dict = {"zones": [], "groups": [], "channels": {}, "ts": 0.0}
CACHE_TTL = 300  # 5 minutes


async def _refresh() -> None:
    async with httpx.AsyncClient(base_url=config.BACKEND_URL, timeout=10.0) as client:
        resp = await client.get("/api/zones")
        resp.raise_for_status()
        data = resp.json()
    _cache["zones"] = data.get("placements", [])
    _cache["groups"] = data.get("groups", [])
    _cache["channels"] = data.get("channels", {})
    _cache["ts"] = time.time()


async def get_all_zones() -> list[dict]:
    if time.time() - _cache["ts"] >= CACHE_TTL or not _cache["zones"]:
        await _refresh()
    return _cache["zones"]


async def get_zones_by_obj(objective: str) -> list[dict]:
    zones = await get_all_zones()
    return [z for z in zones if z.get("obj") == objective]


async def get_zone_map() -> dict[str, dict]:
    """Return {zone_id: zone_dict} for fast lookup."""
    zones = await get_all_zones()
    return {z["id"]: z for z in zones}
