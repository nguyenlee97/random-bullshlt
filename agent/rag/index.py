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
import hashlib
import json
from importlib.metadata import version

from config import config
from agent_logger import alog

_qdrant = None
_index_checked = False
INDEX_SCHEMA_VERSION = 2


def get_qdrant():
    global _qdrant
    if _qdrant is None:
        from qdrant_client import QdrantClient
        _qdrant = QdrantClient(url=config.QDRANT_URL, timeout=10)
    return _qdrant


def _segment_text(s: dict) -> str:
    parts = [
        s.get("type") or "",
        s.get("category") or "",
        s.get("subcategory") or "",
        s.get("fullLabel") or s.get("name") or "",
    ]
    if s.get("context"):
        parts.append(s["context"])
    if s.get("sizeRaw"):
        parts.append(f"size {s['sizeRaw']}")
    return " | ".join(p for p in parts if p)


def _catalog_fingerprint(segments: list[dict]) -> str:
    """Stable content hash; unlike Mongo _ids it survives environment reseeds."""
    stable = [
        {
            "segmentId": s.get("segmentId"),
            "type": s.get("type"),
            "category": s.get("category"),
            "subcategory": s.get("subcategory"),
            "fullLabel": s.get("fullLabel") or s.get("name"),
            "context": s.get("context"),
            "sizeMin": s.get("sizeMin"),
            "sizeMax": s.get("sizeMax"),
        }
        for s in sorted(
            segments,
            key=lambda x: (x.get("segmentId") or "",
                           x.get("fullLabel") or x.get("name") or ""),
        )
    ]
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _index_metadata(segments: list[dict]) -> dict:
    return {
        "schema": INDEX_SCHEMA_VERSION,
        "catalog_fingerprint": _catalog_fingerprint(segments),
        "dense_model": config.RAG_DENSE_MODEL,
        "sparse_model": config.RAG_SPARSE_MODEL,
        "fastembed_version": version("fastembed"),
        "segment_count": len(segments),
    }


def _stored_metadata(client, collection: str) -> dict:
    points, _ = client.scroll(collection, limit=1, with_payload=True, with_vectors=False)
    return (points[0].payload or {}).get("_rag_index", {}) if points else {}


async def inspect_index() -> dict:
    """Read-only index integrity check used by readiness and release tooling."""
    from tools.audience_library import get_all_segments

    segments = await get_all_segments(limit=1000)
    expected = _index_metadata(segments) if segments else {}
    client = get_qdrant()
    coll = config.RAG_COLLECTION
    if not segments or not client.collection_exists(coll):
        return {"ready": False, "reason": "missing", "expected": expected}
    count = client.count(coll).count
    stored = _stored_metadata(client, coll)
    ready = count == len(segments) and stored == expected
    return {
        "ready": ready,
        "reason": "ok" if ready else "stale",
        "count": count,
        "expected_count": len(segments),
        "stored": stored,
        "expected": expected,
    }


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
    metadata = _index_metadata(segments)

    exists = client.collection_exists(coll)
    if exists and not force:
        current = client.count(coll).count
        if current == len(segments) and _stored_metadata(client, coll) == metadata:
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
            payload={**segments[i], "_text": texts[i], "_rag_index": metadata},
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
