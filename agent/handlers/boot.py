"""Boot handler — step -1, stateless greeting."""
from models import AgentResponse, ResponseMeta
from version import BUILD_VERSION


async def handle_boot() -> AgentResponse:
    return AgentResponse(
        text=(
            "Xin chào! Tôi là **Advertising Agent** 👋\n\n"
            "Em sẽ hỗ trợ anh/chị thiết lập chiến dịch quảng cáo theo **5 bước**:\n"
            "1. **Brief** — Mục tiêu, ngân sách, thời gian\n"
            "2. **Audience** — Chọn tệp khách hàng mục tiêu (DMP)\n"
            "3. **Creative** — Upload hình ảnh / video quảng cáo\n"
            "4. **Setup** — Chọn vị trí đặt quảng cáo & tạo campaign\n"
            "5. **Kết quả** — Xem tổng kết chiến dịch\n\n"
            "Bạn có thể làm theo từng bước hoặc dùng **Campaign Autopilot** để Agent xây dựng bản campaign và chờ bạn duyệt.\n\n"
            "🔒 Nội dung chat, brief và creative được xử lý bởi dịch vụ AI để xây dựng campaign. Không nhập dữ liệu cá nhân hoặc bí mật không cần thiết. **Chiến dịch mới** sẽ mở một campaign mới và giữ campaign cũ trong Lịch sử.\n\n"
            "Bắt đầu bằng Brief nhé! 🚀"
        ),
        blocks=[{
            "type": "info",
            "text": f"🔖 Agent v{BUILD_VERSION} — sẵn sàng hoạt động.",
        }],
        meta=ResponseMeta(tool="agent_boot", model="none", step=-1),
    )
