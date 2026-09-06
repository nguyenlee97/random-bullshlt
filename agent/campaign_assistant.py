"""Read-only campaign Q&A and navigation hints for Campaign Management."""
from __future__ import annotations

import unicodedata


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


async def answer_campaign_question(entry: dict, question: str) -> dict:
    from evaluation.store import list_incidents

    clean_question = str(question or "").strip()
    if not clean_question:
        raise ValueError("question is required")
    campaign_id = entry.get("campaign_id")
    order = entry.get("order") or {}
    folded = _fold(clean_question)
    title = entry.get("title") or campaign_id
    incidents = await list_incidents(campaign_id)
    active_incidents = [
        item for item in incidents
        if item.get("state") not in {"resolved", "dismissed", "false_positive", "expired"}
    ]

    if any(word in folded for word in ("incident", "canh bao", "evaluation", "bat thuong", "loi")):
        if active_incidents:
            top = active_incidents[0]
            answer = (
                f"{title} hiện có {len(active_incidents)} incident đang mở. "
                f"Incident gần nhất là {top.get('incident_id')} ({top.get('issue_type')}, "
                f"mức {top.get('severity')}). Mở Live Evaluation để xem evidence và tiến trình L2."
            )
        else:
            answer = (
                f"{title} hiện không có incident đang mở. Bạn có thể mở Live Evaluation "
                "để xem lần đánh giá gần nhất hoặc chạy đánh giá mới."
            )
        target = "evaluation"
        label = "Mở Live Evaluation"
    elif any(word in folded for word in ("report", "bao cao", "so lieu", "analytics", "scenario")):
        answer = (
            "Báo cáo và Scenario Lab nằm trong tab Báo cáo. Scenario Lab thay đổi lớp dữ liệu "
            "facts theo revision rồi chạy lại report và Evaluation trên cùng dataset."
        )
        target, label = "reports", "Mở Báo cáo"
    elif any(word in folded for word in ("creative", "placement", "cau hinh", "config", "ngan sach", "thoi gian", "muc tieu")):
        daily = order.get("daily_budget")
        daily_note = (
            f"Ngân sách ngày hiện là {daily:,.0f} đ"
            + (" (ước tính từ tổng ngân sách và số ngày)" if order.get("daily_budget_source") == "derived" else "")
            if daily else "Chưa xác định được ngân sách ngày"
        )
        answer = (
            f"{title}: mục tiêu {order.get('objective') or 'chưa xác định'}, tổng ngân sách "
            f"{float(order.get('budget') or 0):,.0f} đ. {daily_note}. Tab Campaign setup cho phép "
            "sửa các trường vận hành có revision; placement và creative có link/preview riêng."
        )
        target, label = "setup", "Mở Campaign setup"
    else:
        answer = (
            f"{title} ({campaign_id}) đang ở trạng thái {entry.get('lifecycle')}. "
            f"Campaign có {order.get('placement_count', 0)} placement, "
            f"{order.get('creative_count', 0)} creative và {len(active_incidents)} incident đang mở. "
            "Mình chỉ giải đáp và dẫn bạn tới đúng khu vực; mình không thay đổi campaign từ cửa sổ chat này."
        )
        target, label = "overview", "Về Tổng quan"
    return {
        "answer": answer,
        "target_tab": target,
        "target_label": label,
        "read_only": True,
        "suggestions": [
            "Campaign hiện có incident nào?",
            "Tôi xem creative và placement ở đâu?",
            "Mở report và Scenario Lab như thế nào?",
        ],
    }
