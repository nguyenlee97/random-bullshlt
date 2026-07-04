"""
structured() — single entry point for schema-constrained generation.

Strategy per ADR 005 (spike verdict 2026-07-04): C = function-calling-as-schema
won 10/10 on MiniMax; json_schema mode (A) is ignored by the GreenNode endpoint
(0/10) and json_object (B) leaks trailing prose (2/10). Default C.

Two clients:
  role="generator" → MiniMax @ GreenNode  (plans, anything user-facing)
  role="critic"    → CRITIC_MODEL @ CRITIC_BASE_URL (gpt-5.4-mini @ OpenAI —
                     different family+provider than the generator ⛔)

OpenAI GPT-5-family quirks handled adaptively (mirrors eval/judge.py): rejects
max_tokens (wants max_completion_tokens) and may lock temperature.

On ValidationError: one retry with the error appended, then StructuredOutputError.
"""
import json
import os
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from llm import _client as _generator_client
from config import config

T = TypeVar("T", bound=BaseModel)

STRATEGY = os.getenv("STRUCTURED_OUTPUT_STRATEGY", "C").upper()

_critic_client = None


def _get_client(role: str):
    global _critic_client
    if role == "critic" and config.CRITIC_BASE_URL and config.CRITIC_MODEL:
        if _critic_client is None:
            from openai import OpenAI
            _critic_client = OpenAI(base_url=config.CRITIC_BASE_URL,
                                    api_key=config.CRITIC_API_KEY)
        return _critic_client, config.CRITIC_MODEL
    return _generator_client, config.LLM_MODEL


class StructuredOutputError(Exception):
    pass


def _extract_json(text: str) -> str:
    for s in ("<think>", "</think>", "```json", "```"):
        text = text.replace(s, "")
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


def structured(
    messages: list[dict],
    schema: type[T],
    schema_name: str,
    role: str = "generator",
    max_tokens: int = 2000,
) -> tuple[T, int]:
    """Returns (validated_object, total_tokens_used). Raises StructuredOutputError."""
    client, model = _get_client(role)
    tokens = 0
    msgs = list(messages)
    # param names adapt per endpoint (GPT-5 family wants max_completion_tokens)
    params: dict = {"temperature": 0.1, "max_tokens": max_tokens}

    for attempt in (1, 2):
        kwargs: dict = {"model": model, **params}
        if STRATEGY == "A":
            schema_json = schema.model_json_schema()
            kwargs["response_format"] = {"type": "json_schema", "json_schema": {
                "name": schema_name, "strict": True, "schema": schema_json}}
        elif STRATEGY == "B":
            hint = json.dumps(schema.model_json_schema(), ensure_ascii=False)
            msgs = msgs[:-1] + [{
                "role": msgs[-1]["role"],
                "content": msgs[-1]["content"] + f"\n\nTrả lời DUY NHẤT bằng JSON theo schema:\n{hint}",
            }]
            kwargs["response_format"] = {"type": "json_object"}
        else:  # C — function-calling-as-schema (ADR 005 winner)
            kwargs["tools"] = [{"type": "function", "function": {
                "name": f"submit_{schema_name}",
                "description": f"Submit the {schema_name}",
                "parameters": schema.model_json_schema(),
            }}]
            kwargs["tool_choice"] = {"type": "function",
                                     "function": {"name": f"submit_{schema_name}"}}

        # up to 2 param adaptations for OpenAI GPT-5-family endpoints
        for _ in range(3):
            try:
                resp = client.chat.completions.create(messages=msgs, **kwargs)
                break
            except Exception as e:
                m = str(e)
                if "max_completion_tokens" in m and "max_tokens" in params:
                    params["max_completion_tokens"] = params.pop("max_tokens")
                    kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                    continue
                if "temperature" in m and "temperature" in params:
                    params.pop("temperature"); kwargs.pop("temperature", None)
                    continue
                raise StructuredOutputError(f"{schema_name} LLM call failed: {m[:200]}") from e
        else:
            raise StructuredOutputError(f"{schema_name}: param adaptation exhausted")

        if getattr(resp, "usage", None):
            tokens += resp.usage.total_tokens or 0
        m = resp.choices[0].message
        raw = (m.tool_calls[0].function.arguments
               if STRATEGY == "C" and m.tool_calls else (m.content or ""))

        try:
            return schema.model_validate_json(_extract_json(raw)), tokens
        except ValidationError as e:
            if attempt == 2:
                raise StructuredOutputError(f"{schema_name} invalid after retry: {e}") from e
            msgs = msgs + [
                {"role": "assistant", "content": raw[:1500]},
                {"role": "user",
                 "content": f"Output không đúng schema. Lỗi: {str(e)[:400]}. Trả lời lại đúng schema."},
            ]

    raise StructuredOutputError("unreachable")
