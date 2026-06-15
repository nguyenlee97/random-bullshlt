"""
LLM wrapper — OpenAI SDK configured for GreenNode MaaS (minimax-m2.5).
Provides: chat_completion(), simple_generate(), parse_json_response(), sanitize_response()
"""
import json
import re
from openai import OpenAI
from config import config

# Sync client (FastAPI runs async but openai sync client is fine with asyncio)
_client = OpenAI(
    api_key=config.AI_PLATFORM_API_KEY,
    base_url=config.LLM_BASE_URL,
)

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
    kwargs = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return _client.chat.completions.create(**kwargs)


def force_text_completion(messages: list[dict], tools: list[dict] | None = None) -> object:
    """
    Like chat_completion but forces tool_choice='none' so the model MUST return text.
    Use as fallback when the normal call returns empty/None content.
    """
    kwargs = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "none"   # Force text — no tool calls allowed
    return _client.chat.completions.create(**kwargs)



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
