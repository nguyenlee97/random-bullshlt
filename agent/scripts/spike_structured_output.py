"""
Structured-output spike for MiniMax (Phase 1, migration step 6).

Answers ONE question, empirically, per model:
    Which structured-output strategy reliably yields schema-valid JSON?
        A) response_format json_schema (strict)
        B) response_format json_object + schema-in-prompt
        C) function-calling-as-schema (tool with the target schema; forced tool_choice)

Runs each strategy N times against a realistic planner-style prompt (Vietnamese),
validates with Pydantic, reports success rates. The winner becomes the
`structured()` implementation in agent/graph/ and gets recorded in
docs/adr/005-structured-outputs-minimax.md.

Usage (from agent/):  python scripts/spike_structured_output.py --n 10
                      python scripts/spike_structured_output.py --model "qwen..." --n 10
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import AsyncOpenAI  # noqa: E402
from pydantic import BaseModel, Field, ValidationError  # noqa: E402
from config import config  # noqa: E402


# ── Target schema: a realistic Plan (mirrors graph/schemas.py) ────────────────
class PlanTask(BaseModel):
    id: str
    goal: str
    tool: str = Field(pattern="^(recommend_audience|rank_zones|match_creatives|draft_order)$")
    depends_on: list[str] = []


class Plan(BaseModel):
    tasks: list[PlanTask]
    rationale: str


PLAN_JSON_SCHEMA = {
    "name": "plan",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "goal": {"type": "string"},
                        "tool": {"type": "string",
                                 "enum": ["recommend_audience", "rank_zones", "match_creatives", "draft_order"]},
                        "depends_on": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "goal", "tool", "depends_on"],
                    "additionalProperties": False,
                },
            },
            "rationale": {"type": "string"},
        },
        "required": ["tasks", "rationale"],
        "additionalProperties": False,
    },
}

PROMPT = """Bạn là planner của agent thiết lập chiến dịch quảng cáo.
Brief: Brand "ZUMA Ice", objective awareness, KPI reach 5M, budget 600 triệu VND,
thời gian 2026-07-10 → 2026-08-10, ghi chú: "Nam 18-28, thích gaming và bóng đá".
Hãy lập kế hoạch các task cần chạy (dùng đúng các tool được phép:
recommend_audience, rank_zones, match_creatives, draft_order) theo đúng thứ tự phụ thuộc."""

STRIP = ("<think>", "</think>", "```json", "```")


def extract_json(text: str) -> str:
    """Best-effort cleanup for models that wrap JSON in markdown/thinking."""
    for s in STRIP:
        text = text.replace(s, "")
    text = text.strip()
    # take outermost {...}
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


async def run_strategy(client: AsyncOpenAI, model: str, strategy: str) -> tuple[bool, str]:
    kwargs: dict = {"model": model, "max_tokens": 2000, "temperature": 0.1}
    msgs = [{"role": "user", "content": PROMPT}]

    if strategy == "A_json_schema":
        kwargs["response_format"] = {"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA}
    elif strategy == "B_json_object":
        msgs = [{"role": "user", "content": PROMPT + "\n\nTrả lời DUY NHẤT bằng JSON theo schema:\n"
                 + json.dumps(PLAN_JSON_SCHEMA["schema"], ensure_ascii=False)}]
        kwargs["response_format"] = {"type": "json_object"}
    elif strategy == "C_function_call":
        kwargs["tools"] = [{"type": "function", "function": {
            "name": "submit_plan", "description": "Submit the campaign plan",
            "parameters": PLAN_JSON_SCHEMA["schema"]}}]
        kwargs["tool_choice"] = {"type": "function", "function": {"name": "submit_plan"}}

    try:
        resp = await client.chat.completions.create(messages=msgs, **kwargs)
        msg = resp.choices[0].message
        raw = (msg.tool_calls[0].function.arguments if strategy == "C_function_call" and msg.tool_calls
               else msg.content or "")
        Plan.model_validate_json(extract_json(raw))
        return True, ""
    except ValidationError as e:
        return False, f"schema-invalid: {str(e)[:100]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=config.LLM_MODEL)
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    client = AsyncOpenAI(base_url=config.LLM_BASE_URL, api_key=config.AI_PLATFORM_API_KEY)
    print(f"Model: {args.model}   runs per strategy: {args.n}\n")

    summary = {}
    for strategy in ("A_json_schema", "B_json_object", "C_function_call"):
        results = await asyncio.gather(*[run_strategy(client, args.model, strategy) for _ in range(args.n)])
        ok = sum(1 for r, _ in results if r)
        errs = [e for r, e in results if not r][:3]
        summary[strategy] = ok
        print(f"{strategy}: {ok}/{args.n} schema-valid" + (f"   sample errors: {errs}" if errs else ""))

    best = max(summary, key=summary.get)
    print(f"\n➡ Winner: {best} ({summary[best]}/{args.n}).")
    print("Record the verdict in docs/adr/005-structured-outputs-minimax.md and")
    print("implement agent/graph/structured.py accordingly (see graph/README).")


if __name__ == "__main__":
    # Windows: Proactor loop tears down httpx transports noisily ("Event loop
    # is closed" after results print). Selector policy avoids it. Harmless either way.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
