from tools.creative_match import (
    auto_assign,
    dimension_match,
    match_file_to_format,
    score_file_for_zone,
)


def test_dimension_match_accepts_exported_size_with_same_ratio():
    mode, diff = dimension_match(928, 200, 1160, 250)
    assert mode in {"strong_ratio", "same_ratio"}
    assert diff < 0.01


def test_dimension_match_rejects_ratio_delta_at_safety_boundary():
    mode, diff = dimension_match(1000, 300, 1160, 250)
    assert mode == "incompatible_ratio"
    assert diff >= 0.15


def test_skin_format_requires_skin_intent_and_safe_geometry():
    spec = {
        "format_id": "znews-Background",
        "width": 1504,
        "height": 704,
        "intended_format": "skin",
    }
    ordinary = match_file_to_format(
        {"name": "mixifood-wide.png", "width": 1200, "height": 562}, spec
    )
    intended = match_file_to_format(
        {
            "name": "mixifood-znews-background.png",
            "width": 1200,
            "height": 562,
            "intendedFormat": "skin",
        },
        spec,
    )
    assert ordinary["matched"] is False
    assert ordinary["mode"] == "missing_skin_hint"
    assert intended["matched"] is True


def test_filename_cannot_override_incompatible_measured_ratio():
    file = {
        "name": "mixifood-1160x250.png",
        "width": 300,
        "height": 600,
        "intel": {"width": 300, "height": 600, "effective_status": "auto_approved"},
    }
    zone = {"id": "znews_masthead", "size": "1160x250", "format": "banner"}
    score, warnings = score_file_for_zone(file, zone)
    assert score < 1
    assert any("không phù hợp" in warning for warning in warnings)


def test_canonical_format_identity_overrides_ratio_with_advisory():
    match = match_file_to_format(
        {
            "name": "smoney-top-desktop.png",
            "formatId": "smoney-top-desktop",
            "width": 512,
            "height": 512,
        },
        {
            "format_id": "smoney-top-desktop",
            "width": 1440,
            "height": 108,
            "intended_format": "banner",
        },
    )

    assert match["matched"] is True
    assert match["mode"] == "explicit_identity"
    assert match["ratio_advisory"] is True


def test_openai_assignment_falls_back_to_closest_ratio():
    zone = {"id": "generic-banner", "size": "1000x200", "format": "banner"}
    files = [
        {
            "name": "far.png",
            "width": 300,
            "height": 600,
            "intel": {"width": 300, "height": 600, "effective_status": "auto_approved"},
        },
        {
            "name": "closer.png",
            "width": 1000,
            "height": 300,
            "intel": {"width": 1000, "height": 300, "effective_status": "auto_approved"},
        },
    ]

    result = auto_assign([zone], files, prefer_contract_identity=True)

    assert result["assignments"][zone["id"]] == 1
    assert result["fallback_zone_ids"] == [zone["id"]]


def test_np6_side_contract_accepts_side_banner_not_background_skin():
    zone = {
        "id": "Znews_FamilyParenting_SideLeft",
        "format": "skin",
        "size": "skin",
        "creativeContractId": "znews-category-side-left-v1",
    }
    side_file = {
        "name": "family-side.png",
        "formatId": "znews-side-banner",
        "width": 736,
        "height": 1456,
        "intel": {
            "width": 736,
            "height": 1456,
            "effective_status": "auto_approved",
        },
    }
    background_file = {
        "name": "family-background-skin.png",
        "formatId": "znews-Background",
        "intendedFormat": "skin",
        "width": 1504,
        "height": 704,
        "intel": {
            "width": 1504,
            "height": 704,
            "effective_status": "auto_approved",
        },
    }

    side_score, side_warnings = score_file_for_zone(side_file, zone)
    background_score, background_warnings = score_file_for_zone(background_file, zone)

    assert side_score > background_score
    assert side_warnings == []
    assert background_warnings


def test_openai_contract_assignment_prefers_format_id_over_upload_order():
    zone = {
        "id": "Znews_Home_Background",
        "format": "skin",
        "size": "skin",
        "creativeContractId": "znews-home-background-v1",
    }
    files = [
        {
            "name": "first-upload.png",
            "width": 1504,
            "height": 704,
            "intendedFormat": "skin",
            "intel": {
                "width": 1504,
                "height": 704,
                "effective_status": "auto_approved",
            },
        },
        {
            "name": "campaign-hero.png",
            "formatId": "znews-Background",
            "width": 1504,
            "height": 704,
            "intendedFormat": "skin",
            "intel": {
                "width": 1504,
                "height": 704,
                "effective_status": "auto_approved",
            },
        },
    ]

    legacy = auto_assign([zone], files)
    openai = auto_assign([zone], files, prefer_contract_identity=True)

    assert legacy["assignments"][zone["id"]] == 0
    assert openai["assignments"][zone["id"]] == 1
    assert openai["scores"][zone["id"]]["1"] > openai["scores"][zone["id"]]["0"]


def test_openai_contract_assignment_uses_filename_when_format_id_is_missing():
    zone = {
        "id": "Znews_Home_Background",
        "format": "skin",
        "size": "skin",
        "creativeContractId": "znews-home-background-v1",
    }
    files = [
        {
            "name": "first-upload.png",
            "width": 1504,
            "height": 704,
            "intendedFormat": "skin",
            "intel": {
                "width": 1504,
                "height": 704,
                "effective_status": "auto_approved",
            },
        },
        {
            "name": "vietjet-znews-background-final.png",
            "width": 1504,
            "height": 704,
            "intendedFormat": "skin",
            "intel": {
                "width": 1504,
                "height": 704,
                "effective_status": "auto_approved",
            },
        },
    ]

    result = auto_assign([zone], files, prefer_contract_identity=True)

    assert result["assignments"][zone["id"]] == 1
