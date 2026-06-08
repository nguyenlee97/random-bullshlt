# GreenNode AgentBase

## Bắt đầu bằng một ví dụ thực tế

Bạn muốn xây một AI Agent hỗ trợ khách hàng: nhận câu hỏi qua chat, tra cứu đơn hàng trong database, gửi thông báo qua Slack, và nhớ lại nội dung cuộc hội thoại tuần trước.

Nghe đơn giản — nhưng thực tế bạn sẽ phải tự lo:

* **Đâu để chạy agent?** Container, server, autoscaling, CI/CD deploy...
* **Credential để ở đâu?** Database password, Slack token, API key — không thể hardcode vào code.
* **Agent gọi tool nào cũng được?** Cần kiểm soát để agent không vô tình gọi API xóa dữ liệu.
* **Chi phí LLM tháng này bao nhiêu?** Không có dashboard, không biết khi nào vượt budget.
* **Khi có lỗi trên production?** Không có logs tập trung, không biết request nào fail.

**AgentBase giải quyết toàn bộ những điều này** — để bạn chỉ cần tập trung viết logic của agent.

***

## AgentBase là gì?

**GreenNode AgentBase** là nền tảng hạ tầng chuyên biệt dành cho AI Agent — cung cấp đầy đủ lớp vận hành, bảo mật và kiểm soát cần thiết để đưa agent từ code lên production.

![AgentBase — Kiến trúc tổng quan](/files/gTuiip516XzFO6FaQlDn)

AgentBase bao gồm các module sau:

| Module                 | Chức năng                                                                                                 |
| ---------------------- | --------------------------------------------------------------------------------------------------------- |
| **Agent Runtime**      | Deploy và vận hành agent — quản lý container lifecycle, versioning, rollback, scaling                     |
| **Marketplace**        | Triển khai agent dựng sẵn (OpenClaw và các template) chỉ với 1 click, không cần code                      |
| **Access Control**     | Quản lý Agent Identity và lưu trữ credential (API Key, OAuth2) — tự động inject vào agent khi chạy        |
| **MCP Governance**     | Kiểm soát tất cả MCP tool calls từ agent — xác thực và phân quyền qua MCP Gateway + Policy Group          |
| **Protect & Govern**   | Rate Limiting theo model hoặc API Key — tránh agent tiêu thụ quá mức tài nguyên                           |
| **Memory**             | Cho agent ghi nhớ xuyên session — Short-Term (lịch sử hội thoại) và Long-Term (semantic search)           |
| **Container Registry** | Private image registry tự động tạo kèm mỗi org — lưu trữ container image cho Custom Agent                 |
| **Team & Permissions** | Quản lý thành viên với 4 role (Root / Admin / Member / Viewer) và phân quyền chi tiết                     |
| **Usage & Budget**     | Dashboard theo dõi requests, tokens, cost theo agent/model/provider; đặt budget limit và cảnh báo tự động |

***

## Hai cách bắt đầu

**Không cần code — dùng ngay:** Vào [Marketplace](/vng-cloud-document/vn/ai-stack/agent-base/marketplace.md), chọn **OpenClaw**, điền API key và kênh chat — agent chạy trong vài phút.

**Tự build agent:** Đóng gói agent thành Docker image, push lên [Container Registry](/vng-cloud-document/vn/ai-stack/agent-base/container-registry.md), deploy qua [Agent Runtime](/vng-cloud-document/vn/ai-stack/agent-base/agent-runtime.md). Thêm credential trong [Access Control](/vng-cloud-document/vn/ai-stack/agent-base.md), gắn [MCP Gateway](/vng-cloud-document/vn/ai-stack/agent-base/mcp-governance/mcp-gateway.md) nếu agent cần gọi external tools.

***

## Dành cho ai?

| Đối tượng                   | AgentBase mang lại                                                      |
| --------------------------- | ----------------------------------------------------------------------- |
| **AI Engineer / Developer** | Tập trung viết logic agent — infra, credential, observability đã có sẵn |
| **Startup / Product Team**  | Ra mắt AI product nhanh hơn                                             |
| **Doanh nghiệp**            | Kiểm soát chi phí, phân quyền theo team, bảo mật credential theo chuẩn  |


# GreenNode AgentBase

## Bắt đầu bằng một ví dụ thực tế

Bạn muốn xây một AI Agent hỗ trợ khách hàng: nhận câu hỏi qua chat, tra cứu đơn hàng trong database, gửi thông báo qua Slack, và nhớ lại nội dung cuộc hội thoại tuần trước.

