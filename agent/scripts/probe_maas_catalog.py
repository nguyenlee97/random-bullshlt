"""
MaaS catalog probe — answers the Phase-1 day-1 questions:
  1. What models does GreenNode MaaS actually expose?
  2. Which support tool calling? json_schema structured output? vision? embeddings?
  3. Is there a reranker endpoint, and what API shape does it use?

Run from agent/ (uses your .env):   python scripts/probe_maas_catalog.py
Writes results to ../docs/maas-catalog.md — several production-plan decisions
key off that file (critic model, fallback model, reranker integration).

Read-only + tiny prompts: costs a few hundred tokens total.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from config import config  # noqa: E402

HEADERS = {"Authorization": f"Bearer {config.AI_PLATFORM_API_KEY}"}
BASE = config.LLM_BASE_URL.rstrip("/")

TINY_TOOL = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}]

JSON_SCHEMA_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "pick",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"answer": {"type": "string"}, "confidence": {"type": "integer"}},
            "required": ["answer", "confidence"],
            "additionalProperties": False,
        },
    },
}


async def list_models(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(f"{BASE}/models", headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    return [m["id"] for m in data.get("data", [])]


async def probe_chat(client: httpx.AsyncClient, model: str) -> dict:
    """Probe one model: basic chat, tool calling, json_schema mode."""
    out = {"model": model, "chat": None, "tools": None, "json_schema": None, "error": None}

    async def post(payload):
        return await client.post(f"{BASE}/chat/completions", headers=HEADERS, json=payload, timeout=45)

    base_msg = [{"role": "user", "content": "Reply with the single word: ok"}]
    try:
        r = await post({"model": model, "messages": base_msg, "max_tokens": 300})
        out["chat"] = r.status_code == 200
        if not out["chat"]:
            out["error"] = f"chat {r.status_code}: {r.text[:150]}"
            return out
    except Exception as e:
        out["error"] = f"chat: {e}"
        return out

    # tool calling
    try:
        r = await post({
            "model": model, "max_tokens": 300,
            "messages": [{"role": "user", "content": "What's the weather in Hanoi? Use the tool."}],
            "tools": TINY_TOOL,
        })
        if r.status_code == 200:
            msg = r.json()["choices"][0]["message"]
            out["tools"] = bool(msg.get("tool_calls"))
        else:
            out["tools"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["tools"] = f"err: {str(e)[:80]}"

    # json_schema structured output
    try:
        r = await post({
            "model": model, "max_tokens": 300,
            "messages": [{"role": "user", "content": "Pick a color. Respond as JSON."}],
            "response_format": JSON_SCHEMA_FORMAT,
        })
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"].get("content") or ""
            try:
                parsed = json.loads(content)
                out["json_schema"] = "answer" in parsed and "confidence" in parsed
            except json.JSONDecodeError:
                out["json_schema"] = f"200 but non-JSON: {content[:60]!r}"
        else:
            out["json_schema"] = f"HTTP {r.status_code}"
    except Exception as e:
        out["json_schema"] = f"err: {str(e)[:80]}"

    return out


async def probe_extras(client: httpx.AsyncClient, models: list[str]) -> dict:
    """Embeddings + reranker endpoint shapes."""
    extras = {"embeddings": {}, "rerank": {}}
    emb_candidates = [m for m in models if any(k in m.lower() for k in ("embed", "bge", "e5", "gte"))]
    rr_candidates = [m for m in models if any(k in m.lower() for k in ("rerank", "reranker"))]

    for m in emb_candidates or models[:0]:
        try:
            r = await client.post(f"{BASE}/embeddings", headers=HEADERS,
                                  json={"model": m, "input": ["xin chào"]}, timeout=30)
            dim = len(r.json()["data"][0]["embedding"]) if r.status_code == 200 else None
            extras["embeddings"][m] = f"OK dim={dim}" if dim else f"HTTP {r.status_code}"
        except Exception as e:
            extras["embeddings"][m] = f"err: {str(e)[:80]}"

    # Try common rerank API shapes (Jina/Cohere-style /rerank, TEI-style)
    rerank_payload = {
        "query": "nước giải khát cho giới trẻ",
        "documents": ["Segment: Gen Z yêu thích đồ uống", "Segment: Người cao tuổi tập dưỡng sinh"],
    }
    for m in rr_candidates:
        for path in ("/rerank", "/v1/rerank", "/reranking"):
            url = BASE.replace("/v1", "") + path if path.startswith("/v1") else f"{BASE}{path}"
            try:
                r = await client.post(url, headers=HEADERS, json={"model": m, **rerank_payload}, timeout=30)
                if r.status_code == 200:
                    extras["rerank"][m] = f"OK via {path}: {str(r.json())[:120]}"
                    break
                extras["rerank"][m] = f"{path} → HTTP {r.status_code}"
            except Exception as e:
                extras["rerank"][m] = f"{path} → err: {str(e)[:60]}"
    return extras


def to_markdown(results: list[dict], extras: dict, models: list[str]) -> str:
    lines = [
        "# GreenNode MaaS Catalog — probed capabilities",
        "",
        f"> Generated by `agent/scripts/probe_maas_catalog.py`. Base URL: `{BASE}`",
        "> Re-run after any provider announcement. Production-plan decisions that key",
        "> off this file: CRITIC_MODEL / JUDGE_MODEL (02, 07), fallback secondary (06),",
        "> reranker integration (03), VLM availability (04).",
        "",
        "## Chat models",
        "",
        "| Model | Chat | Tool calling | json_schema |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| `{r['model']}` | {r['chat']} | {r['tools']} | {r['json_schema']} |")
    lines += ["", "## Embeddings", ""]
    lines += [f"- `{m}`: {v}" for m, v in extras["embeddings"].items()] or ["- (none found)"]
    lines += ["", "## Reranker", ""]
    lines += [f"- `{m}`: {v}" for m, v in extras["rerank"].items()] or ["- (none found)"]
    lines += ["", "## Full model list", ""]
    lines += [f"- `{m}`" for m in models]
    return "\n".join(lines) + "\n"


async def main():
    if not config.AI_PLATFORM_API_KEY:
        sys.exit("AI_PLATFORM_API_KEY missing — run from agent/ with .env present")
    async with httpx.AsyncClient() as client:
        models = await list_models(client)
        print(f"Found {len(models)} models: {models}\n")
        chat_models = [m for m in models
                       if not any(k in m.lower() for k in ("embed", "rerank", "whisper", "tts", "image"))]
        results = [await probe_chat(client, m) for m in chat_models]
        for r in results:
            print(r)
        extras = await probe_extras(client, models)
        print(extras)

    out_path = Path(__file__).resolve().parent.parent.parent / "docs" / "maas-catalog.md"
    out_path.write_text(to_markdown(results, extras, models), encoding="utf-8")
    print(f"\n✅ Wrote {out_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
