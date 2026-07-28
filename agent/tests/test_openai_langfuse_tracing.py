from contextlib import nullcontext
from types import SimpleNamespace

import pytest


class _Observation:
    def __init__(self, *, name, as_type, parent=None, **kwargs):
        self.name = name
        self.as_type = as_type
        self.parent = parent
        self.created = kwargs
        self.updates = []
        self.children = []
        self.ended = False

    def start_observation(self, **kwargs):
        child = _Observation(parent=self, **kwargs)
        self.children.append(child)
        return child

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return self

    def end(self):
        self.ended = True
        return self


class _Langfuse:
    def __init__(self, *, fail_start=False):
        self.roots = []
        self.flushes = 0
        self.fail_start = fail_start

    def start_observation(self, **kwargs):
        if self.fail_start:
            raise RuntimeError("trace backend unavailable")
        root = _Observation(**kwargs)
        self.roots.append(root)
        return root

    def flush(self):
        self.flushes += 1


def _response():
    return SimpleNamespace(
        id="resp_full_debug",
        output_text="Câu trả lời đầy đủ",
        output=[{
            "type": "message",
            "content": [{"type": "output_text", "text": "Câu trả lời đầy đủ"}],
        }],
        output_parsed={"workflow_action": "answer_faq", "confidence": 0.93},
        usage=SimpleNamespace(
            input_tokens=321,
            output_tokens=123,
            total_tokens=444,
        ),
    )


@pytest.mark.asyncio
async def test_turn_trace_captures_full_generation_io_tokens_and_final_answer(
    monkeypatch,
):
    import openai_campaign.tracing as tracing

    fake = _Langfuse()
    attributes = []
    monkeypatch.setattr(tracing, "_get_langfuse", lambda: fake)
    monkeypatch.setattr(
        tracing,
        "_attribute_context",
        lambda session_id, trace_name: (
            attributes.append((session_id, trace_name)) or nullcontext()
        ),
    )
    request = {
        "model": "gpt-5.4-mini",
        "instructions": "System instruction in full",
        "input": [{"role": "user", "content": "Original user prompt"}],
        "tools": [{"type": "function", "name": "lookup_catalog"}],
        "text_format": {"type": "object", "properties": {"answer": {}}},
        "store": False,
    }

    async with tracing.trace_openai_turn(
        session_id="trace-session",
        message="Original user prompt",
        step=0,
        workspace={"revision": 4},
    ) as turn:
        result = await tracing.trace_responses_call(
            name="openai.turn_decision",
            session_id="trace-session",
            model="gpt-5.4-mini",
            request=request,
            metadata={"schema": "turn_decision"},
            model_parameters={"reasoning_effort": "low"},
            call=_async_response,
        )
        tracing.update_turn_output(
            turn,
            {"text": result.output_text, "tool": "openai_freeform_chat"},
        )

    assert attributes == [("trace-session", "openai_campaign_turn")]
    assert len(fake.roots) == 1
    root = fake.roots[0]
    assert root.as_type == "agent"
    assert root.name == "openai_campaign_turn"
    assert root.created["input"]["message"] == "Original user prompt"
    assert root.ended is True
    assert root.updates[-1]["output"]["text"] == "Câu trả lời đầy đủ"

    assert len(root.children) == 1
    generation = root.children[0]
    assert generation.as_type == "generation"
    assert generation.created["input"] == request
    assert generation.created["model"] == "gpt-5.4-mini"
    assert generation.created["model_parameters"] == {"reasoning_effort": "low"}
    assert generation.updates[-1]["output"]["output_text"] == "Câu trả lời đầy đủ"
    assert generation.updates[-1]["output"]["output_parsed"] == {
        "workflow_action": "answer_faq", "confidence": 0.93,
    }
    assert generation.updates[-1]["usage_details"] == {
        "input": 321, "output": 123, "total": 444,
    }
    assert generation.updates[-1]["metadata"]["response_id"] == "resp_full_debug"
    assert generation.ended is True
    assert fake.flushes == 1


async def _async_response():
    return _response()


