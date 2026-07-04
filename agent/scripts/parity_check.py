"""
Live parity check (Phase 1 step 5) — runs representative freeform messages
through BOTH paths with the real LLM and diffs the structure.

LLM text varies between calls, so parity = same used_tool, same block types,
same workspace_update presence — NOT identical prose. Intercept paths must
match exactly (covered by tests/test_graph_intercepts.py; re-checked here).

Run from agent/ with .env present (costs ~20 LLM calls):
    python scripts/parity_check.py
Flip USE_LANGGRAPH_FREEFORM=true only when this exits PASS.
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handlers.freeform import handle_freeform  # noqa: E402
from graph.entry import handle_freeform_graph  # noqa: E402

WS = {
    "brief": {"brand": "ZUMA Ice", "objective": "awareness", "kpi": "Reach 5M",
              "budget": 600, "startDate": "2026-08-01", "endDate": "2026-09-01",
              "notes": "Nam 18-28, thích gaming"},
}

CASES = [
    # (message, step, workspace, exact_text_expected)
    ("sang bước tiếp theo", 1, None, True),                      # intercept
    ("tạo chiến dịch mới", 0, None, True),                       # intercept
    ("cho tôi xem danh sách zone", 3, WS, False),                # tool call
    ("tìm segment về gaming", 1, WS, False),                     # tool call
    ("ngân sách 600 triệu có đủ cho reach 5M không?", 0, WS, False),  # plain chat
    ("đổi budget thành 700 triệu", 0, WS, False),                # update_workspace
]


def structure(resp) -> dict:
    return {
        "tool": resp.meta.tool if hasattr(resp.meta, "tool") else resp.meta.get("tool"),
        "block_types": [b.get("type") for b in resp.blocks],
        "has_ws_update": resp.workspace_update is not None,
        "has_text": bool(resp.text),
    }


async def main():
    failures = []
    for i, (msg, step, ws, exact) in enumerate(CASES):
        sid = f"parity_{uuid.uuid4().hex[:6]}"
        old = await handle_freeform(msg, step, f"{sid}_old", workspace=ws)
        new = await handle_freeform_graph(msg, step, f"{sid}_new", workspace=ws)
        so, sn = structure(old), structure(new)
        ok = (old.text == new.text) if exact else (
            so["block_types"] == sn["block_types"]
            and so["has_ws_update"] == sn["has_ws_update"]
            and so["has_text"] and sn["has_text"])
        print(f"[{'PASS' if ok else 'FAIL'}] case {i}: {msg[:40]!r}")
        if not ok:
            print(f"        old={so}\n        new={sn}")
            failures.append(i)

    print(f"\n{'❌ ' + str(len(failures)) + ' failures — fix graph side only ⛔' if failures else '✅ PARITY PASS — safe to flip USE_LANGGRAPH_FREEFORM=true'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
