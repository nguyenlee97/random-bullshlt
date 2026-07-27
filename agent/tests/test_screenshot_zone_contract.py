import pytest
from playwright.async_api import async_playwright

from handlers.screenshot import _is_background_zone, _read_zone_state


@pytest.mark.asyncio
async def test_catalog_zone_resolves_by_id_or_data_zone_and_reports_inactive():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(
                """
                <style>
                  .zone { display:block; position:absolute; width:300px; height:250px; }
                  #hidden { display:none; }
                </style>
                <div id="Exact_Zone" class="zone"></div>
                <div id="generic-mount" class="zone" data-zone="Catalog_Data_Zone"></div>
                <div id="hidden" data-zone="Inactive_Zone"></div>
                """
            )

            exact = await _read_zone_state(page, "Exact_Zone")
            data_zone = await _read_zone_state(page, "Catalog_Data_Zone")
            inactive = await _read_zone_state(page, "Inactive_Zone")
            missing = await _read_zone_state(page, "Missing_Zone")

            assert exact["found"] is True
            assert exact["matched_by"] == "id"
            assert exact["bbox"]["width"] == 300
            assert data_zone["found"] is True
            assert data_zone["matched_by"] == "data-zone"
            assert data_zone["dom_id"] == "generic-mount"
            assert data_zone["bbox"]["height"] == 250
            assert inactive["found"] is True
            assert inactive["style_active"] is False
            assert inactive["reason"] == "display-none"
            assert missing == {"found": False, "reason": "not-found"}
        finally:
            await browser.close()


def test_np6_background_ids_use_background_geometry_without_hardcoding_topics():
    assert _is_background_zone("BaoMoi_FoodDining_Background")
    assert _is_background_zone("Znews_MusicLiveEvents_Background")
    assert _is_background_zone("BaoMoi_Background")
    assert not _is_background_zone("BaoMoi_FoodDining_Masthead")
