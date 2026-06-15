"""
Order API wrappers — POST/GET /api/orders
Real schema confirmed from live API data.
"""
import httpx
from datetime import date
from config import config

_client = httpx.AsyncClient(base_url=config.BACKEND_URL, timeout=15.0)


async def create_order(payload: dict) -> dict:
    """POST /api/orders — creates a single campaign order (all zones in one)."""
    resp = await _client.post("/api/orders", json=payload)
    if resp.status_code == 409:
        return {"error": "conflict", "detail": resp.json()}
    resp.raise_for_status()
    return resp.json()


async def fetch_order(order_id: str) -> dict:
    """GET /api/orders/:id"""
    resp = await _client.get(f"/api/orders/{order_id}")
    resp.raise_for_status()
    return resp.json()


async def fetch_all_orders() -> list[dict]:
    """GET /api/orders"""
    resp = await _client.get("/api/orders")
    resp.raise_for_status()
    return resp.json()


async def fetch_zone_conflicts(start_date: str, end_date: str) -> dict[str, dict]:
    """
    Returns a dict { zone_id: { orderId, campaignName, startDate, endDate } }
    for all zones that are already booked by an active order whose date range
    overlaps with [start_date, end_date].

    Overlap condition: start1 <= end2 AND start2 <= end1
    """
    if not start_date or not end_date:
        return {}

    try:
        orders = await fetch_all_orders()
    except Exception:
        return {}  # Non-critical — don't block zone fetch on failure

    # Normalize to date objects for comparison
    def parse(d: str) -> date | None:
        try:
            return date.fromisoformat(d[:10])
        except Exception:
            return None

    camp_start = parse(start_date)
    camp_end = parse(end_date)
    if not camp_start or not camp_end:
        return {}

    conflicts: dict[str, dict] = {}
    skip_statuses = {"archived", "cancelled", "deleted"}

    for order in orders:
        status = (order.get("status") or "").lower()
        if status in skip_statuses:
            continue

        o_start = parse(order.get("startDate") or order.get("start_date") or "")
        o_end   = parse(order.get("endDate")   or order.get("end_date")   or "")
        if not o_start or not o_end:
            continue

        # Check overlap
        if camp_start <= o_end and o_start <= camp_end:
            placements = order.get("placements") or []
            order_id = order.get("id") or order.get("_id") or "?"
            campaign_name = order.get("brand") or order.get("name") or order_id
            for zone_id in placements:
                if zone_id not in conflicts:  # First conflict wins
                    conflicts[zone_id] = {
                        "orderId": order_id,
                        "campaignName": campaign_name,
                        "startDate": str(o_start),
                        "endDate": str(o_end),
                    }

    return conflicts
