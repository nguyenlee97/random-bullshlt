from tools.creative_match import dimension_match, match_file_to_format, score_file_for_zone


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
