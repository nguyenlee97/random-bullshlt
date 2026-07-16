from autopilot.placement_planning import (
    build_creative_format_plan,
    format_spec_for_zone,
)


def _zone(zone_id, size, score):
    return {"id": zone_id, "size": size, "score": score}


def test_format_plan_deduplicates_dimensions_and_respects_cost_cap():
    intent = {"revision": 7, "candidates": [
        _zone("A", "300x250", 0.99),
        _zone("B", "300 x 250", 0.95),
        _zone("C", "300x600", 0.90),
        _zone("D", "1160x250", 0.85),
        _zone("E", "2032x528", 0.80),
    ]}
    plan = build_creative_format_plan(intent, source="ai_generate", max_assets=3)

    assert [item["format_id"] for item in plan["formats"]] == [
        "zuma-box", "display-halfpage-300x600", "znews-masthead-1160x250",
    ]
    assert plan["formats"][0]["zone_ids"] == ["A", "B"]
    assert plan["estimated_provider_calls"] == 3
    assert plan["omitted_by_cost_cap_zone_ids"] == ["E"]


def test_format_plan_reports_unsupported_dimensions_without_inventing_assets():
    plan = build_creative_format_plan(
        {"candidates": [_zone("UNKNOWN", "970x250", 1.0)]},
        source="upload",
        max_assets=3,
    )
    assert plan["formats"] == []
    assert plan["unsupported_zone_ids"] == ["UNKNOWN"]
    assert plan["estimated_provider_calls"] == 0


def test_skin_zone_uses_the_supported_skin_format():
    spec = format_spec_for_zone({"id": "SKIN", "size": "skin", "format": "skin"})
    assert spec["format_id"] == "znews-Background"
    assert spec["intended_format"] == "skin"
