"""
Creative-intel service: analyze files, store verdicts, serve status.

Verdict logic (production-plan/04 §1):
    auto_approved  — deterministic pass ok AND (no VLM configured OR VLM ok:
                     confidence ≥ threshold, no safety flag)
    needs_review   — any safety flag, low confidence, decode/fetch error,
                     VLM failure (fail-CLOSED ⛔), or video (no PIL support)
Results in Mongo `creative_intel` keyed by (session_id, url-hash); in-memory
fallback mirrors session.py behavior. Jobs run as fire-and-forget asyncio
tasks — at demo scale a queue broker would be overkill (ADR 018).
"""
import asyncio
import hashlib

import httpx

from config import config
from agent_logger import alog

_mem: dict[str, dict] = {}


def _key(session_id: str, url: str) -> str:
    return f"{session_id}_{hashlib.sha1(url.encode()).hexdigest()[:12]}"


async def _col():
    from session import _ensure_mongo
    if await _ensure_mongo():
        import session as _s
        return _s._client[config.MONGODB_DB]["creative_intel"]
    return None


async def _save(doc: dict) -> None:
    col = await _col()
    if col is not None:
        await col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    else:
        _mem[doc["_id"]] = doc


async def get_intel(session_id: str) -> list[dict]:
    col = await _col()
    if col is not None:
        return [d async for d in col.find({"session_id": session_id}, {"_id": 0})]
    return [ {k: v for k, v in d.items() if k != "_id"}
             for d in _mem.values() if d.get("session_id") == session_id]


def _normalize_url(url: str) -> str:
    """Browser-facing URLs (localhost:3000) aren't reachable from inside the
    agent container — rewrite to the container-internal BACKEND_URL."""
    for host in ("http://localhost:3000", "http://127.0.0.1:3000"):
        if url.startswith(host):
            return config.BACKEND_URL + url[len(host):]
    return url


async def _analyze_one(session_id: str, file: dict) -> None:
    url, name = _normalize_url(file.get("url", "")), file.get("name", "")
    doc = {"_id": _key(session_id, url), "session_id": session_id,
           "url": url, "name": name, "status": "analyzing"}
    await _save(doc)

    # stage 1 — deterministic (PIL on real bytes)
    from creative_intel.analyzer import analyze_url
    det = await analyze_url(url, name=name)
    doc["deterministic"] = det

    reasons: list[str] = []
    if det.get("fetch_error") or det.get("decode_error"):
        reasons.append(det.get("fetch_error") or f"không decode được ({det.get('decode_error')})")
    elif not det.get("min_size_ok", False):
        reasons.append(f"kích thước nhỏ ({det.get('width')}×{det.get('height')} < 300px)")

    # stage 2 — VLM semantics (only if configured; fail-CLOSED on error ⛔)
    if config.VLM_MODEL and not det.get("fetch_error"):
        try:
            resp = await httpx.AsyncClient(timeout=20).get(url)
            from creative_intel.vlm import analyze_image_sync
            vlm = await asyncio.to_thread(analyze_image_sync, resp.content)
            doc["vlm"] = vlm.model_dump()
            flags = [k for k, v in vlm.safety.model_dump().items() if v]
            if flags:
                reasons.append(f"cờ an toàn: {', '.join(flags)}")
            if vlm.confidence < config.VLM_CONFIDENCE_THRESHOLD:
                reasons.append(f"VLM confidence thấp ({vlm.confidence:.2f})")
        except Exception as e:
            reasons.append(f"VLM lỗi — cần review thủ công ({str(e)[:60]})")

    doc["status"] = "needs_review" if reasons else "auto_approved"
    doc["review_reasons"] = reasons
    await _save(doc)
    await alog(session_id, "info", {"creative_intel": doc["status"], "file": name,
                                    "reasons": reasons[:3]})


def enqueue_analysis(session_id: str, files: list[dict]) -> int:
    """Fire-and-forget per file with a URL. Returns number enqueued."""
    n = 0
    for f in files or []:
        if f.get("url"):
            asyncio.get_event_loop().create_task(_analyze_one(session_id, f))
            n += 1
    return n
