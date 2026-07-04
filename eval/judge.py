"""
LLM-as-judge for audience recommendations (07-eval-framework.md §3).

⛔ Judge model MUST be a different family than the generator (MiniMax).
Set JUDGE_MODEL in .env to a Qwen/Gemma/GPT-OSS id from docs/maas-catalog.md.
Reference-guided: the judge sees the labels. Temperature 0, k samples, median.

⛔ Do NOT trust judge scores until calibration passes (§4: ρ ≥ 0.7 vs human
on 30 outputs). Run calibration once, commit the report, then rely on this.
"""
import asyncio
import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))

from openai import AsyncOpenAI  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from config import config  # noqa: E402

JUDGE_MODEL = os.getenv("JUDGE_MODEL", "")  # REQUIRED — different family than generator
# Judge can live on a DIFFERENT provider than the generator (recommended):
# e.g. JUDGE_BASE_URL=https://api.openai.com/v1, JUDGE_API_KEY=sk-..., JUDGE_MODEL=gpt-4o-mini
JUDGE_BASE_URL = os.getenv("JUDGE_BASE_URL", "") or config.LLM_BASE_URL
JUDGE_API_KEY = os.getenv("JUDGE_API_KEY", "") or config.AI_PLATFORM_API_KEY

RUBRIC = """Bạn là giám khảo đánh giá chất lượng gợi ý audience segment cho chiến dịch quảng cáo.
Chấm từng tiêu chí thang 1-5 (neo điểm: 1=sai hoàn toàn, 2=kém, 3=chấp nhận được, 4=tốt, 5=xuất sắc):

1. brief_fit: Các segment gợi ý có đúng với brand, objective và ghi chú audience trong brief không?
   (5: tất cả segment khớp rõ ràng; 3: đa số khớp, 1-2 cái lạc đề; 1: phần lớn lạc đề)
2. label_recall: So với danh sách segment ĐÚNG (labels.must_include), gợi ý bao phủ được bao nhiêu?
   (5: đủ hết must_include; 3: được một nửa; 1: không trúng cái nào)
3. exclusion_safety: Có segment nào thuộc danh sách CẤM (labels.must_exclude) bị gợi ý không?
   (5: không có; 1: có bất kỳ segment cấm nào — tiêu chí này chấm 1 hoặc 5, không ở giữa)
4. justification_quality: Lý do (reason) cho từng gợi ý có cụ thể, đúng logic, tiếng Việt tự nhiên không?
   (5: lý do cụ thể gắn với brief; 3: chung chung nhưng đúng; 1: sáo rỗng hoặc sai)

Trả về JSON: {"scores": [{"criterion": str, "score": int, "justification": str (ngắn gọn)}]}"""


class _Score(BaseModel):
    criterion: str
    score: int = Field(ge=1, le=5)
    justification: str = ""


class _JudgeOut(BaseModel):
    scores: list[_Score]


async def judge_audience(brief: dict, labels: dict, recommendations: list[dict],
                         samples: int = 3) -> dict:
    """Returns {"scores": {criterion: median_score}, "mean": float, "raw": [...]}."""
    if not JUDGE_MODEL:
        raise SystemExit("JUDGE_MODEL not set — pick a non-MiniMax model from docs/maas-catalog.md")
    client = AsyncOpenAI(base_url=JUDGE_BASE_URL, api_key=JUDGE_API_KEY)

    user = json.dumps({
        "brief": brief,
        "labels_must_include": labels["audience"]["must_include"],
        "labels_acceptable": labels["audience"]["acceptable"],
        "labels_must_exclude": labels["audience"]["must_exclude"],
        "recommendations": recommendations,
    }, ensure_ascii=False)

    # GPT-5-family models want max_completion_tokens (not max_tokens) and may
    # reject temperature != default. Start with the modern params and adaptively
    # drop whatever the endpoint rejects (kwargs shared so we only learn once).
    kw: dict = {"model": JUDGE_MODEL, "temperature": 0, "max_completion_tokens": 1200,
                "response_format": {"type": "json_object"}}

    async def one() -> _JudgeOut | None:
        for _ in range(3):  # at most 2 param-adaptations then a real attempt
            try:
                resp = await client.chat.completions.create(
                    messages=[{"role": "system", "content": RUBRIC},
                              {"role": "user", "content": user}],
                    **kw,
                )
                raw = resp.choices[0].message.content or ""
                start, end = raw.find("{"), raw.rfind("}")
                return _JudgeOut.model_validate_json(raw[start:end + 1])
            except Exception as e:
                msg = str(e)
                if "max_completion_tokens" in msg and "max_completion_tokens" in kw:
                    kw["max_tokens"] = kw.pop("max_completion_tokens")   # older endpoint
                    continue
                if "max_tokens" in msg and "max_tokens" in kw:
                    kw["max_completion_tokens"] = kw.pop("max_tokens")   # newer endpoint
                    continue
                if "temperature" in msg and "temperature" in kw:
                    kw.pop("temperature")                                # locked-temp model
                    continue
                print(f"  judge sample failed: {e}", file=sys.stderr)
                return None
        return None

    outs = [o for o in await asyncio.gather(*[one() for _ in range(samples)]) if o]
    if not outs:
        return {"scores": {}, "mean": 0.0, "raw": [], "error": "all judge samples failed"}

    per_criterion: dict[str, list[int]] = {}
    for o in outs:
        for s in o.scores:
            per_criterion.setdefault(s.criterion, []).append(s.score)
    med = {c: statistics.median(v) for c, v in per_criterion.items()}
    return {"scores": med,
            "mean": sum(med.values()) / max(len(med), 1),
            "raw": [o.model_dump() for o in outs]}
