import pytest


@pytest.mark.asyncio
async def test_boot_intro_is_specific_to_copilot_and_offers_brief_help():
    from handlers.boot import handle_boot

    response = await handle_boot("guided")

    assert "Campaign Copilot" in response.text
    assert "Campaign Autopilot" not in response.text
    assert "sản phẩm hoặc dịch vụ" in response.text
    assert "gợi ý giúp tôi phần còn thiếu" in response.text


@pytest.mark.asyncio
async def test_boot_intro_is_specific_to_autopilot_and_explains_minimum():
    from handlers.boot import handle_boot

    response = await handle_boot("autopilot")

    assert "Campaign Autopilot" in response.text
    assert "brief tối thiểu" in response.text
    assert "sản phẩm/dịch vụ" in response.text
    assert "gợi ý giúp tôi hoàn thiện brief" in response.text


@pytest.mark.asyncio
async def test_boot_readiness_message_does_not_expose_build_version():
    from handlers.boot import handle_boot

    response = await handle_boot("guided")

    assert response.blocks == [{
        "type": "info",
        "text": "🔖 Agent sẵn sàng hoạt động.",
    }]
    assert "Agent v" not in response.blocks[0]["text"]
