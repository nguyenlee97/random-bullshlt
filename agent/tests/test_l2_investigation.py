"""L2 investigation: probes, deterministic ranking, and scenario coverage.

The scenario helper invokes the actual JavaScript preset engine. No mirrored
transforms or external services are used.
"""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from evaluation.engine import evaluate_records
from evaluation.investigator import build_bundle, summarize_bundle
from evaluation.playbooks import rank_hypotheses
from evaluation.probes import (
    ANOMALY, OK, UNAVAILABLE, InvestigationContext, probe_click_telemetry,
    probe_config_drift, probe_creative_compatibility, probe_creative_fatigue,
    probe_data_completeness, probe_delivery_pattern, probe_placement_benchmark,
)


PLACEMENT = "ZingNews_Masthead"
OTHER = "BaoMoi_Masthead"
DATES = [f"2026-08-{day:02d}" for day in range(1, 11)]


def _row(placement: str, date: str, **overrides) -> dict:
    row = {
        "campaignId": "ORD-2026-001", "placementId": placement, "date": date,
        "channel": "news", "format": "banner", "impressions": 5000, "clicks": 50,
        "spend": 500_000, "reach": 3000, "conversions": 10, "vi": 62.0,
        "outcomes": {"visits": 40}, "scenario": None,
    }
    row.update(overrides)
    row["ctr"] = round(row["clicks"] / row["impressions"] * 100, 3) if row["impressions"] else 0
    return row


def baseline_records() -> list[dict]:
    return [_row(placement, date) for placement in (PLACEMENT, OTHER) for date in DATES]


def apply_scenario(records: list[dict], preset: str, *, target: str = PLACEMENT,
                   window_days: int = 3, persistence: int = 2,
                   impact: float = 0.75) -> list[dict]:
    """Invoke the production JS preset engine through JSON stdin/stdout."""
    source = """
const fs = require('node:fs');
const { applyScenario } = require('./lib/reportScenarios');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(applyScenario(input.records, input.config).records));
"""
    result = subprocess.run(
        ['node', '-e', source], input=json.dumps({
            'records': records, 'config': {
                'presetId': preset, 'targetPlacementId': target,
                'windowDays': window_days, 'persistenceWindows': persistence,
                'impact': impact, 'seed': 'test',
            },
        }), text=True, encoding='utf-8', capture_output=True, check=True, timeout=10,
        cwd=Path(__file__).resolve().parents[2] / 'backend',
    )
    return json.loads(result.stdout)


ORDER = {
    "id": "ORD-2026-001", "objective": "awareness", "budget": 100_000_000,
    "startDate": "2026-08-01", "endDate": "2026-08-10",
    "placements": [PLACEMENT, OTHER],
    "creatives": [
        {"name": "hero", "size": "1160x280", "format": "banner", "zones": [PLACEMENT]},
        {"name": "alt", "size": "970x250", "format": "banner", "zones": [OTHER]},
    ],
}

ZONE_MAP = {
    PLACEMENT: {
        "id": PLACEMENT, "size": "1160x280", "format": "banner", "ctr": 1.0, "cpm": 90_000,
        "reach": 900_000, "vi": 62, "comparisonGroupId": "masthead_news",
        "topicId": "society_news_law", "lifecycleStatus": "active", "metricSource": "demo",
    },
    OTHER: {
        "id": OTHER, "size": "970x250", "format": "banner", "ctr": 0.9, "cpm": 80_000,
        "reach": 800_000, "vi": 60, "comparisonGroupId": "masthead_news",
        "topicId": "society_news_law", "lifecycleStatus": "active", "metricSource": "demo",
    },
    "Znews_Family_Masthead": {
        "id": "Znews_Family_Masthead", "size": "1160x280", "format": "banner", "ctr": 2.4,
        "cpm": 95_000, "reach": 500_000, "vi": 70, "comparisonGroupId": "masthead_news",
        "topicId": "society_news_law", "lifecycleStatus": "active", "metricSource": "demo",
    },
}

BASELINE_INPUT = {
    "objective": "awareness", "budget": 100_000_000,
    "startDate": "2026-08-01", "endDate": "2026-08-10",
    "zones": [{"id": PLACEMENT}, {"id": OTHER}],
}


def context_for(preset: str, *, scope: str = PLACEMENT, issue_type: str = "ctr_regression",
                order: dict | None = ORDER, **kwargs) -> InvestigationContext:
    base = baseline_records()
    return InvestigationContext(
        campaign_id="ORD-2026-001", scope=scope, issue_type=issue_type,
        baseline_records=base, active_records=apply_scenario(base, preset, **kwargs),
        baseline_input=BASELINE_INPUT, order=copy.deepcopy(order) if order else None,
        zone_map=copy.deepcopy(ZONE_MAP),
    )


