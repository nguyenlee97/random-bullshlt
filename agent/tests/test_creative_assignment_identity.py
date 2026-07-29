from tools.creative_match import (
    auto_assign,
    creative_assignment_identity_score,
)


FILES = [
    {
        "name": "ai-zuma-box-campaign.png",
        "formatId": "zuma-box",
        "width": 300,
        "height": 250,
        "intel": {"width": 300, "height": 250, "effective_status": "auto_approved"},
    },
    {
        "name": "znews-side-banner.png",
        "formatId": "znews-side-banner",
        "width": 736,
        "height": 1456,
        "intel": {"width": 736, "height": 1456, "effective_status": "auto_approved"},
    },
    {
        "name": "zuma-Left.png",
        "formatId": "zuma-Left",
        "width": 465,
        "height": 1200,
        "intel": {"width": 465, "height": 1200, "effective_status": "auto_approved"},
    },
    {
        "name": "zuma-Right.png",
        "formatId": "zuma-Right",
        "width": 465,
        "height": 1200,
        "intel": {"width": 465, "height": 1200, "effective_status": "auto_approved"},
    },
]


def test_znews_side_contract_prefers_znews_asset():
    zone = {
        "id": "Znews_ShoppingEcommerce_SideLeft",
        "platform": "Znews",
        "format": "skin",
        "size": "skin",
        "creativeContractId": "znews-category-side-left-v1",
    }

    result = auto_assign([zone], FILES, prefer_contract_identity=True)

    assert result["assignments"][zone["id"]] == 1
    assert result["scores"][zone["id"]]["1"] > result["scores"][zone["id"]]["2"]
    assert result["scores"][zone["id"]]["0"] < 1


def test_baomoi_right_contract_prefers_right_baomoi_asset():
    zone = {
        "id": "BaoMoi_ShoppingEcommerce_SideRight",
        "platform": "BaoMoi",
        "format": "skin",
        "size": "skin",
        "creativeContractId": "baomoi-category-side-right-v1",
    }

    result = auto_assign([zone], FILES, prefer_contract_identity=True)

    assert result["assignments"][zone["id"]] == 3
    assert result["scores"][zone["id"]]["3"] > result["scores"][zone["id"]]["2"]
    assert result["scores"][zone["id"]]["3"] > result["scores"][zone["id"]]["1"]


def test_non_contract_skin_side_still_uses_platform_and_direction():
    zone = {
        "id": "BaoMoi_ShoppingEcommerce_SideRight",
        "platform": "BaoMoi",
        "format": "skin",
        "size": "skin",
    }

    result = auto_assign([zone], FILES, prefer_contract_identity=True)

    assert result["assignments"][zone["id"]] == 3


def test_generic_names_remain_neutral_for_geometry_fallback():
    score, warnings = creative_assignment_identity_score(
        {"name": "campaign-final.png"},
        {"id": "Znews_ShoppingEcommerce_SideLeft"},
    )

    assert score == 0
    assert warnings == []


def test_shared_category_background_contract_beats_publisher_name_penalty():
    zone = {
        "id": "BaoMoi_GamingEsports_Background",
        "platform": "BaoMoi",
        "format": "skin",
        "size": "skin",
        "creativeContractId": "category-background-v1",
    }
    shared_background = {
        "name": "znews-Background.png",
        "formatId": "znews-Background",
        "width": 1504,
        "height": 704,
        "intel": {
            "width": 1504,
            "height": 704,
            "effective_status": "auto_approved",
        },
    }
    wrong_side = {
        "name": "zuma-Left.png",
        "formatId": "zuma-Left",
        "width": 465,
        "height": 1200,
        "intel": {
            "width": 465,
            "height": 1200,
            "effective_status": "auto_approved",
        },
    }

    result = auto_assign(
        [zone],
        [wrong_side, shared_background],
        prefer_contract_identity=True,
    )

    assert result["assignments"][zone["id"]] == 1
    assert result["scores"][zone["id"]]["1"] > 100
