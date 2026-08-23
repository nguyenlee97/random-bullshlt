from __future__ import annotations

from collections import defaultdict
from math import sqrt
from statistics import median


DEFAULT_POLICY = {
    "version": "evaluation-policy-v1",
    "enabled": True,
    "level": "L1",
    "schedule_minutes": 60,
    "delivery_ratio_threshold": 0.70,
    "persistence_windows": 2,
    "ctr_relative_drop_threshold": 0.30,
    "ctr_z_threshold": -2.58,
    "ctr_min_impressions": 500,
    "pacing_low_threshold": 0.65,
    "pacing_high_threshold": 1.35,
}


def _group(records: list[dict]) -> dict[tuple[str, str], dict]:
    return {
        (str(row.get("placementId") or "unknown"), str(row.get("date") or "")): row
        for row in records
    }


def _issue(issue_type: str, scope: str, severity: str, title: str,
           evidence: dict, action: str) -> dict:
    return {
        "issue_type": issue_type,
        "scope": scope,
        "severity": severity,
        "title": title,
        "evidence": evidence,
        "recommended_action": action,
    }


def _signal_issues(active: list[dict]) -> list[dict]:
    issues: list[dict] = []
    by_scope: dict[str, set[str]] = defaultdict(set)
    for row in active:
        signals = (row.get("scenario") or {}).get("signals") or {}
        for key, enabled in signals.items():
            if enabled:
                by_scope[str(row.get("placementId") or "campaign")].add(key)
    mapping = {
        "creativeRenderFailure": (
            "creative_failure", "critical", "Creative không render đúng",
            "Kiểm tra asset/format và chuẩn bị thay creative.",
        ),
        "clickTelemetryFailure": (
            "click_tracking_failure", "critical", "Click telemetry bị gián đoạn",
            "Kiểm tra click area và event tracking trước khi đổi media.",
        ),
        "configDrift": (
            "config_drift", "high", "Cấu hình campaign đã drift",
            "So sánh config hash và khôi phục revision đã duyệt.",
        ),
        "trackingDelay": (
            "data_quality", "medium", "Outcome data đang trễ",
            "Chờ attribution window và kiểm tra lại trước khi tối ưu.",
        ),
    }
    for scope, signals in by_scope.items():
        for signal in sorted(signals):
            if signal not in mapping:
                continue
            issue_type, severity, title, action = mapping[signal]
            issues.append(_issue(
                issue_type, scope, severity, title,
                {"signal": signal, "source": "scenario_fact"}, action,
            ))
    return issues


def evaluate_records(baseline: list[dict], active: list[dict],
                     policy_value: dict | None = None) -> list[dict]:
    policy = {**DEFAULT_POLICY, **(policy_value or {})}
    if not active:
        return [_issue(
            "data_quality", "campaign", "critical", "Không có dữ liệu report",
            {"active_record_count": 0}, "Kiểm tra report pipeline trước khi đánh giá.",
        )]
    base = _group(baseline)
    current = _group(active)
    issues = _signal_issues(active)
    placements = sorted({scope for scope, _date in set(base) | set(current)})

    for placement in placements:
        dates = sorted({date for scope, date in set(base) | set(current) if scope == placement})
        ratios: list[dict] = []
        spend_ratios: list[dict] = []
        ctr_series: list[float] = []
        for date in dates:
            expected = base.get((placement, date), {})
            observed = current.get((placement, date), {})
            expected_impressions = float(expected.get("impressions") or 0)
            actual_impressions = float(observed.get("impressions") or 0)
            if expected_impressions > 0:
                ratios.append({"date": date, "ratio": actual_impressions / expected_impressions})
            expected_spend = float(expected.get("spend") or 0)
            if expected_spend > 0:
                spend_ratios.append({
                    "date": date,
                    "ratio": float(observed.get("spend") or 0) / expected_spend,
                })
            if actual_impressions > 0:
                ctr_series.append(float(observed.get("clicks") or 0) / actual_impressions)

        persistence = int(policy["persistence_windows"])
        recent_delivery = ratios[-persistence:]
        if len(recent_delivery) >= persistence and all(
            item["ratio"] < float(policy["delivery_ratio_threshold"])
            for item in recent_delivery
        ):
            issues.append(_issue(
                "delivery_drop", placement, "high", "Delivery thấp kéo dài",
                {"windows": recent_delivery, "threshold": policy["delivery_ratio_threshold"]},
                "Kiểm tra creative/config và cân nhắc chuyển phân bổ sang zone khỏe hơn.",
            ))

        expected_impressions = sum(float(base.get((placement, date), {}).get("impressions") or 0) for date in dates)
        expected_clicks = sum(float(base.get((placement, date), {}).get("clicks") or 0) for date in dates)
        actual_impressions = sum(float(current.get((placement, date), {}).get("impressions") or 0) for date in dates)
        actual_clicks = sum(float(current.get((placement, date), {}).get("clicks") or 0) for date in dates)
        if expected_impressions and actual_impressions >= float(policy["ctr_min_impressions"]):
            p0 = expected_clicks / expected_impressions
            observed_ctr = actual_clicks / actual_impressions
            standard_error = sqrt(p0 * (1 - p0) / actual_impressions) if 0 < p0 < 1 else 0
            z_score = (observed_ctr - p0) / standard_error if standard_error else 0
            relative_drop = (p0 - observed_ctr) / p0 if p0 else 0
            if relative_drop >= float(policy["ctr_relative_drop_threshold"]) and z_score <= float(policy["ctr_z_threshold"]):
                issues.append(_issue(
                    "ctr_regression", placement, "high", "CTR giảm có ý nghĩa thống kê",
                    {
                        "baseline_ctr": round(p0, 6), "observed_ctr": round(observed_ctr, 6),
                        "relative_drop": round(relative_drop, 4), "z_score": round(z_score, 3),
                        "impressions": int(actual_impressions),
                    },
                    "Kiểm tra click telemetry; nếu tracking tốt, thử creative hoặc placement thay thế.",
                ))

        recent_pacing = spend_ratios[-persistence:]
        if len(recent_pacing) >= persistence and all(
            item["ratio"] < float(policy["pacing_low_threshold"])
            or item["ratio"] > float(policy["pacing_high_threshold"])
            for item in recent_pacing
        ):
            issues.append(_issue(
                "pacing_error", placement, "medium", "Pacing lệch kế hoạch",
                {"windows": recent_pacing}, "Kiểm tra budget cap, delivery và lịch phân phối.",
            ))

        if len(ctr_series) >= 5:
            history, latest = ctr_series[:-1], ctr_series[-1]
            center = median(history)
            mad = median([abs(value - center) for value in history])
            robust_z = 0 if mad == 0 else 0.6745 * (latest - center) / mad
            if robust_z <= -3.5:
                issues.append(_issue(
                    "robust_trend_drop", placement, "medium", "Xu hướng CTR có outlier âm",
                    {"latest_ctr": latest, "median_ctr": center, "mad": mad, "robust_z": robust_z},
                    "Theo dõi thêm một window và kiểm tra fatigue/creative.",
                ))

    deduped: dict[tuple[str, str], dict] = {}
    for issue in issues:
        deduped[(issue["issue_type"], issue["scope"])] = issue
    return list(deduped.values())
