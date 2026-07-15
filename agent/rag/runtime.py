"""Lifecycle state for the local embedding runtime."""
from __future__ import annotations

import asyncio
from contextlib import suppress


_task: asyncio.Task | None = None
_ready = False
_error: str | None = None


async def _prewarm() -> None:
    global _ready, _error
    try:
        from rag.embeddings import embed_dense, embed_sparse

        await asyncio.gather(
            asyncio.to_thread(embed_dense, ["advertising agent startup warmup"]),
            asyncio.to_thread(embed_sparse, ["advertising agent startup warmup"]),
        )
        _ready = True
        _error = None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _ready = False
        _error = f"{type(exc).__name__}: {str(exc)[:160]}"


async def start_prewarm() -> None:
    """Start one nonblocking warmup; readiness remains false until it finishes."""
    global _task, _ready, _error
    if _task is not None and not _task.done():
        return
    _ready = False
    _error = None
    _task = asyncio.create_task(_prewarm(), name="rag-runtime-prewarm")


async def stop_prewarm() -> None:
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
        with suppress(asyncio.CancelledError):
            await _task
    _task = None


def runtime_status() -> dict:
    return {
        "ready": _ready,
        "warming": bool(_task is not None and not _task.done()),
        "error": _error,
    }
