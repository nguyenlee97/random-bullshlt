"""Deterministic L2 diagnostic playbooks.

A playbook binds one L1 issue type to the probes worth running and to a fixed
set of candidate root causes. Ranking is rule-based and reproducible: the same
evidence always yields the same order and the same confidence numbers, so the
eleven scenario presets can be asserted in tests.

Weight keys are ``(probe_id, status)`` or ``(probe_id, status, finding)``. The
three-part form is what lets two anomalies from the same probe support
different causes — a placement with no creative and a placement whose creative
is the wrong size both make ``creative_compatibility`` anomalous, but they are
not the same fault and must not collapse into one ranking.

No model is called here. An LLM may later narrate this output, but it must not
change the ranking.
"""
from __future__ import annotations
from copy import deepcopy

from evaluation.probes import ANOMALY, OK, UNAVAILABLE


# Causes that must be ruled out before creative or placement is blamed. A
# broken measurement path imitates every performance problem at once.
GATE_CATEGORIES = ("data_quality", "tracking")

# How hard non-gate hypotheses are damped while a gate cause is live.
# Measurement faults occupy a separate priority tier; scores are not probabilities.


HYPOTHESES: dict[str, dict] = {
    "data_quality_incomplete": {
        "label": "Dữ liệu report thiếu hoặc trễ",
        "category": "data_quality",
        "explanation": "Số liệu chưa đủ để kết luận; chỉ số xấu có thể là ảo.",
    },
    "click_tracking_failure": {
        "label": "Click telemetry hỏng",
        "category": "tracking",
        "explanation": "Quảng cáo vẫn hiển thị nhưng click không được ghi nhận.",
    },
    "creative_render_failure": {
        "label": "Creative không render được",
        "category": "creative",
        "explanation": "Asset không hiển thị đúng nên không thể tạo tương tác.",
    },
    "creative_format_mismatch": {
        "label": "Creative sai kích thước hoặc format",
        "category": "creative",
        "explanation": "Creative không khớp hợp đồng placement; chưa kiểm chứng việc publisher từ chối asset.",
    },
    "creative_missing": {
        "label": "Placement không có creative",
        "category": "creative",
        "explanation": "Placement đang chạy mà không có asset nào được gán.",
    },
    "creative_fatigue": {
        "label": "Creative bị bão hòa",
        "category": "creative",
        "explanation": "CTR giảm theo thời gian gợi ý fatigue; cần frequency và lịch sử creative để xác nhận.",
    },
    "creative_underperformance": {
        "label": "Creative không thuyết phục",
        "category": "creative",
        "explanation": (
            "CTR thấp khi delivery còn ổn định; cần thử creative và loại trừ lỗi "
            "tracking trước khi kết luận về nội dung."
        ),
    },
    "placement_underperformance": {
        "label": "Placement kém hiệu quả",
        "category": "placement",
        "explanation": "Placement dưới benchmark catalog; lựa chọn khác chưa được xác minh về khả dụng hoặc hiệu quả.",
    },
    "config_drift": {
        "label": "Cấu hình campaign đã thay đổi",
        "category": "config",
        "explanation": "Cấu hình khác snapshot report baseline; baseline không phải bản cấu hình có chữ ký phê duyệt.",
    },
    "inventory_shortfall": {
        "label": "Thiếu inventory tại placement",
        "category": "placement",
        "explanation": "Delivery thiếu so với baseline; cần dữ liệu inventory publisher để xác nhận nguyên nhân nguồn cung.",
    },
    "budget_pacing_shortfall": {
        "label": "Ngân sách không được tiêu thụ",
        "category": "pacing",
        "explanation": "Spend thấp hoặc lệch baseline; quan hệ nhân quả với delivery chưa được xác minh.",
    },
    "natural_variance": {
        "label": "Dao động tự nhiên",
        "category": "baseline",
        "explanation": "Chưa có tín hiệu kỹ thuật đủ mạnh; dao động tự nhiên vẫn cần được kiểm tra bằng thêm dữ liệu.",
    },
}


def _recovery(action_id: str, label: str, impact: str, risk: str,
              verification: str, mutating: bool = True) -> dict:
    return {
        "action_id": action_id,
        "label": label,
        "expected_impact": impact,
        "risk": risk,
        "verification_plan": verification,
        "mutating": mutating,
        "available": False,  # Full L3 execution is deliberately unavailable.
    }


