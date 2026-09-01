"""Read-only L2 diagnostic probes.

Every probe is a pure function over a pre-built :class:`InvestigationContext`.
All I/O happens once in ``build_context`` so probes stay deterministic and
unit-testable, and so no probe can reach a mutating endpoint by accident.

A probe never changes campaign, report, or incident state. It reports one of
three statuses:

``ok``           the probe ran and found nothing wrong;
``anomaly``      the probe ran and found supporting evidence;
``unavailable``  the probe could not run because its source is missing.

``unavailable`` is deliberately distinct from ``ok``: a probe that could not
read the order must never be scored as evidence that the order is healthy.

Every result also carries a ``finding`` code. Two anomalies from the same probe
can mean completely different things — a placement with no creative at all and
a placement whose creative is the wrong size are not the same fault — so
playbooks score the finding, not merely the status.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


# Sources are recorded on every probe result so a reader can tell measured
# evidence from scenario-injected test facts.
SOURCE_SCENARIO = "scenario_fact"
SOURCE_ORDER = "order_api"
SOURCE_CATALOG = "zone_catalog"
SOURCE_DATASET = "report_dataset"
SOURCE_DERIVED = "derived"

OK = "ok"
ANOMALY = "anomaly"
UNAVAILABLE = "unavailable"


@dataclass
class InvestigationContext:
    """Everything a probe is allowed to see, resolved once, read-only."""

    campaign_id: str
    scope: str = "campaign"
    issue_type: str = ""
    baseline_records: list[dict] = field(default_factory=list)
    active_records: list[dict] = field(default_factory=list)
    baseline_input: dict = field(default_factory=dict)
    order: dict | None = None
    zone_map: dict[str, dict] = field(default_factory=dict)
    policy: dict = field(default_factory=dict)
    evaluation_dates: list[str] = field(default_factory=list)

    def scoped(self, records: list[dict]) -> list[dict]:
        if self.scope in ("", "campaign"):
            return list(records)
        return [row for row in records if str(row.get("placementId") or "") == self.scope]

    def signals(self) -> set[str]:
        found: set[str] = set()
        for row in self.scoped(self.active_records):
            for key, enabled in ((row.get("scenario") or {}).get("signals") or {}).items():
                if enabled:
                    found.add(str(key))
        return found

    def recent(self, records: list[dict]) -> list[dict]:
        rows = self.scoped(records)
        return [row for row in rows if row.get('date') in self.evaluation_dates] if self.evaluation_dates else rows


def _result(probe_id: str, status: str, finding: str, summary: str, source: str,
            findings: list[str] | None = None, evidence: dict | None = None) -> dict:
    return {
        "probe_id": probe_id,
        "status": status,
        "finding": finding,
        "summary": summary,
        "source": source,
        "findings": findings or [],
        "evidence": evidence or {},
    }


def _totals(rows: list[dict]) -> dict:
    return {
        "impressions": sum(float(row.get("impressions") or 0) for row in rows),
        "clicks": sum(float(row.get("clicks") or 0) for row in rows),
        "spend": sum(float(row.get("spend") or 0) for row in rows),
        "reach": sum(float(row.get("reach") or 0) for row in rows),
        "conversions": sum(float(row.get("conversions") or 0) for row in rows),
    }


def _by_date(rows: list[dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for row in rows:
        date = str(row.get("date") or "")
        current = merged.setdefault(date, {"impressions": 0.0, "clicks": 0.0, "spend": 0.0})
        current["impressions"] += float(row.get("impressions") or 0)
        current["clicks"] += float(row.get("clicks") or 0)
        current["spend"] += float(row.get("spend") or 0)
    return merged


def _ctr(row: dict) -> float | None:
    impressions = float(row.get("impressions") or 0)
    return (float(row.get("clicks") or 0) / impressions) if impressions > 0 else None


# ---------------------------------------------------------------------------
# Probe 1 — data completeness
# ---------------------------------------------------------------------------

def probe_data_completeness(ctx: InvestigationContext) -> dict:
    """Rule data gaps in or out before any performance cause is considered."""
    active = ctx.scoped(ctx.active_records)
    if not active:
        return _result(
            "data_completeness", ANOMALY, "no_records",
            "Không có analytics record nào trong phạm vi đang điều tra.",
            SOURCE_DATASET, ["Active dataset trống cho scope này."],
            {"active_record_count": 0},
        )
    baseline_dates = {str(row.get("date") or "") for row in ctx.scoped(ctx.baseline_records)}
    if not baseline_dates:
        return _result('data_completeness', UNAVAILABLE, 'no_baseline', 'Thiếu baseline để kiểm tra độ đầy đủ.', SOURCE_DATASET)
    expected_keys = {(row.get('placementId'), row.get('date')) for row in ctx.scoped(ctx.baseline_records)}
    actual_keys = {(row.get('placementId'), row.get('date')) for row in active}
    active_dates = {str(row.get("date") or "") for row in active}
    missing = sorted(baseline_dates - active_dates)
    zero_days = sorted(
        date for date, value in _by_date(active).items() if value["impressions"] <= 0
    )
    coverage = (len(active_dates) / len(baseline_dates)) if baseline_dates else 1.0
    evidence = {
        "active_record_count": len(active),
        "expected_days": len(baseline_dates),
        "observed_days": len(active_dates),
        "coverage": round(coverage, 4),
        "missing_dates": missing[:10],
        "zero_impression_dates": zero_days[:10],
    }
    findings: list[str] = []
    if missing:
        findings.append(f"Thiếu {len(missing)} ngày dữ liệu so với baseline.")
    if zero_days:
        findings.append(f"{len(zero_days)} ngày có impressions bằng 0.")
    if "trackingDelay" in ctx.signals():
        findings.append("Có tín hiệu tracking delay trong dữ liệu.")
        return _result(
            "data_completeness", ANOMALY, "tracking_delay_signal",
            "Dữ liệu outcome đang trễ; kết luận hiệu suất chưa đáng tin.",
            SOURCE_SCENARIO, findings, {**evidence, "signal": "trackingDelay"},
        )
    if coverage < 0.8 or missing or expected_keys - actual_keys:
        return _result(
            "data_completeness", ANOMALY, "missing_days",
            "Dữ liệu report không đủ để kết luận nguyên nhân hiệu suất.",
            SOURCE_DATASET, findings, evidence,
        )
    return _result(
        "data_completeness", OK, "complete",
        "Dữ liệu report đầy đủ theo baseline.", SOURCE_DATASET, findings, evidence,
    )


# ---------------------------------------------------------------------------
# Probe 2 — click telemetry
# ---------------------------------------------------------------------------

def probe_click_telemetry(ctx: InvestigationContext) -> dict:
    """Separate 'nobody clicked' from 'clicks were not recorded'."""
    active = ctx.recent(ctx.active_records)
    if not active:
        return _result(
            "click_telemetry", UNAVAILABLE, "no_data",
            "Không có dữ liệu để kiểm tra click telemetry.", SOURCE_DATASET,
        )
    totals = _totals(active)
    serving_days = [
        date for date, value in _by_date(active).items() if value["impressions"] > 0
    ]
    dead_days = [
        date for date, value in _by_date(active).items()
        if value["impressions"] > 0 and value["clicks"] <= 0
    ]
    evidence = {
        "impressions": int(totals["impressions"]),
        "clicks": int(totals["clicks"]),
        "serving_days": len(serving_days),
        "days_with_impressions_and_zero_clicks": len(dead_days),
        "affected_dates": sorted(dead_days)[:10],
    }
    if "clickTelemetryFailure" in ctx.signals():
        return _result(
            "click_telemetry", ANOMALY, "telemetry_signal",
            "Click telemetry được báo lỗi; click không được ghi nhận.",
            SOURCE_SCENARIO,
            ["Tín hiệu clickTelemetryFailure đang bật cho scope này."],
            {**evidence, "signal": "clickTelemetryFailure"},
        )
    # Impressions still serving while every click disappears is the signature of
    # a broken click path, not of weak creative.
    if totals["impressions"] >= 500 and totals["clicks"] <= 0 and len(dead_days) >= 2:
        return _result(
            "click_telemetry", ANOMALY, "zero_clicks_while_serving",
            "Có impression nhưng không ghi nhận click nào trong nhiều ngày liên tiếp.",
            SOURCE_DERIVED,
            [f"{len(dead_days)} ngày có impression nhưng 0 click."],
            evidence,
        )
    return _result(
        "click_telemetry", OK, "clicks_recorded",
        "Có click được ghi nhận; chưa kiểm chứng toàn bộ event pipeline.", SOURCE_DERIVED, [], evidence,
    )


# ---------------------------------------------------------------------------
# Probe 3 — creative compatibility
# ---------------------------------------------------------------------------

def _creatives_for_scope(order: dict, scope: str, zone: dict | None = None) -> list[dict]:
    creatives = [item for item in (order.get("creatives") or []) if item]
    if scope in ("", "campaign"):
        return creatives or ([order["creative"]] if order.get("creative") else [])
    assigned = [item for item in creatives if scope in (item.get("zones") or [])]
    if assigned:
        return assigned
    unassigned = [item for item in creatives if not item.get('zones') and item.get('size') and item.get('size') == (zone or {}).get('size')]
    if unassigned:
        return unassigned
    fallback = order.get("creative")
    return [fallback] if fallback and (fallback.get('url') or fallback.get('size')) else []


def probe_creative_compatibility(ctx: InvestigationContext) -> dict:
    """Compare the booked creative against the placement's size/format contract."""
    from tools.creative_match import _parse_dims

    if not ctx.order and 'creativeRenderFailure' not in ctx.signals():
        return _result(
            "creative_compatibility", UNAVAILABLE, "no_order",
            "Không đọc được order để kiểm tra creative.", SOURCE_ORDER,
        )
    if "creativeRenderFailure" in ctx.signals():
        return _result(
            "creative_compatibility", ANOMALY, "render_signal",
            "Creative được báo lỗi render tại placement này.", SOURCE_SCENARIO,
            ["Tín hiệu creativeRenderFailure đang bật cho scope này."],
            {"signal": "creativeRenderFailure"},
        )
    zone = ctx.zone_map.get(ctx.scope) if ctx.scope not in ("", "campaign") else None
    creatives = _creatives_for_scope(ctx.order, ctx.scope, zone)
    evidence = {
        "scope": ctx.scope,
        "zone_size": (zone or {}).get("size"),
        "zone_format": (zone or {}).get("format"),
        "creative_count": len(creatives),
        "creative_sizes": [item.get("size") for item in creatives],
    }
    if not creatives:
        return _result(
            "creative_compatibility", ANOMALY, "no_creative",
            "Không có creative nào được gán cho placement này.", SOURCE_ORDER,
            ["Placement đang chạy mà không có creative được gán."], evidence,
        )
    if not zone:
        return _result(
            "creative_compatibility", UNAVAILABLE, "zone_unknown",
            "Không tìm thấy placement trong catalog để đối chiếu creative.",
            SOURCE_CATALOG, [], evidence,
        )
    zone_dims = _parse_dims(str(zone.get("size") or ""))
    if not zone_dims or any(not _parse_dims(str(item.get('size') or '')) for item in creatives):
        return _result('creative_compatibility', UNAVAILABLE, 'unknown_contract', 'Chưa đủ thông tin kích thước để kiểm tra hợp đồng creative.', SOURCE_DERIVED, [], evidence)
    size_mismatches: list[str] = []
    format_mismatches: list[str] = []
    for item in creatives:
        creative_dims = _parse_dims(str(item.get("size") or ""))
        if zone_dims and creative_dims and creative_dims != zone_dims:
            size_mismatches.append(
                f"{item.get('name') or item.get('label') or 'creative'}: "
                f"{item.get('size')} ≠ {zone.get('size')}"
            )
        zone_format = str(zone.get("format") or "")
        item_format = str(item.get("format") or "")
        if zone_format in {'banner', 'skin', 'video'} and item_format in {'banner', 'skin', 'video'} and zone_format != item_format:
            format_mismatches.append(
                f"{item.get('name') or 'creative'}: format {item_format} ≠ {zone_format}"
            )
    mismatches = size_mismatches + format_mismatches
    if mismatches:
        return _result(
            "creative_compatibility", ANOMALY,
            "size_mismatch" if size_mismatches else "format_mismatch",
            "Creative không khớp hợp đồng kích thước/format của placement.",
            SOURCE_DERIVED, mismatches, {**evidence, "mismatches": mismatches},
        )
    return _result(
        "creative_compatibility", OK, "compatible",
        "Creative khớp kích thước và format của placement.", SOURCE_DERIVED, [], evidence,
    )


