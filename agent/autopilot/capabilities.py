"""Allowlisted Campaign Autopilot capabilities.

Every function returns typed data. Workspace commits, review gating, retries,
and leases are owned by the durable worker rather than hidden inside prompts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from config import config
from models import BriefData
from session import get_or_create_session
from workspace.service import get_workspace


@dataclass
class CapabilityResult:
    value: Any = None
    evidence: list[dict] = field(default_factory=list)
    force_review: bool = False
    externally_committed: bool = False


def _artifact(workspace: dict, name: str, default=None):
    value = workspace.get("artifacts", {}).get(name, {}).get("value")
    return default if value is None else value


def _placement_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not isinstance(value, dict):
        return []
    if value.get("selectedZoneIds"):
        return [str(item) for item in value["selectedZoneIds"]]
    return [str(item.get("id")) for item in value.get("zones", []) if item.get("id")]


def _audience_attrs(value: Any) -> list[dict]:
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []
    return value.get("attrs") or value.get("recommendations") or []


async def _normalize_brief(run: dict, workspace: dict) -> CapabilityResult:
    raw = _artifact(workspace, "brief", {})
    brief = BriefData.model_validate(raw).model_dump()
    return CapabilityResult(
        value=brief,
        evidence=[{"type": "workspace_artifact", "artifact": "brief",
                   "revision": workspace["artifacts"]["brief"]["revision"]}],
    )


def validate_brief_value(
    raw: Any, *, today: date | None = None,
) -> tuple[dict | None, list[str]]:
    """Normalize and validate the canonical brief used by Autopilot."""
    try:
        brief = BriefData.model_validate(raw or {}).model_dump()
    except Exception:
        return None, ["Brief không đúng cấu trúc hoặc còn thiếu trường bắt buộc"]
    errors = []
    if not brief["brand"].strip():
        errors.append("Thiếu tên thương hiệu")
    if brief["objective"] not in {"awareness", "consideration", "conversion", "retention"}:
        errors.append("Mục tiêu chiến dịch không hợp lệ")
    if brief["budget"] <= 0:
        errors.append("Ngân sách phải lớn hơn 0")
    try:
        start = date.fromisoformat(brief["startDate"][:10])
        end = date.fromisoformat(brief["endDate"][:10])
        if start > end:
            errors.append("Ngày bắt đầu phải trước ngày kết thúc")
        if end < (today or date.today()):
            errors.append("Ngày kết thúc đã ở quá khứ")
    except (TypeError, ValueError):
        errors.append("Ngày chạy phải có định dạng YYYY-MM-DD")
    return brief, errors


async def _validate_brief(run: dict, workspace: dict) -> CapabilityResult:
    brief, errors = validate_brief_value(_artifact(workspace, "brief", {}))
    if errors:
        return CapabilityResult(
            value={"valid": False, "errors": errors, "review_action": "retry"},
            evidence=[{"type": "validation", "passed": False, "errors": errors}],
            force_review=True,
        )
    return CapabilityResult(
        value={"valid": True, "brief": brief},
        evidence=[{"type": "validation", "passed": True}],
    )


async def _generate_strategy(run: dict, workspace: dict) -> CapabilityResult:
    brief = _artifact(workspace, "brief", {})
    objective = brief.get("objective", "awareness")
    budget_vnd = max(float(brief.get("budget", 0)), 0) * 1_000_000
    try:
        start = date.fromisoformat(str(brief.get("startDate", ""))[:10])
        end = date.fromisoformat(str(brief.get("endDate", ""))[:10])
        duration_days = max((end - start).days + 1, 1)
    except ValueError:
        duration_days = 7

    # These factors make the directional scenarios respond to the approved
    # brief. They are declared in the artifact so the UI can explain every
    # estimate instead of presenting model-looking numbers without provenance.
    objective_factor = {
        "awareness": 0.92, "consideration": 1.0,
        "conversion": 1.18, "retention": 1.08,
    }.get(objective, 1.0)
    pacing_factor = 1.12 if duration_days <= 3 else 1.05 if duration_days <= 7 else 0.97 if duration_days > 21 else 1.0
    volume_factor = 1.08 if budget_vnd < 10_000_000 else 0.96 if budget_vnd >= 50_000_000 else 1.0
    frequency_adjustment = (-0.15 if duration_days <= 3 else 0.2 if duration_days > 14 else 0) \
        + (0.15 if objective in {"conversion", "retention"} else 0)
    assumptions = [
        {
            "id": "balanced", "label": "Cân bằng",
            "budget_share": {"premium": 40, "reach": 40, "test": 20},
            "base_cpm": 55_000, "base_frequency": 3.0,
            "targeting_mode": "balanced", "placement_mode": "ranked",
            "rationale": "Cân bằng độ phủ, chất lượng hiển thị và khả năng thử nghiệm.",
            "tradeoffs": ["Độ phủ và chất lượng ở mức cân bằng", "20% ngân sách dành cho thử nghiệm"],
        },
        {
            "id": "reach_first", "label": "Ưu tiên độ phủ",
            "budget_share": {"premium": 25, "reach": 60, "test": 15},
            "base_cpm": 38_000, "base_frequency": 2.6,
            "targeting_mode": "broad", "placement_mode": "lowest_cpm",
            "rationale": "Tối đa hóa lượng người tiếp cận trong ngân sách đã duyệt.",
            "tradeoffs": ["Reach cao hơn với CPM mục tiêu thấp", "Chất lượng placement có thể phân tán hơn"],
        },
        {
            "id": "quality_first", "label": "Ưu tiên chất lượng",
            "budget_share": {"premium": 60, "reach": 25, "test": 15},
            "base_cpm": 80_000, "base_frequency": 3.4,
            "targeting_mode": "focused", "placement_mode": "quality",
            "rationale": "Ưu tiên vị trí có viewability và tương tác cao.",
            "tradeoffs": ["Ưu tiên inventory chất lượng cao", "Reach dự kiến thấp hơn do CPM cao"],
        },
    ]
    selected = "reach_first" if objective == "awareness" else (
        "quality_first" if objective == "conversion" else "balanced"
    )
    risk_by_objective = {
        "awareness": {"reach_first": "low", "balanced": "low", "quality_first": "medium"},
        "conversion": {"reach_first": "high", "balanced": "medium", "quality_first": "low"},
        "consideration": {"reach_first": "medium", "balanced": "low", "quality_first": "medium"},
        "retention": {"reach_first": "medium", "balanced": "low", "quality_first": "medium"},
    }
    options = []
    for assumption in assumptions:
        average_cpm = round(
            assumption["base_cpm"] * objective_factor * pacing_factor * volume_factor / 1000
        ) * 1000
        frequency = round(max(1.5, assumption["base_frequency"] + frequency_adjustment), 2)
        impressions = round(budget_vnd / average_cpm * 1000) \
            if average_cpm and budget_vnd else 0
        reach = round(impressions / frequency) if impressions else 0
        option = dict(assumption)
        option["average_cpm"] = average_cpm
        option["frequency"] = frequency
        option["metrics"] = {
            "budget_vnd": round(budget_vnd),
            "estimated_impressions": impressions,
            "estimated_reach": reach,
            "average_cpm": average_cpm,
            "frequency": frequency,
            "risk": risk_by_objective.get(objective, {}).get(assumption["id"], "medium"),
            "is_estimate": True,
        }
        options.append(option)
    selected_option = next(item for item in options if item["id"] == selected)
    return CapabilityResult(
        value={
            "kind": "campaign_strategy_simulation",
            "options": options,
            "selected": selected,
            "objective": objective,
            "selected_reason": selected_option["rationale"],
            "selection": {"source": "deterministic_recommendation"},
            "methodology": "Ước tính định hướng từ brief đã duyệt. CPM nền được điều chỉnh theo objective, thời lượng và quy mô ngân sách; forecast cuối dùng CPM/reach của placement catalog đã chọn.",
            "calculation": {
                "version": "brief_scenario_v2",
                "inputs": {
                    "budget_vnd": round(budget_vnd),
                    "objective": objective,
                    "duration_days": duration_days,
                    "objective_factor": objective_factor,
                    "pacing_factor": pacing_factor,
                    "volume_factor": volume_factor,
                },
                "formulas": {
                    "average_cpm": "base_cpm × objective_factor × pacing_factor × volume_factor",
                    "estimated_impressions": "budget_vnd ÷ average_cpm × 1,000",
                    "estimated_reach": "estimated_impressions ÷ frequency",
                },
            },
        },
        evidence=[
            {"type": "brief_field", "field": "objective", "value": objective},
            {"type": "strategy_simulation", "budget_vnd": round(budget_vnd),
             "option_ids": [item["id"] for item in options], "selected": selected,
             "duration_days": duration_days, "objective_factor": objective_factor,
             "pacing_factor": pacing_factor, "volume_factor": volume_factor,
             "method": "brief_scenario_v2"},
        ],
    )


async def _retrieve_audience(run: dict, workspace: dict) -> CapabilityResult:
    from handlers.audience import handle_dmp_recommend
    brief = dict(_artifact(workspace, "brief", {}))
    strategy = _artifact(workspace, "strategy", {})
    selected = strategy.get("selected", "balanced") if isinstance(strategy, dict) else "balanced"
    strategy_signal = {
        "reach_first": "Chiến lược: ưu tiên độ phủ rộng, CPM thấp và audience có quy mô lớn.",
        "quality_first": "Chiến lược: ưu tiên audience có ý định/độ liên quan cao và inventory chất lượng.",
        "balanced": "Chiến lược: cân bằng độ phủ, độ liên quan và khả năng thử nghiệm.",
    }.get(selected, "")
    brief["notes"] = " ".join(
        item for item in (str(brief.get("notes") or "").strip(), strategy_signal) if item
    )
    recommendation = await handle_dmp_recommend(run["session_id"], brief_override=brief)
    attrs = recommendation.get("recommendations") or []
    if not attrs:
        raise RuntimeError("audience retrieval returned no catalog-backed segments")
    attrs = attrs[:15]
    size = sum(
        int(((item.get("sizeMin") or 0) + (item.get("sizeMax") or 0)) / 2)
        for item in attrs
    )
    diagnostics = dict(
        recommendation.get("rag") or recommendation.get("retrieval") or {}
    )
    diagnostics.setdefault(
        "catalog_segments", recommendation.get("total_segments", len(attrs))
    )
    diagnostics.setdefault(
        "candidates", recommendation.get("total_segments", len(attrs))
    )
    return CapabilityResult(
        value={"attrs": attrs, "size": size, "retrieval": diagnostics},
        evidence=[{
            "type": "catalog_segments", "count": len(attrs),
            "ids": [item.get("_id") for item in attrs if item.get("_id")],
        }, {
            "type": "audience_pipeline",
            "retrieval_candidates": diagnostics.get("candidates", recommendation.get("total_segments", 0)),
            "rerank_enabled": bool(diagnostics.get("rerank_enabled")),
            "reranked": bool(diagnostics.get("reranked")),
            "selector": diagnostics.get("selector", "legacy"),
            "strategy_id": selected,
            "stage_ms": diagnostics.get("stage_ms", {}),
        }],
    )


async def _derive_targeting(run: dict, workspace: dict) -> CapabilityResult:
    from handlers.audience import _normalize_targeting
    from tools.targeting_options import get_targeting_options
    options = await get_targeting_options()
    # Deterministic, catalog-validated fallback. The model-assisted targeting
    # selector can later enrich this without weakening the source boundary.
    strategy = _artifact(workspace, "strategy", {})
    selected = strategy.get("selected", "balanced") if isinstance(strategy, dict) else "balanced"
    ages = {
        "reach_first": ["18-24", "25-34", "35-44"],
        "balanced": ["25-34", "35-44"],
        "quality_first": ["25-34", "35-44"],
    }.get(selected, ["25-34", "35-44"])
    targeting = _normalize_targeting({
        "geo": ["Hà Nội", "TP.HCM", "Đà Nẵng"],
        "age": ages,
        "gender": ["Male", "Female"],
    }, options)
    return CapabilityResult(
        value=targeting,
        evidence=[{"type": "targeting_catalog", "dimensions": list(targeting),
                   "strategy_id": selected}],
    )


async def _plan_placement_intent(run: dict, workspace: dict) -> CapabilityResult:
    """Rank inventory before creative exists; no compatibility decision is made here."""
    from tools.order_api import fetch_zone_conflicts
    from tools.zone_ranker import rank_zones

    brief = _artifact(workspace, "brief", {})
    ranked = await rank_zones(
        objective=brief.get("objective", "awareness"),
        budget=brief.get("budget", 0),
        kpi=brief.get("kpi", ""),
        creative_files=[],
        limit=100,
    )
    conflicts = await fetch_zone_conflicts(
        brief.get("startDate", ""), brief.get("endDate", "")
    )
    available = [zone for zone in ranked if not conflicts.get(zone["id"])]
    strategy = _artifact(workspace, "strategy", {})
    selected = strategy.get("selected", "balanced") if isinstance(strategy, dict) else "balanced"
    if selected == "reach_first":
        available.sort(
            key=lambda zone: (
                -float(zone.get("reach") or 0),
                float(zone.get("cpm") or 10**12),
                -float(zone.get("score") or 0),
            )
        )
    elif selected == "quality_first":
        available.sort(
            key=lambda zone: (
                float(zone.get("viewability") or zone.get("vi") or 0),
                float(zone.get("ctr") or 0),
                float(zone.get("score") or 0),
            ),
            reverse=True,
        )
    candidates = available[:12]
    if not candidates:
        return CapabilityResult(
            value={
                "candidate_zone_ids": [], "candidates": [],
                "reason": "no_available_inventory", "review_action": "retry",
                "message": "Không có placement trống cho thời gian chiến dịch.",
            },
            evidence=[{"type": "placement_intent", "candidate_count": 0,
                       "conflict_count": len(conflicts)}],
            force_review=True,
        )
    now = datetime.now(timezone.utc)
    value = {
        "kind": "placement_intent",
        "candidate_zone_ids": [zone["id"] for zone in candidates],
        "candidates": candidates,
        "strategy_id": selected,
        "inventory_checked_at": now,
        "expires_at": now + timedelta(minutes=10),
        "selection_method": "creative_agnostic_zone_rank_v1",
    }
    return CapabilityResult(
        value=value,
        evidence=[{
            "type": "placement_intent",
            "candidate_count": len(candidates),
            "candidate_zone_ids": value["candidate_zone_ids"],
            "conflict_count": len(conflicts),
            "strategy_id": selected,
        }],
    )


async def _plan_creative_formats(run: dict, workspace: dict) -> CapabilityResult:
    from autopilot.placement_planning import build_creative_format_plan

    intent_item = workspace.get("artifacts", {}).get("placement_intent", {})
    intent = dict(intent_item.get("value") or {})
    intent["artifact_revision"] = int(intent_item.get("revision", 0))
    source = run.get("creative_source", "upload")
    plan = build_creative_format_plan(
        intent,
        source=source,
        max_assets=config.AUTOPILOT_MAX_GENERATED_ASSETS,
    )
    plan["brief_revision"] = int(
        workspace.get("artifacts", {}).get("brief", {}).get("revision", 0)
    )
    if source == "ai_generate" and not plan["formats"]:
        return CapabilityResult(
            value={
                **plan, "reason": "no_supported_generation_format",
                "review_action": "retry",
                "message": "Các placement đề xuất chưa có format AI được hỗ trợ.",
            },
            evidence=[{"type": "creative_format_plan", "format_count": 0}],
            force_review=True,
        )
    return CapabilityResult(
        value=plan,
        evidence=[{
            "type": "creative_format_plan",
            "source": source,
            "format_count": len(plan["formats"]),
            "format_ids": [item["format_id"] for item in plan["formats"]],
            "covered_zone_ids": plan["covered_zone_ids"],
            "estimated_provider_calls": plan["estimated_provider_calls"],
            "max_assets": plan["max_assets"],
        }],
    )


async def _prepare_creatives(run: dict, workspace: dict) -> CapabilityResult:
    creative = _artifact(workspace, "creative", {})
    files = creative.get("files", []) if isinstance(creative, dict) else []
    source = run.get("creative_source", "upload")

    if source == "upload":
        if files:
            from tools.creative_match import match_file_to_format

            format_plan = _artifact(workspace, "creative_format_plan", {})
            required = list(format_plan.get("formats") or []) \
                if isinstance(format_plan, dict) else []
            matches = []
            missing = []
            for item in required:
                candidates = [
                    {"file": file, **match_file_to_format(file, item)}
                    for file in files
                ]
                matched = next((candidate for candidate in candidates if candidate["matched"]), None)
                if matched:
                    matches.append({
                        "format_id": item.get("format_id"),
                        "file_name": matched["file"].get("name"),
                        "mode": matched.get("mode"),
                        "ratio_diff": matched.get("ratio_diff"),
                    })
                else:
                    missing.append(item)
            coverage = {
                "required": len(required), "covered": len(required) - len(missing),
                "matches": matches,
                "missing": [{
                    "format_id": item.get("format_id"),
                    "width": item.get("width"), "height": item.get("height"),
                    "zone_ids": item.get("zone_ids") or [],
                } for item in missing],
            }
            if missing:
                missing_labels = ", ".join(
                    f"{item.get('width')}×{item.get('height')}" for item in missing
                )
                return CapabilityResult(
                    value={
                        **creative, "source": "upload", "formatCoverage": coverage,
                        "reason": "creative_format_coverage_gap",
                        "message": (
                            "Creative chưa phủ mọi format đã lập kế hoạch: "
                            f"{missing_labels}. Tải thêm hoặc duyệt để chỉ dùng placement tương thích."
                        ),
                    },
                    evidence=[
                        {"type": "creative_source", "source": "upload",
                         "count": len(files), "reused": True},
                        {"type": "creative_format_coverage", **coverage},
                    ],
                    externally_committed=True,
                    force_review=True,
                )
            return CapabilityResult(
                value=creative,
                evidence=[
                    {"type": "creative_source", "source": "upload",
                     "count": len(files), "reused": True},
                    {"type": "creative_format_coverage", **coverage},
                ],
                externally_committed=True,
            )
        return CapabilityResult(
            value={
                "files": [], "uploaded": False, "source": "upload",
                "reason": "missing_creative",
                "message": "Hãy tải ít nhất một creative để Autopilot tiếp tục.",
                "review_action": "retry",
            },
            evidence=[{"type": "input_required", "artifact": "creative",
                       "source": "upload"}],
            force_review=True,
        )

    if source != "ai_generate":
        raise ValueError(f"unsupported creative source: {source}")

    format_plan_item = workspace.get("artifacts", {}).get("creative_format_plan", {})
    format_plan = format_plan_item.get("value") or {}
    formats = list(format_plan.get("formats") or [])
    if not formats:
        return CapabilityResult(
            value={
                "files": [], "uploaded": False, "source": "ai_generate",
                "reason": "missing_creative_format_plan",
                "message": "Chưa có kế hoạch format creative hợp lệ.",
                "review_action": "retry",
            },
            evidence=[{"type": "input_required", "artifact": "creative_format_plan"}],
            force_review=True,
        )

    from autopilot.creative_generation import (
        generate_creatives,
        generation_idempotency_key,
    )
    brief_revision = int(
        workspace.get("artifacts", {}).get("brief", {}).get("revision", 0)
    )
    plan_revision = int(format_plan_item.get("revision", 0))
    expected_keys = [
        generation_idempotency_key(
            run["run_id"], spec["format_id"], brief_revision=brief_revision,
            format_plan_revision=plan_revision, variant=0,
        )
        for spec in formats
    ]
    by_key = {
        (item.get("generation") or {}).get("idempotencyKey"): item
        for item in files if item.get("source") == "ai_generated"
    }
    if all(key in by_key for key in expected_keys):
        generated_for_run = [by_key[key] for key in expected_keys]
        return CapabilityResult(
            value={
                "files": generated_for_run, "uploaded": True,
                "source": "ai_generate", "formatPlanRevision": plan_revision,
            },
            evidence=[{"type": "creative_source", "source": "ai_generate",
                       "count": len(generated_for_run), "reused": True}],
            externally_committed=True,
        )

    generated, failures = await generate_creatives(
        run,
        workspace,
        format_plan,
        concurrency=config.AUTOPILOT_CREATIVE_GENERATION_CONCURRENCY,
    )
    value = {
        "files": generated,
        "uploaded": bool(generated),
        "source": "ai_generate",
        "formatPlanRevision": plan_revision,
    }
    evidence = [{
        "type": "creative_generation",
        "source": "ai_generate",
        "count": len(generated),
        "format_ids": [item.get("formatId") for item in generated],
        "models": sorted({
            (item.get("generation") or {}).get("model")
            for item in generated if (item.get("generation") or {}).get("model")
        }),
        "idempotency_keys": [
            (item.get("generation") or {}).get("idempotencyKey") for item in generated
        ],
        "failed_formats": [item.get("format_id") for item in failures],
        "format_plan_revision": plan_revision,
    }]
    if failures:
        return CapabilityResult(
            value={
                **value, "generation_failures": failures,
                "reason": "creative_generation_partial_failure",
                "message": "Một số format chưa tạo được; các asset đã lưu sẽ được tái sử dụng khi thử lại.",
                "review_action": "retry",
            },
            evidence=evidence,
            force_review=True,
        )
    return CapabilityResult(
        value=value,
        evidence=evidence,
    )


async def _analyze_creatives(run: dict, workspace: dict) -> CapabilityResult:
    from creative_intel.service import enqueue_analysis, get_intel
    creative = _artifact(workspace, "creative", {})
    files = creative.get("files", []) if isinstance(creative, dict) else []
    if not files:
        return CapabilityResult(
            value={
                "ready": False, "reason": "missing_creative",
                "message": "Hãy tải ít nhất một creative để Autopilot phân tích.",
                "review_action": "retry",
            },
            evidence=[{"type": "input_required", "artifact": "creative"}],
            force_review=True,
        )
    docs = await get_intel(run["session_id"])
    known_urls = {doc.get("url") for doc in docs}
    pending_files = [item for item in files if item.get("url") not in known_urls]
    if pending_files:
        await enqueue_analysis(run["session_id"], pending_files)
        docs = await get_intel(run["session_id"])
    statuses = {doc.get("effective_status") for doc in docs}
    if statuses & {"queued", "analyzing", "committing"}:
        return CapabilityResult(
            value={
                "ready": False, "reason": "analysis_in_progress",
                "message": "Creative đang được phân tích. Tiếp tục sau khi có verdict.",
                "review_action": "retry",
            },
            evidence=[{"type": "creative_jobs", "statuses": sorted(statuses)}],
            force_review=True,
        )
    review_docs = [doc for doc in docs
                   if doc.get("effective_status") not in {"auto_approved", "approved_override"}]
    if review_docs:
        return CapabilityResult(
            value={
                "ready": False, "reason": "creative_needs_review",
                "analysis_ids": [doc.get("analysis_id") for doc in review_docs],
                "message": "Creative cần được người dùng duyệt hoặc thay thế.",
                "review_action": "retry",
            },
            evidence=[{"type": "creative_review", "count": len(review_docs)}],
            force_review=True,
        )
    current = await get_workspace(run["session_id"])
    verdict_item = current.get("artifacts", {}).get("creative_verdict", {})
    current_verdict = verdict_item.get("value")
    verdict_is_current = (
        verdict_item.get("status") == "approved" and bool(current_verdict)
    )
    refreshed_verdict = {
        "batch_id": (current_verdict or {}).get("batch_id"),
        "files": docs,
    }
    return CapabilityResult(
        value=current_verdict if verdict_is_current else refreshed_verdict,
        evidence=[{"type": "creative_verdicts", "count": len(docs),
                   "analysis_ids": [doc.get("analysis_id") for doc in docs],
                   "revalidated": not verdict_is_current}],
        # A stale canonical verdict must be recommitted by the Autopilot worker
        # against the current strategy/brief/creative input revisions. The VLM
        # result is reused; the stale-result guard is not bypassed.
        externally_committed=verdict_is_current,
    )


async def _rank_placements(run: dict, workspace: dict) -> CapabilityResult:
    from creative_intel.service import get_intel
    from tools.creative_match import enrich_files_with_intel
    from tools.order_api import fetch_zone_conflicts
    from tools.zone_ranker import rank_zones
    brief = _artifact(workspace, "brief", {})
    creative = _artifact(workspace, "creative", {})
    files = enrich_files_with_intel(
        (creative or {}).get("files", []), await get_intel(run["session_id"])
    )
    intent = _artifact(workspace, "placement_intent", {})
    candidate_ids = set(intent.get("candidate_zone_ids") or [])
    ranked = await rank_zones(
        objective=brief.get("objective", "awareness"),
        budget=brief.get("budget", 0), kpi=brief.get("kpi", ""),
        creative_files=files, limit=100,
    )
    conflicts = await fetch_zone_conflicts(
        brief.get("startDate", ""), brief.get("endDate", "")
    )
    # Delivery uses the explicit zone→creative assignment produced in the next
    # task.  Exact pixels are preferred, while assets inside the same 15% ratio
    # boundary as the Guided matcher are also safe to keep.  Larger mismatches
    # remain excluded even when their filename claims the target format.
    compatible_modes = {
        "exact_size", "strong_ratio", "same_ratio", "acceptable_ratio",
        "skin_match",
    }
    available = [
        zone for zone in ranked
        if (not candidate_ids or zone["id"] in candidate_ids)
        and not conflicts.get(zone["id"])
        and zone.get("match_mode") in compatible_modes
    ]
    strategy = _artifact(workspace, "strategy", {})
    selected = strategy.get("selected", "balanced") if isinstance(strategy, dict) else "balanced"
    if selected == "reach_first":
        available.sort(
            key=lambda zone: (
                -float(zone.get("reach") or 0),
                float(zone.get("cpm") or 10**12),
                -float(zone.get("score") or 0),
            )
        )
    elif selected == "quality_first":
        available.sort(
            key=lambda zone: (
                float(zone.get("viewability") or zone.get("vi") or 0),
                float(zone.get("ctr") or 0),
                float(zone.get("score") or 0),
            ),
            reverse=True,
        )
    available = available[:6]
    if not available:
        return CapabilityResult(
            value={
                "selectedZoneIds": [], "zones": [], "phase": "zones",
                "reason": "no_compatible_placements", "review_action": "retry",
                "message": "Chưa có placement trống tương thích với kích thước/định dạng creative.",
            },
            evidence=[{
                "type": "creative_placement_compatibility", "passed": False,
                "ranked": len(ranked), "conflicts": len(conflicts),
            }],
            force_review=True,
        )
    return CapabilityResult(
        value={"selectedZoneIds": [zone["id"] for zone in available],
               "zones": available, "phase": "zones"},
        evidence=[{"type": "zone_catalog", "ids": [zone["id"] for zone in available],
                   "strategy_id": selected, "placement_intent_candidates": len(candidate_ids)},
                  {"type": "conflict_check", "excluded": len(ranked) - len(available)}],
    )


async def _assign_creatives(run: dict, workspace: dict) -> CapabilityResult:
    from creative_intel.service import get_intel
    from tools.creative_match import auto_assign, enrich_files_with_intel
    from tools.zone_catalog import get_zone_map
    creative = _artifact(workspace, "creative", {})
    files = (creative or {}).get("files", [])
    files = enrich_files_with_intel(files, await get_intel(run["session_id"]))
    placement_value = _artifact(workspace, "placements", {})
    zone_ids = _placement_ids(placement_value)
    zone_map = await get_zone_map()
    zones = [zone_map[zone_id] for zone_id in zone_ids if zone_id in zone_map]
    assignment_artifact = workspace.get("artifacts", {}).get("assignments", {})
    assignment_value = assignment_artifact.get("value") or {}
    existing_assignments = (
        assignment_value.get("assignments", assignment_value)
        if isinstance(assignment_value, dict) else {}
    )
    selection = assignment_value.get("selection", {}) \
        if isinstance(assignment_value, dict) else {}
    operator_selected = (
        selection.get("source") == "operator"
        or assignment_artifact.get("updated_by") == "campaign_operator"
    )
    approved_file_indexes = {
        index for index, file in enumerate(files)
        if (
            file.get("analysisStatus")
            or (file.get("intel") or {}).get("effective_status")
        ) in {"auto_approved", "approved_override"}
    }
    manual_assignments = {
        zone_id: file_index
        for zone_id, file_index in existing_assignments.items()
        if zone_id in zone_ids
        and isinstance(file_index, int)
        and file_index in approved_file_indexes
    }
    if operator_selected and zone_ids and len(manual_assignments) == len(zone_ids):
        return CapabilityResult(
            value={
                "assignments": manual_assignments,
                "selection": selection or {"source": "operator"},
                "manual_override": True,
                "warnings": assignment_value.get("warnings", []),
            },
            evidence=[{
                "type": "manual_creative_assignment",
                "count": len(manual_assignments),
                "passed": True,
            }],
        )
    result = auto_assign(zones, files)
    if len(result["assignments"]) != len(zones):
        return CapabilityResult(
            value={**result, "review_action": "retry",
                   "message": "Chưa có creative đã duyệt cho mọi placement."},
            evidence=[{"type": "assignment_gap", "assigned": len(result["assignments"]),
                       "placements": len(zones)}],
            force_review=True,
        )
    weak = [
        zone_id for zone_id, file_index in result["assignments"].items()
        if float(result.get("scores", {}).get(zone_id, {}).get(str(file_index), -999)) < 1
    ]
    if weak:
        return CapabilityResult(
            value={**result, "review_action": "retry",
                   "message": "Creative không đủ tương thích cho: " + ", ".join(weak),
                   "incompatible_placements": weak},
            evidence=[{"type": "assignment_compatibility", "passed": False,
                       "placements": weak}],
            force_review=True,
        )
    return CapabilityResult(
        value=result,
        evidence=[{"type": "creative_assignment", "count": len(result["assignments"])}],
    )


async def _forecast(run: dict, workspace: dict) -> CapabilityResult:
    brief = _artifact(workspace, "brief", {})
    placements = _artifact(workspace, "placements", {})
    zones = placements.get("zones", []) if isinstance(placements, dict) else []
    budget_vnd = float(brief.get("budget", 0)) * 1_000_000
    valid_zones = [zone for zone in zones if float(zone.get("cpm", 0) or 0) > 0]
    weighted_reach = sum(max(float(zone.get("reach", 0) or 0), 1) for zone in valid_zones)
    avg_cpm = (
        sum(
            float(zone.get("cpm", 0)) * max(float(zone.get("reach", 0) or 0), 1)
            for zone in valid_zones
        ) / weighted_reach
        if valid_zones and weighted_reach > 0 else 0
    )
    impressions = round(budget_vnd / avg_cpm * 1000) if avg_cpm > 0 else 0
    reach_cap = sum(int(zone.get("reach", 0)) for zone in zones)
    strategy = _artifact(workspace, "strategy", {})
    selected = strategy.get("selected", "balanced") if isinstance(strategy, dict) else "balanced"
    selected_option = next(
        (item for item in strategy.get("options", []) if item.get("id") == selected), {}
    ) if isinstance(strategy, dict) else {}
    frequency = float((selected_option.get("metrics") or {}).get("frequency") or 3)
    reach = min(reach_cap, round(impressions / frequency)) if reach_cap > 0 else 0
    risk = "medium" if not zones or impressions <= 0 else "low"
    return CapabilityResult(
        value={"budget_vnd": budget_vnd, "estimated_impressions": impressions,
               "estimated_reach": reach, "average_cpm": round(avg_cpm),
               "frequency": frequency, "inventory_reach_cap": reach_cap,
               "risk": risk, "is_estimate": True,
               "calculation": {
                   "version": "catalog_forecast_v2",
                   "source": "selected placement catalog",
                   "inputs": {
                       "budget_vnd": budget_vnd,
                       "strategy_id": selected,
                       "frequency": frequency,
                       "inventory_reach_cap": reach_cap,
                       "zones": [{
                           "id": zone.get("id"), "name": zone.get("name"),
                           "cpm": zone.get("cpm", 0), "reach": zone.get("reach", 0),
                       } for zone in valid_zones],
                   },
                   "formulas": {
                       "average_cpm": "reach-weighted average CPM of selected catalog placements",
                       "estimated_impressions": "budget_vnd ÷ average_cpm × 1,000",
                       "estimated_reach": "min(inventory_reach_cap, estimated_impressions ÷ frequency)",
                   },
               }},
        evidence=[{"type": "forecast_inputs", "zone_count": len(zones),
                   "budget_vnd": budget_vnd, "average_cpm": round(avg_cpm),
                   "frequency": frequency, "inventory_reach_cap": reach_cap,
                   "method": "catalog_forecast_v2"}],
        force_review=risk != "low",
    )


def _build_creatives(files: list[dict], assignments: dict, zone_ids: list[str]) -> list[dict]:
    by_file: dict[int, list[str]] = {}
    for zone_id in zone_ids:
        if zone_id in assignments:
            by_file.setdefault(int(assignments[zone_id]), []).append(zone_id)
    creatives = []
    for file_idx, assigned_zones in by_file.items():
        file = files[file_idx] if file_idx < len(files) else {}
        intel = file.get("intel") or {}
        width = intel.get("width") or file.get("width", 0)
        height = intel.get("height") or file.get("height", 0)
        intended_format = (
            intel.get("intended_format")
            or file.get("intendedFormat")
            or ("skin" if intel.get("is_skin") else "banner")
        )
        creatives.append({
            "groupId": f"g_{file_idx}", "name": file.get("name", ""),
            "size": "skin" if intended_format == "skin" else f"{width}x{height}",
            "format": intended_format,
            "url": file.get("url", ""), "zones": assigned_zones,
            "analysisId": file.get("analysisId") or intel.get("analysis_id", ""),
        })
    return creatives


async def _build_order_draft(run: dict, workspace: dict) -> CapabilityResult:
    from config import config
    from creative_intel.service import get_intel
    from tools.creative_match import enrich_files_with_intel
    brief = _artifact(workspace, "brief", {})
    audience = _audience_attrs(_artifact(workspace, "audience", {}))
    targeting = _artifact(workspace, "targeting", {})
    creative = _artifact(workspace, "creative", {})
    files = enrich_files_with_intel(
        (creative or {}).get("files", []), await get_intel(run["session_id"])
    )
    placements = _placement_ids(_artifact(workspace, "placements", {}))
    assignments_value = _artifact(workspace, "assignments", {})
    assignments = assignments_value.get("assignments", assignments_value)
    payload = {
        "brand": brief.get("brand", ""),
        "advertiser": brief.get("advertiser") or brief.get("brand", ""),
        "objective": brief.get("objective", "awareness"),
        # The explicit launch review is the activation boundary. Once approved,
        # Autopilot creates a live campaign in the same side effect instead of
        # leaving an unexpected manual activation step in AdsPilot.
        "status": "active", "budget": brief.get("budget", 0) * 1_000_000,
        "daily": 0, "rate": 0, "rateType": "CPM",
        "startDate": brief.get("startDate", ""), "endDate": brief.get("endDate", ""),
        "placements": placements, "targeting": targeting,
        "dmp": {"include": [item.get("_id") for item in audience if item.get("_id")],
                "exclude": []},
        "freqCap": "3", "demoNamespace": config.DEMO_NAMESPACE,
        "idempotencyKey": f"autopilot:{config.DEMO_NAMESPACE}:{run['run_id']}:launch",
    }
    payload["creatives"] = _build_creatives(files, assignments, placements)
    payload["creative"] = payload["creatives"][0] if payload["creatives"] else {}
    return CapabilityResult(
        value={"payload": payload, "status": "draft"},
        evidence=[{"type": "order_draft", "placements": len(placements),
                   "creatives": len(payload["creatives"]),
                   "idempotency_key": payload["idempotencyKey"]}],
    )


async def _run_order_guard(run: dict, workspace: dict) -> CapabilityResult:
    from validation.order_guard import OrderValidationError, guard_order
    draft = _artifact(workspace, "order_draft", {})
    payload = draft.get("payload", {}) if isinstance(draft, dict) else {}
    session = await get_or_create_session(run["session_id"])
    try:
        await guard_order(payload, session)
    except OrderValidationError as exc:
        return CapabilityResult(
            value={"passed": False, "reasons": exc.reasons,
                   "review_action": "retry"},
            evidence=[{"type": "order_guard", "passed": False,
                       "reasons": exc.reasons}], force_review=True,
        )
    return CapabilityResult(
        value={"passed": True},
        evidence=[{"type": "order_guard", "passed": True}],
    )


async def _launch_approval(run: dict, workspace: dict) -> CapabilityResult:
    draft_item = workspace.get("artifacts", {}).get("order_draft", {})
    draft = draft_item.get("value") or {}
    payload = draft.get("payload", {}) if isinstance(draft, dict) else {}
    return CapabilityResult(
        value={"ready": True, "requires_explicit_approval": True,
               "order_draft_revision": int(draft_item.get("revision", 0)),
               "summary": {"brand": payload.get("brand"),
                           "budget": payload.get("budget"),
                           "placements": payload.get("placements", [])}},
        evidence=[{"type": "launch_boundary", "auto_approvable": False}],
        force_review=True,
    )


async def _create_order(run: dict, workspace: dict) -> CapabilityResult:
    from tools.order_api import create_order
    from validation.order_guard import guard_order
    from session import update_order_ids
    draft_item = workspace.get("artifacts", {}).get("order_draft", {})
    if draft_item.get("status") != "approved":
        raise RuntimeError("order draft is stale or missing; replan before launch")
    launch = next(
        (task for task in run.get("tasks", []) if task.get("key") == "launch_approval"),
        {},
    )
    approved_revision = int((launch.get("result") or {}).get("order_draft_revision", -1))
    current_revision = int(draft_item.get("revision", 0))
    if launch.get("status") != "succeeded" or approved_revision != current_revision:
        raise RuntimeError("launch approval does not match the current order draft")
    draft = draft_item.get("value") or {}
    payload = draft.get("payload", {}) if isinstance(draft, dict) else {}
    # Recheck live catalogs/conflicts immediately before the side effect.
    await guard_order(payload, await get_or_create_session(run["session_id"]))
    result = await create_order(payload)
    if result.get("error"):
        raise RuntimeError(f"order API rejected launch: {result}")
    order_id = result.get("id") or result.get("_id")
    if order_id:
        session = await get_or_create_session(run["session_id"])
        order_ids = list(dict.fromkeys([
            *(session.get("created_order_ids") or []), str(order_id),
        ]))
        await update_order_ids(run["session_id"], order_ids)
    return CapabilityResult(
        value={"order": result, "idempotency_key": payload["idempotencyKey"]},
        evidence=[{"type": "order_api", "order_id": order_id,
                   "idempotency_key": payload["idempotencyKey"]}],
    )


async def _verify_order(run: dict, workspace: dict) -> CapabilityResult:
    from tools.order_api import fetch_order
    current = _artifact(workspace, "order", {})
    order = current.get("order", current) if isinstance(current, dict) else {}
    order_id = order.get("id") or order.get("_id")
    if not order_id:
        raise RuntimeError("created order has no id")
    verified = await fetch_order(str(order_id))
    return CapabilityResult(
        value={"order": verified, "verified": True,
               "idempotency_key": current.get("idempotency_key")},
        evidence=[{"type": "order_verification", "order_id": order_id}],
    )


async def _create_setup_report(run: dict, workspace: dict) -> CapabilityResult:
    order = _artifact(workspace, "order", {})
    forecast = _artifact(workspace, "forecast", {})
    order_value = order.get("order", order) if isinstance(order, dict) else {}
    active = order_value.get("status") == "active"
    return CapabilityResult(
        value={"kind": "setup_report", "order": order, "forecast": forecast,
               "performance_data_available": active,
               "performance_data_mode": "synthetic_showcase" if active else "unavailable",
               "note": (
                   "Dữ liệu hiệu suất mô phỏng được suy ra từ forecast, ngân sách, thời gian và placement để minh họa cách báo cáo hoạt động. Khi có delivery thật, số liệu thực sẽ thay thế phần mô phỏng."
                   if active else "Báo cáo mô phỏng mở khi campaign ở trạng thái active."
               )},
        evidence=[{"type": "workspace_artifacts", "artifacts": ["order", "forecast"]}],
    )


CAPABILITIES = {
    "normalize_brief": _normalize_brief,
    "validate_brief": _validate_brief,
    "generate_strategy_options": _generate_strategy,
    "retrieve_and_rank_audience": _retrieve_audience,
    "derive_targeting_and_exclusions": _derive_targeting,
    "plan_placement_intent": _plan_placement_intent,
    "plan_creative_formats": _plan_creative_formats,
    "prepare_creatives": _prepare_creatives,
    "analyze_creatives": _analyze_creatives,
    "rank_available_placements": _rank_placements,
    "assign_creatives_to_placements": _assign_creatives,
    "forecast_reach_cost_and_risk": _forecast,
    "build_order_draft": _build_order_draft,
    "run_order_guard": _run_order_guard,
    "request_launch_approval": _launch_approval,
    "create_order_idempotently": _create_order,
    "verify_order": _verify_order,
    "create_setup_report": _create_setup_report,
}


async def execute(task: dict, run: dict) -> CapabilityResult:
    capability = CAPABILITIES.get(task["capability"])
    if capability is None:
        raise ValueError(f"unsupported capability: {task['capability']}")
    workspace = await get_workspace(run["session_id"])
    return await capability(run, workspace)
