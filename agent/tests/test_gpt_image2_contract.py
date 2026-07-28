from handlers.image_gen import (
    AD_FORMATS,
    _build_prompt,
    generation_provenance,
    generation_size,
)


def test_every_generation_proxy_satisfies_gpt_image2_size_constraints():
    for format_id, fmt in AD_FORMATS.items():
        width, height = map(int, generation_size(fmt).split("x"))
        assert width % 16 == 0, format_id
        assert height % 16 == 0, format_id
        assert max(width, height) / min(width, height) <= 3, format_id
        assert 655_360 <= width * height <= 8_294_400, format_id
        assert max(width, height) <= 3840, format_id


def test_wide_format_prompt_declares_proxy_crop_and_exact_final_size():
    provenance = generation_provenance(
        {"brand": "Bún Bò Hutao", "notes": "hero bowl"},
        "znews-top-banner",
        "red palette",
        assets=[{"asset_id": "logo", "name": "Logo Hutao", "kind": "logo", "required": True}],
    )
    assert provenance["provider"] == "openai"
    assert provenance["model"] == "gpt-image-2"
    assert provenance["finalSize"] == "2224x480"
    assert provenance["generationSize"] == "1440x480"
    assert len(provenance["promptFingerprint"]) == 64


def test_openai_image_prompt_contains_product_and_selected_audience_context():
    prompt = _build_prompt(
        AD_FORMATS["zuma-box"],
        {
            "brand": "Tốt",
            "objective": "awareness",
            "notes": "Cửa hàng bán phân bón cho cây trồng.",
            "audience_summary": (
                "Selected DMP segments: Agriculture (industry), Farmers\n"
                "Targeting: location: miền Tây"
            ),
        },
    )

    assert "Cửa hàng bán phân bón" in prompt
    assert "Agriculture (industry), Farmers" in prompt
    assert "location: miền Tây" in prompt
