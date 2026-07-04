"""
Build/rebuild the Qdrant DMP-segment index (Phase 2).

Run from agent/ (or in Docker: docker compose exec agent python scripts/build_rag_index.py):
    python scripts/build_rag_index.py            # skip if up to date
    python scripts/build_rag_index.py --force    # full rebuild

First run downloads the ONNX embedding models (~500MB) to the HF cache.
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.index import build_index  # noqa: E402
from config import config  # noqa: E402


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    print(f"Qdrant: {config.QDRANT_URL}  collection: {config.RAG_COLLECTION}")
    print(f"dense: {config.RAG_DENSE_MODEL}\nsparse: {config.RAG_SPARSE_MODEL}")
    n = await build_index(force=args.force)
    print(f"✅ index ready: {n} segments in {time.time() - t0:.1f}s")

    # smoke query
    from rag.recommend import _hybrid_search
    hits = await _hybrid_search(["gaming và bóng đá nam trẻ"], 5)
    print("smoke query top-5:", [h.get("fullLabel") for h in hits])


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