def top_hypothesis(preset: str, issue_type: str, **kwargs) -> str:
    ctx = context_for(preset, issue_type=issue_type, **kwargs)
    incident = {
        "incident_id": "INC-TEST01", "campaign_id": "ORD-2026-001",
        "issue_type": issue_type, "scope": ctx.scope,
    }
    bundle = build_bundle(incident, ctx, trigger="test")
    return bundle["top_hypothesis"]["hypothesis_id"]


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

def test_data_completeness_flags_missing_days():
    ctx = context_for("healthy_baseline")
    ctx.active_records = [row for row in ctx.active_records if row["date"] not in DATES[-4:]]
    assert probe_data_completeness(ctx)["status"] == ANOMALY


def test_data_completeness_ok_on_healthy_baseline():
    assert probe_data_completeness(context_for("healthy_baseline"))["status"] == OK


def test_tracking_delay_signal_becomes_data_quality_anomaly():
    result = probe_data_completeness(context_for("tracking_delay"))
    assert result["status"] == ANOMALY
    assert result["source"] == "scenario_fact"


def test_click_telemetry_detects_zero_clicks_with_live_impressions():
    result = probe_click_telemetry(context_for("click_tracking_failure"))
    assert result["status"] == ANOMALY
    assert result["evidence"]["impressions"] > 0


def test_click_telemetry_ok_when_low_ctr_but_clicks_present():
    assert probe_click_telemetry(context_for("low_ctr"))["status"] == OK


def test_creative_compatibility_detects_size_mismatch():
    ctx = context_for("healthy_baseline")
    ctx.order["creatives"][0]["size"] = "300x250"
    result = probe_creative_compatibility(ctx)
    assert result["status"] == ANOMALY
    assert result["evidence"]["mismatches"]


def test_creative_compatibility_flags_placement_without_creative():
    ctx = context_for("healthy_baseline")
    ctx.order = {**ORDER, "creatives": [], "creative": None}
    assert probe_creative_compatibility(ctx)["status"] == ANOMALY


def test_creative_compatibility_unavailable_without_order():
    ctx = context_for("healthy_baseline", order=None)
    assert probe_creative_compatibility(ctx)["status"] == UNAVAILABLE


def test_config_drift_diffs_baseline_input_against_live_order():
    ctx = context_for("healthy_baseline")
    ctx.order["budget"] = 55_000_000
    result = probe_config_drift(ctx)
    assert result["status"] == ANOMALY
    assert any(item["field"] == "budget" for item in result["evidence"]["changes"])


def test_config_drift_detects_added_placement():
    ctx = context_for("healthy_baseline")
    ctx.order["placements"] = [PLACEMENT, OTHER, "Znews_Family_Masthead"]
    changes = probe_config_drift(ctx)["evidence"]["changes"]
    assert any(item["field"] == "placements.added" for item in changes)


def test_config_drift_ok_when_order_matches_baseline():
    assert probe_config_drift(context_for("healthy_baseline"))["status"] == OK


def test_delivery_pattern_reports_cliff_and_scope_isolation():
    result = probe_delivery_pattern(context_for("low_impression_zone"))
    assert result["status"] == ANOMALY
    assert result["evidence"]["shape"] in {"cliff", "gradual_decline", "zero_delivery"}
    assert result["evidence"]["campaign_wide"] is False


def test_delivery_pattern_stable_on_healthy_baseline():
    assert probe_delivery_pattern(context_for("healthy_baseline"))["status"] == OK


def test_placement_benchmark_finds_better_alternative():
    result = probe_placement_benchmark(context_for("poor_placement"))
    assert result["status"] == ANOMALY
    assert result["evidence"]["alternatives"][0]["id"] == "Znews_Family_Masthead"


def test_placement_benchmark_unavailable_for_campaign_scope():
    ctx = context_for("low_ctr", scope="campaign")
    assert probe_placement_benchmark(ctx)["status"] == UNAVAILABLE


def test_creative_fatigue_needs_steady_impressions():
    # Delivery collapsed too, so this is not the fatigue signature.
    assert probe_creative_fatigue(context_for("creative_failure"))["status"] == OK


def test_creative_fatigue_fires_on_progressive_decay():
    ctx = context_for("healthy_baseline")
    # Impressions and reach hold steady while clicks decay day over day.
    decaying = [80, 74, 68, 60, 52, 45, 38, 32, 27, 22]
    for row in ctx.active_records:
        if row["placementId"] == PLACEMENT:
            row["clicks"] = decaying[DATES.index(row["date"])]
    result = probe_creative_fatigue(ctx)
    assert result["status"] == ANOMALY
    assert result["evidence"]["progressive_decline"] is True


def test_creative_fatigue_rejects_step_change():
    # poor_placement drops CTR at one point rather than decaying over time.
    result = probe_creative_fatigue(context_for("poor_placement"))
    assert result["status"] == OK
    assert result["evidence"]["progressive_decline"] is False


