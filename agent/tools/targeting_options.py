"""Targeting options — GET /api/targeting/options (cached)"""
import time
import httpx
from config import config

_cache: dict = {"data": {}, "ts": 0.0}
CACHE_TTL = 600  # 10 minutes (targeting options rarely change)


async def get_targeting_options() -> dict:
    """
    Returns full targeting options dict:
    { geo: {region: [cities]}, age: [], gender: [], deviceOS: [], ... }
    """
    if time.time() - _cache["ts"] < CACHE_TTL and _cache["data"]:
        return _cache["data"]
    async with httpx.AsyncClient(base_url=config.BACKEND_URL, timeout=10.0) as client:
        resp = await client.get("/api/targeting/options")
        resp.raise_for_status()
        _cache["data"] = resp.json()
        _cache["ts"] = time.time()
    return _cache["data"]
