from config import config
from handlers.screenshot import ALLOWED_DOMAINS, SITE_ZONES, _is_allowed, _site_zones


def test_np6_property_domains_are_whitelisted_with_exact_zone_ids():
    expected = {
        "smoney-stg.pawgrammers.io.vn": {
            "SMoney_TopPromo_Desktop",
            "SMoney_TopPromo_Mobile",
            "SMoney_StockScreener_InContent_Desktop",
            "SMoney_StockScreener_InContent_Mobile",
        },
        "dicungcon-stg.pawgrammers.io.vn": {
            "DiCungCon_ContentBridge_Desktop",
            "DiCungCon_ContentBridge_Mobile",
            "DiCungCon_SidebarRail_Desktop",
        },
        "zagoo-stg.pawgrammers.io.vn": {
            "Zagoo_Interstitial_Desktop",
            "Zagoo_Interstitial_Mobile",
        },
    }

    for domain, zone_ids in expected.items():
        assert domain in ALLOWED_DOMAINS
        assert _is_allowed(f"https://{domain}/")
        assert {zone_id for zone_id, _label in SITE_ZONES[domain]} == zone_ids


def test_similar_untrusted_domains_remain_blocked():
    assert not _is_allowed("https://smoney-stg.pawgrammers.io.vn.evil.example/")
    assert not _is_allowed("https://zagoo-stg.pawgrammers.io.vn@evil.example/")


def test_path_based_hackathon_publishers_are_allowed_without_opening_the_host(monkeypatch):
    monkeypatch.setattr(config, "LOCAL_ZNEWS_URL", "https://zah-4.123c.vn/znews/")
    monkeypatch.setattr(config, "LOCAL_BAOMOI_URL", "https://zah-4.123c.vn/baomoi/")

    assert _is_allowed("https://zah-4.123c.vn/znews/cong-nghe.html")
    assert _is_allowed("https://zah-4.123c.vn/baomoi/category.html?topic=family")
    assert _site_zones("https://zah-4.123c.vn/baomoi/") == SITE_ZONES[
        "baomoi-stg.pawgrammers.io.vn"
    ]

    assert not _is_allowed("https://zah-4.123c.vn/manage")
    assert not _is_allowed("https://zah-4.123c.vn/znews-evil/")
    assert not _is_allowed("https://zah-4.123c.vn.evil.example/znews/")
