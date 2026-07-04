"""
Reranker client — GreenNode MaaS reranker (primary; see docs/maas-catalog.md).

API shape tolerance: tries the Cohere/Jina-style POST body first
({model, query, documents}) and reads both common response shapes
(results[].relevance_score / scores[]). Unknown shape or any failure →
returns None and the caller keeps RRF order (rerank must never break the
Audience step ⛔). Configure RERANK_URL + RERANK_MODEL in .env.
"""
import httpx

from config import config

_client = httpx.AsyncClient(timeout=15.0)


async def rerank(query: str, documents: list[str]) -> list[int] | None:
    """Returns document indices sorted best-first, or None to skip reranking."""
    if not config.RERANK_URL or not config.RERANK_MODEL or not documents:
        return None
    try:
        resp = await _client.post(
            config.RERANK_URL,
            headers={"Authorization": f"Bearer {config.AI_PLATFORM_API_KEY}"},
            json={"model": config.RERANK_MODEL, "query": query,
                  "documents": documents, "top_n": len(documents)},
        )
        resp.raise_for_status()
        data = resp.json()
        if "results" in data:            # Cohere/Jina style
            pairs = [(r.get("index", i), r.get("relevance_score", r.get("score", 0)))
                     for i, r in enumerate(data["results"])]
        elif "scores" in data:           # TEI style: parallel score list
            pairs = list(enumerate(data["scores"]))
        elif "data" in data:             # OpenAI-wrapped style
            pairs = [(r.get("index", i), r.get("relevance_score", r.get("score", 0)))
                     for i, r in enumerate(data["data"])]
        else:
            return None
        return [i for i, _ in sorted(pairs, key=lambda p: -p[1])]
    except Exception:
        return None
