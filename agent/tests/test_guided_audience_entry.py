import pytest

from handlers import audience as audience_handler
from session import update_form_state


BRIEF = {
    "brand": "Mixifood",
    "objective": "awareness",
    "kpi": "Reach 1 triệu",
    "budget": 5,
    "startDate": "2026-08-20",
    "endDate": "2026-08-22",
    "notes": "Nhắm người thích đồ ăn vặt",
}


@pytest.mark.asyncio
async def test_guided_entry_uses_shared_grounded_retrieval_and_dedupes(monkeypatch):
    calls = []

    async def recommend(session_id, brief_override=None):
        calls.append((session_id, brief_override))
        return {
            "recommendations": [
                {
                    "segmentId": "INT158",
                    "fullLabel": "Fast food (food & drink)",
                    "type": "Interest",
                    "sizeRaw": "1.2M",
                    "reason": "Phù hợp với người thích đồ ăn nhanh.",
                },
                {
                    "segmentId": "INT158",
                    "fullLabel": "Fast food (food & drink)",
                    "type": "Interest",
                    "sizeRaw": "1.2M",
                    "reason": "Bản trùng từ selector.",
                },
                {
                    "segmentId": "INT202",
                    "fullLabel": "Snack foods (food & drink)",
                    "type": "Interest",
                    "sizeRaw": "900K",
                    "reason": "Khớp trực tiếp với sản phẩm snack.",
                },
            ],
            "total_segments": 310,
            "rag": {"candidates": 15},
        }

    async def targeting(_sid, _brief, _options, segments=None):
        assert [item["segmentId"] for item in segments] == ["INT158", "INT202"]
        return (
            {"geo": ["TP.HCM"], "age": ["18-24"], "gender": []},
            [{"field": "geo", "picks": ["TP.HCM"], "reason": "Thị trường chính"}],
            "targeting-test-model",
        )

    async def options():
        return {"geo": ["TP.HCM"], "age": ["18-24"], "gender": []}

    monkeypatch.setattr(audience_handler, "handle_dmp_recommend", recommend)
    monkeypatch.setattr(audience_handler, "_recommend_targeting", targeting)
    monkeypatch.setattr(audience_handler, "get_targeting_options", options)
    monkeypatch.setattr(
        audience_handler,
        "simple_generate",
        lambda *_args, **_kwargs: pytest.fail("legacy full-catalog selector was called"),
    )

    session_id = "guided-audience-shared-pipeline"
    await update_form_state(session_id, "brief", BRIEF)
    result = await audience_handler.handle_audience_entry(session_id)

    assert calls == [(session_id, BRIEF)]
    assert result["need_more_info"] is False
    proposal = next(
        block for block in result["blocks"] if block["type"] == "workspace_proposal"
    )
    attrs = proposal["changes"]["value"]["attrs"]
    assert [item["segmentId"] for item in attrs] == ["INT158", "INT202"]
    assert result["meta"]["model"] == "targeting-test-model"


@pytest.mark.asyncio
async def test_guided_entry_does_not_propose_when_grounded_retrieval_is_empty(monkeypatch):
    async def recommend(_session_id, brief_override=None):
        assert brief_override == BRIEF
        return {"recommendations": [], "total_segments": 310}

    monkeypatch.setattr(audience_handler, "handle_dmp_recommend", recommend)
    session_id = "guided-audience-empty-retrieval"
    await update_form_state(session_id, "brief", BRIEF)

    result = await audience_handler.handle_audience_entry(session_id)

    assert result["need_more_info"] is True
    assert result["meta"]["tool"] == "audience_entry_retry"
    assert all(block["type"] != "workspace_proposal" for block in result["blocks"])