# ---------------------------------------------------------------------------
# Probe 4 — configuration drift
# ---------------------------------------------------------------------------

_DRIFT_FIELDS = ("objective", "budget", "startDate", "endDate")


def probe_config_drift(ctx: InvestigationContext) -> dict:
    """Diff the frozen baseline report input against the live order.

    There is no signed approved-config record in this system. The baseline
    ``ReportDataset.input`` is the only immutable point-in-time copy of the
    campaign, so it is the honest reference for drift.
    """
    if "configDrift" in ctx.signals():
        return _result(
            "config_drift", ANOMALY, "drift_signal",
            "Cấu hình campaign được báo là đã drift.", SOURCE_SCENARIO,
            ["Tín hiệu configDrift đang bật."], {"signal": "configDrift"},
        )
    if not ctx.order or not ctx.baseline_input:
        return _result(
            "config_drift", UNAVAILABLE, "no_baseline_input",
            "Thiếu baseline input hoặc order để so sánh cấu hình.", SOURCE_DATASET,
        )
    changes: list[dict] = []
    compared, missing = [], []
    for key in _DRIFT_FIELDS:
        before, after = ctx.baseline_input.get(key), ctx.order.get(key)
        if before in (None, "") or after in (None, ""):
            missing.append(key)
            continue
        compared.append(key)
        different = float(before) != float(after) if key == 'budget' else str(before) != str(after)
        if different:
            changes.append({"field": key, "baseline": before, "current": after})
    baseline_zones = {
        str(zone.get("id")) for zone in (ctx.baseline_input.get("zones") or []) if zone.get("id")
    }
    current_zones = {str(zone) for zone in (ctx.order.get("placements") or [])}
    zones_known = 'zones' in ctx.baseline_input and 'placements' in ctx.order
    (compared if zones_known else missing).append('placements')
    added, removed = (sorted(current_zones - baseline_zones), sorted(baseline_zones - current_zones)) if zones_known else ([], [])
    if added:
        changes.append({"field": "placements.added", "baseline": None, "current": added})
    if removed:
        changes.append({"field": "placements.removed", "baseline": removed, "current": None})
    evidence = {
        "compared_fields": compared,
        "missing_fields": missing,
        "changes": changes,
        "baseline_reference": "report_dataset.baseline.input",
    }
    if changes:
        return _result(
            "config_drift", ANOMALY, "field_changed",
            "Cấu hình hiện tại khác snapshot baseline.", SOURCE_DERIVED,
            [f"{item['field']} đã thay đổi." for item in changes], evidence,
        )
    if not compared:
        return _result('config_drift', UNAVAILABLE, 'no_comparable_fields',
                       'Không có trường cấu hình đủ dữ liệu để đối chiếu.', SOURCE_DERIVED, [], evidence)
    return _result(
        "config_drift", OK, "matches_baseline",
        "Các trường cấu hình đã đối chiếu khớp snapshot baseline; trường thiếu dữ liệu chưa được kiểm tra.", SOURCE_DERIVED, [], evidence,
    )


