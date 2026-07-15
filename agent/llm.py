"""
LLM wrapper — OpenAI SDK configured for GreenNode MaaS (minimax-m2.5).
Provides: chat_completion(), simple_generate(), parse_json_response(), sanitize_response()
"""
import json
import os
import re
import time as _time
from config import config
from openai import OpenAI

from metrics import LLM_CALLS, LLM_PROVIDER_EVENTS, LLM_TOKENS, SESSION_COST  # noqa: E402
from provider_resilience import CircuitBreaker, execute_with_fallback
from security import redact_langfuse, redact_pii, redact_text
from request_context import get_request_id

# ── Langfuse tracing (Phase 0 B3) ─────────────────────────────────────────────
# NOTE: The langfuse.openai drop-in wrapper only works for the standard OpenAI
# endpoint. Since we use a custom base_url (GreenNode MaaS), it silently falls
# back to plain OpenAI and produces no traces.
# Fix: use explicit langfuse_context to manually record each LLM call — this
# approach works with ANY OpenAI-compatible provider.
_langfuse = None
if os.getenv("LANGFUSE_PUBLIC_KEY"):
    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            mask=redact_langfuse,
        )  # picks up LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST
        # Keep startup output ASCII-safe: Windows cp1252 terminals can raise on
        # the arrow character, which used to be caught as a Langfuse init error.
        print("[llm] Langfuse tracing enabled ->", os.getenv("LANGFUSE_HOST"))
    except Exception as _lf_err:
        print(f"[llm] Langfuse init failed, tracing disabled: {_lf_err}")

# Sync client (FastAPI runs async but openai sync client is fine with asyncio)
_client = OpenAI(
    api_key=config.AI_PLATFORM_API_KEY,
    base_url=config.LLM_BASE_URL,
    timeout=config.LLM_TIMEOUT_SECONDS,
    max_retries=config.LLM_MAX_RETRIES,
)
_primary_breaker = CircuitBreaker(
    config.LLM_CIRCUIT_FAILURE_THRESHOLD,
    config.LLM_CIRCUIT_COOLDOWN_SECONDS,
)


def _fallback_is_allowed() -> bool:
    return bool(
        config.ALLOW_OFFSHORE_LLM_FALLBACK
        and config.DATA_CLASSIFICATION in config.LLM_FALLBACK_ALLOWED_CLASSIFICATIONS
        and config.LLM_FALLBACK_BASE_URL
        and config.LLM_FALLBACK_API_KEY
        and config.LLM_FALLBACK_MODEL
    )


_fallback_client = (
    OpenAI(
        api_key=config.LLM_FALLBACK_API_KEY,
        base_url=config.LLM_FALLBACK_BASE_URL,
        timeout=config.LLM_TIMEOUT_SECONDS,
        max_retries=config.LLM_MAX_RETRIES,
    )
    if _fallback_is_allowed()
    else None
)


def _kwargs_for_model(kwargs: dict, model: str) -> dict:
    """Adapt common generation controls for reasoning-model endpoints."""
    adapted = dict(kwargs)
    adapted["model"] = model
    normalized = model.lower()
    if normalized.startswith(("gpt-5", "o1", "o3", "o4")):
        if "max_tokens" in adapted:
            adapted["max_completion_tokens"] = adapted.pop("max_tokens")
        adapted.pop("temperature", None)
    return adapted


def _create_completion(kwargs: dict):
    """Return (response, actual_model, actual_base_url, provider_route)."""
    fallback = None
    if _fallback_client is not None:
        fallback_kwargs = _kwargs_for_model(kwargs, config.LLM_FALLBACK_MODEL)
        fallback = lambda: _fallback_client.chat.completions.create(**fallback_kwargs)
    try:
        response, route = execute_with_fallback(
            lambda: _client.chat.completions.create(**kwargs),
            _primary_breaker,
            fallback,
        )
    except Exception:
        LLM_PROVIDER_EVENTS.labels(provider="primary", outcome="error").inc()
        raise
    if route == "fallback":
        LLM_PROVIDER_EVENTS.labels(provider="primary", outcome="bypassed").inc()
        LLM_PROVIDER_EVENTS.labels(provider="fallback", outcome="ok").inc()
        return (
            response,
            config.LLM_FALLBACK_MODEL,
            config.LLM_FALLBACK_BASE_URL,
            route,
        )
    LLM_PROVIDER_EVENTS.labels(provider="primary", outcome="ok").inc()
    return response, config.LLM_MODEL, config.LLM_BASE_URL, route


