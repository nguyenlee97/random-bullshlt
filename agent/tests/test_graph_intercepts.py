"""
Parity tests: deterministic intercept paths must behave IDENTICALLY through
the old freeform handler and the new graph path. No LLM, no Mongo needed
(session.py falls back to in-memory when Mongo is unreachable).

Run: python -m pytest tests/test_graph_intercepts.py -q
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Env overrides live in tests/conftest.py (must run before app imports —
# setdefault here was too weak inside Docker where compose sets a real URI).

from handlers.freeform import handle_freeform  # noqa: E402
from graph.entry import handle_freeform_graph  # noqa: E402


async def both(message: str, step: int, sid_prefix: str, workspace=None):
    old = await handle_freeform(message, step, f"{sid_prefix}_old", workspace=workspace)
    new = await handle_freeform_graph(message, step, f"{sid_prefix}_new", workspace=workspace)
    return old, new


@pytest.mark.asyncio
async def test_next_step_redirect_parity():
    old, new = await both("sang bước tiếp theo", 1, "t_next")
    assert old.text == new.text
    assert [b["type"] for b in old.blocks] == [b["type"] for b in new.blocks]


@pytest.mark.asyncio
async def test_reset_intent_parity():
    old, new = await both("tạo chiến dịch mới", 0, "t_reset")
    assert old.text == new.text
    assert old.blocks[0]["type"] == new.blocks[0]["type"] == "action_reset"


@pytest.mark.asyncio
async def test_step1_auto_confirm_parity():
    ws = {"segment": {"attrs": [{"_id": "x", "fullLabel": "Gamers"}], "size": 100000}}
    old, new = await both("đồng ý", 1, "t_conf1", workspace=ws)
    assert old.workspace_update == new.workspace_update
    assert old.text == new.text


@pytest.mark.asyncio
async def test_step3_auto_confirm_parity():
    ws = {"setup": {"selectedZoneIds": ["ZN-001", "ZN-002"], "phase": "zones"}}
    old, new = await both("duyệt các zones này", 3, "t_conf3", workspace=ws)
    assert old.workspace_update == new.workspace_update
    assert old.text == new.text
    assert len(old.suggestions) == len(new.suggestions)


@pytest.mark.asyncio
async def test_checkpointer_no_stale_replay():
    """Regression (prod bug 2026-07-04): with a checkpointer, turn N must never
    replay turn N-1's response. Root cause was transient channels (response_text
    etc.) persisting across invokes because the entry state didn't reset them."""
    from langgraph.checkpoint.memory import MemorySaver
    import graph.entry as entry

    # Force checkpointed graphs (tests otherwise run stateless — mongo is down)
    saver = MemorySaver()
    entry._chat_graph = None
    entry._auto_graph = None
    entry._checkpointer = saver

    sid = "t_replay"
    r1 = await entry.handle_freeform_graph("sang bước tiếp theo", 1, sid)
    r2 = await entry.handle_freeform_graph("tạo chiến dịch mới", 1, sid)

    # cleanup so other tests rebuild stateless graphs
    entry._chat_graph = None
    entry._auto_graph = None
    entry._checkpointer = None

    assert r2.text != r1.text, "turn 2 replayed turn 1 — stale channel leak"
    assert r2.blocks and r2.blocks[0]["type"] == "action_reset"


@pytest.mark.asyncio
async def test_negated_confirm_not_intercepted_shape():
    """'không đồng ý' must NOT trigger the confirm path in either implementation.
    (Both fall through to the LLM; without a reachable LLM both should error
    the same way — we only assert neither produced a workspace_update.)"""
    ws = {"segment": {"attrs": [{"_id": "x"}], "size": 1}}
    old, new = await both("không đồng ý", 1, "t_neg", workspace=ws)
    assert old.workspace_update is None and new.workspace_update is None