# ---------------------------------------------------------------------------
# Probe 5 — delivery pattern
# ---------------------------------------------------------------------------

def probe_delivery_pattern(ctx: InvestigationContext) -> dict:
    """Describe the shape of the delivery change and how far it spreads."""
    baseline_by_date = _by_date(ctx.scoped(ctx.baseline_records))
    active_by_date = _by_date(ctx.scoped(ctx.active_records))
    dates = sorted(set(baseline_by_date) | set(active_by_date))
    series = []
    for date in dates:
        expected = baseline_by_date.get(date, {}).get("impressions", 0.0)
        observed = active_by_date.get(date, {}).get("impressions", 0.0)
        if expected > 0:
            series.append({"date": date, "ratio": round(observed / expected, 4)})
    if not series:
        return _result(
            "delivery_pattern", UNAVAILABLE, "no_baseline",
            "Không đủ dữ liệu baseline để dựng chuỗi delivery.", SOURCE_DATASET,
        )

    # Campaign-wide comparison tells apart one broken placement from a
    # campaign-level problem, which points at very different causes.
    affected: list[str] = []
    placements = {
        str(row.get("placementId") or "") for row in ctx.baseline_records
    } | {str(row.get("placementId") or "") for row in ctx.active_records}
    for placement in sorted(placements):
        expected = sum(
            float(row.get("impressions") or 0) for row in ctx.baseline_records
            if str(row.get("placementId") or "") == placement
        )
        observed = sum(
            float(row.get("impressions") or 0) for row in ctx.active_records
            if str(row.get("placementId") or "") == placement
        )
        if expected > 0 and observed / expected < 0.7:
            affected.append(placement)

    ratios = [item["ratio"] for item in series]
    latest = ratios[-1]
    shape = "stable"
    if latest <= 0.02:
        shape = "zero_delivery"
    elif len(ratios) >= 3:
        healthy = [index for index, value in enumerate(ratios) if value >= 0.9]
        # A cliff is a sustained low tail after a healthy head; a gradual
        # decline never has a clean healthy segment to fall from.
        if healthy and healthy[-1] < len(ratios) - 1 and latest < 0.7:
            tail = ratios[healthy[-1] + 1:]
            shape = "cliff" if all(value < 0.7 for value in tail) else "gradual_decline"
        elif latest < 0.7:
            shape = "gradual_decline"
    evidence = {
        "shape": shape,
        "series": series[-14:],
        "latest_ratio": latest,
        "median_ratio": round(median(ratios), 4),
        "affected_placements": affected,
        "total_placements": len(placements),
        "campaign_wide": len(affected) > 1,
    }
    findings = [f"Dạng suy giảm: {shape}."]
    if len(affected) > 1:
        findings.append(f"{len(affected)}/{len(placements)} placement cùng giảm.")
    elif affected:
        findings.append("Chỉ một placement bị ảnh hưởng.")
    status = ANOMALY if shape != "stable" else OK
    summary = (
        "Delivery giảm và chưa hồi phục." if status == ANOMALY
        else "Delivery bám sát baseline."
    )
    return _result("delivery_pattern", status, shape, summary, SOURCE_DERIVED,
                   findings, evidence)