def _trace_to_langfuse(
    handler: str,
    messages: list[dict],
    resp,
    duration_ms: int,
    model: str,
    base_url: str,
    provider_route: str,
) -> None:
    """Push one LLM call as an independent Langfuse generation (v4 API). No-op if not configured.

    Uses start_observation() + .end() (NOT start_as_current_observation) so that
    each LLM call gets its own trace record in Langfuse, rather than nesting all
    calls from one HTTP request under a single shared OTel context/trace.
    """
    if _langfuse is None:
        return
    try:
        usage = getattr(resp, "usage", None)
        msg = resp.choices[0].message
        output = msg.content or ""
        if msg.tool_calls:
            output = str([{"name": tc.function.name, "args": tc.function.arguments} for tc in msg.tool_calls])
        obs = _langfuse.start_observation(
            as_type="generation",
            name=handler,
            model=model,
            input=redact_pii(messages),
            output=redact_text(output),
            usage_details={
                "input": getattr(usage, "prompt_tokens", None),
                "output": getattr(usage, "completion_tokens", None),
                "total": getattr(usage, "total_tokens", None),
            } if usage else None,
            metadata={
                "duration_ms": duration_ms,
                "base_url": base_url,
                "provider_route": provider_route,
                "data_classification": config.DATA_CLASSIFICATION,
                "request_id": get_request_id(),
            },
        )
        obs.end()
        _langfuse.flush()
    except Exception as _e:
        print(f"[llm] Langfuse trace push failed: {_e}")


def _record_metrics(resp, duration_s: float, handler: str, model: str) -> None:
    """Prometheus counters for every LLM call (Phase 0 B4)."""
    try:
        content = resp.choices[0].message.content or ""
        outcome = "ok" if (content or resp.choices[0].message.tool_calls) else "empty"
        LLM_CALLS.labels(model=model, handler=handler, outcome=outcome).inc()
        SESSION_COST.observe(duration_s)
        if getattr(resp, "usage", None):
            LLM_TOKENS.labels(model=model, direction="prompt").inc(
                resp.usage.prompt_tokens or 0)
            LLM_TOKENS.labels(model=model, direction="completion").inc(
                resp.usage.completion_tokens or 0)
    except Exception:
        pass  # metrics must never break the request path

# ── Debug printer (stdout only, controlled by AGENT_DEBUG env var) ────────────
_DBG_ON = config.AGENT_DEBUG
_SEP = "=" * 80

def _dbg_input(messages: list[dict], call_id: str) -> None:
    if not _DBG_ON:
        return
    print(f"\n\033[36m{_SEP}\033[0m", flush=True)
    print(f"\033[36m[LLM_INPUT] call_id={call_id}  messages={len(messages)}\033[0m", flush=True)
    for i, m in enumerate(messages):
        role = m.get("role", "?")
        content = redact_text(m.get("content") or "")
        tc = m.get("tool_calls")
        if tc:
            print(f"\033[36m  [{i}] {role}: <tool_calls: {[t['function']['name'] for t in tc]}>\033[0m", flush=True)
        else:
            # Print full content, but cap at 3000 chars to avoid flooding
            preview = content if len(content) <= 3000 else content[:3000] + "\n…[truncated]"
            print(f"\033[36m  [{i}] {role}:\033[0m\n{preview}", flush=True)
    print(f"\033[36m{_SEP}\033[0m\n", flush=True)