RECOVERY_OPTIONS: dict[str, list[dict]] = {
    "data_quality_incomplete": [
        _recovery(
            "wait_attribution_window", "Chờ hết attribution window rồi đánh giá lại",
            "Khôi phục độ tin cậy của số liệu, không đổi hiệu suất thật.",
            "low", "Chạy lại evaluation sau khi dữ liệu đủ ngày.", mutating=False,
        ),
    ],
    "click_tracking_failure": [
        _recovery(
            "repair_click_tracking", "Sửa click area và event pipeline",
            "Khôi phục CTR đo được về mức thật.",
            "medium", "So sánh click/impression trước và sau trong 2 window.",
        ),
    ],
    "creative_render_failure": [
        _recovery(
            "replace_creative", "Thay creative bằng asset hợp lệ",
            "Khôi phục delivery và CTR về mức baseline.",
            "medium", "Kiểm tra render và delivery ratio trong 2 window.",
        ),
        _recovery(
            "pause_placement", "Tạm dừng placement lỗi",
            "Ngăn ngân sách chi cho inventory không hiển thị.",
            "high", "Xác nhận spend dừng và ngân sách được giữ lại.",
        ),
    ],
    "creative_format_mismatch": [
        _recovery(
            "reassign_creative", "Gán lại creative đúng kích thước cho placement",
            "Placement bắt đầu phân phối đúng hợp đồng.",
            "medium", "Đối chiếu size creative với size placement rồi kiểm tra delivery.",
        ),
    ],
    "creative_missing": [
        _recovery(
            "assign_creative", "Gán creative phù hợp cho placement",
            "Placement bắt đầu có thể phân phối.",
            "medium", "Kiểm tra impression xuất hiện trong window kế tiếp.",
        ),
    ],
    "creative_fatigue": [
        _recovery(
            "rotate_creative", "Luân phiên hoặc làm mới creative",
            "CTR phục hồi một phần về mức đầu chiến dịch.",
            "medium", "So sánh CTR 2 window sau khi đổi creative.",
        ),
        _recovery(
            "cap_frequency", "Giới hạn tần suất hiển thị",
            "Giảm bão hòa, CTR ổn định lại.",
            "medium", "Theo dõi frequency và CTR trong 2 window.",
        ),
    ],
    "creative_underperformance": [
        _recovery(
            "test_alternative_creative", "Thử creative thay thế trên cùng placement",
            "Tách bạch thông điệp khỏi vị trí; giữ nguyên biến số placement.",
            "medium", "So sánh CTR hai creative trên cùng placement trong 2 window.",
        ),
    ],
    "placement_underperformance": [
        _recovery(
            "shift_allocation", "Chuyển phân bổ sang placement tương đương tốt hơn",
            "Cải thiện CTR tổng thể theo chênh lệch benchmark.",
            "high", "So sánh CTR và spend giữa hai placement sau 2 window.",
        ),
    ],
    "config_drift": [
        _recovery(
            "restore_config", "Khôi phục cấu hình về revision baseline",
            "Đưa campaign về trạng thái đã được duyệt.",
            "high", "Đối chiếu lại config với baseline và chạy evaluation.",
        ),
    ],
    "inventory_shortfall": [
        _recovery(
            "add_placement", "Bổ sung placement cùng nhóm để bù delivery",
            "Bù phần impression còn thiếu so với kế hoạch.",
            "high", "Theo dõi delivery ratio tổng trong 2 window.",
        ),
    ],
    "budget_pacing_shortfall": [
        _recovery(
            "raise_daily_cap", "Nới daily cap hoặc mở lại phân phối",
            "Ngân sách được tiêu thụ đúng kế hoạch trở lại.",
            "high", "So sánh spend tích lũy với kế hoạch trong 2 window.",
        ),
    ],
    "natural_variance": [],
}