# ---------------------------------------------------------------------------
# Probe 6 — placement benchmark and alternatives
# ---------------------------------------------------------------------------

def probe_placement_benchmark(ctx: InvestigationContext) -> dict:
    """Compare observed CTR to the catalog benchmark and find real alternatives."""
    if ctx.scope in ("", "campaign"):
        return _result(
            "placement_benchmark", UNAVAILABLE, "campaign_scope",
            "Probe này chỉ chạy cho scope placement.", SOURCE_CATALOG,
        )
    zone = ctx.zone_map.get(ctx.scope)
    if not zone:
        return _result(
            "placement_benchmark", UNAVAILABLE, "not_in_catalog",
            "Không tìm thấy placement trong catalog.", SOURCE_CATALOG,
        )
    totals = _totals(ctx.recent(ctx.active_records))
    if totals["impressions"] <= 0:
        return _result(
            "placement_benchmark", UNAVAILABLE, "no_impressions",
            "Không có impression để so sánh với benchmark.", SOURCE_DATASET,
        )
    observed_ctr = totals["clicks"] / totals["impressions"] * 100
    benchmark_ctr = float(zone.get("ctr") or 0)
    booked = set(str(item) for item in ((ctx.order or {}).get("placements") or []))
    group = zone.get("comparisonGroupId")
    topic = zone.get("topicId")
    alternatives = []
    for candidate_id, candidate in ctx.zone_map.items():
        if candidate_id == ctx.scope or candidate_id in booked:
            continue
        same_group = group and candidate.get("comparisonGroupId") == group
        same_topic = topic and candidate.get("topicId") == topic
        if not (same_group or same_topic):
            continue
        if str(candidate.get("lifecycleStatus") or "active") != "active":
            continue
        if float(candidate.get("ctr") or 0) <= max(observed_ctr, benchmark_ctr):
            continue
        alternatives.append({
            "id": candidate_id,
            "ctr": candidate.get("ctr"),
            "cpm": candidate.get("cpm"),
            "reach": candidate.get("reach"),
            "vi": candidate.get("vi"),
            "match": "comparison_group" if same_group else "topic",
            'availability': 'not_checked', 'creative_compatibility': 'not_checked',
        })
    alternatives.sort(key=lambda item: float(item.get("ctr") or 0), reverse=True)
    evidence = {
        "placement": ctx.scope,
        "observed_ctr_pct": round(observed_ctr, 4),
        "catalog_ctr_pct": benchmark_ctr,
        "catalog_metric_source": zone.get("metricSource"),
        "comparison_group": group,
        "topic": topic,
        "alternatives": alternatives[:5],
    }
    below_benchmark = benchmark_ctr > 0 and observed_ctr < benchmark_ctr * 0.7
    if below_benchmark and alternatives:
        return _result(
            "placement_benchmark", ANOMALY, "below_benchmark_with_alternatives",
            "Placement dưới benchmark; có ứng viên catalog cần kiểm tra booking và creative.",
            SOURCE_CATALOG,
            [
                f"CTR quan sát {round(observed_ctr, 3)}% so với benchmark {benchmark_ctr}%.",
                f"Có {len(alternatives)} placement tương đương tốt hơn.",
            ],
            evidence,
        )
    if below_benchmark:
        # Trailing its benchmark with nothing comparable to move to is not
        # evidence the placement is healthy, and must not be scored as such.
        return _result(
            "placement_benchmark", UNAVAILABLE, "no_alternatives",
            "Placement dưới benchmark nhưng catalog không có lựa chọn tương đương.",
            SOURCE_CATALOG,
            [f"CTR quan sát {round(observed_ctr, 3)}% so với benchmark {benchmark_ctr}%."],
            evidence,
        )
    return _result(
        "placement_benchmark", OK, "at_benchmark",
        "Placement không lệch đáng kể so với benchmark catalog.",
        SOURCE_CATALOG, [], evidence,
    )


