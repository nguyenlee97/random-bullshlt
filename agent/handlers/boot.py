"""Boot handler — step -1, mode-aware deterministic greeting."""
from models import AgentResponse, ResponseMeta


_BRIEF_GUIDE = (
    "Một brief hữu ích thường gồm:\n"
    "- **Brand / nhãn hàng và sản phẩm hoặc dịch vụ**\n"
    "- **Mục tiêu chiến dịch**: awareness, consideration, conversion hoặc retention\n"
    "- **KPI mong muốn**: reach, impressions, clicks, leads, sales…\n"
    "- **Ngân sách và thời gian triển khai**\n"
    "- **Đối tượng mục tiêu**: ai sẽ mua hoặc sử dụng sản phẩm\n"
    "- **Thông điệp chính** và yêu cầu creative / guideline thương hiệu\n"
    "- **Kênh hoặc placement mong muốn**, nếu đã có định hướng\n"
    "- **Ghi chú thêm**: ưu tiên, giới hạn và những điều cần tránh"
)


def _copilot_intro() -> str:
    return (
        "Xin chào! Tôi là **Advertising Agent** 👋\n\n"
        "Bạn đang ở **Campaign Copilot**. Tôi sẽ cùng bạn hoàn thiện từng phần "
        "của campaign; bạn có thể gửi một brief đầy đủ hoặc bổ sung thông tin "
        "từng ý qua chat.\n\n"
        f"{_BRIEF_GUIDE}\n\n"
        "Không cần biết sẵn mọi câu trả lời. Hãy gửi những gì bạn đang có và "
        "nhắn **“gợi ý giúp tôi phần còn thiếu”**; tôi sẽ đề xuất KPI, audience, "
        "thông điệp hoặc placement dựa trên ngữ cảnh rồi chờ bạn xác nhận."
    )


def _autopilot_intro() -> str:
    return (
        "Xin chào! Tôi là **Advertising Agent** 👋\n\n"
        "Bạn đang ở **Campaign Autopilot**. Hãy đưa cho tôi mục tiêu và bối cảnh; "
        "Agent sẽ kết nối brief, audience, targeting, placement và creative thành "
        "một plan có thể kiểm tra theo chế độ duyệt bạn chọn.\n\n"
        f"{_BRIEF_GUIDE}\n\n"
        "Để bắt đầu run, brief tối thiểu cần brand, mục tiêu, ngân sách và ngày "
        "chạy. Để recommendation có ý nghĩa, nên nói rõ **sản phẩm/dịch vụ** và "
        "**đối tượng mục tiêu**. Nếu chưa chắc một mục, cứ gửi phần đã biết hoặc "
        "nhắn **“gợi ý giúp tôi hoàn thiện brief”**; tôi sẽ đề xuất phần còn thiếu "
        "để bạn duyệt trước khi Autopilot chạy."
    )


async def handle_boot(experience_mode: str | None = None) -> AgentResponse:
    intro = (
        _autopilot_intro()
        if experience_mode == "autopilot"
        else _copilot_intro()
    )
    return AgentResponse(
        text=(
            f"{intro}\n\n"
            "🔒 Nội dung chat, brief và creative được xử lý bởi dịch vụ AI để "
            "xây dựng campaign. Không nhập dữ liệu cá nhân hoặc bí mật không cần thiết."
        ),
        blocks=[{
            "type": "info",
            "text": "🔖 Agent sẵn sàng hoạt động.",
        }],
        meta=ResponseMeta(tool="agent_boot", model="none", step=-1),
    )