PLAYBOOKS: dict[str, dict] = {
    "ctr_regression": {
        "title": "Điều tra CTR giảm",
        "probes": [
            "data_completeness", "click_telemetry", "creative_compatibility",
            "creative_fatigue", "placement_benchmark", "config_drift", "spend_pacing",
        ],
        "hypotheses": [
            {"id": "data_quality_incomplete", "prior": 8, "weights": {
                ("data_completeness", ANOMALY): 62, ("data_completeness", OK): -6,
            }},
            {"id": "click_tracking_failure", "prior": 10, "weights": {
                ("click_telemetry", ANOMALY, "telemetry_signal"): 70,
                ("click_telemetry", ANOMALY, "zero_clicks_while_serving"): 62,
                ("click_telemetry", OK): -8,
            }},
            {"id": "creative_render_failure", "prior": 8, "weights": {
                ("creative_compatibility", ANOMALY, "render_signal"): 46,
                ("creative_compatibility", OK): -6,
                ("click_telemetry", ANOMALY): -12,
            }},
            {"id": "creative_format_mismatch", "prior": 6, "weights": {
                ("creative_compatibility", ANOMALY, "size_mismatch"): 44,
                ("creative_compatibility", ANOMALY, "format_mismatch"): 44,
            }},
            {"id": "creative_missing", "prior": 4, "weights": {
                ("creative_compatibility", ANOMALY, "no_creative"): 50,
            }},
            {"id": "creative_fatigue", "prior": 12, "weights": {
                ("creative_fatigue", ANOMALY, "progressive_decay"): 52,
                ("creative_fatigue", OK): -8,
                ("click_telemetry", ANOMALY): -10,
                # A placement trailing its own benchmark explains the drop
                # without needing creative decay.
                ("placement_benchmark", ANOMALY): -10,
            }},
            {"id": "creative_underperformance", "prior": 10, "weights": {
                # Impressions and money delivered as planned; only the response
                # fell. That points at the message, not the slot or the plumbing.
                ("spend_pacing", ANOMALY, "output_down_spend_flat"): 46,
                ("creative_fatigue", OK, "step_change"): 16,
                ("creative_compatibility", OK): 6,
                ("click_telemetry", OK): 6,
            }},
            {"id": "placement_underperformance", "prior": 10, "weights": {
                ("placement_benchmark", ANOMALY, "below_benchmark_with_compatible_alternatives"): 38,
                ("placement_benchmark", ANOMALY, "below_benchmark_with_unverified_alternatives"): 18,
                # Rising cost per result is the placement's signature.
                ("spend_pacing", ANOMALY, "spend_up_output_down"): 40,
                ("creative_fatigue", ANOMALY): -8,
            }},
            {"id": "config_drift", "prior": 5, "weights": {
                ("config_drift", ANOMALY): 40, ("config_drift", OK): -4,
            }},
            {"id": "natural_variance", "prior": 12, "weights": {
                ("click_telemetry", OK): 6,
                ("creative_fatigue", OK, "no_fatigue"): 6,
                ("placement_benchmark", OK): 6,
                ("data_completeness", OK): 4,
                ("spend_pacing", OK): 6,
            }},
        ],
    },
    "delivery_drop": {
        "title": "Điều tra delivery giảm",
        "probes": [
            "data_completeness", "delivery_pattern", "creative_compatibility",
            "config_drift", "placement_benchmark", "click_telemetry", "spend_pacing",
        ],
        "hypotheses": [
            {"id": "data_quality_incomplete", "prior": 8, "weights": {
                ("data_completeness", ANOMALY): 58, ("data_completeness", OK): -6,
            }},
            {"id": "creative_render_failure", "prior": 12, "weights": {
                ("creative_compatibility", ANOMALY, "render_signal"): 56,
                ("creative_compatibility", OK): -8,
                ("delivery_pattern", ANOMALY): 10,
                ("spend_pacing", ANOMALY, "cost_efficiency_drop"): 14,
            }},
            {"id": "creative_format_mismatch", "prior": 6, "weights": {
                ("creative_compatibility", ANOMALY, "size_mismatch"): 40,
                ("creative_compatibility", ANOMALY, "format_mismatch"): 40,
            }},
            {"id": "creative_missing", "prior": 5, "weights": {
                ("creative_compatibility", ANOMALY, "no_creative"): 52,
            }},
            {"id": "config_drift", "prior": 10, "weights": {
                ("config_drift", ANOMALY): 54, ("config_drift", OK): -6,
            }},
            {"id": "inventory_shortfall", "prior": 12, "weights": {
                ("delivery_pattern", ANOMALY): 26,
                ("creative_compatibility", OK): 12,
                ("config_drift", OK): 8,
                ("spend_pacing", ANOMALY, "spend_down"): 22,
            }},
            {"id": "budget_pacing_shortfall", "prior": 8, "weights": {
                ("spend_pacing", ANOMALY, "spend_collapsed"): 44,
                ("spend_pacing", ANOMALY, "spend_down"): 18,
                ("delivery_pattern", ANOMALY): 8,
            }},
            {"id": "placement_underperformance", "prior": 8, "weights": {
                ("placement_benchmark", ANOMALY): 26,
                ("spend_pacing", ANOMALY, "spend_up_output_down"): 24,
                ("spend_pacing", ANOMALY, "cost_efficiency_drop"): 20,
            }},
            {"id": "natural_variance", "prior": 10, "weights": {
                ("delivery_pattern", OK): 24,
                ("data_completeness", OK): 4,
                ("spend_pacing", OK): 8,
            }},
        ],
    },
    "creative_failure": {
        "title": "Điều tra lỗi creative",
        "probes": [
            "data_completeness", "creative_compatibility", "delivery_pattern",
            "click_telemetry", "config_drift", "spend_pacing",
        ],
        "hypotheses": [
            {"id": "data_quality_incomplete", "prior": 5, "weights": {
                ("data_completeness", ANOMALY): 48, ("data_completeness", OK): -4,
            }},
            {"id": "creative_render_failure", "prior": 30, "weights": {
                # L1 raised this incident from the render signal, so the probe
                # reading that same signal is confirmation, not new evidence.
                # A large weight here would re-count one fact twice.
                ("creative_compatibility", ANOMALY, "render_signal"): 12,
                ("creative_compatibility", OK): -18,
                ("delivery_pattern", ANOMALY): 10,
            }},
            {"id": "creative_format_mismatch", "prior": 10, "weights": {
                ("creative_compatibility", ANOMALY, "size_mismatch"): 50,
                ("creative_compatibility", ANOMALY, "format_mismatch"): 50,
            }},
            {"id": "creative_missing", "prior": 8, "weights": {
                ("creative_compatibility", ANOMALY, "no_creative"): 56,
            }},
            {"id": "click_tracking_failure", "prior": 6, "weights": {
                ("click_telemetry", ANOMALY, "telemetry_signal"): 50,
                ("click_telemetry", ANOMALY, "zero_clicks_while_serving"): 20,
                ("click_telemetry", OK): -6,
            }},
            {"id": "config_drift", "prior": 5, "weights": {
                ("config_drift", ANOMALY): 34, ("config_drift", OK): -4,
            }},
            {"id": "natural_variance", "prior": 4, "weights": {
                ("creative_compatibility", OK): 10, ("delivery_pattern", OK): 10,
            }},
        ],
    },
}