def _dbg_output(content: str, tool_calls: list, call_id: str, duration_ms: int) -> None:
    if not _DBG_ON:
        return
    print(f"\n\033[32m{_SEP}\033[0m", flush=True)
    print(f"\033[32m[LLM_OUTPUT] call_id={call_id}  duration={duration_ms}ms\033[0m", flush=True)
    if tool_calls:
        for tc in tool_calls:
            args_preview = redact_text(tc.function.arguments[:500]) if tc.function.arguments else ""
            print(f"\033[32m  TOOL_CALL: {tc.function.name}({args_preview})\033[0m", flush=True)
    if content:
        safe_content = redact_text(content)
        preview = safe_content if len(safe_content) <= 3000 else safe_content[:3000] + "\n…[truncated]"
        print(f"\033[32m  CONTENT:\033[0m\n{preview}", flush=True)
    print(f"\033[32m{_SEP}\033[0m\n", flush=True)

_call_counter = 0
def _next_call_id() -> str:
    global _call_counter
    _call_counter += 1
    return f"llm_{_call_counter:04d}"


# ── Response sanitizers ───────────────────────────────────────────────────────
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_TOOL_XML_RE = re.compile(
    r"</?(?:invoke|minimax:tool_call|parameter)[^>]*>.*?(?:</(?:invoke|minimax:tool_call)>|$)",
    re.DOTALL | re.IGNORECASE,
)
_ORPHAN_TAG_RE = re.compile(
    r"</?(think|invoke|minimax:tool_call|parameter)[^>]*>",
    re.IGNORECASE,
)


def sanitize_response(text: str) -> str:
    """Strip internal reasoning tags and leaked tool XML from LLM output."""
    if not text:
        return ""
    text = _THINK_RE.sub("", text)
    text = _TOOL_XML_RE.sub("", text)
    text = _ORPHAN_TAG_RE.sub("", text)
    return text.strip()


def chat_completion(messages: list[dict], tools: list[dict] | None = None) -> object:
    """
    Raw OpenAI chat completion call.
    Returns the full response object (caller accesses .choices[0].message).
    """
    call_id = _next_call_id()
    _dbg_input(messages, call_id)
    kwargs = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    t0 = _time.time()
    resp, model, base_url, route = _create_completion(kwargs)
    dur = int((_time.time() - t0) * 1000)
    _record_metrics(resp, dur / 1000, handler="chat_completion", model=model)
    _trace_to_langfuse(
        "chat_completion", messages, resp, dur, model, base_url, route
    )
    msg = resp.choices[0].message
    _dbg_output(msg.content or "", msg.tool_calls or [], call_id, dur)
    return resp


def force_text_completion(messages: list[dict], tools: list[dict] | None = None) -> object:
    """
    Like chat_completion but forces tool_choice='none' so the model MUST return text.
    Use as fallback when the normal call returns empty/None content.
    """
    call_id = _next_call_id()
    _dbg_input(messages, call_id)
    kwargs = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "none"   # Force text — no tool calls allowed
    t0 = _time.time()
    resp, model, base_url, route = _create_completion(kwargs)
    dur = int((_time.time() - t0) * 1000)
    _record_metrics(resp, dur / 1000, handler="force_text", model=model)
    _trace_to_langfuse(
        "force_text_completion", messages, resp, dur, model, base_url, route
    )
    msg = resp.choices[0].message
    _dbg_output(msg.content or "", [], call_id, dur)
    return resp



def simple_generate(system: str, user: str) -> str:
    """
    Simple one-shot generation: system + user → assistant text.
    Used by brief/audience handlers for validation and reasoning.
    Auto-sanitizes output to strip <think> and leaked XML tags.
    """
    resp = chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    return sanitize_response(resp.choices[0].message.content or "")


def parse_json_response(raw: str) -> dict:
    """
    Extract JSON from LLM response, handling markdown code fences.
    Returns empty dict on parse failure (handlers should use fallback).
    """
    # Strip ```json ... ``` fences
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    # Find first { ... } block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}
