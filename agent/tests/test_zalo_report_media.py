import base64
import io
from unittest.mock import AsyncMock

import pytest
from PIL import Image


def _image_bytes(fmt="PNG", size=(320, 200), color="navy"):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format=fmt, quality=88)
    return output.getvalue()


def _campaign():
    return {
        "campaign_id": "ORD-REPORT-1",
        "conversation_id": "conv-report-1",
        "session_id": "sess-report-1",
        "order": {
            "id": "ORD-REPORT-1", "brand": "Warm Brand", "status": "active",
            "objective": "awareness", "budget": 25_000_000,
            "placements": ["BaoMoi_Masthead", "ZingNews_Masthead", "ZingMP3_Masthead"],
        },
    }


def test_report_catalog_exposes_all_six_explained_views():
    from zalo_reports import report_catalog_for_model

    reports = report_catalog_for_model()
    assert [item["view"] for item in reports] == [
        "daily_ops", "awareness", "consideration", "conversion",
        "retention", "executive",
    ]
    assert all(item["label"] and item["description"] for item in reports)


def test_complete_pdf_requires_all_six_report_types_ready():
    from zalo_reports import _all_reports_ready

    ready = {
        "types": {
            view: "ready"
            for view in (
                "daily_ops", "awareness", "consideration",
                "conversion", "retention", "executive",
            )
        }
    }
    assert _all_reports_ready(ready) is True
    ready["types"]["executive"] = "generating"
    assert _all_reports_ready(ready) is False


def test_report_renderer_creates_zalo_sized_jpeg_from_existing_metrics():
    from zalo_media import ZALO_IMAGE_SAFE_BYTES, prepare_zalo_image
    from zalo_reports import render_report_images

    records = [
        {
            "date": f"2026-07-{day:02d}", "placementId": "BaoMoi_Masthead",
            "impressions": 100_000 + day * 1000, "clicks": 750 + day * 5,
            "spend": 2_000_000 + day * 20_000, "reach": 65_000 + day * 500,
            "conversions": 30 + day, "vi": 72 + day / 10,
        }
        for day in range(1, 15)
    ]
    analysis = {
        "overall": "Độ phủ tăng đều, viewability ổn định và CPM nằm trong vùng kế hoạch.",
        "questions": [{"question": "Reach thay đổi thế nào?"}],
    }
    rendered_pages = render_report_images(
        campaign=_campaign(), view="awareness", records=records, analysis=analysis,
    )
    assert len(rendered_pages) == 3
    for rendered in rendered_pages:
        with Image.open(io.BytesIO(rendered)) as opened:
            assert opened.format == "JPEG"
            assert opened.size == (1080, 1350)
        prepared = prepare_zalo_image(rendered, "image/jpeg")
        assert len(prepared.data) <= ZALO_IMAGE_SAFE_BYTES


def test_oversized_image_is_reduced_below_zalo_limit():
    from zalo_media import prepare_zalo_image

    noisy = Image.effect_noise((2200, 2200), 90).convert("RGB")
    output = io.BytesIO()
    noisy.save(output, format="PNG")
    original = output.getvalue()
    prepared = prepare_zalo_image(original, "image/png", max_bytes=120_000)
    assert prepared.changed is True
    assert prepared.content_type == "image/jpeg"
    assert len(prepared.data) <= 120_000


@pytest.mark.asyncio
async def test_general_report_discovery_does_not_require_or_select_campaign():
    from zalo_tools import ToolExecutionContext, execute_zalo_tool

    ctx = ToolExecutionContext(thread={"thread_id": "zth-1"}, current_message="cho xem báo cáo", history=[])
    result = await execute_zalo_tool(ctx, "list_report_types", {})
    assert result["ok"] is True
    assert len(result["reports"]) == 6
    assert "Do not choose" in result["instruction"]


