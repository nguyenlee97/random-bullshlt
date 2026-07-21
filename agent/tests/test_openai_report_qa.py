from unittest.mock import AsyncMock

import pytest


def _analyses():
    contract = {
        "contractVersion": "report-evidence-v1",
        "metricDefinitions": {"ctr": {"formula": "clicks / impressions * 100"}},
        "findings": [{"id": "campaign_totals", "metrics": {"ctr": 0.72}}],
        "limitations": ["Synthetic showcase data."],
    }
    return {
        "daily_ops": {
            "overall": "Synthetic overview",
            "dataContract": contract,
            "questions": [{
                "id": "op_q1", "question": "Tổng quan hiệu suất",
                "findingIds": ["campaign_totals"], "answer": {"sections": []},
            }],
        },
    }


@pytest.mark.asyncio
async def test_report_qa_uses_semantic_structured_model_and_valid_citations(monkeypatch):
    import openai_campaign.report_qa as report_qa

    answer = report_qa.ReportQAAnswer(
        answer="CTR là 0,72% trong dữ liệu mô phỏng.", report_type="daily_ops",
        question_ids=["op_q1"], finding_ids=["campaign_totals"], metric_ids=["ctr"],
        limitations=["Synthetic showcase data."], suggestions=[], confidence=0.95,
    )
    generator = AsyncMock(return_value=(answer, {"model": "gpt-5.4-mini"}))
    monkeypatch.setattr(report_qa, "generate_structured", generator)

    result, provenance = await report_qa.answer_report_question(
        session_id="report-semantic", message="Hiệu quả click có ổn không?",
        preferred_type="daily_ops", analyses=_analyses(), history=[],
    )

    assert result.finding_ids == ["campaign_totals"]
    assert provenance["model"] == "gpt-5.4-mini"
    assert "keyword" not in generator.await_args.kwargs["input_data"]


@pytest.mark.asyncio
async def test_report_qa_rejects_unknown_metric_citation(monkeypatch):
    import openai_campaign.report_qa as report_qa

    answer = report_qa.ReportQAAnswer(
        answer="Invented.", report_type="daily_ops", question_ids=["op_q1"],
        finding_ids=["campaign_totals"], metric_ids=["imaginary_roi"], confidence=0.9,
    )
    monkeypatch.setattr(report_qa, "generate_structured", AsyncMock(return_value=(answer, {})))

    with pytest.raises(ValueError, match="unknown metric"):
        await report_qa.answer_report_question(
            session_id="report-bad", message="ROI?", preferred_type="daily_ops",
            analyses=_analyses(), history=[],
        )
