"""
LLM wrapper — OpenAI SDK configured for GreenNode MaaS (minimax-m2.5).
Provides: chat_completion(), simple_generate(), parse_json_response(), sanitize_response()
"""
import json
import re
import time as _time
from openai import OpenAI
from config import config

# Sync client (FastAPI runs async but openai sync client is fine with asyncio)
_client = OpenAI(
    api_key=config.AI_PLATFORM_API_KEY,
    base_url=config.LLM_BASE_URL,
)

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
        content = m.get("content") or ""
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
            args_preview = tc.function.arguments[:500] if tc.function.arguments else ""
            print(f"\033[32m  TOOL_CALL: {tc.function.name}({args_preview})\033[0m", flush=True)
    if content:
        preview = content if len(content) <= 3000 else content[:3000] + "\n…[truncated]"
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
    resp = _client.chat.completions.create(**kwargs)
    dur = int((_time.time() - t0) * 1000)
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
    resp = _client.chat.completions.create(**kwargs)
    dur = int((_time.time() - t0) * 1000)
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