# ---------------------------------------------------------------------------
# Ranking and the data-quality gate
# ---------------------------------------------------------------------------

def test_gate_puts_measurement_causes_first():
    ranking = rank_hypotheses("ctr_regression", {
        "data_completeness": {"probe_id": "data_completeness", "status": ANOMALY},
        "click_telemetry": {"probe_id": "click_telemetry", "status": OK},
        "creative_compatibility": {"probe_id": "creative_compatibility", "status": ANOMALY},
        "creative_fatigue": {"probe_id": "creative_fatigue", "status": ANOMALY},
        "placement_benchmark": {"probe_id": "placement_benchmark", "status": ANOMALY},
        "config_drift": {"probe_id": "config_drift", "status": OK},
    })
    assert ranking["gate"]["applied"] is True
    assert ranking["hypotheses"][0]["hypothesis_id"] == "data_quality_incomplete"


def test_confidence_sums_to_one_hundred():
    ranking = rank_hypotheses("ctr_regression", {
        "click_telemetry": {"probe_id": "click_telemetry", "status": ANOMALY, "finding": "telemetry_signal"},
    })
    assert round(sum(item["confidence"] for item in ranking["hypotheses"])) == 100


def test_ranking_is_reproducible():
    results = {"click_telemetry": {"probe_id": "click_telemetry", "status": ANOMALY}}
    first = rank_hypotheses("ctr_regression", results)
    second = rank_hypotheses("ctr_regression", results)
    assert first["hypotheses"] == second["hypotheses"]


def test_unsupported_issue_type_is_reported_not_guessed():
    ranking = rank_hypotheses("unknown_future_issue", {})
    assert ranking["supported"] is False
    assert ranking["hypotheses"] == []


def test_unavailable_probe_is_not_scored_as_healthy():
    with_ok = rank_hypotheses("ctr_regression", {
        "click_telemetry": {"probe_id": "click_telemetry", "status": OK},
    })
    with_unavailable = rank_hypotheses("ctr_regression", {
        "click_telemetry": {"probe_id": "click_telemetry", "status": UNAVAILABLE},
    })
    assert with_unavailable["assessment"] == "insufficient_evidence"
    assert with_unavailable["hypotheses"] == []
    assert with_ok["assessment"] != "insufficient_evidence"


# ---------------------------------------------------------------------------
# Scenario coverage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset,issue_type,expected", [
    ("click_tracking_failure", "ctr_regression", "click_tracking_failure"),
    ("creative_failure", "creative_failure", "creative_render_failure"),
    ("tracking_delay", "ctr_regression", "data_quality_incomplete"),
    ("poor_placement", "ctr_regression", "placement_underperformance"),
    ("low_impression_zone", "delivery_drop", "inventory_shortfall"),
    ("healthy_baseline", "ctr_regression", "natural_variance"),
])
def test_scenario_produces_expected_top_hypothesis(preset, issue_type, expected):
    assert top_hypothesis(preset, issue_type) == expected


def test_low_ctr_and_poor_placement_are_diagnosed_differently():
    # Both drop CTR with impressions intact. Spend is the only fact that tells
    # a weak message apart from an expensive slot.
    assert top_hypothesis("low_ctr", "ctr_regression") == "creative_underperformance"
    assert top_hypothesis("poor_placement", "ctr_regression") == "placement_underperformance"


def test_spend_pacing_distinguishes_flat_spend_from_rising_spend():
    from evaluation.probes import probe_spend_pacing
    assert probe_spend_pacing(context_for("low_ctr"))["finding"] == "output_down_spend_flat"
    assert probe_spend_pacing(context_for("poor_placement"))["finding"] == "spend_up_output_down"
    assert probe_spend_pacing(context_for("low_impression_zone"))["finding"] == "spend_down"
    assert probe_spend_pacing(context_for("healthy_baseline"))["status"] == OK


def test_size_mismatch_outranks_render_failure():
    ctx = context_for("healthy_baseline")
    ctx.order["creatives"][0]["size"] = "300x250"
    incident = {"incident_id": "INC-A", "campaign_id": "C",
                "issue_type": "ctr_regression", "scope": PLACEMENT}
    bundle = build_bundle(incident, ctx, trigger="test")
    assert bundle["top_hypothesis"]["hypothesis_id"] == "creative_format_mismatch"


def test_absent_creative_outranks_render_failure():
    ctx = context_for("healthy_baseline")
    ctx.order = {**ORDER, "creatives": [], "creative": None}
    incident = {"incident_id": "INC-B", "campaign_id": "C",
                "issue_type": "ctr_regression", "scope": PLACEMENT}
    bundle = build_bundle(incident, ctx, trigger="test")
    assert bundle["top_hypothesis"]["hypothesis_id"] == "creative_missing"


