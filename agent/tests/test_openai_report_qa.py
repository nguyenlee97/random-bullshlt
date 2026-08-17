import json
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
        answer="CTR là 0,72% trong kỳ báo cáo.", report_type="daily_ops",
        question_ids=["op_q1"], finding_ids=["campaign_totals"], metric_ids=["ctr"],
        limitations=[], suggestions=[], confidence=0.95,
    )
    generator = AsyncMock(return_value=(answer, {"model": "gpt-5.4-mini"}))
    monkeypatch.setattr(report_qa, "generate_structured", generator)

    result, provenance = await report_qa.answer_report_question(
        session_id="report-semantic", message="Hiệu quả click có ổn không?",
        preferred_type="daily_ops", analyses=_analyses(), history=[{
            "role": "assistant",
            "content": "Lưu ý: dữ liệu là dữ liệu mô phỏng (showcase).",
        }],
    )

    assert result.finding_ids == ["campaign_totals"]
    assert provenance["model"] == "gpt-5.4-mini"
    model_input = generator.await_args.kwargs["input_data"]
    assert "keyword" not in model_input
    assert "synthetic" not in model_input.lower()
    assert "showcase" not in model_input.lower()
    assert "synthetic" not in generator.await_args.kwargs["instructions"].lower()
    assert "read-only follow-up questions" in generator.await_args.kwargs["instructions"]
    payload = json.loads(model_input)
    contract = payload["evidence"]["reports"][0]["data_contract"]
    assert contract["findings"][0]["metrics"]["ctr"] == 0.72
    assert contract["limitations"] == []
    assert result.suggestions
    assert all("cảnh báo" not in item.lower() for item in result.suggestions)


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


def test_report_suggestions_remove_unsupported_operations_and_keep_analysis():
    from openai_campaign.report_qa import safe_report_suggestions

    suggestions = safe_report_suggestions(
        [
            "Thiết lập cảnh báo khi CTR giảm",
            "Theo dõi chiến dịch này mỗi ngày",
            "Theo dõi hiệu suất theo thời gian thực",
            "Gửi báo cáo cho tôi qua email",
            "CTR và CPM nên được đọc cùng nhau như thế nào?",
            "Dữ liệu nào còn thiếu để kết luận về hiệu quả chuyển đổi?",
        ],
        _analyses(),
        preferred_type="daily_ops",
    )

    assert suggestions[:2] == [
        "CTR và CPM nên được đọc cùng nhau như thế nào?",
        "Dữ liệu nào còn thiếu để kết luận về hiệu quả chuyển đổi?",
    ]
    assert len(suggestions) == 4
    assert not any(
        marker in " ".join(suggestions).lower()
        for marker in ("cảnh báo", "mỗi ngày", "thời gian thực", "email")
    )


@pytest.mark.asyncio
async def test_report_qa_replaces_unsafe_model_suggestions(monkeypatch):
    import openai_campaign.report_qa as report_qa

    answer = report_qa.ReportQAAnswer(
        answer="CTR là 0,72% trong kỳ báo cáo.",
        report_type="daily_ops",
        question_ids=["op_q1"],
        finding_ids=["campaign_totals"],
        metric_ids=["ctr"],
        suggestions=[
            "Tạo cảnh báo tự động khi CTR giảm",
            "Cài đặt tracking cho conversion",
            "Xu hướng CTR trong kỳ báo cáo có gì đáng chú ý?",
        ],
        confidence=0.95,
    )
    monkeypatch.setattr(
        report_qa,
        "generate_structured",
        AsyncMock(return_value=(answer, {"model": "gpt-5.4-mini"})),
    )

    result, _ = await report_qa.answer_report_question(
        session_id="report-safe-suggestions",
        message="CTR có ổn không?",
        preferred_type="daily_ops",
        analyses=_analyses(),
        history=[],
    )

    assert result.suggestions[0] == "Xu hướng CTR trong kỳ báo cáo có gì đáng chú ý?"
    assert len(result.suggestions) == 4
    assert not any("cảnh báo" in item.lower() for item in result.suggestions)
    assert not any("tracking" in item.lower() for item in result.suggestions)