Nghe đơn giản — nhưng thực tế bạn sẽ phải tự lo:

* **Đâu để chạy agent?** Container, server, autoscaling, CI/CD deploy...
* **Credential để ở đâu?** Database password, Slack token, API key — không thể hardcode vào code.
* **Agent gọi tool nào cũng được?** Cần kiểm soát để agent không vô tình gọi API xóa dữ liệu.
* **Chi phí LLM tháng này bao nhiêu?** Không có dashboard, không biết khi nào vượt budget.
* **Khi có lỗi trên production?** Không có logs tập trung, không biết request nào fail.

**AgentBase giải quyết toàn bộ những điều này** — để bạn chỉ cần tập trung viết logic của agent.

***

## AgentBase là gì?

**GreenNode AgentBase** là nền tảng hạ tầng chuyên biệt dành cho AI Agent — cung cấp đầy đủ lớp vận hành, bảo mật và kiểm soát cần thiết để đưa agent từ code lên production.

![AgentBase — Kiến trúc tổng quan](/files/gTuiip516XzFO6FaQlDn)

AgentBase bao gồm các module sau:

| Module                 | Chức năng                                                                                                 |
| ---------------------- | --------------------------------------------------------------------------------------------------------- |
| **Agent Runtime**      | Deploy và vận hành agent — quản lý container lifecycle, versioning, rollback, scaling                     |
| **Marketplace**        | Triển khai agent dựng sẵn (OpenClaw và các template) chỉ với 1 click, không cần code                      |
| **Access Control**     | Quản lý Agent Identity và lưu trữ credential (API Key, OAuth2) — tự động inject vào agent khi chạy        |
| **MCP Governance**     | Kiểm soát tất cả MCP tool calls từ agent — xác thực và phân quyền qua MCP Gateway + Policy Group          |
| **Protect & Govern**   | Rate Limiting theo model hoặc API Key — tránh agent tiêu thụ quá mức tài nguyên                           |
| **Memory**             | Cho agent ghi nhớ xuyên session — Short-Term (lịch sử hội thoại) và Long-Term (semantic search)           |
| **Container Registry** | Private image registry tự động tạo kèm mỗi org — lưu trữ container image cho Custom Agent                 |
| **Team & Permissions** | Quản lý thành viên với 4 role (Root / Admin / Member / Viewer) và phân quyền chi tiết                     |
| **Usage & Budget**     | Dashboard theo dõi requests, tokens, cost theo agent/model/provider; đặt budget limit và cảnh báo tự động |

***

## Hai cách bắt đầu

**Không cần code — dùng ngay:** Vào [Marketplace](/vng-cloud-document/vn/ai-stack/agent-base/marketplace.md), chọn **OpenClaw**, điền API key và kênh chat — agent chạy trong vài phút.

**Tự build agent:** Đóng gói agent thành Docker image, push lên [Container Registry](/vng-cloud-document/vn/ai-stack/agent-base/container-registry.md), deploy qua [Agent Runtime](/vng-cloud-document/vn/ai-stack/agent-base/agent-runtime.md). Thêm credential trong [Access Control](/vng-cloud-document/vn/ai-stack/agent-base.md), gắn [MCP Gateway](/vng-cloud-document/vn/ai-stack/agent-base/mcp-governance/mcp-gateway.md) nếu agent cần gọi external tools.

***

## Dành cho ai?

| Đối tượng                   | AgentBase mang lại                                                      |
| --------------------------- | ----------------------------------------------------------------------- |
| **AI Engineer / Developer** | Tập trung viết logic agent — infra, credential, observability đã có sẵn |
| **Startup / Product Team**  | Ra mắt AI product nhanh hơn                                             |
| **Doanh nghiệp**            | Kiểm soát chi phí, phân quyền theo team, bảo mật credential theo chuẩn  |


# Lịch sử cập nhật

## Tháng 5, 2026

GreenNode AgentBase ra mắt **Phase 2** với các tính năng mới mở rộng khả năng quản trị, bảo mật và tích hợp cho AI Agent:

**Tính năng mới:**

* **Marketplace:** Browse và deploy AI agent từ thư viện template theo danh mục — AI Chat, Coding, Automation. Hỗ trợ filter, xem chi tiết và deploy 1 click.
  * Tìm hiểu thêm tại [Marketplace](/vng-cloud-document/vn/ai-stack/agent-base/marketplace.md).
