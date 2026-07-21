"""Langfuse observability for the independent OpenAI campaign engine.

One web chat turn becomes an ``agent`` trace. Every Responses API call and
server-side tool execution is recorded as a child observation with the exact
request/response payload available to this process. Standalone Guided and
Autopilot model calls remain visible as root generations.

Tracing is deliberately best-effort: Langfuse must never retry, replace, or
otherwise change an OpenAI provider call.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, nullcontext
from contextvars import ContextVar
import os
import time
from typing import Any, Awaitable, Callable, TypeVar

from config import config
from request_context import get_request_id
from security import redact_langfuse
from version import BUILD_VERSION


T = TypeVar("T")

_langfuse: Any | None = None
_langfuse_initialized = False
_current_turn: ContextVar[Any | None] = ContextVar(
    "openai_campaign_langfuse_turn", default=None,
)


def _get_langfuse() -> Any | None:
    global _langfuse, _langfuse_initialized
    if _langfuse_initialized:
        return _langfuse
    _langfuse_initialized = True
    # A developer checkout may contain real Langfuse credentials. Never pollute
    # the production project with fake provider responses from pytest unless a
    # dedicated trace-test run explicitly opts in.
    if (
        os.getenv("PYTEST_CURRENT_TEST")
        and os.getenv("LANGFUSE_TRACE_TESTS", "false").lower() != "true"
    ):
        return None
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return None
    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            mask=redact_langfuse,
            release=BUILD_VERSION,
        )
        print(
            "[openai_campaign] Langfuse tracing enabled ->",
            os.getenv("LANGFUSE_HOST"),
        )
    except Exception as exc:  # pragma: no cover - environment-specific
        print(
            "[openai_campaign] Langfuse init failed; tracing disabled:",
            str(exc)[:300],
        )
        _langfuse = None
    return _langfuse


def _jsonable(value: Any, *, depth: int = 0) -> Any:
    if depth > 12:
        return "[TRUNCATED_DEPTH]"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(
                value.model_dump(mode="json", exclude_none=True),
                depth=depth + 1,
            )
        except Exception:
            pass
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item, depth=depth + 1) for item in value]
    if hasattr(value, "__dict__"):
        try:
            return _jsonable(vars(value), depth=depth + 1)
        except Exception:
            pass
    return str(value)


def response_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input": 0, "output": 0, "total": 0}
    raw = _jsonable(usage)
    if not isinstance(raw, dict):
        raw = {}
    return {
        "input": int(raw.get("input_tokens") or raw.get("prompt_tokens") or 0),
        "output": int(
            raw.get("output_tokens") or raw.get("completion_tokens") or 0
        ),
        "total": int(raw.get("total_tokens") or 0),
    }


def _response_output(response: Any) -> Any:
    if hasattr(response, "model_dump"):
        try:
            return response.model_dump(mode="json", exclude_none=True)
        except Exception:
            pass
    result = {
        "id": getattr(response, "id", None),
        "output_text": getattr(response, "output_text", None),
        "output": getattr(response, "output", None),
        "output_parsed": getattr(response, "output_parsed", None),
        "usage": getattr(response, "usage", None),
    }
    return _jsonable({key: value for key, value in result.items() if value is not None})


def _attribute_context(session_id: str, trace_name: str):
    try:
        from langfuse import propagate_attributes

        return propagate_attributes(
            session_id=session_id,
            trace_name=trace_name,
            version=BUILD_VERSION,
            tags=["provider:openai", "component:openai_campaign"],
            metadata={
                "provider": "openai",
                "component": "openai_campaign",
                "request_id": get_request_id(),
                "data_classification": config.DATA_CLASSIFICATION,
            },
        )
    except Exception:
        return nullcontext()


def _safe_update(observation: Any | None, **kwargs: Any) -> None:
    if observation is None:
        return
    try:
        observation.update(**kwargs)
    except Exception as exc:
        print("[openai_campaign] Langfuse update failed:", str(exc)[:300])


def _safe_end(observation: Any | None) -> None:
    if observation is None:
        return
    try:
        observation.end()
    except Exception as exc:
        print("[openai_campaign] Langfuse end failed:", str(exc)[:300])


async def _safe_flush(client: Any | None) -> None:
    if client is None:
        return
    try:
        await asyncio.to_thread(client.flush)
    except Exception as exc:
        print("[openai_campaign] Langfuse flush failed:", str(exc)[:300])


@asynccontextmanager
async def trace_openai_turn(
    *,
    session_id: str,
    message: str,
    step: int,
    workspace: dict | None,
):
    """Create one root trace for a web OpenAI campaign turn."""
    client = _get_langfuse()
    if client is None:
        yield None
        return

    attributes = _attribute_context(session_id, "openai_campaign_turn")
    root = None
    attributes_entered = False
    try:
        attributes.__enter__()
        attributes_entered = True
        root = client.start_observation(
            as_type="agent",
            name="openai_campaign_turn",
            input={
                "message": message,
                "step": step,
                "workspace": _jsonable(workspace or {}),
            },
            metadata={
                "provider": "openai",
                "model": config.OPENAI_CAMPAIGN_MODEL,
                "step": step,
                "request_id": get_request_id(),
            },
            version=BUILD_VERSION,
        )
    except Exception as exc:
        print("[openai_campaign] Langfuse turn start failed:", str(exc)[:300])
        if attributes_entered:
            try:
                attributes.__exit__(None, None, None)
            except Exception:
                pass
        yield None
        return

    token = _current_turn.set(root)
    try:
        yield root
    except BaseException as exc:
        _safe_update(
            root,
            level="ERROR",
            status_message=str(exc)[:500],
            output={"error": type(exc).__name__, "message": str(exc)[:1000]},
        )
        raise
    finally:
        _current_turn.reset(token)
        _safe_end(root)
        if attributes_entered:
            try:
                attributes.__exit__(None, None, None)
            except Exception as exc:
                print(
                    "[openai_campaign] Langfuse attributes end failed:",
                    str(exc)[:300],
                )
        await _safe_flush(client)


def update_turn_output(observation: Any | None, response: Any) -> None:
    """Attach the final user-visible response to the root turn trace."""
    _safe_update(observation, output=_jsonable(response))


async def trace_responses_call(
    *,
    name: str,
    session_id: str,
    model: str,
    request: dict,
    call: Callable[[], Awaitable[T]],
    metadata: dict | None = None,
    model_parameters: dict | None = None,
) -> T:
    """Run one Responses API call and capture its complete observable I/O."""
    client = _get_langfuse()
    if client is None:
        return await call()

    parent = _current_turn.get()
    attributes = None
    attributes_entered = False
    observation = None
    started = time.perf_counter()
    try:
        if parent is None:
            attributes = _attribute_context(session_id, name)
            attributes.__enter__()
            attributes_entered = True
        start = parent.start_observation if parent is not None else client.start_observation
        observation = start(
            as_type="generation",
            name=name,
            model=model,
            input=_jsonable(request),
            metadata={
                "provider": "openai",
                "request_id": get_request_id(),
                **(metadata or {}),
            },
            model_parameters=_jsonable(model_parameters or {}),
            version=BUILD_VERSION,
        )
    except Exception as exc:
        print("[openai_campaign] Langfuse generation start failed:", str(exc)[:300])
        if attributes_entered and attributes is not None:
            try:
                attributes.__exit__(None, None, None)
            except Exception:
                pass
        return await call()

    try:
        response = await call()
    except BaseException as exc:
        _safe_update(
            observation,
            level="ERROR",
            status_message=str(exc)[:500],
            output={"error": type(exc).__name__, "message": str(exc)[:1000]},
            metadata={
                "provider": "openai",
                "request_id": get_request_id(),
                "duration_ms": int((time.perf_counter() - started) * 1000),
                **(metadata or {}),
            },
        )
        raise
    else:
        _safe_update(
            observation,
            output=_response_output(response),
            usage_details=response_usage(response),
            metadata={
                "provider": "openai",
                "request_id": get_request_id(),
                "response_id": getattr(response, "id", None),
                "duration_ms": int((time.perf_counter() - started) * 1000),
                **(metadata or {}),
            },
        )
        return response
    finally:
        _safe_end(observation)
        if attributes_entered and attributes is not None:
            try:
                attributes.__exit__(None, None, None)
            except Exception:
                pass
        if parent is None:
            await _safe_flush(client)


async def trace_tool_call(
    *,
    session_id: str,
    name: str,
    arguments: dict,
    call: Callable[[], Awaitable[T]],
) -> T:
    """Record a server-owned tool execution as a sibling of model calls."""
    client = _get_langfuse()
    parent = _current_turn.get()
    if client is None or parent is None:
        return await call()
    observation = None
    started = time.perf_counter()
    try:
        observation = parent.start_observation(
            as_type="tool",
            name=f"openai.tool.{name}",
            input=_jsonable(arguments),
            metadata={"request_id": get_request_id(), "provider": "server"},
            version=BUILD_VERSION,
        )
    except Exception as exc:
        print("[openai_campaign] Langfuse tool start failed:", str(exc)[:300])
        return await call()

    try:
        result = await call()
    except BaseException as exc:
        _safe_update(
            observation,
            level="ERROR",
            status_message=str(exc)[:500],
            output={"error": type(exc).__name__, "message": str(exc)[:1000]},
        )
        raise
    else:
        _safe_update(
            observation,
            output=_jsonable(result),
            metadata={
                "request_id": get_request_id(),
                "provider": "server",
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return result
    finally:
        _safe_end(observation)


def reset_for_test() -> None:
    global _langfuse, _langfuse_initialized
    _langfuse = None
    _langfuse_initialized = False
