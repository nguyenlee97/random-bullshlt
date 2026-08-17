import asyncio
import time

import pytest


@pytest.mark.asyncio
async def test_two_slow_model_calls_do_not_starve_workspace_polling(monkeypatch):
    from graph.nodes import agent_node as node
    from provider_resilience import PROVIDER_UNAVAILABLE_MESSAGE
    from workspace.service import get_workspace

    def slow_provider(**_kwargs):
        time.sleep(15)
        raise TimeoutError("simulated provider timeout")

    monkeypatch.setattr(node, "chat_completion", slow_provider)
    chat_tasks = [
        asyncio.create_task(node.agent_node({
            "session_id": f"slow_chat_{index}",
            "messages": [{"role": "user", "content": "hello"}],
            "tokens_spent": 0,
            "token_budget": 100,
        }))
        for index in range(2)
    ]

    poll_latencies = []
    for tick in range(15):
        started = time.perf_counter()
        await asyncio.wait_for(
            asyncio.gather(*[
                get_workspace(f"poll_{tick}_{index}") for index in range(20)
            ]),
            timeout=5,
        )
        elapsed = time.perf_counter() - started
        poll_latencies.append(elapsed)
        await asyncio.sleep(max(0, 1 - elapsed))

    responses = await asyncio.gather(*chat_tasks)
    assert max(poll_latencies) < 1
    assert all(item["response_text"] == PROVIDER_UNAVAILABLE_MESSAGE for item in responses)
    assert all(item["used_tool"] == "provider_unavailable" for item in responses)
