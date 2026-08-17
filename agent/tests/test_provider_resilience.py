from types import SimpleNamespace

import pytest

from provider_resilience import (
    CircuitBreaker,
    CircuitOpenError,
    execute_with_fallback,
    is_retryable_provider_error,
)


class ProviderError(RuntimeError):
    def __init__(self, status_code: int):
        super().__init__(f"provider returned {status_code}")
        self.status_code = status_code


def test_retryable_errors_are_limited_to_transient_failures():
    assert is_retryable_provider_error(TimeoutError("timed out"))
    assert is_retryable_provider_error(ProviderError(429))
    assert is_retryable_provider_error(ProviderError(503))
    assert not is_retryable_provider_error(ProviderError(400))
    assert not is_retryable_provider_error(ProviderError(401))


def test_circuit_opens_and_recovers_after_cooldown(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr("provider_resilience.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=5)

    for _ in range(2):
        with pytest.raises(TimeoutError):
            breaker.call(lambda: (_ for _ in ()).throw(TimeoutError("slow")))
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: "not called")

    clock[0] += 5
    assert breaker.call(lambda: "healthy") == "healthy"
    assert not breaker.is_open


def test_fallback_only_handles_transient_or_open_circuit_errors():
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=30)
    value, route = execute_with_fallback(
        lambda: (_ for _ in ()).throw(TimeoutError("slow")),
        breaker,
        lambda: "fallback-value",
    )
    assert (value, route) == ("fallback-value", "fallback")

    breaker.reset()
    with pytest.raises(ProviderError):
        execute_with_fallback(
            lambda: (_ for _ in ()).throw(ProviderError(401)),
            breaker,
            lambda: "must-not-run",
        )


def test_fallback_policy_defaults_to_disabled():
    import llm

    assert llm.config.ALLOW_OFFSHORE_LLM_FALLBACK is False
    assert llm._fallback_client is None


def test_reasoning_model_parameter_adaptation():
    from llm import _kwargs_for_model

    result = _kwargs_for_model(
        {"model": "primary", "max_tokens": 100, "temperature": 0.1},
        "gpt-5.4-mini",
    )
    assert result == {"model": "gpt-5.4-mini", "max_completion_tokens": 100}


@pytest.mark.asyncio
async def test_graph_provider_outage_returns_safe_deterministic_response(monkeypatch):
    from graph.nodes import agent_node as node
    from provider_resilience import PROVIDER_UNAVAILABLE_MESSAGE

    monkeypatch.setattr(
        node,
        "chat_completion",
        lambda **_kwargs: (_ for _ in ()).throw(TimeoutError("secret upstream detail")),
    )
    result = await node.agent_node({
        "session_id": "provider_outage_test",
        "messages": [{"role": "user", "content": "hello"}],
        "tokens_spent": 0,
        "token_budget": 100,
    })
    assert result["response_text"] == PROVIDER_UNAVAILABLE_MESSAGE
    assert result["used_tool"] == "provider_unavailable"
    assert result["fallback_level"] == 3
    assert "secret upstream detail" not in result["response_text"]
