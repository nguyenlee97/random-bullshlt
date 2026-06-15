"""Boot handler — step -1, stateless greeting."""
from models import AgentResponse, ResponseMeta


async def handle_boot() -> AgentResponse:
    return AgentResponse(
        text=(
            "Xin chào! Em là **Camp Ads Agent** 👋\n\n"
            "Em sẽ hỗ trợ anh thiết lập chiến dịch quảng cáo theo 5 bước:\n"
            "1. **Brief** — Mục tiêu, ngân sách, thời gian\n"
            "2. **Creative** — Upload hình ảnh / video quảng cáo\n"
            "3. **Audience** — Chọn tệp khách hàng mục tiêu\n"
            "4. **Setup** — Chọn vị trí đặt quảng cáo\n"
            "5. **Kết quả** — Xem tổng kết chiến dịch\n\n"
            "Anh bắt đầu bằng cách điền thông tin Brief ở panel bên phải nhé! 🚀"
        ),
        blocks=[],
        meta=ResponseMeta(tool="agent_boot", model="none", step=-1),
    )