@pytest.mark.asyncio
async def test_specific_report_queues_image_then_generated_questions(monkeypatch):
    import zalo_tools
    from zalo_tools import ToolExecutionContext, execute_zalo_tool

    campaign = _campaign()
    async def update(thread, updates):
        return {**thread, **updates}

    monkeypatch.setattr("zalo_campaign_agent.owned_campaigns", AsyncMock(return_value=[campaign]))
    monkeypatch.setattr("zalo_campaign_agent._update_thread", update)
    monkeypatch.setattr(
        zalo_tools, "_campaign_for_reference",
        AsyncMock(return_value=(campaign, None)),
    )
    monkeypatch.setattr(
        "zalo_reports.get_report_bundle",
        AsyncMock(return_value={
            "ok": True, "status": "ready", "view": "awareness",
            "overall": "Reach đang tăng.",
            "suggested_questions": ["Reach thay đổi thế nào?", "CPM có ổn không?"],
            "image_pages": [_image_bytes("JPEG") for _ in range(3)],
            "image_content_type": "image/jpeg",
        }),
    )
    ctx = ToolExecutionContext(
        thread={"thread_id": "zth-2"},
        current_message="xem Awareness của Warm Brand", history=[],
    )
    result = await execute_zalo_tool(ctx, "get_campaign_report", {
        "campaign_reference": "Warm Brand", "view": "awareness",
        "mode": "show", "question": None,
    })
    assert result["status"] == "ready"
    assert len([part for part in ctx.media_parts if isinstance(part, dict)]) == 3
    assert all(part["byte_size"] < 1_000_000 for part in ctx.media_parts if isinstance(part, dict))
    assert "Reach thay đổi" in ctx.media_parts[-1]
    assert ctx.media_parts[-1].count("Bạn có thể hỏi tiếp") == 1
    assert "Tôi muốn file report PDF" in ctx.media_parts[-1]
    assert "suggested_questions" not in result
    assert "data_class" not in result


@pytest.mark.asyncio
async def test_report_without_campaign_never_silently_uses_active_or_only_campaign(monkeypatch):
    from zalo_tools import ToolExecutionContext, execute_zalo_tool

    campaign = _campaign()
    async def update(thread, updates):
        return {**thread, **updates}

    monkeypatch.setattr("zalo_campaign_agent.owned_campaigns", AsyncMock(return_value=[campaign]))
    monkeypatch.setattr("zalo_campaign_agent._update_thread", update)
    report_bundle = AsyncMock()
    monkeypatch.setattr("zalo_reports.get_report_bundle", report_bundle)
    ctx = ToolExecutionContext(
        thread={"thread_id": "zth-missing", "active_campaign_id": campaign["campaign_id"]},
        current_message="cho xin report awareness", history=[],
    )
    result = await execute_zalo_tool(ctx, "get_campaign_report", {
        "campaign_reference": "Warm Brand", "view": "awareness",
        "mode": "show", "question": None,
    })
    assert result["error"] == "campaign_reference_required"
    assert result["candidates"][0]["brand"] == "Warm Brand"
    assert ctx.thread["pending_report_request"]["view"] == "awareness"
    report_bundle.assert_not_awaited()


@pytest.mark.asyncio
async def test_pdf_request_uses_active_report_and_queues_only_opaque_link(monkeypatch):
    from zalo_tools import ToolExecutionContext, execute_zalo_tool

    campaign = _campaign()
    async def update(thread, updates):
        return {**thread, **updates}

    async def select(thread, selected):
        return {**thread, "active_campaign_id": selected["campaign_id"]}

    monkeypatch.setattr("zalo_campaign_agent.owned_campaigns", AsyncMock(return_value=[campaign]))
    monkeypatch.setattr("zalo_campaign_agent._update_thread", update)
    monkeypatch.setattr("zalo_campaign_agent._select_campaign", select)
    monkeypatch.setattr("zalo_campaign_agent._store_channel_media", AsyncMock(
        return_value="https://agent.test/zalo/media/opaque-token",
    ))
    monkeypatch.setattr("zalo_reports.get_report_bundle", AsyncMock(return_value={
        "ok": True, "status": "ready", "view": "awareness",
        "pdf_bytes": b"%PDF-test", "pdf_content_type": "application/pdf",
    }))
    ctx = ToolExecutionContext(thread={
        "thread_id": "zth-pdf", "active_report_campaign_id": campaign["campaign_id"],
        "active_report_view": "awareness",
    }, current_message="toi muon file report pfd", history=[])
    result = await execute_zalo_tool(ctx, "get_campaign_report", {
        "campaign_reference": "", "view": "daily_ops", "mode": "pdf", "question": None,
    })
    assert result["view"] == "awareness"
    assert "opaque-token" in ctx.media_parts[-1]
    assert "opaque-token" not in str(result)
    assert result["pdf_delivery"].startswith("One opaque")


