import asyncio
from unittest.mock import AsyncMock

import pytest

from autopilot import worker


@pytest.mark.asyncio
async def test_worker_recovers_after_transient_task_claim_failure(monkeypatch):
    stop = asyncio.Event()
    claim_calls = 0

    async def claim_next(_worker_id):
        nonlocal claim_calls
        claim_calls += 1
        if claim_calls == 1:
            raise RuntimeError("temporary Mongo timeout")
        stop.set()
        return None

    log = AsyncMock()
    monkeypatch.setattr(worker, "_stop_event", stop)
    monkeypatch.setattr(worker, "reconcile_active_runs", AsyncMock())
    monkeypatch.setattr(worker, "claim_next_task", claim_next)
    monkeypatch.setattr(worker, "alog", log)
    monkeypatch.setattr(worker.config, "AUTOPILOT_WORKER_POLL_SECONDS", 0.01)

    await worker._loop()

    assert claim_calls == 2
    log.assert_awaited_once()
    assert log.await_args.args[2]["handler"] == "autopilot_worker_loop"
