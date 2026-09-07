"""Canonical, server-owned L3 action contracts.

L2 may identify a bounded cause, but it never chooses a command or executor.
Only definitions in this registry can become a recovery proposal.
"""
from __future__ import annotations

from copy import deepcopy


SCHEMA_VERSION = "l3-recovery-proposal-v2"
ACTION_KINDS = {"executable_action", "operator_workflow", "engineering_escalation"}


def _definition(action_id: str, *, label: str, kind: str, issues: tuple[str, ...],
                causes: tuple[str, ...], risk: str, instructions: tuple[str, ...],
                lab_intervention: str | None = None,
                production_executor: str | None = None) -> dict:
    if kind not in ACTION_KINDS:
        raise ValueError(f"unsupported recovery action kind: {kind}")
    return {
        "action_id": action_id,
        "action_version": 1,
        "label": label,
        "kind": kind,
        "supported_issue_types": list(issues),
        "supported_causes": list(causes),
        "risk": risk,
        "supported_scopes": ["campaign", "placement"],
        "expected_impact": "Tạo một bước recovery có kiểm soát để kiểm chứng bằng Evaluation; không tự suy diễn KPI đã phục hồi.",
        "verification": {
            "kind": "rerun_evaluation_same_scope",
            "note": "Kết quả chỉ được xác nhận từ revision/evidence mới, không từ trạng thái checklist.",
        },
        "rollback": {
            "supported": bool(production_executor),
            "note": "Production rollback chỉ tồn tại khi action có executor đã đăng ký.",
        },
        "instructions": [
            {"step_id": f"step-{index}", "label": text, "required": True}
            for index, text in enumerate(instructions, 1)
        ],
        "lab_intervention": lab_intervention,
        "production_executor": production_executor,
    }


ACTION_DEFINITIONS = {
    "restore_config_revision": _definition(
        "restore_config_revision",
        label="Khôi phục campaign config về revision đã duyệt",
        kind="executable_action",
        issues=("config_drift",), causes=("configuration_drift",), risk="medium",
        instructions=("Kiểm tra exact diff và target revision.", "Duyệt bằng mã một lần."),
        lab_intervention="restore_config_fixture",
        production_executor="restore_config_revision",
    ),
    "hold_optimization_and_recheck": _definition(
        "hold_optimization_and_recheck",
        label="Tạm dừng tối ưu và đánh giá lại",
        kind="operator_workflow",
        issues=("data_quality", "robust_trend_drop", "pacing_error", "config_drift",
                "delivery_drop", "ctr_regression", "creative_failure", "click_tracking_failure"),
        causes=("none", "budget_pacing_shortfall", "natural_variance", "configuration_drift"), risk="low",
        instructions=(
            "Không thay creative, placement hoặc budget khi bằng chứng còn thiếu.",
            "Chờ đủ attribution/report window rồi chạy Evaluation lại.",
        ),
        lab_intervention=None,
    ),
    "request_measurement_reconciliation": _definition(
        "request_measurement_reconciliation",
        label="Đối soát measurement trước khi tối ưu",
        kind="operator_workflow",
        issues=("click_tracking_failure", "data_quality", "ctr_regression", "delivery_drop", "creative_failure"),
        causes=("click_measurement_gap", "report_measurement_gap", "click_tracking_failure", "data_quality_incomplete"),
        risk="low",
        instructions=(
            "Đối chiếu serving, click event và report record theo cùng time window.",
            "Ghi nhận phần dữ liệu thiếu hoặc trễ và chạy Evaluation lại.",
        ),
        lab_intervention="restore_click_measurement",
    ),
    "prepare_creative_replacement": _definition(
        "prepare_creative_replacement",
        label="Chuẩn bị creative thay thế để review",
        kind="operator_workflow",
        issues=("creative_failure", "ctr_regression", "robust_trend_drop", "delivery_drop"),
        causes=("creative_contract_mismatch", "creative_render_failure", "creative_underperformance", "creative_fatigue"),
        risk="medium",
        instructions=(
            "Chuẩn bị asset tương thích placement; không tự thay creative live.",
            "Review preview và quyền sử dụng asset trước khi tạo thay đổi riêng.",
        ),
        lab_intervention="replace_creative_fixture",
    ),
    "propose_placement_switch": _definition(
        "propose_placement_switch",
        label="Chuẩn bị phương án placement thay thế",
        kind="operator_workflow",
        issues=("delivery_drop", "ctr_regression", "pacing_error"),
        causes=("placement_benchmark_gap", "placement_underperformance", "inventory_shortfall"),
        risk="medium",
        instructions=(
            "Kiểm tra benchmark, creative compatibility và booking availability.",
            "Tạo phương án phân bổ để operator review; không tự chuyển placement live.",
        ),
        lab_intervention="switch_placement_fixture",
    ),
    "prepare_click_surface_fix": _definition(
        "prepare_click_surface_fix",
        label="Escalate sửa click surface",
        kind="engineering_escalation",
        issues=("click_tracking_failure", "ctr_regression"),
        causes=("click_obstruction",), risk="medium",
        instructions=(
            "Đính kèm browser evidence và selector/hit-target bị ảnh hưởng.",
            "Chuyển engineering owner xử lý qua quy trình release riêng.",
        ),
        lab_intervention="remove_click_overlay_fixture",
    ),
    "prepare_report_pipeline_fix": _definition(
        "prepare_report_pipeline_fix",
        label="Escalate sửa report pipeline",
        kind="engineering_escalation",
        issues=("data_quality", "click_tracking_failure"),
        causes=("report_measurement_gap",), risk="medium",
        instructions=(
            "Đính kèm missing rows, revision và time window bị ảnh hưởng.",
            "Chuyển data/report owner xử lý qua quy trình release riêng.",
        ),
        lab_intervention="backfill_attribution_fixture",
    ),
}


LEGACY_CAUSE_MAP = {
    "config_drift": "configuration_drift",
    "click_tracking_failure": "click_measurement_gap",
    "data_quality_incomplete": "report_measurement_gap",
    "placement_underperformance": "placement_benchmark_gap",
    "creative_render_failure": "creative_contract_mismatch",
    "creative_format_mismatch": "creative_contract_mismatch",
    "creative_missing": "creative_contract_mismatch",
}


def action_definition(action_id: str) -> dict | None:
    value = ACTION_DEFINITIONS.get(str(action_id or ""))
    return deepcopy(value) if value else None


def public_definitions() -> list[dict]:
    return [deepcopy(value) for value in ACTION_DEFINITIONS.values()]


def canonical_cause(bundle: dict) -> str:
    """Return a cause only when the current L2 bundle actually supports it."""
    if not bundle or bundle.get("assessment") != "supported_hypothesis":
        return "none"
    if bundle.get("mode") == "multi_agent":
        if bundle.get("cause_status") != "supported_hypothesis":
            return "none"
        if bundle.get("partial") or (bundle.get("review") or {}).get("contradictions"):
            return "none"
        return str(bundle.get("cause_code") or "none")
    if bundle.get("ambiguous"):
        return "none"
    cause = str((bundle.get("top_hypothesis") or {}).get("hypothesis_id") or "none")
    return LEGACY_CAUSE_MAP.get(cause, cause)
