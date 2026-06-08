# 06 · UI Design Spec — thiết kế giao diện kéo vote

> Voting page chấm bằng ấn tượng 30 giây. UI phải **tự kể chuyện**: người lạ mở lên là hiểu ngay agent làm gì và thấy "wow".

## 1. Nguyên tắc thiết kế
- **Một màn, một luồng**: chat bên trái, kết quả bên phải; cuộn dọc theo 6 bước.
- **Nút "Dùng thử ngay với mock data"** to, đặt đầu trang — bỏ qua mọi setup.
- **Mỗi bước có "wow" trực quan**: bảng có màu, badge good/bad, con số lớn.
- **Hiển thị con số hiệu quả** cố định ở header: "20 giây thay vì 2 giờ".
- Tiếng Việt, sạch, ít chữ. Tông xanh GreenNode/Adtima.

## 2. Sơ đồ màn hình (wireframe)

```
┌────────────────────────────────────────────────────────────┐
│  Camp Ads Agent      [▶ Dùng thử ngay]   ⏱ 20s thay vì 2h   │  header
├──────────────────────────┬─────────────────────────────────┤
│  CHAT (trái)             │  KẾT QUẢ (phải, theo bước)        │
│                          │                                   │
│  🧑 dán brief...         │  ① Brief đã bóc tách  [card JSON] │
│  🤖 Đã hiểu! funnel...   │  ② Creative  [3 thẻ angle]        │
│  [ô nhập / nút mẫu A B]  │  ③ Audience/DMP                   │
│                          │     matched ▦▦▦  size 2.1M-2.6M   │
│                          │     ⚠ Gap: Insurance, Du học      │
│                          │  ④ Setup plan [bảng zone/bid]     │
│                          │  ⑤ Report 500 camps               │
│                          │     [bảng: ●good ●watch ●bad +lý do]│
│                          │  ⑥ Cảnh báo AO  [khung message]   │
└──────────────────────────┴─────────────────────────────────┘
```

## 3. Component chính
| Component | Mô tả | Ghi chú "wow" |
|-----------|-------|---------------|
| Brief card | hiển thị Brief JSON dạng đẹp (chip funnel, target, KPI) | badge màu theo funnel |
| Creative cards | 3–5 thẻ angle + headline | — |
| Segment panel | thanh matched + size lớn + **box cảnh báo gap màu đỏ** | gap là điểm nhấn nghiệp vụ |
| Setup table | zone / bid / lịch / % ngân sách | tổng % = 100 hiển thị rõ |
| Report table | 500 dòng, cột verdict có chấm màu, sort theo verdict | filter "chỉ xem cần cứu" |
| KPI strip | đếm good/watch/bad + % | số lớn, đập vào mắt |
| AO alert box | khung như Slack message + nút "Copy" | cảm giác "gửi được luôn" |

## 4. Bảng màu verdict (nhất quán toàn app)
| Nhãn | Màu nền | Màu chữ | Ý nghĩa |
|------|---------|---------|---------|
| good | `#EAF3DE` | `#27500A` | ổn, giữ nguyên |
| watch | `#FAEEDA` | `#854F0B` | theo dõi |
| bad | `#FCEBEB` | `#A32D2D` | cần xử lý ngay |

## 5. Luồng demo 60–90s (kịch bản quay video)
1. (0–10s) Mở app → bấm "Dùng thử ngay" → chọn **Brief Brand A (Awareness)**.
2. (10–25s) Agent bóc brief → tạo segment → **chỉ ra DMP thiếu tệp** (khoảnh khắc nghề).
3. (25–40s) Sinh setup plan tự động.
4. (40–65s) Thả file **500 camps** → 20 giây sau ra bảng good/bad + KPI strip.
5. (65–85s) Hiện **message cảnh báo AO** soạn sẵn → bấm Copy.
6. (85–90s) Chốt câu: "Đọc 500 báo cáo & cảnh báo AO trong 30 giây, chạy trên model nhẹ của GreenNode."

## 6. File thiết kế nên kèm trong repo
- `app/ui/index.html` (1 file, vanilla JS — bám repo mẫu BTC, không framework nặng).
- `app/ui/styles.css` (dùng bảng màu trên).
- `design/wireframe.png` hoặc figma link (tùy chọn).
- Nếu muốn nhanh: tái dùng layout của `Camp Ads Agent - Clawathon.html` làm cảm hứng tông màu/typography.

## 7. Tự kiểm UI trước nộp
- [ ] Người chưa biết gì mở lên hiểu trong 30s.
- [ ] Có nút dùng thử + mock nạp sẵn (không bắt nhập tay).
- [ ] Con số hiệu quả hiển thị rõ.
- [ ] Bảng report sort/filter được "camp cần cứu".
- [ ] AO message copy được.
- [ ] Chạy 10 lần không màn trống/lỗi.
