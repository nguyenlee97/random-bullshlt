from handlers.screenshot import ALLOWED_DOMAINS, SITE_ZONES, _is_allowed


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
