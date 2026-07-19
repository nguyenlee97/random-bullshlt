import pytest

from models import SegmentData


@pytest.mark.asyncio
async def test_missing_catalog_size_is_unknown_not_zero(monkeypatch):
    from handlers import audience as handler

    captured = {}

    async def update_form_state(_session_id, key, value):
        captured[key] = value

    async def get_session(_session_id):
        return {"form_state": {"brief": {
            "brand": "Test Brand",
            "objective": "awareness",
            "kpi": "Reach",
            "notes": "Teen music fans",
        }}}

    async def log_event(*_args, **_kwargs):
        return None

    def generate(_system, prompt):
        captured["prompt"] = prompt
        return '{"reasoning":"Phù hợp brief","match_quality":"good","segment_notes":[],"warnings":[]}'

    monkeypatch.setattr(handler, "update_form_state", update_form_state)
    monkeypatch.setattr(handler, "get_or_create_session", get_session)
    monkeypatch.setattr(handler, "log_event", log_event)
    monkeypatch.setattr(handler, "simple_generate", generate)

    response = await handler.handle_audience(
        SegmentData(attrs=[{
            "_id": "catalog-1",
            "segmentId": "INT001",
            "fullLabel": "Music fans",
            "type": "interest",
        }]),
        "audience-unknown-size",
    )

    assert captured["segment"]["size"] == 0
    assert captured["segment"]["sizeKnown"] is False
    assert "Chưa biết" in captured["prompt"]
    assert "không cung cấp size" in captured["prompt"]
    assert "0 người" not in response.text
    assert response.blocks[0]["size_known"] is False
    assert response.blocks[0]["count"] == 1


def test_known_catalog_size_remains_estimable():
    from handlers.audience import _calc_audience_size, _has_known_audience_size

    attrs = [{"sizeMin": 100_000, "sizeMax": 200_000}]
    assert _has_known_audience_size(attrs) is True
    assert _calc_audience_size(attrs) == 150_000
