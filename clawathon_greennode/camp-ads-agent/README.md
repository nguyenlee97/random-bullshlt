# Camp Ads Agent — Gói triển khai & bàn giao (Handoff Package)

> Đội **Pawgrammers** · GreenNode Claw-a-thon 2026
> Mục tiêu của gói này: **làm sẵn bằng model xịn (Claude/GPT), bàn giao bằng tài liệu để rebuild lại bằng model yếu hơn của GreenNode (Qwen3.6-27b / Gemma-4-31b-it / MiniMax 2.5-229b) mà chất lượng vẫn tương đương.**

## Triết lý 1 dòng

> Model xịn dựng **bộ khung + prompt + logic**; model yếu chỉ điền vào **các ô trống hẹp, ràng buộc chặt**. Càng nhiều logic nằm ở Python (deterministic) và càng siết JSON contract, khoảng cách Claude ↔ Gemma càng nhỏ.

## Đọc theo thứ tự

| # | File | Dành cho ai | Nội dung |
|---|------|-------------|----------|
| 0 | [handoff/00_IMPLEMENTATION_PLAN.md](handoff/00_IMPLEMENTATION_PLAN.md) | Cả team | Lộ trình, kiến trúc model-agnostic, vì sao model yếu vẫn làm được |
| 1 | [handoff/01_PRD.md](handoff/01_PRD.md) | Product/PM | Vấn đề, người dùng, scope, tiêu chí thắng vote |
| 2 | [handoff/02_AGENT_SPEC.md](handoff/02_AGENT_SPEC.md) | Builder | Kiến trúc 6 bước, `call_llm()`, hợp đồng AgentBase Runtime |
| 3 | [handoff/03_PROMPT_LIBRARY.md](handoff/03_PROMPT_LIBRARY.md) | Builder/Prompt | Prompt từng bước + few-shot + JSON schema cho model yếu |
| 4 | [handoff/04_EVAL_SET.md](handoff/04_EVAL_SET.md) | Cả team | 18 case input→expected để đo parity khi đổi model |
| 5 | [handoff/05_PORTING_RUNBOOK.md](handoff/05_PORTING_RUNBOOK.md) | Builder | Quy trình swap model + rebuild trong 7 ngày |
| 6 | [handoff/06_UI_DESIGN_SPEC.md](handoff/06_UI_DESIGN_SPEC.md) | Builder/Demo | Màn hình, component, luồng demo kéo vote |
| 7 | [handoff/07_MOCK_DATA_SPEC.md](handoff/07_MOCK_DATA_SPEC.md) | Data | 2 brief, schema 500 camps, taxonomy DMP |

## Skill

- [skill/camp-ads-agent/](skill/camp-ads-agent/) — skill tùy biến để Claude Code/Codex build agent đúng convention model-agnostic.
- Khuyến nghị **dùng kèm** skill pack chính chủ của BTC: `github.com/vngcloud/greennode-agentbase-skills` (`/agentbase-wizard`, `/agentbase-deploy`, `/agentbase-monitor`) để deploy — không tự dựng lại.

## Quy ước thư mục khi build

```
camp-ads-agent-app/            # repo code thật (Builder tạo)
├── app/
│   ├── main.py                # FastAPI + /health (port 8080)
│   ├── llm.py                 # call_llm() — cổng LLM duy nhất
│   ├── steps/                 # 6 bước, mỗi bước 1 module
│   ├── schemas.py             # pydantic models (JSON contract)
│   ├── logic/                 # rule deterministic (thresholds, DMP match, KPI)
│   └── ui/                    # static UI
├── config/models.yaml        # map task -> model (swap ở đây)
├── data/                      # mock data (xem file 07)
├── evals/                     # golden set (xem file 04)
├── Dockerfile
└── README.md
```
