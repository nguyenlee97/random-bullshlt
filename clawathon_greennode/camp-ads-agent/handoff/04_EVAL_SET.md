# 04 · Eval Set — đo parity khi đổi model

Mục đích: biến câu hỏi "rebuild bằng Gemma có ngang Claude không?" thành **con số**. Chạy bộ này sau mỗi lần đổi model/sửa prompt.

## 1. Cách chấm (3 chỉ số)
1. **JSON valid %** — output parse được theo schema. Mục tiêu ≥ 90%.
2. **Field match %** — field quan trọng khớp expected (so khớp mềm cho text, khớp cứng cho enum/số). Mục tiêu ≥ 85%.
3. **Classification accuracy** — verdict camp đúng. Vì phân loại nằm ở Python nên mục tiêu ≥ 99% (lệch chỉ do bug).

Parity gate để deploy: cả 3 đạt ngưỡng trên golden set.

## 2. Cấu trúc 1 case (file `evals/cases.jsonl`)
```json
{"id":"brief_aw_01","step":"brief_parse","input":"<text brief>",
 "expect":{"funnel_stage":"awareness","brand":"Brand A",
           "kpi_contains":["CPM"],"budget_vnd":425000000}}
```
`expect` chỉ liệt kê field cần kiểm (không cần khớp 100% string với phần text tự do).

## 3. 18 case khuyến nghị (phủ đủ rủi ro)

### Bước 1 — brief_parse (5 case)
| id | Kiểm điều gì |
|----|--------------|
| brief_aw_01 | Brief Awareness đầy đủ → funnel=awareness, KPI có CPM/VTR |
| brief_cv_01 | Brief Conversion → funnel=conversion, KPI có CR/CPL |
| brief_missing_budget | Thiếu budget → budget_vnd=0, không crash |
| brief_mixed_lang | Brief lẫn Anh-Việt → vẫn bóc đúng target |
| brief_noisy | Brief dài lan man → vẫn ra JSON gọn |

### Bước 3 — segment/DMP (4 case)
| id | Kiểm |
|----|------|
| seg_all_match | Toàn interest có trong DMP → gaps rỗng |
| seg_with_gap | Có "Insurance"/"Du học" → gaps liệt kê đúng |
| seg_size | size_est đúng dải cộng từ taxonomy |
| seg_proxy | Có gap → explain đề xuất proxy |

### Bước 4 — setup_plan (2 case)
| id | Kiểm |
|----|------|
| setup_budget_split | tổng pct = 100 |
| setup_kpi_funnel | KPI target khớp funnel_stage |

### Bước 5 — report (4 case)
| id | Kiểm |
|----|------|
| rep_good | camp CTR cao → verdict=good |
| rep_bad_cpc | CPC vượt ngưỡng → verdict=bad |
| rep_watch | nằm giữa → verdict=watch |
| rep_batch20 | 20 camp/lần → không vỡ JSON, đếm đúng |

### Bước 6 — ao_alert (3 case)
| id | Kiểm |
|----|------|
| alert_has_camps | message liệt kê đúng camp bad |
| alert_empty | không camp xấu → message "tất cả ổn" |
| alert_tone | tiếng Việt, có khuyến nghị tổng |

## 4. Runner mẫu (`evals/run.py`)
```python
import json, jsonschema
from app.steps import pipeline   # hàm chạy 1 bước theo step name

def run():
    total, jvalid, fmatch = 0, 0, 0
    for line in open("evals/cases.jsonl", encoding="utf-8"):
        c = json.loads(line); total += 1
        out = pipeline.run_step(c["step"], c["input"])  # gọi call_llm thật
        try: data = json.loads(out); jvalid += 1
        except: 
            print("JSON FAIL", c["id"]); continue
        if match_expect(data, c["expect"]): fmatch += 1
        else: print("FIELD MISS", c["id"])
    print(f"JSON valid: {jvalid}/{total}  Field match: {fmatch}/{total}")
```

## 5. Workflow dùng eval khi porting
1. Pha A: chạy eval bằng model mạnh → lưu baseline (vd 18/18).
2. Pha B: đổi `models.yaml` sang GreenNode → chạy lại.
3. Case nào rớt → mở [03_PROMPT_LIBRARY](03_PROMPT_LIBRARY.md), thêm few-shot/hạ temp cho đúng bước đó.
4. Lặp tới khi đạt gate. **Không sửa kiến trúc, chỉ sửa prompt.**
