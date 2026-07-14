"""Creative intelligence job, override, and assignment safety tests."""
from datetime import timedelta
from io import BytesIO

import pytest
from PIL import Image


@pytest.mark.asyncio
async def test_deterministic_analysis_uses_real_pixels():
    from creative_intel.analyzer import analyze_bytes

    buffer = BytesIO()
    Image.new("RGB", (1200, 628), color="white").save(buffer, format="PNG")
    result = await analyze_bytes(buffer.getvalue(), name="misleading-name-300x250.png")

    assert result["width"] == 1200
    assert result["height"] == 628
    assert result["min_size_ok"] is True


@pytest.mark.asyncio
async def test_job_is_persisted_processed_and_override_is_audited(monkeypatch):
    import creative_intel.service as service

    async def no_mongo():
        return None

    async def fake_analysis(_doc):
        return {
            "status": "needs_review",
            "review_reasons": ["low confidence"],
            "deterministic": {"width": 1200, "height": 628},
        }

    async def no_log(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "_col", no_mongo)
    monkeypatch.setattr(service, "_analyze_job", fake_analysis)
    monkeypatch.setattr(service, "alog", no_log)
    service._mem.clear()

    jobs = await service.enqueue_analysis("sess-test", [{
        "id": "file-1",
        "name": "banner.png",
        "type": "image/png",
        "url": "http://localhost:3000/uploads/banner.png",
    }])
    assert jobs[0]["status"] == "queued"
    assert await service.process_next_job() is True

    verdict = (await service.get_intel("sess-test"))[0]
    assert verdict["status"] == "needs_review"
    assert verdict["effective_status"] == "needs_review"

    approved = await service.approve_override(
        "sess-test", verdict["analysis_id"], "Đã kiểm tra nội dung thủ công", "reviewer-1"
    )
    assert approved["effective_status"] == "approved_override"
    assert approved["override"]["actor"] == "reviewer-1"
    assert approved["override"]["original_reasons"] == ["low confidence"]


@pytest.mark.asyncio
async def test_stale_analyzing_job_is_requeued(monkeypatch):
    import creative_intel.service as service

    async def no_mongo():
        return None

    monkeypatch.setattr(service, "_col", no_mongo)
    service._mem.clear()
    stale = service._now() - timedelta(seconds=service.config.CREATIVE_JOB_STALE_SECONDS + 1)
    service._mem["ci-stale"] = {
        "_id": "ci-stale", "session_id": "s", "status": "analyzing",
        "started_at": stale, "created_at": stale,
    }

    assert await service.recover_stale_jobs() == 1
    assert service._mem["ci-stale"]["status"] == "queued"


def test_auto_assignment_excludes_unreviewed_creative():
    from tools.creative_match import auto_assign

    zone = {"id": "ZN-1", "format": "banner", "size": "1200x628"}
    files = [
        {"name": "blocked.png", "width": 1200, "height": 628,
         "intel": {"status": "needs_review", "effective_status": "needs_review"}},
        {"name": "approved.png", "width": 600, "height": 314,
         "intel": {"status": "auto_approved", "effective_status": "auto_approved"}},
    ]

    result = auto_assign([zone], files)
    assert result["assignments"]["ZN-1"] == 1
    assert 0 not in result["scores"]["ZN-1"]


def test_explicit_intended_format_beats_uncertain_vlm_layout():
    from tools.creative_match import enrich_files_with_intel

    files = [{"name": "innocuous.png", "url": "http://x/creative.png"}]
    docs = [{
        "name": "innocuous.png",
        "url": "http://x/creative.png",
        "status": "auto_approved",
        "effective_status": "auto_approved",
        "intended_format": "skin",
        "deterministic": {"width": 395, "height": 890, "is_skin_layout": False},
        "vlm": {"is_skin_takeover": False},
    }]
    enriched = enrich_files_with_intel(files, docs)
    assert enriched[0]["intel"]["is_skin"] is True
    assert enriched[0]["intel"]["intended_format"] == "skin"


def test_vlm_normalizes_provider_safety_shapes_without_defaulting_fields():
    from creative_intel.vlm import CreativeVLMResult, _normalize_payload

    raw = """{
      "ocr_text": "Learn English",
      "brand_guess": "ELSA",
      "subject_desc": "Ứng dụng học tiếng Anh",
      "is_skin_takeover": false,
      "safety": [],
      "brief_match_score": 5,
      "brief_match_reasons": "Đúng thương hiệu",
      "confidence": 0.95
    }"""
    result = CreativeVLMResult.model_validate(_normalize_payload(raw))
    assert result.ocr_text == ["Learn English"]
    assert result.safety.model_dump() == {
        "nsfw": False, "alcohol": False, "gambling": False,
        "political": False, "medical": False,
    }
    assert result.brief_match_reasons == ["Đúng thương hiệu"]

    boolean_safe = raw.replace('"safety": []', '"safety": false')
    result = CreativeVLMResult.model_validate(_normalize_payload(boolean_safe))
    assert not any(result.safety.model_dump().values())

    stringified = raw.replace(
        '"safety": []',
        '"safety": "{\\"nsfw\\": false, \\"alcohol\\": false, '
        '\\"gambling\\": false, \\"political\\": false, \\"medical\\": false}"',
    )
    result = CreativeVLMResult.model_validate(_normalize_payload(stringified))
    assert not any(result.safety.model_dump().values())


def test_vlm_copy_is_resized_without_touching_deterministic_source():
    from creative_intel.vlm import _prepare_image

    source = BytesIO()
    Image.new("RGB", (1600, 1200), color="white").save(source, format="PNG")
    prepared, mime = _prepare_image(source.getvalue(), "image/png")
    with Image.open(BytesIO(prepared)) as image:
        assert max(image.size) == 768
    assert mime == "image/jpeg"
