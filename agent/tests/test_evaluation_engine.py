from evaluation.engine import evaluate_records


def row(date: str, placement: str = "zone-a", impressions: int = 1000,
        clicks: int = 30, spend: int = 100_000, signals: dict | None = None) -> dict:
    return {
        "date": date, "placementId": placement, "impressions": impressions,
        "clicks": clicks, "spend": spend, "reach": impressions * 0.8,
        "conversions": 5, "outcomes": {"lead": 5},
        "scenario": {"signals": signals or {}},
    }


def test_delivery_requires_persistent_windows():
    baseline = [row("2026-08-01"), row("2026-08-02"), row("2026-08-03")]
    one_window = [row("2026-08-01"), row("2026-08-02"), row("2026-08-03", impressions=200, clicks=6, spend=20_000)]
    assert not any(item["issue_type"] == "delivery_drop" for item in evaluate_records(baseline, one_window))
    two_windows = [row("2026-08-01"), row("2026-08-02", impressions=200, clicks=6, spend=20_000), row("2026-08-03", impressions=200, clicks=6, spend=20_000)]
    assert any(item["issue_type"] == "delivery_drop" for item in evaluate_records(baseline, two_windows))


def test_ctr_regression_uses_sample_and_statistical_gate():
    baseline = [row(f"2026-08-0{day}") for day in range(1, 5)]
    active = [row(f"2026-08-0{day}", clicks=5) for day in range(1, 5)]
    incident = next(item for item in evaluate_records(baseline, active) if item["issue_type"] == "ctr_regression")
    assert incident["evidence"]["z_score"] <= -2.58
    assert incident["evidence"]["relative_drop"] > 0.3


def test_technical_signals_are_not_inferred_from_ctr_alone():
    baseline = [row("2026-08-01")]
    active = [row("2026-08-01", clicks=0, signals={"clickTelemetryFailure": True})]
    issues = evaluate_records(baseline, active)
    assert any(item["issue_type"] == "click_tracking_failure" for item in issues)
    assert not any(item["issue_type"] == "creative_failure" for item in issues)


def test_empty_active_dataset_fails_data_quality_gate():
    issues = evaluate_records([row("2026-08-01")], [])
    assert issues == [{
        "issue_type": "data_quality", "scope": "campaign", "severity": "critical",
        "title": "Không có dữ liệu report", "evidence": {"active_record_count": 0},
        "recommended_action": "Kiểm tra report pipeline trước khi đánh giá.",
    }]


def test_zero_sample_and_invalid_numbers_fail_without_dividing_by_zero():
    baseline = [row('2026-08-01')]
    assert not any(i['issue_type'] == 'ctr_regression' for i in evaluate_records(
        baseline, [row('2026-08-01', impressions=0, clicks=0)], {'ctr_min_impressions': 0}))
    for invalid in [float('nan'), float('inf'), 'bad-metric', -1]:
        active = [row('2026-08-01')]
        active[0]['impressions'] = invalid
        assert {i['issue_type'] for i in evaluate_records(baseline, active)} == {'data_quality'}


def test_duplicate_dimensions_are_aggregated_without_false_delivery_drop():
    baseline = [row('2026-08-01'), row('2026-08-02')]
    active = [row(date, impressions=500, clicks=15, spend=50000)
              for date in ('2026-08-01', '2026-08-02') for _ in range(2)]
    assert evaluate_records(baseline, active) == []
