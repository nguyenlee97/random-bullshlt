import base64
import asyncio
from io import BytesIO

import pytest
from PIL import Image

import autopilot.creative_generation as generation
from campaign_models import OPENAI_GPT_5_4_MINI


async def _async_value(value):
    return value


def _image_b64(size=(16, 16)) -> str:
    output = BytesIO()
    Image.new("RGB", size, color=(0, 104, 255)).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _edge_marked_image_b64(size=(400, 100)) -> str:
    image = Image.new("RGB", size, color=(0, 180, 80))
    for x in range(80):
        for y in range(size[1]):
            image.putpixel((x, y), (230, 30, 30))
            image.putpixel((size[0] - x - 1, y), (30, 60, 230))
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


class _Response:
    def __init__(self, status_code, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


def test_fit_png_preserves_full_composition_in_different_target_ratio():
    fitted = base64.b64decode(
        generation._fit_png(_edge_marked_image_b64(), 200, 200)
    )
    with Image.open(BytesIO(fitted)) as image:
        assert image.size == (200, 200)
        # The foreground is scaled to 200x50 and centered. Both source edges
        # remain visible; the old center-crop implementation removed them.
        left = image.getpixel((2, 100))
        right = image.getpixel((197, 100))
        assert left[0] > left[2]
        assert right[2] > right[0]


def test_side_slider_fit_is_opaque_full_bleed_without_blurred_letterbox():
    fitted = base64.b64decode(
        generation._fit_png(_image_b64((40, 40)), 465, 1200, "zuma-Left")
    )
    with Image.open(BytesIO(fitted)) as image:
        assert image.size == (465, 1200)
        assert image.mode == "RGB"
        assert image.getpixel((0, 0)) == image.getpixel((232, 600))


@pytest.mark.asyncio
async def test_generate_creative_resizes_uploads_and_records_provenance(monkeypatch):
    calls = {"generate": 0, "post": None}

    async def fake_generate(session_id, brief, format_id, *args, **kwargs):
        calls["generate"] += 1
        return {
            "ok": True, "imageB64": _image_b64(), "formatId": format_id,
            "width": 300, "height": 250, "provider": "openai",
            "model": "gpt-image-2", "promptVersion": "creative-prompt-v2",
            "promptFingerprint": "prompt-sha",
        }

    async def fake_workspace(session_id):
        return {"artifacts": {
            "brief": {"revision": 4},
            "creative_format_plan": {"revision": 2},
        }}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def head(self, url):
            return _Response(404)

        async def post(self, url, json):
            calls["post"] = {"url": url, "json": json}
            return _Response(201, {
                "ok": True, "url": "http://backend:3000/uploads/generated.png",
                "filename": "generated.png", "size": 1024,
                "mimeType": "image/png", "reused": False,
            })

    monkeypatch.setattr(generation, "handle_generate_image", fake_generate)
    monkeypatch.setattr(generation, "actor_for_session", lambda *_args: _async_value({"anonymous_id": "test"}))
    monkeypatch.setattr(generation, "get_assets", lambda *_args: _async_value([]))
    monkeypatch.setattr(generation, "compose_prompt_spec", lambda *_args, **_kwargs: _async_value(({
        "creative_direction": "blue", "primary_promise": "benefit", "cta": "learn more", "quality": "medium",
    }, {"model": "gpt-5.4-mini"})))
    monkeypatch.setattr(generation, "inspect_generated_creative", lambda *_args, **_kwargs: _async_value(({
        "acceptable": True, "confidence": "high",
    }, {"model": "gpt-5.4-mini"})))
    monkeypatch.setattr(generation, "get_workspace", fake_workspace)
    monkeypatch.setattr(generation.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(generation.config, "BACKEND_URL", "http://backend:3000")

    workspace = {"artifacts": {
        "brief": {"revision": 4, "value": {"brand": "Zalo", "notes": "blue"}},
        "creative_format_plan": {"revision": 2},
    }}
    result = await generation.generate_creative(
        {
            "run_id": "run-4",
            "session_id": "session-4",
            "conversation_model": OPENAI_GPT_5_4_MINI,
        },
        workspace,
    )

    assert calls["generate"] == 1
    assert calls["post"]["json"]["idempotencyKey"].endswith("brief-r4")
    assert ":plan-r2:" in calls["post"]["json"]["idempotencyKey"]
    uploaded = base64.b64decode(calls["post"]["json"]["base64"])
    with Image.open(BytesIO(uploaded)) as image:
        assert image.size == (300, 250)
    assert result["url"] == "http://localhost:3000/uploads/generated.png"
    assert result["name"].startswith("ai-zuma-box-")
    assert result["source"] == "ai_generated"
    assert result["generation"]["promptFingerprint"] == "prompt-sha"
    assert result["generation"]["fitMode"] == "contain_with_blurred_background"


@pytest.mark.asyncio
async def test_generate_creative_recovers_uploaded_asset_without_regeneration(monkeypatch):
    async def forbidden_generate(*args, **kwargs):
        raise AssertionError("generation provider must not be called after durable upload")

    async def fake_workspace(session_id):
        return {"artifacts": {
            "brief": {"revision": 7},
            "creative_format_plan": {"revision": 3},
        }}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def head(self, url):
            return _Response(200, headers={"content-length": "2048"})

    monkeypatch.setattr(generation, "handle_generate_image", forbidden_generate)
    monkeypatch.setattr(generation, "actor_for_session", lambda *_args: _async_value({"anonymous_id": "test"}))
    monkeypatch.setattr(generation, "get_assets", lambda *_args: _async_value([]))
    monkeypatch.setattr(generation, "get_workspace", fake_workspace)
    monkeypatch.setattr(generation.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(generation.config, "BACKEND_URL", "http://backend:3000")

    workspace = {"artifacts": {
        "brief": {"revision": 7, "value": {"brand": "Zalo", "notes": "blue"}},
        "creative_format_plan": {"revision": 3},
    }}
    result = await generation.generate_creative(
        {
            "run_id": "run-7",
            "session_id": "session-7",
            "conversation_model": OPENAI_GPT_5_4_MINI,
        },
        workspace,
    )
    assert result["generation"]["reused"] is True
    assert result["size"] == 2048
    assert result["url"].startswith("http://localhost:3000/uploads/")
    assert result["name"].startswith("ai-zuma-box-")


@pytest.mark.asyncio
async def test_generate_creatives_is_bounded_and_reports_partial_failures(monkeypatch):
    active = 0
    peak = 0

    async def fake_generate(run, workspace, *, format_id, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        if format_id == "display-halfpage-300x600":
            raise RuntimeError("provider timeout")
        return {"formatId": format_id, "source": "ai_generated"}

    monkeypatch.setattr(generation, "generate_creative", fake_generate)
    plan = {"formats": [
        {"format_id": "zuma-box", "zone_ids": ["A"]},
        {"format_id": "display-halfpage-300x600", "zone_ids": ["B"]},
        {"format_id": "znews-masthead-1160x250", "zone_ids": ["C"]},
    ]}
    generated, failures = await generation.generate_creatives(
        {"run_id": "multi", "session_id": "multi"}, {}, plan, concurrency=2,
    )
    assert peak <= 2
    assert [item["formatId"] for item in generated] == [
        "zuma-box", "znews-masthead-1160x250",
    ]
    assert failures == [{
        "format_id": "display-halfpage-300x600",
        "zone_ids": ["B"],
        "error": "provider timeout",
    }]
