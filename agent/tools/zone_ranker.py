"""
Zone scoring algorithm — Python port of n8n Ad Zone Ranker v4.
Handles both banner (pixel sizes) and skin (format-only match) zones.
Reach is RAW numbers from API (not millions).
"""
from __future__ import annotations
import re

# Objective weights (same as agent_frontend scoring)
OBJECTIVE_WEIGHTS = {
    "awareness":     {"reach": 0.40, "vi": 0.35, "ctr": 0.05, "efficiency": 0.20},
    "consideration": {"reach": 0.30, "vi": 0.35, "ctr": 0.20, "efficiency": 0.15},
    "conversion":    {"reach": 0.10, "vi": 0.20, "ctr": 0.50, "efficiency": 0.20},
    "retention":     {"reach": 0.20, "vi": 0.50, "ctr": 0.20, "efficiency": 0.10},
}

TIER_LABELS = {
    "homepage-masthead": "masthead trang chủ premium",
    "homepage-inline": "banner inline trang chủ",
    "background-skin": "background skin",
    "large-middle-unit": "banner cỡ lớn trong nội dung",
    "content-pr-box": "PR box trong nội dung",
    "homepage-side-left": "side skin trang chủ",
    "homepage-side-right": "side skin trang chủ",
    "category-side-left": "side skin trang chuyên mục",
    "category-side-right": "side skin trang chuyên mục",
    "standard-box": "box tiêu chuẩn",
}

# A single explicit brief keyword (0.18 * catalog confidence 0.9 = 0.162)
# is enough to enter contextual retrieval. Broad category-only affinities
# (0.14 * 0.9 = 0.126) remain supporting evidence, not a hard retrieval match.
CONTEXT_RELEVANCE_THRESHOLD = 0.15


