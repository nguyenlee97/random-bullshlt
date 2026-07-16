import asyncio

import pytest

from rag import runtime


@pytest.mark.asyncio
async def test_runtime_is_not_ready_until_background_prewarm_finishes(monkeypatch):
    import rag.embeddings as embeddings

    def wait_then_embed(_texts):
        # The worker thread cannot await an asyncio.Event; a short blocking
        # wait gives the test enough time to observe the warming state.
        import time
        time.sleep(0.04)
        return [[0.1]]

    monkeypatch.setattr(embeddings, "embed_dense", wait_then_embed)
    monkeypatch.setattr(embeddings, "embed_sparse", wait_then_embed)
    await runtime.stop_prewarm()
    await runtime.start_prewarm()
    assert runtime.runtime_status()["ready"] is False
    assert runtime.runtime_status()["warming"] is True
    await asyncio.sleep(0.08)
    assert runtime.runtime_status() == {"ready": True, "warming": False, "error": None}
    await runtime.stop_prewarm()


@pytest.mark.asyncio
async def test_runtime_failure_keeps_readiness_false(monkeypatch):
    import rag.embeddings as embeddings

    def broken(_texts):
        raise RuntimeError("fixture failed")

    monkeypatch.setattr(embeddings, "embed_dense", broken)
    monkeypatch.setattr(embeddings, "embed_sparse", broken)
    await runtime.stop_prewarm()
    await runtime.start_prewarm()
    # A busy suite may delay the default thread-pool worker. Poll the actual
    # lifecycle condition instead of assuming the failure finishes in 20 ms.
    for _ in range(100):
        if not runtime.runtime_status()["warming"]:
            break
        await asyncio.sleep(0.01)
    status = runtime.runtime_status()
    assert status["ready"] is False
    assert status["warming"] is False
    assert "fixture failed" in status["error"]
    await runtime.stop_prewarm()
