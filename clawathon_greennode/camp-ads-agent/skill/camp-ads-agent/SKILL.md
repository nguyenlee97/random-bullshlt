---
name: camp-ads-agent
description: >
  Build, extend, or port the "Camp Ads Agent" hackathon agent (Adtima ad-campaign
  automation) in a MODEL-AGNOSTIC way so prototypes made with strong models (Claude/GPT)
  rebuild correctly on GreenNode's weaker models (Qwen3.6-27b, Gemma-4-31b-it, MiniMax 2.5-229b).
  Use when: scaffolding the FastAPI agent, adding/editing any of the 6 pipeline steps,
  writing prompts for weak models, defining JSON schemas, wiring call_llm, building the
  threshold/DMP/KPI logic, or running the eval parity gate before deploying to AgentBase.
---

# Camp Ads Agent — build skill (model-agnostic)

Áp dụng các convention này MỖI KHI sinh hoặc sửa code cho Camp Ads Agent. Mục tiêu tối thượng: code chạy bằng Claude/GPT phải rebuild ngang bằng trên Qwen/Gemma.

## Luật bất biến (không được vi phạm)

1. **Deterministic-first.** LLM chỉ làm 3 việc: đọc-hiểu (NL→JSON), giải thích, soạn văn bản. MỌI quyết định số/logic (phân loại camp theo ngưỡng, match DMP, chọn KPI theo funnel, ước lượng size, chia ngân sách) phải viết bằng Python trong `app/logic/`, KHÔNG để LLM tính.

2. **Một cổng LLM duy nhất.** Mọi lời gọi model đi qua `app/llm.py::call_llm(task, messages, ...)` chuẩn OpenAI. Model được chọn qua `config/models.yaml` theo `task`. Không gọi SDK model trực tiếp ở nơi khác. Đổi model = sửa config, không sửa code nghiệp vụ.

3. **JSON contract + validate + repair.** Mỗi bước trả JSON đúng pydantic schema ở `app/schemas.py`. Prompt phải: (a) dán schema, (b) "CHỈ trả JSON", (c) kèm ≥1 few-shot. Dùng `call_llm_json(..., retries=1)` để tự hỏi lại khi parse fail. `temperature` ≤ 0.2 cho bước cần ổn định.

4. **Few-shot thay cho độ thông minh.** Khi viết/sửa prompt, luôn kèm ví dụ input→output. Đây là cách "transfer" hành vi model mạnh sang model yếu.

5. **Eval gate.** Sau khi sinh/sửa bất kỳ bước nào, cập nhật `evals/cases.jsonl` và chạy `python -m evals.run`. Không coi là "xong" nếu chưa đạt: JSON valid ≥ 90%, classification accuracy ≥ 99%, field match ≥ 85%.

## Kiến trúc bắt buộc

```
app/main.py        FastAPI, GET /health -> 200, lắng nghe 0.0.0.0:8080
app/llm.py         call_llm / call_llm_json  (cổng duy nhất)
app/schemas.py     pydantic: Brief, Target, Segment, CampVerdict, AgentOutput
app/steps/         s1_brief, s2_creative, s3_segment, s4_setup, s5_report, s6_alert, pipeline
app/logic/         thresholds.py, dmp_match.py, kpi_table.py, budget.py   (KHÔNG gọi LLM)
app/ui/            index.html + styles.css (vanilla JS, không framework nặng)
config/models.yaml map task -> {model path, temperature}
data/              briefs/, dmp_taxonomy.csv, camps_report.csv, gen_camps.py
evals/             cases.jsonl, run.py
Dockerfile
```

## Quy tắc cho từng bước
- Bước 3/5 (hero): Python tính trước (match/classify) → bơm KẾT QUẢ vào prompt → LLM chỉ viết explain/reason, KHÔNG đổi verdict/gap.
- Bước 5: xử lý report theo batch ~20 camp/lần; camp `good` không gửi LLM (chỉ đếm).
- Bước 4: KPI target chọn bằng `logic/kpi_table.py` theo `funnel_stage`, không hỏi LLM.

## Khi porting sang model yếu (bậc thang, dừng khi đạt parity)
1. temperature → 0.0–0.1
2. thêm few-shot vào đúng prompt rớt
3. `retries=2`
4. đẩy thêm logic số/format sang Python
5. đổi sang model khác trong 3 model BTC cho task đó
KHÔNG leo thang sang đổi kiến trúc / thêm framework.

## Hợp đồng AgentBase Runtime
- `/health` 200, port 8080 cố định.
- Không hardcode key; đọc qua env `MAAS_BASE_URL`, `MAAS_API_KEY`; `.env` vào `.gitignore`.
- Image: `vcr.vngcloud.vn/{backendName}/camp-ads-agent:{tag}`.
- Deploy ưu tiên dùng skill pack chính chủ BTC (`/agentbase-wizard`, `/agentbase-deploy`, `/agentbase-monitor`).

## Tham chiếu
Xem `references/conventions.md` để biết chi tiết schema, ngưỡng mẫu, và mẫu prompt đầy đủ. Tài liệu nghiệp vụ đầy đủ ở `../../handoff/`.
