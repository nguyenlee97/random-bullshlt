# Báo cáo production model — VoltRide × MộcAn Dairy

## Mục đích

Artifact này dùng để kiểm tra riêng bước report, không cần chạy lại toàn bộ workflow lập kế hoạch media. Mỗi brief được chuẩn hóa thành Measurement Spec, sinh một bộ campaign facts nhất quán, tạo Evidence Contract, sau đó gửi contract sang Agent production đang khóa model `openai_gpt_5_4_mini`.

Phần facts, KPI status và action có guardrail thuộc quyền sở hữu của contract. GPT-5.4-mini đọc evidence để viết câu trả lời theo ngữ cảnh; output sau đó được ground lại về metric canonical và validate trước khi hiển thị.

## VoltRide

- Objective: Conversion.
- Thời gian: 20/08/2026–23/09/2026, đủ 35 ngày theo brief.
- Ngân sách: 450 triệu VND.
- Business funnel: đăng ký lái thử → đủ điều kiện → đến lái thử → đặt cọc → purchase.
- Trạng thái tổng thể: BAD; 0 KPI đạt, 3 KPI Watch, 2 KPI Bad.
- Insight chính của model: phễu rơi mạnh ở các bước giữa và cuối; số đăng ký đủ điều kiện và số đặt cọc chưa đạt.
- Zone đáng thử tiếp: `zalo_news_native`, được chọn theo business outcome và cost-per-outcome, không chỉ theo CTR.

## MộcAn Dairy

- Objective: Conversion.
- Brief chỉ ghi “3 tuần”, nên artifact giả định 10/08/2026–30/08/2026 để có một cửa sổ đúng 21 ngày.
- Ngân sách: 250 triệu VND.
- Business funnel: lead/subscription → lead chất lượng → đăng ký gói giao sữa.
- Cụm “~5.000 lead/đơn” được diễn giải là mục tiêu top-funnel gồm lead hoặc đăng ký subscription; đây là giả định cần xác nhận với user/business owner.
- Trạng thái tổng thể: BAD; 1 KPI Good, 1 KPI Watch, 1 KPI Bad.
- Insight chính của model: CVR vượt 4%, nhưng volume chỉ đạt 2.182/5.000 và CPL là 97.388 VND so với mục tiêu 85.000 VND.
- Zone đáng thử tiếp: `zalo_retargeting_mobile`, được chọn theo business outcome và cost-per-outcome.
- ROAS để ở N/A vì brief không cung cấp giá trị gói, doanh thu ghi nhận, hoàn/huỷ và quy tắc attribution doanh thu. Không tự bịa ROAS.

## Cách đọc

1. KPI scorecard trả lời “campaign có đạt brief không?”.
2. Funnel trả lời “rơi ở bước business nào?”.
3. Zone efficiency trả lời “nên giữ, thử hay giảm ở đâu?” bằng outcome và chi phí/outcome.
4. GPT analysis trả lời bằng ngôn ngữ tự nhiên nhưng metric và status được contract ground lại.
5. Action Ledger luôn có problem, proposed action, expected movement, guardrail và review window.

## Provenance

Cả hai output được lấy từ Agent API production, model thực tế trả về là `gpt-5.4-mini`, có tool `search_ad_knowledge`, và đều qua schema/evidence validation ở attempt 1. Artifact không lưu conversation ID, cookie, CSRF token hay secret.

## Giới hạn

Các campaign facts trong bài test là scenario facts nhất quán được tạo để kiểm tra quyết định và chất lượng phân tích; không phải log delivery từ ad server. Không sử dụng market benchmark bên ngoài. Các action cần được operator review và đo lại trong cửa sổ có kiểm soát trước khi scale.
