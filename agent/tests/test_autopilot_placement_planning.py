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


def test_np6_contract_distinguishes_background_from_side_skin_assets():
    background = format_spec_for_zone({
        "id": "BG",
        "size": "skin",
        "format": "skin",
        "placementFamily": "category_background",
        "creativeContractId": "category-background-v1",
    })
    side = format_spec_for_zone({
        "id": "SIDE",
        "size": "skin",
        "format": "skin",
        "placementFamily": "category_side_left",
        "creativeContractId": "znews-category-side-left-v1",
    })

    assert background["format_id"] == "znews-Background"
    assert background["intended_format"] == "skin"
    assert side["format_id"] == "znews-side-banner"
    assert side["intended_format"] == "banner"


def test_np6_contract_selects_publisher_specific_masthead():
    znews = format_spec_for_zone({
        "id": "ZN",
        "size": "1160x250",
        "creativeContractId": "znews-category-masthead-v1",
    })
    baomoi = format_spec_for_zone({
        "id": "BM",
        "size": "1160x280",
        "creativeContractId": "baomoi-category-masthead-v1",
    })
    assert znews["format_id"] == "znews-top-banner"
    assert baomoi["format_id"] == "zuma-baomoi-masthead"


def test_np6_property_contracts_preserve_exact_desktop_and_mobile_formats():
    cases = {
        "smoney-top-desktop-v1": ("1440x108", "smoney-top-desktop"),
        "smoney-top-mobile-v1": ("390x96", "smoney-top-mobile"),
        "smoney-screener-desktop-v1": ("1090x280", "smoney-screener-desktop"),
        "smoney-screener-mobile-v1": ("387x387", "smoney-screener-mobile"),
        "dicungcon-bridge-desktop-v1": ("966x249", "dicungcon-bridge-desktop"),
        "dicungcon-bridge-mobile-v1": ("343x88", "dicungcon-bridge-mobile"),
        "zagoo-interstitial-desktop-v1": ("512x512", "zagoo-interstitial-desktop"),
        "zagoo-interstitial-mobile-v1": ("350x470", "zagoo-interstitial-mobile"),
    }
    for contract, (size, expected_format) in cases.items():
        spec = format_spec_for_zone({
            "id": contract,
            "size": size,
            "creativeContractId": contract,
        })
        assert spec["format_id"] == expected_format
