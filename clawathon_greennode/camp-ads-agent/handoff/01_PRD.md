# 01 · PRD — Camp Ads Agent

## 1. Một câu định vị
Camp Ads Agent là **trợ lý hội thoại tự động hóa toàn bộ vòng đời một chiến dịch quảng cáo Adtima** — từ brief khách → tạo audience segment trên DMP → setup camp → phân tích báo cáo 500 camps → soạn cảnh báo cho team AO — chạy hoàn toàn trên dữ liệu giả lập.

## 2. Vấn đề
Vận hành ads Adtima hiện tốn người ở 2 chỗ: (1) dịch brief khách thành audience segment đúng (DMP thường thiếu tệp khách cần) và (2) đọc tay hàng trăm báo cáo camp để biết camp nào cần cứu rồi báo AO. Việc lặp lại, dễ sót, không scale.

## 3. Người dùng & ngữ cảnh cuộc thi
- **Người dùng demo (voter)**: nhân viên VNG, phần lớn không phải dân ads. → Sản phẩm phải tự giải thích, test được trong 30 giây bằng mock data.
- **Người dùng thật (giả định)**: Campaign Operation (AO), Account, Planner của Adtima.
- **Tiêu chí chấm**: 100% community vote trên 3 trục — **tính khả thi · tính hữu dụng · tính hiệu quả**.

## 4. Scope (làm gì / không làm gì)
**Trong scope (6 bước):** nhận brief, gợi ý creative (text), tạo audience segment + báo gap (DMP), setup plan, phân tích report, cảnh báo AO.
**Hero (đầu tư AI sâu):** bước 3 (Audience/DMP), bước 5 (Report), bước 6 (AO alert).
**Ngoài scope:** gọi API production Adtima; render ảnh banner thật; tích hợp CRM/Zalo thật. → mock hết.

## 5. User stories (rút gọn)
- Là planner, tôi dán brief khách → agent bóc tách objective/funnel/target/budget/KPI thành cấu trúc rõ ràng.
- Là planner, tôi muốn agent map target sang tệp DMP có sẵn, **ước lượng size** và **chỉ rõ tệp nào DMP chưa có** để tôi biết phải bổ sung.
- Là AO, tôi thả file 500 camps → agent xếp hạng tốt/xấu kèm lý do và **soạn sẵn message cảnh báo** camp cần xử lý.

## 6. Yêu cầu sản phẩm
### Chức năng
- F1 Chat nhận brief, hỗ trợ 2 funnel: Awareness & Conversion (đổi bộ KPI theo funnel).
- F2 Gợi ý 3–5 angle/headline creative từ brief.
- F3 Audience segment: matched interests + size ước lượng + danh sách gap.
- F4 Setup plan: zone, bid, lịch, chia ngân sách (bảng/JSON).
- F5 Report analyzer: upload CSV 500 camps → bảng verdict + lý do.
- F6 AO alert: message ngắn (Slack/email mock) + khuyến nghị hành động.

### Phi chức năng (quan trọng cho vote)
- N1 **Ổn định**: chạy 10+ lần không lỗi, output không đổi dạng.
- N2 **Tự giải thích**: nút "dùng thử ngay" + mock data nạp sẵn.
- N3 **Định lượng hiệu quả**: hiển thị con số tiết kiệm (vd "20 giây thay vì 2 giờ").
- N4 **Model-agnostic**: chạy được trên model GreenNode yếu (xem 00).
- N5 **Tuân thủ AgentBase**: `/health`, port 8080, không hardcode key.

## 7. Tiêu chí thành công (đo được)
| Trục vote | Cách sản phẩm "ghi điểm" |
|-----------|--------------------------|
| Khả thi | Demo chạy thật, deploy thật trên AgentBase, mock data trông như thật |
| Hữu dụng | Giải đúng pain "đọc 500 camps" + "DMP thiếu tệp" — ai cũng hiểu |
| Hiệu quả | Con số tiết kiệm cụ thể + chạy rẻ trên model nhẹ |

## 8. Track nộp
**Automation & Integration** (cánh tay nối dài), nhưng phô diễn cả 3 năng lực: chat (nhận brief) + automation (setup) + data insight (report).