@pytest.mark.asyncio
async def test_opaque_pdf_media_preserves_download_filename(monkeypatch):
    import zalo_campaign_agent as agent

    monkeypatch.setattr(agent, "_collections", AsyncMock(return_value=None))
    url = await agent._store_channel_media(
        b"%PDF-test", "application/pdf", filename="report-ORD-REPORT-1.pdf",
    )
    token = url.rsplit("/", 1)[-1]
    media = await agent.get_channel_media_download(token)
    assert media == (b"%PDF-test", "application/pdf", "report-ORD-REPORT-1.pdf")


def test_intro_guidance_and_report_tool_contract_are_explicit():
    from zalo_campaign_agent import _help_text
    from zalo_openai import _TOOL_AGENT_INSTRUCTIONS
    from zalo_tools import ZALO_TOOLS

    assert "Nếu bạn muốn được hướng dẫn kỹ hơn" in _help_text()
    assert 'generic placeholders such as "campaign A"' in _TOOL_AGENT_INSTRUCTIONS
    report_tool = next(tool for tool in ZALO_TOOLS if tool["name"] == "get_campaign_report")
    assert report_tool["parameters"]["properties"]["mode"]["enum"] == ["show", "question", "pdf"]
    assert "synthetic report" not in report_tool["description"].lower()


def test_similar_report_question_matches_generated_analysis():
    from zalo_reports import _matched_question

    expected = {
        "id": "awareness_reach", "question": "Reach thay đổi như thế nào theo ngày?",
        "answer": {"sections": [{"type": "summary", "text": "Reach tăng 12%."}]},
    }
    analysis = {"questions": [
        expected,
        {"id": "cpm", "question": "CPM có đang tối ưu không?", "answer": {}},
    ]}
    assert _matched_question(analysis, "độ phủ reach mấy ngày nay thay đổi ra sao") == expected


@pytest.mark.asyncio
async def test_all_live_sites_are_grouped_heading_zone_then_full(monkeypatch):
    import zalo_campaign_agent as agent

    png = base64.b64encode(_image_bytes("PNG")).decode()
    jpeg = base64.b64encode(_image_bytes("JPEG")).decode()

    async def screenshot(url, session_id, zone_ids):
        return {
            "ok": True,
            "zones": [{"id": zone_ids[0], "label": zone_ids[0], "crop_b64": png}],
            "full_b64": jpeg,
        }

    monkeypatch.setattr("handlers.screenshot.handle_screenshot", screenshot)
    parts = await agent._live_response(_campaign(), requested_site="all")
    assert parts[0] == "Đây là ảnh live quảng cáo trên BaoMoi:"
    assert parts[1]["kind"] == "image"
    assert parts[2]["kind"] == "image"
    assert parts[3] == "Đây là ảnh live quảng cáo trên Znews:"
    assert parts[6] == "Đây là ảnh live quảng cáo trên ZingMP3:"
    assert all(
        part["byte_size"] < 1_000_000
        for part in parts if isinstance(part, dict)
    )


@pytest.mark.asyncio
async def test_outbound_rejects_provider_oversized_image_before_queueing():
    from zalo_worker import enqueue_image

    with pytest.raises(ValueError, match="1 MB"):
        await enqueue_image(
            thread={"thread_id": "zth", "external_uid": "uid"},
            image_url="https://example.test/image.jpg",
            idempotency_key="oversized", byte_size=1_000_001,
        )
