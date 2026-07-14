from eval_utils import rec_segment_ids, resolve_segments


def test_recommendations_join_on_segment_id_before_display_label():
    recs = [
        {"segmentId": "BEH006", "fullLabel": "Purchase behavior (Purchase behavior)"},
        {"fullLabel": "Soccer"},
    ]

    assert rec_segment_ids(recs, {"Soccer": "INT001"}) == ["BEH006", "INT001"]


def test_golden_mongo_ids_resolve_to_stable_segment_ids():
    assert resolve_segments(
        ["mongo-id-a", "already-stable"], {"mongo-id-a": "INT123"}
    ) == {"INT123", "already-stable"}
