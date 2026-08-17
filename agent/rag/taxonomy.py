"""Live-catalog audience taxonomy helpers for the OpenAI recommendation path.

The DMP catalog does not expose explicit parent IDs. Most relationships can be
derived from its category, subcategory, and context fields. A deliberately
small ID-based correction layer covers relationships that the source catalog
cannot currently express. This module never translates free-form user text and
never changes the GreenNode path.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Iterable


SEMANTIC_RELATION_OVERRIDES: dict[str, tuple[str, ...]] = {
    # The catalog places all of these below Vehicles, but does not encode the
    # closer passenger-automobile relationship needed for car campaigns.
    "INT219": ("INT221", "INT222", "INT223", "INT227"),
    # Engagement variants are behavior children of the broad Soccer behavior.
    "BEH002": ("BEH004", "BEH005"),
}


def segment_id(segment: dict) -> str:
    return str(
        segment.get("segmentId")
        or segment.get("_id")
        or segment.get("fullLabel")
        or segment.get("name")
        or ""
    ).strip()


def _fold(value: object) -> str:
    text = str(value or "").casefold().replace("đ", "d")
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    text = re.sub(r"\([^)]*\)", " ", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _label(segment: dict) -> str:
    return str(segment.get("fullLabel") or segment.get("name") or "").strip()


@dataclass
class AudienceTaxonomyGraph:
    segments: dict[str, dict]
    parents: dict[str, dict[str, str]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    children: dict[str, dict[str, str]] = field(
        default_factory=lambda: defaultdict(dict)
    )

    def add_edge(self, parent_id: str, child_id: str, source: str) -> None:
        if not parent_id or not child_id or parent_id == child_id:
            return
        previous = self.parents[child_id].get(parent_id)
        if previous == "semantic_override":
            return
        self.parents[child_id][parent_id] = source
        self.children[parent_id][child_id] = source

    def ancestor_relations(self, child_id: str) -> dict[str, dict]:
        """Return every ancestor with shortest distance and path sources."""
        found: dict[str, dict] = {}
        queue = deque(
            (parent_id, 1, (source,))
            for parent_id, source in self.parents.get(child_id, {}).items()
        )
        while queue:
            parent_id, distance, sources = queue.popleft()
            previous = found.get(parent_id)
            if previous and previous["distance"] <= distance:
                continue
            found[parent_id] = {
                "distance": distance,
                "sources": list(dict.fromkeys(sources)),
            }
            for next_parent, source in self.parents.get(parent_id, {}).items():
                if next_parent == child_id:
                    continue
                queue.append(
                    (next_parent, distance + 1, sources + (source,))
                )
        return found

    def descendant_ids(self, parent_id: str) -> set[str]:
        found: set[str] = set()
        queue = deque(self.children.get(parent_id, {}))
        while queue:
            child_id = queue.popleft()
            if child_id in found or child_id == parent_id:
                continue
            found.add(child_id)
            queue.extend(self.children.get(child_id, {}))
        return found

    def metadata(self, candidate_id: str) -> dict:
        ancestor_relations = self.ancestor_relations(candidate_id)
        direct_parents = self.parents.get(candidate_id, {})
        direct_children = self.children.get(candidate_id, {})
        descendants = self.descendant_ids(candidate_id)
        return {
            "direct_parent_ids": list(direct_parents),
            "direct_parent_labels": [
                _label(self.segments[parent_id])
                for parent_id in direct_parents
                if parent_id in self.segments
            ],
            "direct_parent_sources": dict(direct_parents),
            "ancestor_ids": list(ancestor_relations),
            "ancestor_relations": ancestor_relations,
            "direct_child_ids": list(direct_children),
            "direct_child_labels": [
                _label(self.segments[child_id])
                for child_id in direct_children
                if child_id in self.segments
            ][:12],
            "descendant_count": len(descendants),
            "descendant_sample_ids": sorted(descendants)[:12],
        }

    def summary(self) -> dict:
        sources: dict[str, int] = defaultdict(int)
        for relations in self.children.values():
            for source in relations.values():
                sources[source] += 1
        return {
            "catalog_segments": len(self.segments),
            "parent_segments": sum(bool(rows) for rows in self.children.values()),
            "edge_count": sum(len(rows) for rows in self.children.values()),
            "edge_sources": dict(sorted(sources.items())),
        }


def build_taxonomy_graph(catalog: Iterable[dict]) -> AudienceTaxonomyGraph:
    segments = {
        segment_id(segment): dict(segment)
        for segment in catalog
        if segment_id(segment)
    }
    graph = AudienceTaxonomyGraph(segments=segments)
    rows = list(segments.items())
    for parent_id, parent in rows:
        parent_core = _fold(parent.get("name") or parent.get("fullLabel"))
        parent_category = _fold(parent.get("category"))
        parent_type = _fold(parent.get("type"))
        if not parent_core:
            continue
        for child_id, child in rows:
            if parent_id == child_id or parent_type != _fold(child.get("type")):
                continue
            child_category = _fold(child.get("category"))
            category_compatible = (
                not parent_category
                or not child_category
                or parent_category == child_category
                or parent_core == child_category
            )
            if not category_compatible:
                continue
            if parent_core == _fold(child.get("subcategory")):
                graph.add_edge(parent_id, child_id, "catalog_subcategory")
            if parent_core == _fold(child.get("context")):
                graph.add_edge(parent_id, child_id, "catalog_context")

    for parent_id, child_ids in SEMANTIC_RELATION_OVERRIDES.items():
        if parent_id not in segments:
            continue
        for child_id in child_ids:
            if child_id in segments:
                graph.add_edge(parent_id, child_id, "semantic_override")
    return graph


def expand_candidates_with_taxonomy(
    candidates: list[dict],
    catalog: list[dict],
    *,
    candidate_limit: int,
    seed_limit: int = 24,
    max_injected: int = 8,
) -> tuple[list[dict], AudienceTaxonomyGraph, dict]:
    """Put relevant ancestors inside the bounded reranker window.

    Existing retrieval order is preserved except for ancestors that would
    otherwise fall outside the window. No descendant or sibling is injected.
    """
    graph = build_taxonomy_graph(catalog or candidates)
    candidate_copies = [dict(candidate) for candidate in candidates]
    by_id = {segment_id(candidate): candidate for candidate in candidate_copies}
    bounded_limit = max(1, min(candidate_limit, 50))
    seed_rows = candidate_copies[: min(seed_limit, bounded_limit)]

    ancestor_reasons: dict[str, dict] = {}
    for rank, child in enumerate(seed_rows):
        child_id = segment_id(child)
        for parent_id, relation in graph.ancestor_relations(child_id).items():
            if parent_id not in graph.segments:
                continue
            current = ancestor_reasons.get(parent_id)
            proposal = {
                "parent_id": parent_id,
                "first_child_rank": rank,
                "distance": relation["distance"],
                "sources": relation["sources"],
                "trigger_child_ids": [child_id],
            }
            if current is None:
                ancestor_reasons[parent_id] = proposal
            else:
                current["first_child_rank"] = min(
                    current["first_child_rank"], rank
                )
                current["distance"] = min(
                    current["distance"], relation["distance"]
                )
                current["sources"] = list(dict.fromkeys(
                    current["sources"] + relation["sources"]
                ))
                if child_id not in current["trigger_child_ids"]:
                    current["trigger_child_ids"].append(child_id)

    source_priority = {
        "semantic_override": 0,
        "catalog_context": 1,
        "catalog_subcategory": 2,
    }
    ranked_parents = sorted(
        ancestor_reasons.values(),
        key=lambda row: (
            row["first_child_rank"],
            row["distance"],
            min(source_priority.get(source, 9) for source in row["sources"]),
            len(graph.descendant_ids(row["parent_id"])),
            row["parent_id"],
        ),
    )

    current_prefix_ids = {
        segment_id(candidate)
        for candidate in candidate_copies[:bounded_limit]
    }
    forced: list[dict] = []
    injected_trace: list[dict] = []
    for reason in ranked_parents:
        parent_id = reason["parent_id"]
        if parent_id in current_prefix_ids or len(forced) >= max_injected:
            continue
        parent = dict(by_id.get(parent_id) or graph.segments[parent_id])
        trigger = next(
            (
                by_id[child_id]
                for child_id in reason["trigger_child_ids"]
                if child_id in by_id
            ),
            {},
        )
        parent.setdefault("_text", " | ".join(
            str(parent.get(key) or "")
            for key in ("type", "category", "subcategory", "fullLabel", "context")
        ))
        parent["_rank"] = float(trigger.get("_rank") or reason["first_child_rank"])
        parent.setdefault("_fusion_score", 0.0)
        parent.setdefault("_query_hits", 0)
        parent.setdefault("_query_matches", [])
        parent.setdefault("_aspect_hits", list(trigger.get("_aspect_hits") or []))
        parent.setdefault("_rag_index", dict(trigger.get("_rag_index") or {}))
        parent["_taxonomy_injected"] = True
        forced.append(parent)
        current_prefix_ids.add(parent_id)
        injected_trace.append({
            **reason,
            "full_label": _label(parent),
            "was_retrieved": parent_id in by_id,
        })

    forced_ids = {segment_id(candidate) for candidate in forced}
    keep_count = max(0, bounded_limit - len(forced))
    prefix = [
        candidate
        for candidate in candidate_copies
        if segment_id(candidate) not in forced_ids
    ][:keep_count]
    prefix.extend(forced)
    prefix_ids = {segment_id(candidate) for candidate in prefix}
    remainder = [
        candidate
        for candidate in candidate_copies
        if segment_id(candidate) not in prefix_ids
    ]
    expanded = prefix + remainder
    for candidate in expanded:
        candidate_id = segment_id(candidate)
        if candidate_id in graph.segments:
            candidate["_taxonomy"] = graph.metadata(candidate_id)

    return expanded, graph, {
        **graph.summary(),
        "candidate_limit": bounded_limit,
        "seed_count": len(seed_rows),
        "injected_count": len(forced),
        "injected": injected_trace,
    }