# ---------------------------------------------------------------------------
# Probe 7 — creative fatigue
# ---------------------------------------------------------------------------

def probe_creative_fatigue(ctx: InvestigationContext) -> dict:
    """Look for the fatigue signature: steady impressions, decaying CTR."""
    rows = sorted(ctx.scoped(ctx.active_records), key=lambda row: str(row.get("date") or ""))
    points = [(str(row.get("date") or ""), _ctr(row), row) for row in rows]
    usable = [(date, value, row) for date, value, row in points if value is not None]
    if len(usable) < 6:
        return _result(
            "creative_fatigue", UNAVAILABLE, "insufficient_days",
            "Chưa đủ số ngày để đánh giá fatigue.", SOURCE_DATASET,
            [], {"observed_days": len(usable)},
        )
    # Thirds, not halves. Fatigue decays progressively; a single step down is a
    # discrete fault (placement, creative swap, config change) wearing the same
    # shape as fatigue when only two buckets are compared.
    size = len(usable) // 3
    early, mid, late = usable[:size], usable[size:size * 2], usable[size * 2:]

    def _median_ctr(subset: list[tuple]) -> float:
        return median([value for _date, value, _row in subset]) if subset else 0.0

    def _median_impressions(subset: list[tuple]) -> float:
        return median([float(row.get("impressions") or 0) for _d, _v, row in subset]) or 0.0

    def _frequency(subset: list[tuple]) -> float:
        reach = sum(float(row.get("reach") or 0) for _d, _v, row in subset)
        impressions = sum(float(row.get("impressions") or 0) for _d, _v, row in subset)
        return (impressions / reach) if reach > 0 else 0.0

    early_ctr, mid_ctr, late_ctr = _median_ctr(early), _median_ctr(mid), _median_ctr(late)
    decline = ((early_ctr - late_ctr) / early_ctr) if early_ctr > 0 else 0.0
    early_impressions, late_impressions = _median_impressions(early), _median_impressions(late)
    impression_ratio = (late_impressions / early_impressions) if early_impressions > 0 else 0.0
    early_frequency, late_frequency = _frequency(early), _frequency(late)
    # Each third must be meaningfully below the one before it.
    progressive = (
        early_ctr > 0 and mid_ctr > 0
        and (early_ctr - mid_ctr) / early_ctr >= 0.08
        and (mid_ctr - late_ctr) / mid_ctr >= 0.08
    )
    evidence = {
        "early_ctr": round(early_ctr, 6),
        "mid_ctr": round(mid_ctr, 6),
        "late_ctr": round(late_ctr, 6),
        "ctr_decline": round(decline, 4),
        "progressive_decline": progressive,
        "impression_ratio": round(impression_ratio, 4),
        "early_frequency": round(early_frequency, 4),
        "late_frequency": round(late_frequency, 4),
        "observed_days": len(usable),
    }
    # Fatigue means the audience saw the same creative too often. Impressions
    # must hold up: if delivery collapsed too, the cause is elsewhere.
    if progressive and decline >= 0.25 and impression_ratio >= 0.85 \
            and late_frequency >= early_frequency:
        return _result(
            "creative_fatigue", ANOMALY, "progressive_decay",
            "CTR suy giảm dần qua từng giai đoạn trong khi impression giữ nguyên.",
            SOURCE_DERIVED,
            [
                f"CTR giảm {round(decline * 100)}% và giảm liên tục qua ba giai đoạn.",
                f"Tần suất {round(early_frequency, 2)} → {round(late_frequency, 2)}.",
            ],
            evidence,
        )
    if decline >= 0.25 and not progressive:
        return _result(
            "creative_fatigue", OK, "step_change",
            "CTR giảm theo bậc chứ không suy giảm dần; không khớp dấu hiệu fatigue.",
            SOURCE_DERIVED,
            ["Mức giảm tập trung vào một thời điểm thay vì tăng dần."],
            evidence,
        )
    return _result(
        "creative_fatigue", OK, "no_fatigue",
        "Không thấy dấu hiệu fatigue rõ rệt.", SOURCE_DERIVED, [], evidence,
    )


