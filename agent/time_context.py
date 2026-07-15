"""Authoritative local clock helpers for campaign date interpretation."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


# Vietnam has observed UTC+7 without daylight-saving changes since 1975. An
# explicit fixed offset keeps Windows environments deterministic even when the
# optional IANA ``tzdata`` package is not installed.
CAMPAIGN_TIMEZONE = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def campaign_now() -> datetime:
    return datetime.now(CAMPAIGN_TIMEZONE)


def campaign_today() -> date:
    return campaign_now().date()


def campaign_time_system_message() -> str:
    now = campaign_now()
    return (
        "THỜI GIAN HỆ THỐNG CÓ THẨM QUYỀN: "
        f"{now.isoformat(timespec='seconds')} (Asia/Ho_Chi_Minh). "
        f"Hôm nay là {now.date().isoformat()}. "
        "Khi người dùng không ghi năm, chọn lần xuất hiện gần nhất không sớm hơn hôm nay. "
        "Không được tự suy đoán năm từ dữ liệu huấn luyện của model."
    )
