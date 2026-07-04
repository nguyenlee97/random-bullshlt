"""
Qdrant index over the DMP segment catalog (hybrid: dense + sparse vectors).

Segment text: "{type} | {category} | {fullLabel} | {context} | size ..."
Payload keeps the FULL segment doc so recommendations can be returned enriched
without a second backend call.

ensure_index(): builds automatically if the collection is missing/stale vs the
backend count (310 docs embed in seconds on CPU with MiniLM ONNX).
Full rebuild: python scripts/build_rag_index.py
"""
import asyncio

from config import config
from agent_logger import alog

_qdrant = None
_index_checked = False


def get_qdrant():
    global _qdrant
    if _qdrant is None:
        from qdrant_client import QdrantClient
        _qdrant = QdrantClient(url=config.QDRANT_URL, timeout=10)
    return _qdrant


def _segment_text(s: dict) -> str:
    parts = [s.get("type") or "", s.get("category") or "", s.get("fullLabel") or s.get("name") or ""]
    if s.get("context"):
        parts.append(s["context"])
    if s.get("sizeRaw"):
        parts.append(f"size {s['sizeRaw']}")
    return " | ".join(p for p in parts if p)


async def build_index(force: bool = False) -> int:
    """(Re)build the collection from the live backend catalog. Returns count."""
    from qdrant_client import models as qm
    from rag.embeddings import embed_dense, embed_sparse
    from tools.audience_library import get_all_segments

    segments = await get_all_segments(limit=1000)
    if not segments:
        raise RuntimeError("backend returned 0 segments — refusing to build empty index")

    client = get_qdrant()
    coll = config.RAG_COLLECTION

    exists = client.collection_exists(coll)
    if exists and not force:
        current = client.count(coll).count
        if current == len(segments):
            return current  # up to date

    texts = [_segment_text(s) for s in segments]
    # run CPU embedding off the event loop
    dense, sparse = await asyncio.gather(
        asyncio.to_thread(embed_dense, texts),
        asyncio.to_thread(embed_sparse, texts),
    )

    if exists:
        client.delete_collection(coll)
    client.create_collection(
        coll,
        vectors_config={"dense": qm.VectorParams(size=len(dense[0]), distance=qm.Distance.COSINE)},
        sparse_vectors_config={"sparse": qm.SparseVectorParams()},
    )
    points = [
        qm.PointStruct(
            id=i,
            vector={
                "dense": dense[i],
                "sparse": qm.SparseVector(indices=sparse[i].indices.tolist(),
                                          values=sparse[i].values.tolist()),
            },
            payload={**segments[i], "_text": texts[i]},
        )
        for i in range(len(segments))
    ]
    client.upsert(coll, points=points, wait=True)
    return len(points)


async def ensure_index(session_id: str = "rag") -> bool:
    """Cheap idempotent check on first use; True if index is usable."""
    global _index_checked
    if _index_checked:
        return True
    try:
        n = await build_index(force=False)
        await alog(session_id, "info", {"rag": "index_ready", "count": n})
        _index_checked = True
        return True
    except Exception as e:
        await alog(session_id, "error", {"rag": "index_unavailable", "error": str(e)[:150]})
        return False