# Bounded playbooks for the remaining L1 incident types.
for issue, title, base, selected in [
    ('data_quality', 'Điều tra chất lượng dữ liệu', 'ctr_regression', ['data_completeness', 'click_telemetry']),
    ('click_tracking_failure', 'Điều tra click tracking', 'ctr_regression', ['data_completeness', 'click_telemetry', 'creative_compatibility', 'config_drift']),
    ('config_drift', 'Điều tra thay đổi cấu hình', 'delivery_drop', ['data_completeness', 'config_drift', 'delivery_pattern']),
    ('pacing_error', 'Điều tra pacing ngân sách', 'delivery_drop', ['data_completeness', 'spend_pacing', 'delivery_pattern', 'config_drift']),
    ('robust_trend_drop', 'Điều tra xu hướng CTR', 'ctr_regression', ['data_completeness', 'creative_fatigue', 'click_telemetry', 'spend_pacing', 'placement_benchmark']),
]:
    candidates = deepcopy(PLAYBOOKS[base]['hypotheses'])
    candidates = [c for c in candidates if any(k[0] in selected and w > 0 for k, w in c['weights'].items())]
    PLAYBOOKS[issue] = {'title': title, 'probes': selected, 'hypotheses': candidates}


def supported_issue_types() -> list[str]:
    return sorted(PLAYBOOKS)


def probes_for(issue_type: str) -> list[str]:
    return list((PLAYBOOKS.get(issue_type) or {}).get("probes") or [])


