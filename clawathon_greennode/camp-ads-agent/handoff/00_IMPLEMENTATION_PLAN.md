# 00 · Implementation Plan — Camp Ads Agent

## 1. Mục tiêu kỹ thuật cốt lõi

Thắng cuộc thi chấm-bằng-vote = **demo cực mượt + output ổn định khi người lạ test**. Thách thức lớn nhất: prototype dựng bằng Claude/GPT (mạnh) phải **rebuild lại bằng model GreenNode yếu hơn** mà không vỡ. Toàn bộ plan này xoay quanh việc **thu hẹp khoảng cách giữa model mạnh và model yếu**.

## 2. Nguyên lý "model-agnostic" — 5 trụ cột

Đây là phần quan trọng nhất. Model yếu (Qwen3.6-27b, Gemma-4-31b-it) làm được tương đương model mạnh **chỉ khi** ta tuân thủ 5 trụ:

### Trụ 1 — Đẩy logic ra khỏi model (deterministic-first)
Model **không** được quyết định những thứ có thể tính bằng code. Cụ thể:

| Việc | Ai làm | Vì sao |
|------|--------|--------|
| Phân loại camp tốt/xấu theo ngưỡng CTR/CPC/CR | **Python** (`logic/thresholds.py`) | Là phép so sánh số → model yếu hay sai số học |
| Match interest brief ↔ taxonomy DMP | **Python** (fuzzy/embedding match) | Tra cứu danh sách → không cần "suy luận" |
| Chọn bộ KPI theo funnel_stage | **Python** (lookup table) | Mapping cứng |
| Ước lượng size segment | **Python** (cộng size từ taxonomy) | Số học |
| Hiểu ngôn ngữ brief (NL → JSON) | **LLM** | Cần ngôn ngữ tự nhiên |
| Viết lời giải thích "vì sao camp xấu" | **LLM** | Cần diễn đạt |
| Soạn message cảnh báo AO | **LLM** | Cần văn phong |

> Quy tắc vàng: **LLM chỉ làm 3 việc — đọc hiểu, giải thích, soạn văn bản.** Mọi quyết định số/logic là của Python. Đây là lý do số 1 khiến Gemma chạy ngang Claude.

### Trụ 2 — Một cổng LLM duy nhất (`call_llm`)
Mọi lời gọi model đi qua đúng 1 hàm, chuẩn OpenAI. Đổi từ Claude → GreenNode MaaS = **đổi 1 file config**, không sửa code nghiệp vụ. Chi tiết ở [02_AGENT_SPEC](02_AGENT_SPEC.md).

### Trụ 3 — JSON contract + validate + repair
Mỗi bước trả JSON đúng schema (pydantic). Model yếu hay trả thừa chữ/sai format → ta:
1. Đưa JSON schema vào prompt + 1–2 few-shot.
2. `temperature` thấp (0–0.3) cho bước cần ổn định.
3. Nếu parse fail → **tự hỏi lại 1 lần** ("Chỉ trả JSON hợp lệ theo schema sau...").

### Trụ 4 — Few-shot thay cho "độ thông minh"
Model mạnh đoán đúng ý dù prompt mơ hồ; model yếu thì không. Bù lại bằng **ví dụ mẫu** trong prompt (input→output). Đây là cách "transfer" hành vi của Claude sang Gemma — xem [03_PROMPT_LIBRARY](03_PROMPT_LIBRARY.md).

### Trụ 5 — Eval gate trước khi deploy
Có [golden set 18 case](04_EVAL_SET.md). Sau khi đổi model, chạy eval → đo: % JSON hợp lệ, độ khớp field, accuracy phân loại. **Chỉ deploy khi parity đạt ngưỡng.** Biến "rebuild có ngang không" từ cảm tính thành con số.

## 3. Phân tầng model (chọn đúng việc)

| Bước | Loại việc | Model GreenNode | Ghi chú |
|------|-----------|-----------------|---------|
| 1 Nhận brief | NL → JSON | Qwen3.6-27b | Hội thoại, bóc tách |
| 2 Creative | Sinh text ngắn | Qwen3.6-27b | Nhẹ |
| 3 Audience/DMP | Giải thích match (logic ở Python) | Gemma-4-31b-it | Cần diễn giải gap |
| 4 Setup camp | Sinh JSON có cấu trúc | Gemma-4-31b-it | Ràng schema chặt |
| 5 Report analyze | Giải thích verdict (phân loại ở Python) | Gemma-4-31b-it | Mặc định repo mẫu |
| 6 AO alert | Soạn văn bản | Qwen3.6-27b | Văn phong |
| (DEV) sinh code | Code-gen nặng | MiniMax 2.5-229b | **Chỉ lúc build**, không trong runtime |

## 4. Lộ trình 2 pha

### Pha A — Pre-build bằng model xịn (từ nay → 09/06)
1. Builder dùng Claude Code/Codex + skill `camp-ads-agent` dựng full app 6 bước chạy trên mock data.
2. Ngay từ đầu **đặt model mặc định = Gemma-tương-đương** (hoặc test song song) để prompt không "lệ thuộc" độ thông minh của Claude.
3. Data chuẩn bị mock (2 brief, 500 camps, taxonomy DMP) + viết golden set eval.
4. Product chốt prompt library + JSON schema.
5. **Đầu ra pha A = chính gói handoff này + repo code chạy được.**

### Pha B — Rebuild trên GreenNode (10/06 → 17/06)
Theo [05_PORTING_RUNBOOK](05_PORTING_RUNBOOK.md):
- D0: nhận token → sửa `config/models.yaml` trỏ MaaS → chạy eval đo parity.
- D1–D2: tinh chỉnh prompt/few-shot cho chỗ Gemma kém (KHÔNG đổi kiến trúc).
- D3: end-to-end thông trên model BTC.
- D4–D5: polish UI + demo + con số hiệu quả.
- D6: freeze, deploy AgentBase, quay video.
- D7: nộp sớm.

## 5. Định nghĩa "Done" cho rebuild
- [ ] Eval parity ≥ 90% JSON hợp lệ, ≥ 95% accuracy phân loại camp (logic Python nên gần 100%), field-match ≥ 85% trên golden set.
- [ ] Chạy 10 lần liên tiếp không màn trống/lỗi.
- [ ] Agent ACTIVE trên AgentBase Runtime, `/health` 200.
- [ ] Demo "dùng thử ngay" người lạ hiểu < 30s.

## 6. Rủi ro porting & cách chặn
| Rủi ro | Chặn |
|--------|------|
| Gemma trả JSON lỗi | Schema-in-prompt + few-shot + repair retry + temperature thấp |
| Output kém hơn Claude | Đẩy thêm logic sang Python; thêm few-shot; KHÔNG đổi kiến trúc |
| Lệ thuộc tính năng chỉ model mạnh có | Test trên model yếu NGAY pha A |
| Hết giờ vì sửa lung tung | Eval gate + nguyên tắc "chỉ sửa prompt, không sửa kiến trúc" ở pha B |
