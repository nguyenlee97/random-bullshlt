from audience_reach import AUDIENCE_UNIVERSE, estimate_unique_reach


def _segment(segment_id: str, low: int, high: int, **extra):
    return {
        "segmentId": segment_id,
        "sizeMin": low,
        "sizeMax": high,
        **extra,
    }


def test_single_segment_matches_catalog_midpoint_and_range():
    result = estimate_unique_reach([_segment("A", 100_000, 200_000)])
    assert result["unique_reach"] == 150_000
    assert result["range"] == {"low": 100_000, "high": 200_000}
    assert result["method"] == "calibrated_estimate"


def test_duplicate_segment_does_not_change_unique_reach():
    segment = _segment("A", 1_000_000, 2_000_000)
    assert estimate_unique_reach([segment])["unique_reach"] == estimate_unique_reach(
        [segment, {**segment, "_id": "another-document-id"}]
    )["unique_reach"]


def test_adding_a_known_segment_never_reduces_reach():
    base = estimate_unique_reach([_segment("A", 8_000_000, 10_000_000)])
    expanded = estimate_unique_reach([
        _segment("A", 8_000_000, 10_000_000),
        _segment("B", 2_000_000, 4_000_000),
    ])
    assert expanded["unique_reach"] >= base["unique_reach"]
    assert expanded["range"]["low"] >= base["range"]["low"]


def test_select_all_scale_is_universe_capped():
    segments = [
        _segment(f"S{index}", 8_000_000, 12_000_000, sizeSource="modeled_estimate")
        for index in range(310)
    ]
    result = estimate_unique_reach(segments)
    assert result["unique_reach"] <= AUDIENCE_UNIVERSE
    assert result["range"]["high"] <= AUDIENCE_UNIVERSE
    assert result["unique_reach"] != 300_000_000


def test_unknown_segments_are_explicit_not_zero_reach():
    result = estimate_unique_reach([{"segmentId": "UNKNOWN"}])
    assert result["unique_reach"] is None
    assert result["range"] is None
    assert result["status"] == "unavailable"
    assert result["unknown_segment_ids"] == ["UNKNOWN"]


def test_catalog_version_changes_response_metadata():
    first = estimate_unique_reach([
        _segment("A", 100_000, 200_000, sizeEstimateVersion="catalog-v1")
    ])
    second = estimate_unique_reach([
        _segment("A", 100_000, 200_000, sizeEstimateVersion="catalog-v2")
    ])
    assert first["catalog_version"] == "catalog-v1"
    assert second["catalog_version"] == "catalog-v2"