def _confidence_label(score: float) -> str:
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def rank_hypotheses(issue_type: str, probe_results: dict[str, dict]) -> dict:
    """Score candidate causes from probe evidence. Pure and reproducible."""
    playbook = PLAYBOOKS.get(issue_type)
    if not playbook:
        return {
            "issue_type": issue_type,
            "supported": False,
            "hypotheses": [],
            "gate": {"applied": False, "reasons": []},
        }

    gate_reasons = [
        probe_id for probe_id, result in probe_results.items()
        if result.get("status") == ANOMALY and probe_id in ("data_completeness", "click_telemetry")
    ]
    gate_applied = bool(gate_reasons)

    scored: list[dict] = []
    for candidate in playbook["hypotheses"]:
        meta = HYPOTHESES[candidate["id"]]
        score = float(candidate["prior"])
        supporting: list[str] = []
        contradicting: list[str] = []
        unavailable: list[str] = []
        for key, weight in candidate["weights"].items():
            probe_id, status = key[0], key[1]
            finding = key[2] if len(key) > 2 else None
            result = probe_results.get(probe_id)
            if not result:
                continue
            if result["status"] == UNAVAILABLE:
                unavailable.append(probe_id)
                continue
            if result["status"] != status:
                continue
            # A finding-specific edge only fires for that exact finding, so two
            # anomalies from one probe can support different causes.
            if finding is not None and result.get("finding") != finding:
                continue
            score += weight
            (supporting if weight > 0 else contradicting).append(probe_id)
        # Nothing may outrank a live measurement problem: a broken data or
        # click path makes every downstream metric untrustworthy.
        prioritized = gate_applied and meta['category'] in GATE_CATEGORIES and any(p in gate_reasons for p in supporting)
        scored.append({
            "hypothesis_id": candidate["id"],
            "label": meta["label"],
            "category": meta["category"],
            "explanation": meta["explanation"],
            "raw_score": round(max(score, 0.0), 3),
            'measurement_priority': prioritized,
            "supporting_probes": sorted(set(supporting)),
            "contradicting_probes": sorted(set(contradicting)),
            "unavailable_probes": sorted(set(unavailable)),
            "recovery_options": RECOVERY_OPTIONS.get(candidate["id"], []),
        })

    total = sum(item["raw_score"] for item in scored)
    for item in scored:
        item["confidence"] = round(item["raw_score"] / total * 100, 1) if total else 0.0
        item['score_share'] = item['confidence']
        item['score_semantics'] = 'relative_rule_support_not_probability'
        item["confidence_label"] = _confidence_label(item["confidence"])
    # Ties break on hypothesis id so the order is stable across runs.
    scored.sort(key=lambda item: (not item['measurement_priority'], -item['score_share'], item['hypothesis_id']))
    available = [p for p in probe_results.values() if p.get('status') != UNAVAILABLE]
    insufficient = not available or not scored or not scored[0]['supporting_probes']
    margin = abs(scored[0]['score_share'] - scored[1]['score_share']) if len(scored) > 1 else 100
    ambiguous = not insufficient and (margin < 10 or scored[0]['hypothesis_id'] in {'creative_underperformance', 'placement_underperformance', 'inventory_shortfall', 'creative_fatigue', 'natural_variance'}
        or (scored[0]['hypothesis_id'] == 'click_tracking_failure' and probe_results.get('click_telemetry', {}).get('finding') != 'telemetry_signal'))
    return {
        "issue_type": issue_type,
        "supported": True,
        "title": playbook["title"],
        "hypotheses": [] if insufficient else scored,
        'assessment': 'insufficient_evidence' if insufficient else 'ambiguous' if ambiguous else 'supported_hypothesis',
        'ambiguous': ambiguous,
        'margin': margin,
        'missing_probes': [p for p in playbook['probes'] if probe_results.get(p, {}).get('status', UNAVAILABLE) == UNAVAILABLE],
        "gate": {
            "applied": gate_applied,
            "reasons": sorted(gate_reasons),
            "strategy": 'measurement_first' if gate_applied else 'rule_support',
            "note": (
                "Nguyên nhân đo lường được ưu tiên; các giả thuyết creative/placement "
                "chỉ là giả thuyết cho tới khi dữ liệu và tracking được xác nhận."
            ) if gate_applied else "",
        },
    }