def test_render_signal_is_not_double_counted_in_creative_playbook():
    # L1 raised the incident from this same signal, so the probe reading it
    # again is confirmation and must contribute only a small amount.
    from evaluation.playbooks import rank_hypotheses
    base = {"probe_id": "creative_compatibility", "status": ANOMALY}
    confirming = rank_hypotheses("creative_failure", {
        "creative_compatibility": {**base, "finding": "render_signal"},
    })
    informative = rank_hypotheses("creative_failure", {
        "creative_compatibility": {**base, "finding": "size_mismatch"},
    })
    render = next(h for h in confirming["hypotheses"]
                  if h["hypothesis_id"] == "creative_render_failure")
    mismatch = next(h for h in informative["hypotheses"]
                    if h["hypothesis_id"] == "creative_format_mismatch")
    assert render["raw_score"] == 42  # prior 30 + confirmatory 12
    assert mismatch["raw_score"] == 60  # prior 10 + genuinely new evidence 50


def test_placement_below_benchmark_without_alternatives_is_unavailable():
    ctx = context_for("poor_placement")
    # Remove the only better comparable from the catalog.
    ctx.zone_map.pop("Znews_Family_Masthead")
    result = probe_placement_benchmark(ctx)
    assert result["status"] == UNAVAILABLE
    assert result["finding"] == "no_alternatives"


def test_every_probe_result_carries_a_finding_code():
    ctx = context_for("multiple_issues")
    incident = {"incident_id": "INC-C", "campaign_id": "C",
                "issue_type": "delivery_drop", "scope": PLACEMENT}
    bundle = build_bundle(incident, ctx, trigger="test")
    for probe in bundle["probes"]:
        assert probe.get("finding"), f"{probe['probe_id']} has no finding code"


def test_config_drift_scenario_ranks_config_first():
    ctx = context_for("config_drift", scope="campaign", issue_type="delivery_drop")
    incident = {
        "incident_id": "INC-TEST02", "campaign_id": "ORD-2026-001",
        "issue_type": "delivery_drop", "scope": "campaign",
    }
    bundle = build_bundle(incident, ctx, trigger="test")
    assert bundle["top_hypothesis"]["hypothesis_id"] == "config_drift"


def test_every_preset_produces_a_bundle_without_error():
    presets = [
        "healthy_baseline", "low_impression_zone", "low_ctr", "creative_failure",
        "click_tracking_failure", "config_drift", "poor_placement", "tracking_delay",
        "multiple_issues", "recovery_success", "recovery_ineffective",
    ]
    for preset in presets:
        for issue_type in ("ctr_regression", "delivery_drop", "creative_failure"):
            ctx = context_for(preset, issue_type=issue_type)
            incident = {
                "incident_id": "INC-TEST03", "campaign_id": "ORD-2026-001",
                "issue_type": issue_type, "scope": PLACEMENT,
            }
            bundle = build_bundle(incident, ctx, trigger="test")
            assert bundle["supported"] is True
            assert bundle["hypotheses"]
            assert bundle["mutations"] == []
            assert summarize_bundle(bundle)


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

def test_l2_records_no_mutations_and_declares_sources():
    ctx = context_for("low_ctr")
    incident = {
        "incident_id": "INC-TEST04", "campaign_id": "ORD-2026-001",
        "issue_type": "ctr_regression", "scope": PLACEMENT,
    }
    bundle = build_bundle(incident, ctx, trigger="test")
    assert bundle["mutations"] == []
    assert bundle["sources"]["order"] is True
    assert bundle["sources"]["zone_catalog"] is True
    for option in bundle["recovery_options"]:
        # L2 proposes; nothing is executable until L3 implements the action.
        assert option["available"] is False


def test_missing_evidence_sources_are_reported_not_hidden():
    ctx = context_for("low_ctr", order=None)
    ctx.zone_map = {}
    incident = {
        "incident_id": "INC-TEST05", "campaign_id": "ORD-2026-001",
        "issue_type": "ctr_regression", "scope": PLACEMENT,
    }
    bundle = build_bundle(incident, ctx, trigger="test")
    assert bundle["sources"]["order"] is False
    statuses = {probe["probe_id"]: probe["status"] for probe in bundle["probes"]}
    assert statuses["creative_compatibility"] == UNAVAILABLE
    assert statuses["placement_benchmark"] == UNAVAILABLE


def test_campaign_wide_config_drift_creates_one_incident_not_one_per_placement():
    base = baseline_records()
    issues = evaluate_records(base, apply_scenario(base, "config_drift"))
    drift = [item for item in issues if item["issue_type"] == "config_drift"]
    assert len(drift) == 1
    assert drift[0]["scope"] == "campaign"
