import base64
from io import BytesIO

import pytest
from PIL import Image

import autopilot.creative_generation as generation


def _image_b64(size=(16, 16)) -> str:
    output = BytesIO()
    Image.new("RGB", size, color=(0, 104, 255)).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


class _Response:
    def __init__(self, status_code, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_generate_creative_resizes_uploads_and_records_provenance(monkeypatch):
    calls = {"generate": 0, "post": None}

    async def fake_generate(session_id, brief, format_id):
        calls["generate"] += 1
        return {
            "ok": True, "imageB64": _image_b64(), "formatId": format_id,
            "width": 300, "height": 250, "provider": "vngcloud_maas",
            "model": "openai/gpt-image-1", "promptVersion": "image-gen-v1",
            "promptFingerprint": "prompt-sha",
        }

    async def fake_workspace(session_id):
        return {"artifacts": {"brief": {"revision": 4}}}

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
    monkeypatch.setattr(generation, "get_workspace", fake_workspace)
    monkeypatch.setattr(generation.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(generation.config, "BACKEND_URL", "http://backend:3000")

    workspace = {"artifacts": {"brief": {
        "revision": 4, "value": {"brand": "Zalo", "notes": "blue"},
    }}}
    result = await generation.generate_creative(
        {"run_id": "run-4", "session_id": "session-4"}, workspace
    )

    assert calls["generate"] == 1
    assert calls["post"]["json"]["idempotencyKey"].endswith("brief-r4")
    uploaded = base64.b64decode(calls["post"]["json"]["base64"])
    with Image.open(BytesIO(uploaded)) as image:
        assert image.size == (300, 250)
    assert result["url"] == "http://localhost:3000/uploads/generated.png"
    assert result["source"] == "ai_generated"
    assert result["generation"]["promptFingerprint"] == "prompt-sha"


@pytest.mark.asyncio
async def test_generate_creative_recovers_uploaded_asset_without_regeneration(monkeypatch):
    async def forbidden_generate(*args, **kwargs):
        raise AssertionError("generation provider must not be called after durable upload")

    async def fake_workspace(session_id):
        return {"artifacts": {"brief": {"revision": 7}}}

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
    monkeypatch.setattr(generation, "get_workspace", fake_workspace)
    monkeypatch.setattr(generation.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(generation.config, "BACKEND_URL", "http://backend:3000")

    workspace = {"artifacts": {"brief": {
        "revision": 7, "value": {"brand": "Zalo", "notes": "blue"},
    }}}
    result = await generation.generate_creative(
        {"run_id": "run-7", "session_id": "session-7"}, workspace
    )
    assert result["generation"]["reused"] is True
    assert result["size"] == 2048
    assert result["url"].startswith("http://localhost:3000/uploads/")