@pytest.mark.asyncio
async def test_langfuse_start_failure_does_not_duplicate_or_break_provider_call(
    monkeypatch,
):
    import openai_campaign.tracing as tracing

    fake = _Langfuse(fail_start=True)
    calls = 0

    async def provider_call():
        nonlocal calls
        calls += 1
        return _response()

    monkeypatch.setattr(tracing, "_get_langfuse", lambda: fake)
    monkeypatch.setattr(
        tracing, "_attribute_context", lambda *_: nullcontext(),
    )
    result = await tracing.trace_responses_call(
        name="openai.structured.test",
        session_id="trace-fallback",
        model="gpt-5.4-mini",
        request={"input": "hello"},
        call=provider_call,
    )

    assert result.id == "resp_full_debug"
    assert calls == 1


@pytest.mark.asyncio
async def test_provider_error_is_recorded_and_preserves_original_exception(
    monkeypatch,
):
    import openai_campaign.tracing as tracing

    fake = _Langfuse()
    monkeypatch.setattr(tracing, "_get_langfuse", lambda: fake)
    monkeypatch.setattr(
        tracing, "_attribute_context", lambda *_: nullcontext(),
    )

    async def provider_call():
        raise TimeoutError("OpenAI timeout")

    with pytest.raises(TimeoutError, match="OpenAI timeout"):
        await tracing.trace_responses_call(
            name="openai.answer_tool_round",
            session_id="trace-error",
            model="gpt-5.4-mini",
            request={"input": "hello"},
            call=provider_call,
        )

    generation = fake.roots[0]
    assert generation.updates[-1]["level"] == "ERROR"
    assert generation.updates[-1]["output"]["error"] == "TimeoutError"
    assert generation.ended is True
    assert fake.flushes == 1


@pytest.mark.asyncio
async def test_tool_execution_is_nested_with_arguments_and_output(monkeypatch):
    import openai_campaign.tracing as tracing

    fake = _Langfuse()
    monkeypatch.setattr(tracing, "_get_langfuse", lambda: fake)
    monkeypatch.setattr(
        tracing, "_attribute_context", lambda *_: nullcontext(),
    )

    async with tracing.trace_openai_turn(
        session_id="tool-trace", message="find zones", step=3, workspace={},
    ):
        result = await tracing.trace_tool_call(
            session_id="tool-trace",
            name="search_zones",
            arguments={"query": "food"},
            call=lambda: _async_tool_result(),
        )

    tool = fake.roots[0].children[0]
    assert result == {"output": "zone-1"}
    assert tool.as_type == "tool"
    assert tool.name == "openai.tool.search_zones"
    assert tool.created["input"] == {"query": "food"}
    assert tool.updates[-1]["output"] == {"output": "zone-1"}
    assert tool.ended is True


async def _async_tool_result():
    return {"output": "zone-1"}


def test_every_openai_campaign_responses_call_uses_the_shared_tracer():
    from pathlib import Path

    root = Path(__file__).parents[1] / "openai_campaign"
    expected = {
        "audience_search.py": "trace_responses_call",
        "decision.py": "trace_responses_call",
        "structured.py": "trace_responses_call",
        "engine.py": "trace_responses_call",
    }
    direct_call_files = set()
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if ".responses.create(" in source or ".responses.parse(" in source:
            direct_call_files.add(path.name)
            assert expected[path.name] in source
    assert direct_call_files == set(expected)


def test_pytest_does_not_initialize_real_langfuse_without_explicit_opt_in(
    monkeypatch,
):
    import openai_campaign.tracing as tracing

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-live-would-be-real")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_trace.py::test_guard (call)")
    monkeypatch.delenv("LANGFUSE_TRACE_TESTS", raising=False)
    tracing.reset_for_test()

    assert tracing._get_langfuse() is None
    assert tracing._langfuse_initialized is True


def test_legacy_langgraph_callback_is_also_suppressed_during_pytest(monkeypatch):
    from graph.entry import _langfuse_config

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-live-would-be-real")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_trace.py::test_guard (call)")
    monkeypatch.delenv("LANGFUSE_TRACE_TESTS", raising=False)

    config = _langfuse_config("test-session", "test-request", "chat")

    assert config == {"configurable": {"thread_id": "test-session"}}


def test_legacy_generation_trace_is_suppressed_during_pytest(monkeypatch):
    import llm

    class FailIfCalled:
        def start_observation(self, **_kwargs):
            raise AssertionError("pytest must not send Langfuse observations")

    monkeypatch.setattr(llm, "_langfuse", FailIfCalled())
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_trace.py::test_guard (call)")
    monkeypatch.delenv("LANGFUSE_TRACE_TESTS", raising=False)

    llm._trace_to_langfuse(
        "chat_completion", [], object(), 1, "test-model", "test-url", "primary",
    )