* **Container Registry:** Kho lưu trữ container image riêng, được cấp phát tự động cho tổ chức. Hỗ trợ push image qua AgentBase Skills (khuyến nghị) hoặc Docker CLI thủ công; image dùng trực tiếp khi tạo Runtime.
  * Tìm hiểu thêm tại [Container Registry](/vng-cloud-document/vn/ai-stack/agent-base/container-registry.md).
* **Rate Limit:** Kiểm soát tần suất gọi API theo số request hoặc token trên từng model và API key, ngăn quá tải hệ thống và kiểm soát chi phí.
  * Tìm hiểu thêm tại [Rate Limit](/vng-cloud-document/vn/ai-stack/agent-base/protect-govern/rate-limit.md).
* **MCP Governance:** Kiểm soát tập trung kết nối giữa AI Agent và external service:
  * **MCP Gateway** — Proxy tập trung, tự động nhận diện protocol, áp dụng Policy và hỗ trợ Private mode qua VPC Peering.
  * **Policy Groups** — Bộ quy tắc Allow/Deny theo tool name, input pattern và output pattern.
  * Tìm hiểu thêm tại [MCP Governance](/vng-cloud-document/vn/ai-stack/agent-base/mcp-governance.md).
* **AI Coding:** Kết nối Claude Code CLI và các AI coding tool OpenAI-compatible (OpenAI SDK, LiteLLM, Cursor...) trực tiếp với GreenNode MaaS — thanh toán bằng credit-token nội bộ.
  * Tìm hiểu thêm tại [AI Coding](/vng-cloud-document/vn/ai-stack/agent-base/ai-coding.md).
* **Usage & Budget:** Dashboard theo dõi lượng tiêu thụ token và chi phí realtime theo agent, model, API key và khoảng thời gian; cài đặt ngân sách tháng với cảnh báo tự động khi đạt 80% và 100%.
  * Tìm hiểu thêm tại [Usage & Budget](/vng-cloud-document/vn/ai-stack/agent-base/usage-budget.md).
* **Mạng riêng tư (Private Networking):** VPC Peering cho Agent Runtime và MCP Gateway — cho phép agent kết nối đến internal service mà không cần expose ra internet.
  * Tìm hiểu thêm tại [Mạng riêng tư](/vng-cloud-document/vn/ai-stack/agent-base/private-networking.md).

***

## Tháng 4, 2026

GreenNode ra mắt **OpenClaw 1-Click** trên AgentBase, cho phép triển khai AI Agent cá nhân dựa trên OpenClaw ngay từ **Agent Marketplace** — không cần kiến thức kỹ thuật, không cần cài đặt thủ công, chỉ trong 40–60 giây.

**Tính năng mới:**

* **OpenClaw 1-Click:** Deploy OpenClaw instance trực tiếp từ Marketplace với cấu hình tối giản.
  * **Tự động kết nối GreenNode MaaS:** Tài khoản GreenNode được tự động cấp quyền truy cập model AI, không cần cấu hình API key thủ công. Model mặc định: **qwen3-5-27b**.
  * **BYOK — Bring Your Own Key:** Hỗ trợ mang API key từ provider bên ngoài (OpenAI, Anthropic, Gemini...).
  * **Tích hợp Channel:** Cấu hình kết nối Telegram và Zalo ngay trong bước deploy.
  * **My Agents:** Quản lý toàn bộ OpenClaw instance với filter theo trạng thái, stop, restart và xóa.
  * Tìm hiểu thêm tại [OpenClaw 1-Click](/vng-cloud-document/vn/ai-stack/agent-base/agent-runtime/openclaw/openclaw-1-click.md).

***

## Tháng 3, 2026

GreenNode AgentBase ra mắt **Phase 1** — nền tảng hạ tầng chuyên biệt dành cho AI Agent, giúp developer triển khai và vận hành AI Agent trên cloud mà không cần tự quản lý server, scaling hay credential.

**Tính năng mới:**

* **Agent Runtime:** Deploy agent dưới dạng container với autoscaling, versioning và zero-downtime deployment; hỗ trợ Custom Agent và OpenClaw 1-Click.
* **Access Control & Team Permissions:** Quản lý danh tính agent, tự động inject credentials vào container; phân quyền thành viên theo Role với Service Accounts.
* **Memory Service:** Lưu trữ lịch sử hội thoại (short-term) và trích xuất facts ngữ nghĩa (long-term).
* **GreenNode MaaS Integration:** Kết nối trực tiếp với LLM models qua API tương thích OpenAI.
* Tìm hiểu thêm tại [GreenNode AgentBase](/vng-cloud-document/vn/ai-stack/agent-base.md).

***










