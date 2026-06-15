"""Tool registry — definitions + dispatcher for OpenAI function calling."""
import json
from tools.audience_library import search_audience
from tools.zone_catalog import get_all_zones
from tools.order_api import fetch_order, fetch_all_orders
from tools.targeting_options import get_targeting_options

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_zone_list",
            "description": "Lấy danh sách ad zones với metrics. Dùng khi hỏi 'zone nào tốt', 'danh sách vị trí', 'zone awareness'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "description": "awareness|consideration|conversion|retention. Optional."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_audience_list",
            "description": "Tìm audience segments từ DMP. Dùng khi hỏi 'segment du lịch', 'audience tài chính'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Từ khoá tìm kiếm (EN/VI)"},
                    "type": {"type": "string", "enum": ["Behavior", "Interest"], "description": "Loại segment. Optional."},
                },
                "required": ["query"],
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
                    "step_name": {"type": "string", "enum": ["brief", "creative", "audience", "setup", "result"]},
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
    "brief":    "Bước Brief: Điền brand, objective, KPI, ngân sách, thời gian, ghi chú. Agent phân tích và đề xuất audience.",
    "creative": "Bước Creative: Upload hình/video. Agent kiểm tra format (PNG/JPG/MP4), kích thước (≥300px), dung lượng (≤10MB).",
    "audience": "Bước Audience: Chọn DMP segments (310+ segments). Agent tính audience size theo overlap discount. Sau đó có thể thiết lập targeting nâng cao.",
    "setup":    "Bước Setup 3 phase: (1) Em gợi ý top zone theo objective, (2) gán creative vào zone, (3) tạo 1 order với tất cả zones.",
    "result":   "Bước Kết quả: Hiện tổng kết order đã tạo — trạng thái, ngân sách, links AdsPilot và Analytics.",
}


async def execute_tool(name: str, args: dict) -> dict:
    if name == "get_zone_list":
        zones = await get_all_zones()
        obj = args.get("objective")
        if obj:
            zones = [z for z in zones if z.get("obj") == obj]
        return {"zones": [{"id": z["id"], "format": z["format"], "size": z["size"],
                           "reach": z["reach"], "vi": z["vi"], "ctr": z["ctr"],
                           "cpm": z["cpm"], "obj": z["obj"]} for z in zones]}

    elif name == "get_audience_list":
        results = await search_audience(query=args.get("query", ""), type_filter=args.get("type"), limit=10)
        return {"segments": [{"_id": r["_id"], "fullLabel": r.get("fullLabel", r.get("name", "")),
                               "type": r.get("type", ""), "sizeRaw": r.get("sizeRaw", "")} for r in results]}

    elif name == "explain_step":
        step = args.get("step_name", "brief")
        return {"explanation": _STEP_EXPLANATIONS.get(step, "Bước không tìm thấy.")}

    elif name == "get_order_status":
        oid = args.get("order_id")
        if oid:
            order = await fetch_order(oid)
            return {"order": {"id": order.get("id"), "status": order.get("status"),
                               "brand": order.get("brand"), "placements": order.get("placements", [])}}
        else:
            orders = await fetch_all_orders()
            return {"orders": [{"id": o.get("id"), "status": o.get("status"), "brand": o.get("brand")} for o in orders[:5]]}

    elif name == "get_targeting_options":
        return await get_targeting_options()

    return {"error": f"Unknown tool: {name}"}
