"""Result handler — Step 4. Fetches order status, no LLM."""
from models import AgentResponse, ResponseMeta
from session import get_or_create_session, log_event
from tools.order_api import fetch_order


async def handle_result(session_id: str) -> AgentResponse:
    session = await get_or_create_session(session_id)
    order_ids = session.get("created_order_ids", [])
    brief = session["form_state"].get("brief", {})

    if not order_ids:
        return AgentResponse(
            text="⚠ Chưa có campaign nào. Vui lòng hoàn tất bước Setup trước.",
            blocks=[],
            meta=ResponseMeta(tool="result", model="none", step=4),
        )

    orders = []
    for oid in order_ids:
        try:
            o = await fetch_order(oid)
            orders.append(o)
        except Exception as e:
            await log_event(session_id, "error", {"handler": "result", "order_id": oid, "error": str(e)})
            orders.append({"id": oid, "status": "error", "brand": "?", "budget": 0, "placements": []})

    campaigns = []
    total_budget = 0
    for o in orders:
        b = o.get("budget", 0)
        total_budget += b
        n_zones = len(o.get("placements", []))
        campaigns.append({
            "id": o.get("id", "—"),
            "name": f"{o.get('brand', '?')} — {n_zones} zones",
            "status": o.get("status", "unknown"),
            "budget": round(b / 1_000_000, 1) if b > 1000 else b,
            "reach": 0,
            "impressions": 0,
            "ctr": 0,
        })

    active = sum(1 for c in campaigns if c["status"] in ("active", "pending"))
    total_m = round(total_budget / 1_000_000, 1)

    blocks = [
        {"type": "campaign_list", "campaigns": campaigns},
        {
            "type": "metric_grid",
            "metrics": [
                {"label": "Tổng orders", "value": str(len(campaigns)), "delta": "", "status": "good"},
                {"label": "Active/Pending", "value": str(active), "delta": "", "status": "good"},
                {"label": "Tổng ngân sách", "value": f"{total_m}M VND", "delta": "", "status": "good"},
            ],
        },
        {
            "type": "info",
            "text": (
                "🔗 Xem chi tiết: [AdsPilot](https://adspilot.pawgrammers.io.vn)\n\n"
                "📊 Theo dõi hiệu quả: [Analytics](https://analytics.pawgrammers.io.vn)"
            ),
        },
    ]

    brand = brief.get("brand", "thương hiệu")
    return AgentResponse(
        text=f"🎉 Tổng kết: **{len(campaigns)} chiến dịch** đã được tạo cho **{brand}**!",
        blocks=blocks,
        meta=ResponseMeta(tool="result", model="none", step=4),
    )
