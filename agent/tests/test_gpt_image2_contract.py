from handlers.image_gen import AD_FORMATS, generation_provenance, generation_size


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
