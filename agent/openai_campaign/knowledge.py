"""Versioned, source-controlled read-only knowledge retrieval."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


KNOWLEDGE_VERSION = "2026-07-21.1"
KNOWLEDGE_FILE = (
    Path(__file__).resolve().parents[2]
    / "docs" / "knowledge base" / "ad-operations-faq.md"
)


def _terms(value: str) -> set[str]:
    return {
        item for item in re.findall(r"[\wÀ-ỹ]+", value.casefold(), re.UNICODE)
        if len(item) > 1
    }


@lru_cache(maxsize=1)
def _chunks() -> tuple[dict, ...]:
    text = KNOWLEDGE_FILE.read_text(encoding="utf-8")
    body = text.split("---", 2)[-1].strip()
    chunks: list[dict] = []
    heading = "Overview"
    paragraphs: list[str] = []

    def flush() -> None:
        if not paragraphs:
            return
        content = "\n\n".join(paragraphs).strip()
        chunks.append({
            "source_id": "ad-operations-faq",
            "title": "Advertising operations and campaign setup guidance",
            "section": heading,
            "version": KNOWLEDGE_VERSION,
            "updated_at": "2026-07-21",
            "freshness": "reviewed",
            "citation": f"ad-operations-faq#{heading.casefold().replace(' ', '-')}",
            "content": content,
            "terms": _terms(f"{heading} {content}"),
        })
        paragraphs.clear()

    for line in body.splitlines():
        if line.startswith("# "):
            flush()
            heading = line[2:].strip()
        elif line.startswith("## "):
            flush()
            heading = line[3:].strip()
        elif line.strip():
            paragraphs.append(line.strip())
    flush()
    return tuple(chunks)


def search_ad_knowledge(query: str, *, limit: int = 4) -> dict:
    query_terms = _terms(query)
    ranked = []
    for chunk in _chunks():
        overlap = len(query_terms & chunk["terms"])
        phrase_bonus = 3 if query.casefold() in chunk["content"].casefold() else 0
        score = overlap + phrase_bonus
        if score or not query_terms:
            ranked.append((score, chunk))
    if not ranked:
        ranked = [(0, chunk) for chunk in _chunks()]
    ranked.sort(key=lambda item: (-item[0], item[1]["section"]))
    sources = []
    for score, chunk in ranked[: max(1, min(limit, 6))]:
        sources.append({
            key: value for key, value in chunk.items() if key != "terms"
        } | {"match_score": score})
    return {
        "query": query,
        "knowledge_version": KNOWLEDGE_VERSION,
        "sources": sources,
        "no_result": not sources,
        "instruction": "Cite the supplied source IDs and never invent missing product facts.",
    }
