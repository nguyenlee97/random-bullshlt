"""ASGI request-body limit that also covers chunked requests."""
from __future__ import annotations

from starlette.responses import JSONResponse

from config import config


class RequestSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int | None = None):
        self.app = app
        self.max_bytes = max_bytes or config.MAX_AGENT_REQUEST_BYTES

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") not in {
            "POST", "PUT", "PATCH", "DELETE"
        }:
            await self.app(scope, receive, send)
            return

        # Owned creative endpoints carry validated base64 image data. Keep the
        # normal Agent limit tight while allowing only these scoped routes to
        # carry a 10 MiB image plus JSON/base64 overhead.
        request_limit = self.max_bytes
        if scope.get("path") in {
            "/api/agent/creative/assets",
            "/api/agent/generated-images/finalize",
        }:
            request_limit = max(request_limit, 15 * 1024 * 1024)

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length", b"")
        try:
            if raw_length and int(raw_length) > request_limit:
                await self._reject(scope, receive, send, max_bytes=request_limit)
                return
        except ValueError:
            await self._reject(scope, receive, send, "invalid content-length")
            return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > request_limit:
                    raise _RequestTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestTooLarge:
            await self._reject(scope, receive, send, max_bytes=request_limit)

    async def _reject(self, scope, receive, send, detail: str | None = None, max_bytes: int | None = None):
        limit = max_bytes or self.max_bytes
        response = JSONResponse(
            status_code=413,
            content={
                "error": "payload_too_large",
                "detail": detail or (
                    f"Payload vượt giới hạn {limit // 1024} KiB. "
                    "Vui lòng gửi metadata/URL thay vì dữ liệu file trong request agent."
                ),
            },
        )
        await response(scope, receive, send)


class _RequestTooLarge(Exception):
    pass
