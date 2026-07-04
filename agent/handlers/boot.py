"""Boot handler — step -1, stateless greeting."""
from models import AgentResponse, ResponseMeta
from version import BUILD_VERSION


async def handle_boot() -> AgentResponse:
    return AgentResponse(
        text=(
            "Xin chào! Em là **Camp Ads Agent** 👋\n\n"
            "Em sẽ hỗ trợ anh/chị thiết lập chiến dịch quảng cáo theo **5 bước**:\n"
            "1. **Brief** — Mục tiêu, ngân sách, thời gian\n"
            "2. **Audience** — Chọn tệp khách hàng mục tiêu (DMP)\n"
            "3. **Creative** — Upload hình ảnh / video quảng cáo\n"
            "4. **Setup** — Chọn vị trí đặt quảng cáo & tạo campaign\n"
            "5. **Kết quả** — Xem tổng kết chiến dịch\n\n"
            "Anh/Chị bắt đầu bằng cách điền thông tin **Brief** ở panel bên phải nhé! 🚀"
        ),
        blocks=[{
            "type": "info",
            "text": f"🔖 Agent v{BUILD_VERSION} — sẵn sàng hoạt động.",
        }],
        meta=ResponseMeta(tool="agent_boot", model="none", step=-1),
    )