# ---------------------------------------------------------------------------
# Probe 8 — spend efficiency and pacing
# ---------------------------------------------------------------------------

def probe_spend_pacing(ctx: InvestigationContext) -> dict:
    """Read the money.

    Spend separates causes that look identical in impressions and clicks alone.
    Budget still burning while output falls is a cost-efficiency problem, which
    points at the placement. Budget falling with output is a supply or pacing
    problem. Output falling while spend holds steady points back at the
    creative.
    """
    baseline = _totals(ctx.recent(ctx.baseline_records))
    active = _totals(ctx.recent(ctx.active_records))
    if baseline["spend"] <= 0:
        return _result(
            "spend_pacing", UNAVAILABLE, "no_baseline",
            "Không có spend baseline để so sánh.", SOURCE_DATASET,
        )
    spend_ratio = active["spend"] / baseline["spend"]

    def _output_ratio(key: str) -> float:
        return (active[key] / baseline[key]) if baseline[key] > 0 else 0.0

    click_ratio = _output_ratio("clicks")
    impression_ratio = _output_ratio("impressions")
    baseline_cpc = (baseline["spend"] / baseline["clicks"]) if baseline["clicks"] else 0.0
    active_cpc = (active["spend"] / active["clicks"]) if active["clicks"] else 0.0
    evidence = {
        "spend_ratio": round(spend_ratio, 4),
        "click_ratio": round(click_ratio, 4),
        "impression_ratio": round(impression_ratio, 4),
        "baseline_cpc": round(baseline_cpc, 2),
        "active_cpc": round(active_cpc, 2),
        "cpc_ratio": round(active_cpc / baseline_cpc, 4) if baseline_cpc else None,
    }
    if spend_ratio <= 0.15:
        return _result(
            "spend_pacing", ANOMALY, "spend_collapsed",
            "Spend gần như dừng hẳn so với baseline.", SOURCE_DERIVED,
            [f"Spend chỉ còn {round(spend_ratio * 100)}% baseline."], evidence,
        )
    # Order matters. The narrowest signature is checked first so a broader rule
    # cannot swallow it: delivery bought as planned while only the response
    # falls is the message failing, and must not be read as a pacing fault.
    if 0.85 <= spend_ratio <= 1.05 and click_ratio < 0.8 and impression_ratio >= 0.85:
        return _result(
            "spend_pacing", ANOMALY, "output_down_spend_flat",
            "Spend và impression giữ nguyên nhưng click giảm rõ rệt.", SOURCE_DERIVED,
            [f"Click chỉ còn {round(click_ratio * 100)}% với spend không đổi."], evidence,
        )
    # Money keeps going out while output falls: the placement is getting more
    # expensive per result, which is the placement's problem, not the creative's.
    if spend_ratio >= 1.05 and click_ratio < 0.8:
        return _result(
            "spend_pacing", ANOMALY, "spend_up_output_down",
            "Spend tăng trong khi kết quả giảm; chi phí trên mỗi click xấu đi.",
            SOURCE_DERIVED,
            [
                f"Spend {round(spend_ratio * 100)}% baseline, click {round(click_ratio * 100)}%.",
                f"CPC {round(baseline_cpc):,} → {round(active_cpc):,}." if active_cpc
                else "Không còn click để tính CPC.",
            ],
            evidence,
        )
    # Budget still burning while impressions collapse: each impression is
    # costing far more than planned.
    if spend_ratio >= 0.85 and impression_ratio < 0.7:
        return _result(
            "spend_pacing", ANOMALY, "cost_efficiency_drop",
            "Spend giữ gần kế hoạch trong khi impression sụt mạnh.", SOURCE_DERIVED,
            [
                f"Impression còn {round(impression_ratio * 100)}% nhưng spend vẫn "
                f"{round(spend_ratio * 100)}% baseline.",
            ],
            evidence,
        )
    if spend_ratio < 0.7:
        return _result(
            "spend_pacing", ANOMALY, "spend_down",
            "Spend thấp hơn kế hoạch; ngân sách không được tiêu thụ.", SOURCE_DERIVED,
            [f"Spend chỉ đạt {round(spend_ratio * 100)}% baseline."], evidence,
        )
    return _result(
        "spend_pacing", OK, "on_plan",
        "Spend bám sát kế hoạch so với baseline.", SOURCE_DERIVED, [], evidence,
    )


ALL_PROBES = {
    "data_completeness": probe_data_completeness,
    "click_telemetry": probe_click_telemetry,
    "creative_compatibility": probe_creative_compatibility,
    "config_drift": probe_config_drift,
    "delivery_pattern": probe_delivery_pattern,
    "placement_benchmark": probe_placement_benchmark,
    "creative_fatigue": probe_creative_fatigue,
    "spend_pacing": probe_spend_pacing,
}


def run_probes(ctx: InvestigationContext, probe_ids: list[str]) -> dict[str, dict]:
    """Run the named probes. A probe crash degrades to ``unavailable``."""
    results: dict[str, dict] = {}
    for probe_id in probe_ids:
        probe = ALL_PROBES.get(probe_id)
        if not probe:
            continue
        try:
            results[probe_id] = probe(ctx)
        except Exception as exc:  # A broken probe must not sink the whole L2 run.
            results[probe_id] = _result(
                probe_id, UNAVAILABLE, "probe_error",
                f"Probe lỗi: {str(exc)[:160]}", SOURCE_DERIVED,
            )
    return results
