# 02 · Agent Spec — kiến trúc & hợp đồng

## 1. Sơ đồ tổng thể

```
[ Browser UI (chat + upload) ]
            |  HTTP / WS
            v
[ FastAPI :8080  + GET /health -> 200 ]
            |
   ┌────────┴─────────────────────────────────────┐
   |  Orchestrator (steps/pipeline.py)            |
   |  chạy tuần tự 6 bước, validate JSON mỗi bước |
   └───┬───────────────┬──────────────────────────┘
       |               |
       v               v
[ logic/* Python ]  [ llm.py: call_llm(task, messages) ]
  - thresholds          |  chuẩn OpenAI
  - dmp_match           v
  - kpi_table     [ GreenNode MaaS /v1 ]  (đổi model ở config/models.yaml)
```

Bám khuôn repo mẫu BTC (Interview Assistant): FastAPI + UI thuần + gọi MaaS qua OpenAI SDK. **Không** dùng framework agent nặng (LangChain/AutoGen) — thừa cho 6 bước tuần tự và khó debug khi đổi model.

## 2. Cổng LLM duy nhất — `llm.py`

```python
# app/llm.py
import os, yaml, json
from openai import OpenAI

_CFG = yaml.safe_load(open("config/models.yaml"))
_client = OpenAI(
    base_url=os.environ["MAAS_BASE_URL"],   # https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
    api_key=os.environ["MAAS_API_KEY"],
)

def call_llm(task: str, messages: list, *, json_schema: dict | None = None,
             temperature: float | None = None) -> str:
    m = _CFG["tasks"][task]               # {model, temperature}
    resp = _client.chat.completions.create(
        model=m["model"],                 # giá trị PATH của model trên MaaS
        messages=messages,
        temperature=temperature if temperature is not None else m["temperature"],
    )
    return resp.choices[0].message.content

def call_llm_json(task: str, messages: list, schema: dict, *, retries: int = 1):
    """Gọi + parse JSON; nếu fail thì hỏi lại tối đa `retries` lần."""
    last = ""
    for attempt in range(retries + 1):
        last = call_llm(task, messages, temperature=0.1)
        try:
            return json.loads(_strip_fences(last))
        except Exception:
            messages = messages + [
                {"role": "user",
                 "content": f"Output vừa rồi KHÔNG phải JSON hợp lệ. "
                            f"CHỈ trả về đúng JSON theo schema: {json.dumps(schema)}"}
            ]
    raise ValueError(f"Bad JSON after retries: {last[:200]}")
```

> **Đây là điểm swap model.** Pre-build trỏ `MAAS_BASE_URL` về provider model xịn; rebuild chỉ đổi env + `models.yaml`. Code nghiệp vụ không động tới.

## 3. `config/models.yaml`

```yaml
# Pha A (pre-build) có thể trỏ model mạnh; Pha B trỏ model GreenNode.
tasks:
  brief_parse:   { model: "Qwen/Qwen3.6-27b",      temperature: 0.1 }
  creative:      { model: "Qwen/Qwen3.6-27b",      temperature: 0.7 }
  segment_explain:{ model: "google/gemma-4-31b-it", temperature: 0.2 }
  setup_plan:    { model: "google/gemma-4-31b-it", temperature: 0.1 }
  report_explain:{ model: "google/gemma-4-31b-it", temperature: 0.2 }
  ao_alert:      { model: "Qwen/Qwen3.6-27b",      temperature: 0.4 }
# Lưu ý: giá trị `model` là PATH chính xác của model trên MaaS — xác nhận tại training 10/06.
```

## 4. JSON contract — `app/schemas.py` (pydantic)

```python
from pydantic import BaseModel
from typing import Literal

class Target(BaseModel):
    age: str; gender: str; location: str
    interests: list[str]; behaviors: list[str] = []

class Brief(BaseModel):
    brand: str; objective: str
    funnel_stage: Literal["awareness","consideration","conversion"]
    target: Target; budget_vnd: int; flight: str
    kpi: list[str]; format: list[str]

class Segment(BaseModel):
    matched: list[str]; size_est: str; gaps: list[str]

class CampVerdict(BaseModel):
    camp_id: str; verdict: Literal["good","watch","bad"]; reason: str

class AgentOutput(BaseModel):
    brief: Brief; segment: Segment
    setup_plan: dict; kpi_target: dict
    report_eval: list[CampVerdict]; ao_alert: str
```

## 5. 6 bước — phân chia LLM vs Python

| Bước | Module | LLM (task) | Python (logic) |
|------|--------|-----------|----------------|
| 1 Brief | `steps/s1_brief.py` | `brief_parse` → Brief JSON | validate funnel, default KPI nếu thiếu |
| 2 Creative | `steps/s2_creative.py` | `creative` → 3–5 angle | — |
| 3 Segment | `steps/s3_segment.py` | `segment_explain` (diễn giải) | `logic/dmp_match.py`: match interest ↔ taxonomy, cộng size, tìm gap |
| 4 Setup | `steps/s4_setup.py` | `setup_plan` → JSON plan | `logic/budget.py`: chia ngân sách, validate bid hợp lệ |
| 5 Report | `steps/s5_report.py` | `report_explain` (lý do) | `logic/thresholds.py`: phân loại good/watch/bad theo CTR/CPC/CR |
| 6 Alert | `steps/s6_alert.py` | `ao_alert` → message | gom camp `bad`/`watch` làm input |

> Mẫu chuẩn mỗi bước: **Python tính trước → đưa kết quả số vào prompt → LLM chỉ diễn giải/soạn chữ.** Ví dụ bước 5: Python đã gắn nhãn good/bad; LLM chỉ viết "vì sao". Model yếu không thể sai phân loại vì nó không phân loại.

## 6. `logic/thresholds.py` (ví dụ — quyết định KHÔNG để cho LLM)

```python
RULES = {  # ngưỡng demo, chỉnh theo nghiệp vụ
    "ctr_good": 0.015, "ctr_bad": 0.005,
    "cpc_bad": 3000,   "cr_good": 0.02, "cr_bad": 0.005,
}
def classify(c):  # c: dict 1 camp
    if c["ctr"] >= RULES["ctr_good"] and c["cr"] >= RULES["cr_good"]:
        return "good"
    if c["ctr"] < RULES["ctr_bad"] or c["cpc"] > RULES["cpc_bad"] or c["cr"] < RULES["cr_bad"]:
        return "bad"
    return "watch"
```

## 7. Hợp đồng bắt buộc với AgentBase Runtime
- Container nghe `0.0.0.0:8080`; có `GET /health` trả `200`.
- Runtime tự inject `GREENNODE_CLIENT_ID/SECRET/AGENT_IDENTITY`; đọc user/session qua header `X-GreenNode-AgentBase-User-Id`, `X-GreenNode-AgentBase-Session-Id`.
- Không hardcode key — đăng ký ở Access Control, `.env` vào `.gitignore`.
- Cân nhắc SDK `pip install greennode-agentbase` (tự lo `/health` + context).
- Image: `vcr.vngcloud.vn/{backendName}/camp-ads-agent:{tag}`.

> Mọi endpoint/giá trị model là theo tài liệu tại thời điểm research — **xác nhận lại tại training 10/06.**
