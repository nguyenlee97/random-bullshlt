"""
Find GreenNode's rerank endpoint for qwen/qwen3-reranker-8b.

The catalog probe tried 3 paths, all 404. This tries a wider matrix of
path × body-shape combos and prints the first success as ready-to-paste
.env lines. Run from agent/:  python scripts/probe_rerank.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from config import config  # noqa: E402

MODEL = "qwen/qwen3-reranker-8b"
BASE_V1 = config.LLM_BASE_URL.rstrip("/")            # .../v1
BASE = BASE_V1.rsplit("/v1", 1)[0]                   # host root

PATHS = [
    f"{BASE_V1}/rerank", f"{BASE_V1}/reranking", f"{BASE_V1}/score",
    f"{BASE_V1}/rerankers", f"{BASE_V1}/retrieval/rerank",
    f"{BASE}/rerank", f"{BASE}/v2/rerank", f"{BASE}/rerank/v1",
    f"{BASE_V1}/models/{MODEL}/rerank",
]

QUERY = "nước giải khát cho giới trẻ"
DOCS = ["Gen Z yêu thích đồ uống", "Người cao tuổi tập dưỡng sinh", "Game thủ trẻ"]

BODIES = [
    ("cohere", {"model": MODEL, "query": QUERY, "documents": DOCS, "top_n": 3}),
    ("jina",   {"model": MODEL, "query": QUERY, "documents": DOCS}),
    ("tei",    {"query": QUERY, "texts": DOCS}),
    ("pairs",  {"model": MODEL, "pairs": [[QUERY, d] for d in DOCS]}),
    ("input",  {"model": MODEL, "input": {"query": QUERY, "documents": DOCS}}),
]

HEADERS = {"Authorization": f"Bearer {config.AI_PLATFORM_API_KEY}"}


async def main():
    async with httpx.AsyncClient(timeout=20) as client:
        for url in PATHS:
            for shape, body in BODIES:
                try:
                    r = await client.post(url, headers=HEADERS, json=body)
                except Exception as e:
                    print(f"  {url} [{shape}] → {type(e).__name__}")
                    break  # host-level failure, skip other shapes for this url
                tag = f"  {url} [{shape}] → {r.status_code}"
                if r.status_code == 200:
                    print(f"✅ {tag}\n   response: {r.text[:300]}")
                    print("\nPaste into agent/.env:")
                    print(f"RERANK_URL={url}")
                    print(f"RERANK_MODEL={MODEL}")
                    if shape not in ("cohere", "jina"):
                        print(f"⚠ body shape '{shape}' — tell Claude to adapt rag/rerank.py")
                    return
                print(tag + ("" if r.status_code in (404, 405) else f"  {r.text[:120]}"))
    print("\n❌ nothing worked — check GreenNode docs/console for the rerank API reference,")
    print("   or ask GreenNode support for the qwen3-reranker-8b endpoint. The RAG pipeline")
    print("   keeps working without rerank (RRF order) in the meantime.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