def _parse_dims(size_str: str) -> tuple[int, int] | None:
    m = re.match(r"(\d+)[xX×](\d+)", size_str or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _score_zone(zone: dict, objective: str, max_reach: float) -> float:
    w = OBJECTIVE_WEIGHTS.get(objective, OBJECTIVE_WEIGHTS["awareness"])
    reach_norm = min(zone.get("reach", 0) / (max(max_reach, 1) / 100), 100)
    efficiency = (100000 / zone["cpm"]) if zone.get("cpm", 0) > 0 else 0
    return (
        reach_norm * w["reach"]
        + zone.get("vi", 0) * w["vi"]
        + zone.get("ctr", 0) * w["ctr"]
        + efficiency * w["efficiency"]
    )


def _kpi_bonus(zone: dict, kpi: str, max_reach: float) -> float:
    kpi_lower = (kpi or "").lower()
    bonus = 0.0
    if ("vtr" in kpi_lower or "video" in kpi_lower) and zone.get("format") == "video":
        bonus += 0.15
    if "reach" in kpi_lower or "impress" in kpi_lower:
        bonus += 0.10 * min(zone.get("reach", 0) / max(max_reach, 1), 1)
    if "ctr" in kpi_lower:
        bonus += 0.05 * zone.get("ctr", 0)
    return bonus


def _size_compat(zone: dict, files: list[dict]) -> tuple[float, str]:
    """Score creative-zone size compatibility. Handles skin zones."""
    from autopilot.placement_planning import format_spec_for_zone
    from tools.creative_match import dimension_match, match_file_to_format

    if not files:
        return 0.0, "no_creative"

    if zone.get("creativeContractId"):
        spec = format_spec_for_zone(zone)
        if not spec:
            return 0.0, "unsupported_creative_contract"
        best_bonus, best_mode = -1.0, "no_match"
        for file in files:
            match = match_file_to_format(file, spec)
            mode = match.get("mode", "no_match")
            if not match.get("matched"):
                if mode == "incompatible_ratio":
                    bonus = max(
                        -0.35,
                        0.12 - float(match.get("ratio_diff") or 1),
                    )
                    mode = "nearest_ratio"
                else:
                    bonus = 0.0
            elif mode == "explicit_identity":
                # Canonical formatId/name is the strongest operator signal.
                # Measured ratio remains available as an advisory.
                bonus = 0.32
            elif mode == "exact_size":
                bonus = 0.30
            elif mode == "strong_ratio":
                bonus = 0.24
            elif mode in {"same_ratio", "explicit_format_hint"}:
                bonus = 0.20
            else:
                bonus = 0.08
            if bonus > best_bonus:
                best_bonus, best_mode = bonus, mode
        return (best_bonus if best_bonus > -1 else 0.0), best_mode

    # Skin zones: match by creative name containing "skin"
    if zone.get("size") == "skin" or zone.get("format") == "skin":
        for f in files:
            intel = f.get("intel") or {}
            if (
                intel.get("is_skin") is True
                or f.get("intendedFormat") == "skin"
                or "skin" in (f.get("name") or "").lower()
            ):
                return 0.20, "skin_match"
        return 0.0, "no_skin_creative"

    zone_dims = _parse_dims(zone.get("size", ""))
    if not zone_dims:
        return 0.0, "no_zone_size"
    zw, zh = zone_dims

    best_bonus, best_mode = -1.0, "no_match"
    for f in files:
        intel = f.get("intel") or {}
        fw = intel.get("width") or f.get("width", 0)
        fh = intel.get("height") or f.get("height", 0)
        if fw <= 0 or fh <= 0:
            continue
        if fw == zw and fh == zh:
            return 0.30, "exact_size"
        mode, diff = dimension_match(fw, fh, zw, zh)
        if mode == "strong_ratio":
            bonus = 0.24
        elif mode == "same_ratio":
            bonus = 0.20
        elif mode == "acceptable_ratio":
            bonus = 0.08
        elif mode == "incompatible_ratio":
            bonus, mode = max(-0.35, 0.12 - float(diff or 1)), "nearest_ratio"
        else:
            bonus = 0.0
        if bonus > best_bonus:
            best_bonus, best_mode = bonus, mode

    return (best_bonus if best_bonus > -1 else 0.0), best_mode


def _relevance_score(zone: dict) -> float:
    return float(
        zone.get("recommendation_relevance")
        or (zone.get("topic_relevance") or {}).get("score")
        or 0
    )


def _is_context_match(zone: dict) -> bool:
    retrieval = zone.get("placement_retrieval") or {}
    lexical = float((zone.get("topic_relevance") or {}).get("score") or 0)
    if retrieval.get("applied") is True:
        # Once hybrid retrieval is available, one weak generic keyword is only
        # supporting evidence. Require either a semantic topic hit or multiple/
        # stronger catalog signals before entering the protected context tier.
        return retrieval.get("semantic_match") is True or lexical >= 0.30
    return lexical >= CONTEXT_RELEVANCE_THRESHOLD


def sort_ranked_zones_for_strategy(
    zones: list[dict],
    strategy: str = "balanced",
) -> list[dict]:
    """Apply a delivery strategy without discarding contextual relevance.

    Context matching is the retrieval stage. Reach/quality can reorder zones
    inside the matching and fallback tiers, but cannot push an unrelated zone
    above a documented topic/audience match.
    """
    if strategy == "balanced":
        return list(zones)

    def common(zone: dict) -> tuple:
        contextual = zone.get("ranking_mode") == "audience_context"
        return (
            0 if (contextual and _is_context_match(zone)) else 1,
            -_relevance_score(zone) if contextual else 0,
        )

    if strategy == "reach_first":
        return sorted(
            zones,
            key=lambda zone: (
                *common(zone),
                -float(zone.get("reach") or 0),
                float(zone.get("cpm") or 10**12),
                -float(zone.get("score") or 0),
            ),
        )
    if strategy == "quality_first":
        return sorted(
            zones,
            key=lambda zone: (
                *common(zone),
                -float(zone.get("viewability") or zone.get("vi") or 0),
                -float(zone.get("ctr") or 0),
                -float(zone.get("score") or 0),
            ),
        )
    return list(zones)


async def rank_zones(
    objective: str,
    budget: float = 0,
    kpi: str = "",
    creative_files: list[dict] | None = None,
    placement_context: dict | None = None,
    limit: int = 6,
) -> list[dict]:
    """
    Fetch zones from API, score + rank. Returns top `limit`.
    Each result has: score, reason, est_impressions, match_mode.
    """
    from tools.placement_relevance import score_placement_relevance
    from tools.zone_catalog import get_all_zones
    zones = await get_all_zones()
    from config import config

    retrieval_evidence = {}
    retrieval_meta = {"applied": False, "reason": "disabled"}
    topic_rerank_meta = {"applied": False, "reason": "retrieval_not_applied"}
    if (
        config.PLACEMENT_RAG_ENABLED
        and placement_context
        and placement_context.get("text")
    ):
        try:
            from tools.placement_retrieval import retrieve_placements

            retrieval_evidence, retrieval_meta = await retrieve_placements(
                zones,
                placement_context,
                limit=config.PLACEMENT_RAG_RETRIEVE_LIMIT,
            )
        except Exception as exc:
            # Semantic retrieval is an additive relevance stage. The existing
            # scorer remains a complete fail-open path if embeddings/indexing
            # are unavailable.
            retrieval_meta = {
                "applied": False,
                "reason": "retrieval_failure",
                "error_type": type(exc).__name__,
            }
    if retrieval_meta.get("applied") is True:
        from tools.placement_reranker import rerank_topics

        reranked_topics, topic_rerank_meta = await rerank_topics(
            retrieval_meta.get("topics") or [],
            placement_context,
        )
        if topic_rerank_meta.get("applied") is True:
            topic_verdicts = {
                item["topic_id"]: item["topic_rerank"]
                for item in reranked_topics
            }
            for evidence in retrieval_evidence.values():
                verdict = topic_verdicts.get(evidence.get("topic_id"))
                if not verdict:
                    continue
                evidence["topic_rerank_rank"] = verdict["rank"]
                evidence["topic_rerank_score"] = verdict["score"]
                evidence["topic_rerank_rationale"] = verdict["rationale"]
                evidence["semantic_match"] = (
                    verdict["rank"] <= config.PLACEMENT_RAG_CONTEXT_LIMIT
                    and verdict["score"]
                    >= config.PLACEMENT_RAG_TOPIC_RERANK_THRESHOLD
                )
    scored = []
    n = min(limit, len(zones))
    max_reach = max((float(zone.get("reach") or 0) for zone in zones), default=1)

    for zone in zones:
        base = _score_zone(zone, objective, max_reach)
        bonus = _kpi_bonus(zone, kpi, max_reach)
        size_bonus, match_mode = _size_compat(zone, creative_files or [])
        relevance = score_placement_relevance(zone, placement_context)
        retrieval = retrieval_evidence.get(zone.get("id"), {})
        semantic_relevance = (
            max(
                float(retrieval.get("dense_score") or 0),
                float(retrieval.get("topic_rerank_score") or 0),
            )
            if retrieval.get("semantic_match") is True
            else 0.0
        )
        combined_relevance = max(relevance["score"], semantic_relevance)
        topic_bonus = combined_relevance * 25
        total = base + bonus + size_bonus + topic_bonus

        est_imp = None
        if budget > 0 and zone.get("cpm", 0) > 0:
            budget_per_zone = (budget * 1_000_000) / n
            est_imp = round(budget_per_zone / zone["cpm"] * 1000)

        scored.append({
            **zone,
            "score": round(total, 4),
            "score_components": {
                "performance": round(base, 4),
                "kpi": round(bonus, 4),
                "creative": round(size_bonus, 4),
                "topic_relevance": round(topic_bonus, 4),
            },
            "topic_relevance": relevance,
            "placement_retrieval": retrieval,
            "recommendation_relevance": round(combined_relevance, 4),
            "reason": (
                f"{TIER_LABELS.get(zone.get('inventoryTier'), 'Inventory')} phù hợp "
                f"mục tiêu {objective}; "
                + (
                    "chủ đề khớp "
                    + ", ".join(
                        relevance["matched_keywords"]
                        or relevance["matched_segments"]
                        or relevance["matched_subcategories"]
                        or relevance["matched_categories"]
                        or relevance["matched_topics"]
                    )
                    + "."
                    if relevance["score"] > 0
                    else (
                        "ngữ nghĩa brief/audience khớp nội dung "
                        f"{str(zone.get('topicId') or 'placement').replace('_', ' ')}."
                        if retrieval.get("semantic_match") is True
                        else "không có tín hiệu chủ đề trực tiếp trong brief/audience."
                    )
                )
            ),
            "est_impressions": est_imp,
            "match_mode": match_mode,
        })

    contextual_matches = [zone for zone in scored if _is_context_match(zone)]
    ranking_mode = (
        "audience_context"
        if placement_context and placement_context.get("text") and contextual_matches
        else "performance_fallback"
    )
    for zone in scored:
        zone["ranking_mode"] = ranking_mode
        zone["recommendation_basis"] = {
            "mode": ranking_mode,
            "context_match": ranking_mode == "audience_context" and _is_context_match(zone),
            "relevance_threshold": CONTEXT_RELEVANCE_THRESHOLD,
            "brief_fields": (placement_context or {}).get("source_fields") or [],
            "matched_topics": zone["topic_relevance"]["matched_topics"],
            "matched_keywords": zone["topic_relevance"]["matched_keywords"],
            "matched_categories": zone["topic_relevance"]["matched_categories"],
            "matched_subcategories": zone["topic_relevance"]["matched_subcategories"],
            "matched_segments": zone["topic_relevance"]["matched_segments"],
            "retrieval_applied": retrieval_meta.get("applied") is True,
            "retrieval_mode": retrieval_meta.get("mode"),
            "retrieval_rank": (zone.get("placement_retrieval") or {}).get("rank"),
            "topic_rerank_rank": (zone.get("placement_retrieval") or {}).get("topic_rerank_rank"),
            "topic_rerank_score": (zone.get("placement_retrieval") or {}).get("topic_rerank_score"),
            "semantic_score": (zone.get("placement_retrieval") or {}).get("dense_score"),
            "semantic_match": (zone.get("placement_retrieval") or {}).get("semantic_match") is True,
        }

    if ranking_mode == "audience_context":
        scored.sort(
            key=lambda zone: (
                0 if _is_context_match(zone) else 1,
                -_relevance_score(zone),
                -float(zone.get("score") or 0),
            )
        )
    else:
        scored.sort(key=lambda zone: zone["score"], reverse=True)

    if topic_rerank_meta.get("applied") is True:
        reranked, rerank_meta = scored, topic_rerank_meta
    else:
        from tools.placement_reranker import rerank_placements

        reranked, rerank_meta = await rerank_placements(scored, placement_context)
    if ranking_mode == "audience_context":
        # The optional LLM may improve ordering inside the bounded shortlist,
        # but it cannot promote a non-matching placement over deterministic
        # catalog evidence.
        rerank_order = {zone["id"]: index for index, zone in enumerate(reranked)}
        reranked.sort(
            key=lambda zone: (
                0 if _is_context_match(zone) else 1,
                rerank_order[zone["id"]],
            )
        )
    for index, zone in enumerate(reranked, start=1):
        zone["rerank_meta"] = rerank_meta
        zone["context_rank"] = index
    return reranked[:limit]
