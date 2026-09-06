from __future__ import annotations

import asyncio

from config import config
from evaluation.service import run_evaluation
from evaluation.store import claim_due_policy


_runner: asyncio.Task | None = None
_stop = asyncio.Event()


async def process_due_once() -> bool:
    policy = await claim_due_policy()
    if not policy:
        return False
    try:
        await run_evaluation(policy["campaign_id"], trigger="scheduled", force=False)
    except Exception as exc:
        print(f"[evaluation] scheduled run failed for {policy['campaign_id']}: {str(exc)[:240]}")
    return True


async def _loop() -> None:
    while not _stop.is_set():
        try:
            handled = await process_due_once()
        except Exception as exc:
            print(f'[evaluation] worker will retry: {str(exc)[:160]}')
            handled = False
        if handled:
            continue
        try:
            await asyncio.wait_for(
                _stop.wait(), timeout=max(1.0, config.EVALUATION_WORKER_POLL_SECONDS),
            )
        except asyncio.TimeoutError:
            pass


async def start_worker() -> None:
    global _runner
    if _runner and not _runner.done():
        return
    _stop.clear()
    _runner = asyncio.create_task(_loop(), name="evaluation-worker")


async def stop_worker() -> None:
    global _runner
    _stop.set()
    if _runner:
        await _runner
    _runner = None
