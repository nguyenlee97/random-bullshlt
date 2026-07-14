"""Email handler — Step 6. Handles email delivery of campaign reports."""
import httpx
from models import AgentResponse, ResponseMeta
from session import get_or_create_session, add_message, log_event
from config import config

BACKEND_URL = config.BACKEND_URL


async def handle_email_entry(session_id: str) -> AgentResponse:
    """
    Called when user enters Email step (step 6).
    Returns intro message with pre-filled email suggestion.
    """
    session = await get_or_create_session(session_id)
    form = session.get("form_state", {})
    brief = form.get("brief", {})
    brand = brief.get("brand", "")
    report_ctx = form.get("report", {})
    campaign_id = report_ctx.get("campaignId", "")

    brand_slug = brand.lower().replace(" ", "").replace("-", "") if brand else "brand"
    suggested_email = f"{brand_slug}@adtima.vn"

    intro = (
        f"📧 **Bước cuối — Gửi báo cáo**\n\n"
        f"Em sẽ tổng hợp toàn bộ kết quả phân tích chiến dịch **{brand}** thành một bản PDF "
        f"đẹp, bao gồm:\n"
        f"• 6 hạng mục phân tích AI (Daily Ops, Awareness, Consideration, Conversion, Retention, Executive)\n"
        f"• KPI Scorecard tổng quan\n"
        f"• Zone Performance Table\n"
        f"• Sparklines xu hướng theo ngày\n\n"
        f"📎 Anh/chị cũng có thể kèm thêm file **CSV** hoặc **JSON** raw data nếu cần.\n\n"
        f"Nhập email nhận báo cáo vào form bên phải và bấm **Gửi** để bắt đầu!"
    )

    suggestions = [
        f"Gửi đến {suggested_email}",
        "Tôi muốn kèm file CSV",
        "Tôi muốn kèm file JSON",
        "Download PDF thôi, không cần gửi email",
    ]

    await add_message(session_id, "assistant", intro)
    return AgentResponse(
        text=intro,
        blocks=[{
            "type": "info",
            "text": f"💡 Campaign ID: **{campaign_id}** — PDF sẽ được tạo từ dữ liệu trong database.",
        }],
        suggestions=suggestions,
        meta=ResponseMeta(tool="email_entry", model="none", step=6),
        workspace_update={"field": "email", "value": {"suggestedEmail": suggested_email, "campaignId": campaign_id}},
    )


async def handle_email_send(
    session_id: str,
    email: str,
    cc: str = "",
    attach_csv: bool = False,
    attach_json: bool = False,
) -> AgentResponse:
    """
    Calls backend to generate PDF + send via Resend.
    """
    session = await get_or_create_session(session_id)
    form = session.get("form_state", {})
    report_ctx = form.get("report", {})
    campaign_id = report_ctx.get("campaignId", "")
    brand = form.get("brief", {}).get("brand", "Unknown")

    if not campaign_id:
        return AgentResponse(
            text="⚠ Chưa có Campaign ID. Vui lòng hoàn tất bước Report trước.",
            blocks=[],
            meta=ResponseMeta(tool="email_send", model="none", step=6),
        )

    if not email:
        return AgentResponse(
            text="⚠ Vui lòng nhập địa chỉ email nhận báo cáo.",
            blocks=[],
            meta=ResponseMeta(tool="email_send", model="none", step=6),
        )

    await log_event(session_id, "email_send_start", {
        "campaignId": campaign_id, "to": email, "attachCsv": attach_csv, "attachJson": attach_json
    })

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            payload = {
                "email": email,
                "attachCsv": attach_csv,
                "attachJson": attach_json,
            }
            if cc:
                payload["cc"] = cc

            resp = await client.post(
                f"{BACKEND_URL}/api/reports/send-email/{campaign_id}",
                json=payload,
            )

        if resp.status_code != 200:
            error_msg = resp.json().get("error", f"HTTP {resp.status_code}")
            raise Exception(error_msg)

        result = resp.json()
        message_id = result.get("messageId", "")

        attachments = []
        if attach_csv:  attachments.append("CSV")
        if attach_json: attachments.append("JSON")
        att_str = f" + {', '.join(attachments)}" if attachments else ""

        success_text = (
            f"✅ **Email đã gửi thành công!**\n\n"
            f"📬 **Đến:** {email}\n"
            f"📎 **File đính kèm:** PDF{att_str}\n"
            f"🆔 **Message ID:** `{message_id}`\n\n"
            f"Báo cáo chiến dịch **{brand}** đã được tổng hợp đầy đủ. "
            f"Cảm ơn bạn đã sử dụng Advertising Agent! 🎉"
        )

        await add_message(session_id, "assistant", success_text)
        await log_event(session_id, "email_send_ok", {"messageId": message_id, "to": email})

        return AgentResponse(
            text=success_text,
            blocks=[{
                "type": "email_sent",
                "to": email,
                "messageId": message_id,
                "campaignId": campaign_id,
                "attachments": ["pdf"] + (["csv"] if attach_csv else []) + (["json"] if attach_json else []),
            }],
            suggestions=[
                "Download PDF về máy",
                "Gửi đến địa chỉ khác",
            ],
            meta=ResponseMeta(tool="email_send", model="none", step=6),
        )

    except Exception as e:
        err_text = f"⚠ Không thể gửi email: {str(e)[:200]}"
        await log_event(session_id, "email_send_error", {"error": str(e)})
        return AgentResponse(
            text=err_text,
            blocks=[],
            meta=ResponseMeta(tool="email_send", model="none", step=6),
        )
