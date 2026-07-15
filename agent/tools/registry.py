import json
from tools.audience_library import search_audience
from tools.zone_catalog import get_all_zones
from tools.order_api import fetch_order, fetch_all_orders, fetch_zone_conflicts
from tools.targeting_options import get_targeting_options

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_zone_list",
            "description": "Lấy danh sách tất cả ad zones với metrics. Dùng khi hỏi danh sách zone hoặc muốn xem toàn bộ. Luôn truyền start_date và end_date từ brief để kiểm tra availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "description": "awareness|consideration|conversion|retention. Optional."},
                    "start_date": {"type": "string", "description": "Ngày bắt đầu campaign (YYYY-MM-DD) — từ brief. Dùng để check zone availability."},
                    "end_date": {"type": "string", "description": "Ngày kết thúc campaign (YYYY-MM-DD) — từ brief. Dùng để check zone availability."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_zones",
            "description": (
                "Tìm kiếm ad zones theo từ khoá, objective, format hoặc platform. Có tổng 35 zones. "
                "Dùng khi người dùng hỏi 'zone nào phù hợp cho awareness', 'zone ZingNews', "
                "'zone banner 300x250', 'zone có VI% cao', 'zone rẻ nhất'. "
                "Luôn truyền start_date và end_date từ brief để lọc zone bị đặt trước. "
                "Ưu tiên tool này hơn get_zone_list khi có từ khoá tìm kiếm cụ thể."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Từ khoá tìm (tên zone, platform như 'znews'/'baomoi'/'zmp3', format như 'banner'/'masthead'/'skin')"},
                    "objective": {"type": "string", "description": "awareness|consideration|conversion|retention. Optional."},
                    "start_date": {"type": "string", "description": "Ngày bắt đầu campaign (YYYY-MM-DD) — từ brief."},
                    "end_date": {"type": "string", "description": "Ngày kết thúc campaign (YYYY-MM-DD) — từ brief."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_audience_list",
            "description": (
                "Tìm audience segments từ DMP (310+ segments thực tế). "
                "Dùng khi người dùng hỏi về segment, audience hoặc đối tượng mục tiêu. "
                "Hỗ trợ tìm bằng tiếng Anh hoặc tiếng Việt. "
                "Nếu không tìm thấy, thử lại với từ khoá rộng hơn hoặc tiếng Anh "
                "(VD: thay 'Esport' → 'gaming', 'Livestream' → 'streaming', 'âm nhạc' → 'music'). "
                "Có thể tìm theo category: Sports, Entertainment, Finance, Food, Travel, Technology, Gaming, Music, ..."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Từ khoá tìm kiếm (EN/VI). VD: 'gaming', 'du lịch', 'food & drink', 'music'"},
                    "type": {"type": "string", "enum": ["Behavior", "Interest"], "description": "Loại segment. Optional."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_workspace",
            "description": (
                "Đề xuất cập nhật workspace. "
                "CHỈ gọi khi người dùng YÊU CẦU THAY ĐỔI hoặc XÁC NHẬN thông tin rõ ràng. "
                "KHÔNG gọi khi chỉ hỏi thông tin. "
                "Tool tạo đề xuất để user xác nhận — KHÔNG áp dụng ngay. "
                "Khi xác nhận brief (nhiều field) → dùng field='brief' với value là object đầy đủ {brand, objective, kpi, budget, startDate, endDate, notes}. "
                "Chỉ dùng dotted path (vd: 'brief.brand') khi user chỉ đổi đúng 1 field đó."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "Section hoặc dotted path. VD: 'brief' (toàn bộ brief), 'brief.brand' (1 field). Khi có nhiều thay đổi ở cùng 1 bước → dùng 'brief' với object đầy đủ."},
                    "value": {"description": "Giá trị mới. Nếu field='brief': value là object {brand, objective, kpi, budget (số, đơn vị triệu VND), startDate (YYYY-MM-DD), endDate (YYYY-MM-DD), notes}. Budget ghi bằng số nguyên triệu (VD: 600 = 600 triệu)."},
                    "reason": {"type": "string", "description": "Lý do thay đổi — giải thích ngắn cho user."},
                },
                "required": ["field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_step",
            "description": "Giải thích một bước trong quy trình. Dùng khi hỏi 'bước này là gì', 'giải thích setup'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_name": {"type": "string", "enum": ["brief", "audience", "creative", "setup", "result"]},
                },
                "required": ["step_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Xem trạng thái campaign đã tạo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "VD: ORD-2026-005. Optional — nếu trống trả all."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_targeting_options",
            "description": "Lấy danh sách targeting options (geo, age, gender, ...). Dùng khi hỏi về targeting.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

_STEP_EXPLANATIONS = {
    "brief":    "Bước Brief: Anh/chị điền brand, objective (awareness/consideration/conversion/retention), KPI, ngân sách, thời gian và ghi chú. Em phân tích và đề xuất audience phù hợp.",
    "audience": "Bước Audience: Chọn DMP segments (310+ segments). Em tính audience size theo mô hình union (OR logic) với 30% overlap discount. Anh/Chị có thể tìm theo từ khoá hoặc để em gợi ý.",
    "creative": "Bước Creative: Upload hình/video. Em kiểm tra format (PNG/JPG/MP4), kích thước (≥300px), dung lượng (≤10MB).",
    "setup":    "Bước Setup 3 giai đoạn: (1) Em gợi ý top zone theo objective/KPI, (2) gán creative vào zone, (3) tạo order với tất cả zones đã chọn.",
    "result":   "Bước Kết quả: Hiện tổng kết order đã tạo — trạng thái, ngân sách, liên kết quản lý và test site.",
}


async def execute_tool(name: str, args: dict) -> dict:
    """Single dispatcher for all tool calls — metrics recorded here (Phase 0 B4)."""
    from metrics import TOOL_CALLS
    try:
        result = await _execute_tool_inner(name, args)
        TOOL_CALLS.labels(tool=name, outcome="ok").inc()
        return result
    except Exception:
        TOOL_CALLS.labels(tool=name, outcome="error").inc()
        raise


async def _execute_tool_inner(name: str, args: dict) -> dict:
    if name == "get_zone_list":
        zones = await get_all_zones()
        obj = args.get("objective")
        if obj:
            zones = [z for z in zones if z.get("obj") == obj]
        conflicts = await fetch_zone_conflicts(args.get("start_date", ""), args.get("end_date", ""))
        return {"zones": [{
            "id": z["id"], "format": z["format"], "size": z["size"],
            "reach": z["reach"], "vi": z["vi"], "ctr": z["ctr"],
            "cpm": z["cpm"], "obj": z["obj"],
            "channel": z.get("channel", ""),
            "is_booked": z["id"] in conflicts,
            "conflict": conflicts.get(z["id"]),
        } for z in zones]}

    elif name == "search_zones":
        zones = await get_all_zones()
        query = (args.get("query") or "").lower().strip()
        obj = args.get("objective")

        results = zones
        if obj:
            results = [z for z in results if z.get("obj") == obj]
        if query:
            results = [z for z in results if query in " ".join([
                z.get("id", ""), z.get("channel", ""), z.get("format", ""),
                z.get("size", ""), z.get("obj", ""),
            ]).lower()]

        conflicts = await fetch_zone_conflicts(args.get("start_date", ""), args.get("end_date", ""))
        return {
            "zones": [{
                "id": z["id"], "channel": z.get("channel", ""),
                "format": z["format"], "size": z["size"],
                "reach": z["reach"], "vi": z["vi"], "ctr": z["ctr"],
                "cpm": z["cpm"], "obj": z["obj"],
                "siteUrl": z.get("siteUrl", ""),
                "is_booked": z["id"] in conflicts,
                "conflict": conflicts.get(z["id"]),
            } for z in results[:15]],
            "total": len(results),
            "note": "Không tìm thấy zone nào." if not results else f"Tìm thấy {len(results)} zone ({sum(1 for z in results[:15] if z['id'] in conflicts)} bị đặt trước).",
        }

    elif name == "get_audience_list":
        results = await search_audience(
            query=args.get("query", ""),
            type_filter=args.get("type"),
            limit=10,
        )
        if not results:
            return {
                "segments": [],
                "note": (
                    f"Không tìm thấy segment nào với từ khoá '{args.get('query', '')}'. "
                    "Thử lại với từ khoá tiếng Anh hoặc rộng hơn "
                    "(VD: 'gaming', 'streaming', 'music', 'travel', 'food', 'finance')."
                ),
            }
        return {"segments": [{
            "_id": r.get("_id", ""), "fullLabel": r.get("fullLabel", r.get("name", "")),
            "type": r.get("type", ""), "sizeRaw": r.get("sizeRaw", ""),
            "category": r.get("category", ""),
        } for r in results]}

    elif name == "update_workspace":
        # This is handled specially in freeform.py (proposal flow)
        # Just return the proposed args so the second LLM call can explain it
        return {
            "proposed_field": args.get("field", ""),
            "proposed_value": args.get("value"),
            "reason": args.get("reason", ""),
            "status": "pending_user_confirmation",
        }

    elif name == "explain_step":
        step = args.get("step_name", "brief")
        return {"explanation": _STEP_EXPLANATIONS.get(step, "Bước không tìm thấy.")}

    elif name == "get_order_status":
        oid = args.get("order_id")
        if oid:
            order = await fetch_order(oid)
            return {"order": {
                "id": order.get("id"), "status": order.get("status"),
                "brand": order.get("brand"), "placements": order.get("placements", []),
            }}
        else:
            orders = await fetch_all_orders()
            return {"orders": [{
                "id": o.get("id"), "status": o.get("status"), "brand": o.get("brand"),
            } for o in orders[:5]]}

    elif name == "get_targeting_options":
        return await get_targeting_options()

    return {"error": f"Unknown tool: {name}"}
