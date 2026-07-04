"""
Query rewriting — expands the brief into 2–3 catalog-vocabulary search queries.
Cheap-model slot (critic endpoint). Any failure → single fallback query built
from the brief fields (the pipeline must never die on the rewrite step ⛔).
"""
import json

from pydantic import BaseModel, Field

from graph.structured import StructuredOutputError, structured


class RewriteOut(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=3)


_PROMPT = """Brief quảng cáo:
{brief}

Viết 2-3 câu truy vấn NGẮN (mỗi câu < 15 từ) để tìm audience segment phù hợp trong
catalog DMP (catalog gồm các interest/behavior như "Gaming", "Food and drink",
"Soccer", "Online shopping"...). Truy vấn nên dùng từ vựng catalog (tiếng Anh
hoặc tiếng Việt đều được), phủ các khía cạnh khác nhau của audience trong brief."""


def _fallback_queries(brief: dict) -> list[str]:
    q = " ".join(str(brief.get(k) or "") for k in ("brand", "objective", "notes")).strip()
    return [q[:200] or "general audience"]


async def rewrite(brief: dict) -> list[str]:
    prompt = _PROMPT.format(brief=json.dumps(brief, ensure_ascii=False))
    try:
        import asyncio
        out, _ = await asyncio.to_thread(
            structured, [{"role": "user", "content": prompt}],
            RewriteOut, "queries", "critic", 400)
        return out.queries
    except (StructuredOutputError, Exception):
        return _fallback_queries(brief)
