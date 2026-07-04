"""
Embeddings via fastembed (ONNX, CPU-only, no torch) — chosen over bge-m3 for
image size and RAM on the CPU VPS; bge-m3 is the documented upgrade path
(swap RAG_DENSE_MODEL, rebuild index). Dense: multilingual MiniLM (384-d, VN ok).
Sparse: BM25 — gives us hybrid without separate lexical infra.

Models are lazy singletons (first call downloads ~100–500MB to the HF cache;
in Docker this happens once per volume/image layer).
"""
from config import config

_dense = None
_sparse = None


def get_dense():
    global _dense
    if _dense is None:
        from fastembed import TextEmbedding
        _dense = TextEmbedding(model_name=config.RAG_DENSE_MODEL)
    return _dense


def get_sparse():
    global _sparse
    if _sparse is None:
        from fastembed import SparseTextEmbedding
        _sparse = SparseTextEmbedding(model_name=config.RAG_SPARSE_MODEL)
    return _sparse


def embed_dense(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in get_dense().embed(texts)]


def embed_sparse(texts: list[str]):
    """Returns fastembed SparseEmbedding objects (has .indices / .values)."""
    return list(get_sparse().embed(texts))
