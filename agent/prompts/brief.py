"""Brief handler prompts."""

BRIEF_SYSTEM = """Bạn là Camp Ads Agent. Nhiệm vụ: Phân tích brief chiến dịch quảng cáo.
Trả về JSON theo đúng schema. Không thêm text ngoài JSON."""

BRIEF_USER = """Brief chiến dịch:
- Brand: {brand}
- Objective: {objective}
- KPI: {kpi}
- Budget: {budget} triệu VND
- Thời gian: {start} → {end}
- Ghi chú: {notes}

Phân tích và trả JSON:
{{
  "summary": "Tóm tắt 1-2 câu về chiến dịch",
  "audience_hint": "Gợi ý về target audience, viết dạng chuỗi ngăn cách bằng dấu phẩy, ví dụ: Gen Z, Giới trẻ, Người tiêu dùng",
  "kpi_validated": ["KPI hợp lệ"],
  "warnings": ["Cảnh báo nếu có (budget quá thấp, thời gian quá ngắn, ...)"],
  "suggested_kpis": ["KPI bổ sung phù hợp với objective"]
}}"""
