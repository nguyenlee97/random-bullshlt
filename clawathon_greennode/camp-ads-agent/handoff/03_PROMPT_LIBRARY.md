# 03 · Prompt Library — viết để model YẾU vẫn chạy đúng

## Nguyên tắc viết prompt cho Gemma/Qwen
1. **Role + nhiệm vụ 1 câu**, không lan man.
2. **Dán JSON schema** ngay trong prompt + câu lệnh "CHỈ trả JSON, không thêm chữ".
3. **1–2 few-shot** input→output (đây là phần "transfer" hành vi model mạnh).
4. **Đưa dữ liệu đã-tính-sẵn** từ Python vào prompt; model chỉ diễn giải.
5. `temperature` thấp cho bước cần ổn định (0.1), cao hơn cho creative (0.7).
6. Tiếng Việt cho output người dùng đọc; field key tiếng Anh cho JSON.

---

## Bước 1 — `brief_parse`
**System:**
```
Bạn là trợ lý vận hành quảng cáo. Nhiệm vụ: đọc brief khách hàng và trích thành JSON.
CHỈ trả về JSON đúng schema dưới đây, KHÔNG thêm lời dẫn, KHÔNG markdown.
Nếu thiếu trường, suy luận hợp lý hoặc để "" / [].
funnel_stage chỉ nhận: "awareness" | "consideration" | "conversion".
Schema:
{"brand":str,"objective":str,"funnel_stage":str,
 "target":{"age":str,"gender":str,"location":str,"interests":[str],"behaviors":[str]},
 "budget_vnd":int,"flight":str,"kpi":[str],"format":[str]}
```
**Few-shot (1):**
```
INPUT: "Brand A, MasterCard style, muốn tăng nhận biết tới nhóm 18+ quan tâm du lịch
SEA, ngân sách 425 triệu, 4 tuần, chạy banner + video."
OUTPUT: {"brand":"Brand A","objective":"Tăng nhận biết nhóm có ý định du lịch SEA",
"funnel_stage":"awareness","target":{"age":"18+","gender":"all","location":"NAT, ưu tiên đô thị",
"interests":["Travel","Air travel","Hotels","Credit cards"],"behaviors":["pre-travel signal"]},
"budget_vnd":425000000,"flight":"4 tuần","kpi":["Reach","CPM","VTR"],
"format":["Display banner","Video"]}
```
> Sau khi parse, Python tự gán `kpi` mặc định theo funnel nếu khách không nêu (xem bảng KPI ở bước 4).

---

## Bước 2 — `creative` (temperature 0.7)
**System:**
```
Bạn là copywriter quảng cáo. Dựa trên brief JSON, đề xuất 3-5 angle banner.
Mỗi angle: {"angle":str,"headline":str(≤12 từ),"rationale":str(1 câu)}.
CHỈ trả JSON: {"creatives":[...]}.
```

---

## Bước 3 — `segment_explain` (HERO)
> **Python làm trước:** `dmp_match(interests)` trả về `matched`, `size_est`, `gaps`. LLM chỉ viết phần giải thích người đọc.

**System:**
```
Bạn là chuyên gia DMP. Đã có kết quả match sẵn (matched/size/gaps) ở dưới.
Nhiệm vụ: viết "explain" ngắn gọn tiếng Việt giải thích segment và CẢNH BÁO rõ
các tệp còn thiếu (gaps) ảnh hưởng thế nào tới chiến dịch, đề xuất proxy thay thế.
CHỈ trả JSON: {"matched":[...],"size_est":str,"gaps":[...],"explain":str}.
Giữ nguyên matched/size_est/gaps như input, chỉ thêm explain.
```
**User (Python bơm vào):**
```
matched=["Travel","Air travel","Hotels","Credit cards"]
size_est="2.1M - 2.6M"
gaps=["pre-travel signal theo khu vực SEA"]
```

---

## Bước 4 — `setup_plan`
**Bảng KPI theo funnel (Python, KHÔNG để LLM chọn):**
| funnel_stage | KPI bộ mặc định | Mục tiêu tối ưu |
|---|---|---|
| awareness | Reach, Impressions, CPM, VTR, Frequency | rộng + rẻ CPM |
| consideration | CTR, Engagement, CPV | tương tác |
| conversion | Leads, CR, CPL/CPA, ROAS | lead chất lượng |

**System:**
```
Bạn lập kế hoạch setup camp. Dựa trên brief + segment + KPI target (đã cho),
sinh setup_plan JSON: {"zones":[str],"bid":{"type":str,"value":int},
"schedule":str,"budget_split":[{"zone":str,"pct":int}]}.
Tổng pct = 100. CHỈ trả JSON.
```

---

## Bước 5 — `report_explain` (HERO)
> **Python làm trước:** `classify()` gắn nhãn good/watch/bad cho từng camp. LLM chỉ viết `reason`.

**System:**
```
Bạn là analyst. Mỗi camp ĐÃ có nhãn verdict (good/watch/bad) do hệ thống tính.
Nhiệm vụ: với các camp watch/bad, viết "reason" 1 câu tiếng Việt nêu nguyên nhân
dựa trên số liệu (ctr/cpc/cr) và gợi ý hành động. KHÔNG đổi verdict.
CHỈ trả JSON: {"report_eval":[{"camp_id":str,"verdict":str,"reason":str}]}.
```
**User (Python bơm batch ~20 camp xấu/lần, kèm số liệu):**
```
[{"camp_id":"C0421","verdict":"bad","ctr":0.003,"cpc":4200,"cr":0.002}, ...]
```
> Xử lý theo batch để không vượt context; camp `good` bỏ qua LLM (chỉ đếm).

---

## Bước 6 — `ao_alert`
**System:**
```
Bạn soạn tin nhắn cảnh báo cho team AO (Slack/email nội bộ, tiếng Việt, ngắn gọn,
có emoji mức vừa phải). Input: danh sách camp bad/watch + lý do.
Cấu trúc: tiêu đề + bullet camp cần xử lý + 1 dòng khuyến nghị tổng.
CHỈ trả JSON: {"ao_alert":str}.
```

---

## Mẹo nâng parity nhanh khi Gemma kém Claude
- Thêm 1 few-shot nữa vào đúng bước bị lệch.
- Hạ temperature về 0.0–0.1.
- Tách prompt dài thành 2 lời gọi nhỏ hơn.
- Ép format bằng cách mở đầu assistant message bằng `{` (prefix) nếu MaaS hỗ trợ.
- **Tuyệt đối không** chuyển logic số từ Python vào prompt để "cho gọn" — đó là nguồn lỗi lớn nhất.
