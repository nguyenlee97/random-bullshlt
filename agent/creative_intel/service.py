"""Durable creative-analysis jobs, verdicts, and human overrides.

The Mongo document is both the job record and the immutable analysis verdict.
Queued jobs are claimed by one in-process worker. Jobs left in ``analyzing``
after a process restart are returned to the queue, so analysis is recoverable
without introducing Redis/Celery at hackathon scale.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from agent_logger import alog
from config import config

TERMINAL_STATUSES = {"auto_approved", "needs_review"}
_mem: dict[str, dict] = {}
_worker_tasks: list[asyncio.Task] = []
_stop_event: asyncio.Event | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _key(session_id: str, url: str) -> str:
    return f"ci_{hashlib.sha256(f'{session_id}:{url}'.encode()).hexdigest()[:24]}"


def _fetch_url(url: str) -> str:
    """Translate a browser-local upload URL for container-to-container access."""
    for host in ("http://localhost:3000", "http://127.0.0.1:3000"):
        if url.startswith(host):
            return config.BACKEND_URL.rstrip("/") + url[len(host):]
    return url


def effective_status(doc: dict) -> str:
    override = doc.get("override") or {}
    if doc.get("status") == "needs_review" and override.get("approved"):
        return "approved_override"
    return doc.get("status", "queued")


def _public(doc: dict) -> dict:
    out = {k: v for k, v in doc.items() if k not in {"_id", "fetch_url"}}
    out["analysis_id"] = doc.get("_id") or doc.get("analysis_id")
    out["effective_status"] = effective_status(doc)
    return out


async def _col():
    from session import _ensure_mongo

    if await _ensure_mongo():
        import session as _s

        return _s._client[config.MONGODB_DB]["creative_intel_jobs"]
    return None


async def _get(analysis_id: str) -> dict | None:
    col = await _col()
    if col is not None:
        return await col.find_one({"_id": analysis_id})
    return _mem.get(analysis_id)


async def _save(doc: dict) -> None:
    col = await _col()
    if col is not None:
        await col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    else:
        _mem[doc["_id"]] = doc


async def get_intel(session_id: str) -> list[dict]:
    col = await _col()
    if col is not None:
        docs = await col.find({"session_id": session_id}).sort("created_at", 1).to_list(None)
    else:
        docs = [d for d in _mem.values() if d.get("session_id") == session_id]
        docs.sort(key=lambda d: d.get("created_at") or _now())
    return [_public(d) for d in docs]


async def get_intel_by_ids(session_id: str, analysis_ids: list[str]) -> dict[str, dict]:
    wanted = {value for value in analysis_ids if value}
    if not wanted:
        return {}
    col = await _col()
    if col is not None:
        docs = await col.find({"_id": {"$in": list(wanted)}, "session_id": session_id}).to_list(None)
    else:
        docs = [d for key, d in _mem.items() if key in wanted and d.get("session_id") == session_id]
    return {d["_id"]: _public(d) for d in docs}


async def enqueue_analysis(session_id: str, files: list[dict]) -> list[dict]:
    """Persist jobs before returning. Existing terminal verdicts are reused."""
    jobs: list[dict] = []
    for file in files or []:
        url = (file.get("url") or "").strip()
        if not url:
            continue
        analysis_id = _key(session_id, url)
        existing = await _get(analysis_id)
        if existing and existing.get("status") in TERMINAL_STATUSES:
            existing.update({
                "file_id": file.get("id", existing.get("file_id", "")),
                "format_id": file.get("formatId", existing.get("format_id", "")),
                "intended_format": file.get(
                    "intendedFormat", existing.get("intended_format", "")
                ),
                "updated_at": _now(),
            })
            await _save(existing)
            jobs.append(_public(existing))
            continue

        created_at = (existing or {}).get("created_at") or _now()
        doc = {
            **(existing or {}),
            "_id": analysis_id,
            "session_id": session_id,
            "file_id": file.get("id", ""),
            "name": file.get("name", ""),
            "mime_type": file.get("type", ""),
            "format_id": file.get("formatId", ""),
            "intended_format": file.get("intendedFormat", ""),
            "url": url,
            "fetch_url": _fetch_url(url),
            "status": "queued",
            "attempts": (existing or {}).get("attempts", 0),
            "created_at": created_at,
            "updated_at": _now(),
        }
        await _save(doc)
        jobs.append(_public(doc))
    return jobs


async def approve_override(
    session_id: str,
    analysis_id: str,
    reason: str,
    actor: str = "campaign_operator",
) -> dict:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Override reason must contain at least 5 characters")
    doc = await _get(analysis_id)
    if not doc or doc.get("session_id") != session_id:
        raise KeyError("Creative analysis not found")
    if doc.get("status") != "needs_review":
        raise ValueError("Only needs_review creatives can be overridden")
    doc["override"] = {
        "approved": True,
        "reason": reason,
        "actor": actor or "campaign_operator",
        "timestamp": _now(),
        "original_status": "needs_review",
        "original_reasons": list(doc.get("review_reasons") or []),
    }
    doc["updated_at"] = _now()
    await _save(doc)
    await alog(session_id, "creative_override", {
        "analysis_id": analysis_id,
        "actor": doc["override"]["actor"],
        "reason": reason,
    })
    return _public(doc)


async def _claim_job() -> dict | None:
    col = await _col()
    if col is not None:
        from pymongo import ReturnDocument

        return await col.find_one_and_update(
            {"status": "queued"},
            {
                "$set": {"status": "analyzing", "started_at": _now(), "updated_at": _now()},
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )

    queued = sorted(
        (d for d in _mem.values() if d.get("status") == "queued"),
        key=lambda d: d.get("created_at") or _now(),
    )
    if not queued:
        return None
    doc = queued[0]
    doc["status"] = "analyzing"
    doc["started_at"] = _now()
    doc["updated_at"] = _now()
    doc["attempts"] = doc.get("attempts", 0) + 1
    return dict(doc)


async def recover_stale_jobs(force: bool = False) -> int:
    cutoff = _now() - timedelta(seconds=config.CREATIVE_JOB_STALE_SECONDS)
    col = await _col()
    if col is not None:
        query = {"status": "analyzing"}
        if not force:
            query["started_at"] = {"$lt": cutoff}
        result = await col.update_many(
            query,
            {"$set": {"status": "queued", "recovered_at": _now(), "updated_at": _now()}},
        )
        return result.modified_count
    count = 0
    for doc in _mem.values():
        stale = (doc.get("started_at") or cutoff) <= cutoff
        if doc.get("status") == "analyzing" and (force or stale):
            doc.update(status="queued", recovered_at=_now(), updated_at=_now())
            count += 1
    return count


async def _analyze_job(doc: dict) -> dict[str, Any]:
    from creative_intel.analyzer import analyze_url

    url = doc.get("fetch_url") or _fetch_url(doc.get("url", ""))
    name = doc.get("name", "")
    deterministic = await analyze_url(
        url, name=name, mime_type=doc.get("mime_type", "")
    )
    reasons: list[str] = []

    if deterministic.get("fetch_error") or deterministic.get("decode_error"):
        reasons.append(
            deterministic.get("fetch_error")
            or f"Không đọc được tệp ({deterministic.get('decode_error')})"
        )
    elif not deterministic.get("min_size_ok", False):
        reasons.append(
            f"Kích thước nhỏ ({deterministic.get('width')}×{deterministic.get('height')}; "
            "tối thiểu 300×50px)"
        )

    is_video = deterministic.get("kind") == "video"
    if is_video and not deterministic.get("decode_error"):
        reasons.append(
            "Video đã trích xuất metadata nhưng cần người duyệt nội dung trước khi chạy"
        )

    result: dict[str, Any] = {"deterministic": deterministic}
    if (
        config.VLM_MODEL
        and not is_video
        and not deterministic.get("fetch_error")
        and not deterministic.get("decode_error")
    ):
        from metrics import VLM_CALLS, VLM_SECONDS

        started = asyncio.get_running_loop().time()
        try:
            async with httpx.AsyncClient(timeout=config.CREATIVE_ANALYSIS_TIMEOUT_SECONDS) as client:
                response = await client.get(url)
                response.raise_for_status()
            from creative_intel.vlm import analyze_image_sync
            from session import get_or_create_session

            session = await get_or_create_session(doc["session_id"])
            brief = session.get("form_state", {}).get("brief", {}) or {}
            vlm = await asyncio.to_thread(
                analyze_image_sync,
                response.content,
                doc.get("mime_type") or "image/png",
                brief,
            )
            result["vlm"] = vlm.model_dump()
            from creative_intel.policy import contains_prompt_injection

            flags = [flag for flag, value in vlm.safety.model_dump().items() if value]
            if flags:
                reasons.append(f"Cờ an toàn: {', '.join(flags)}")
            if contains_prompt_injection(vlm.ocr_text):
                reasons.append("Phát hiện câu lệnh đáng ngờ trong nội dung OCR")
            if vlm.confidence < config.VLM_CONFIDENCE_THRESHOLD:
                reasons.append(f"Độ tin cậy VLM thấp ({vlm.confidence:.2f})")
            if vlm.brief_match_score <= 2:
                reasons.append(f"Creative không khớp brief ({vlm.brief_match_score}/5)")
            VLM_CALLS.labels(model=config.VLM_MODEL, outcome="success").inc()
        except Exception as exc:
            VLM_CALLS.labels(model=config.VLM_MODEL, outcome="error").inc()
            reasons.append(f"VLM lỗi — cần duyệt thủ công ({str(exc)[:80]})")
        finally:
            VLM_SECONDS.labels(model=config.VLM_MODEL).observe(
                asyncio.get_running_loop().time() - started
            )

    result["review_reasons"] = reasons
    result["status"] = "needs_review" if reasons else "auto_approved"
    return result


async def process_next_job() -> bool:
    """Process one queued job. Public for deterministic worker tests."""
    doc = await _claim_job()
    if not doc:
        return False
    try:
        result = await _analyze_job(doc)
        doc.update(result)
    except Exception as exc:  # final fail-closed boundary
        doc.update(
            status="needs_review",
            review_reasons=[f"Lỗi pipeline — cần duyệt thủ công ({str(exc)[:80]})"],
        )
    doc["completed_at"] = _now()
    doc["updated_at"] = _now()
    await _save(doc)
    await alog(doc["session_id"], "creative_intel", {
        "analysis_id": doc["_id"],
        "status": doc["status"],
        "file": doc.get("name", ""),
        "reasons": (doc.get("review_reasons") or [])[:3],
    })
    return True


async def _worker_loop() -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        try:
            worked = await process_next_job()
            if worked:
                continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[creative-intel] worker error: {exc}")
        try:
            await asyncio.wait_for(
                _stop_event.wait(), timeout=config.CREATIVE_WORKER_POLL_SECONDS
            )
        except asyncio.TimeoutError:
            pass


async def start_worker() -> None:
    global _worker_tasks, _stop_event
    if any(not task.done() for task in _worker_tasks):
        return
    # One worker process owns this collection in the current deployment. After
    # a restart no previous process can still own an analyzing job, so recover
    # all of them immediately instead of waiting for the stale timeout.
    recovered = await recover_stale_jobs(force=True)
    _stop_event = asyncio.Event()
    concurrency = max(1, min(config.CREATIVE_WORKER_CONCURRENCY, 8))
    _worker_tasks = [
        asyncio.create_task(_worker_loop(), name=f"creative-intel-worker-{index + 1}")
        for index in range(concurrency)
    ]
    print(
        f"[creative-intel] workers started; concurrency={concurrency}; recovered={recovered}"
    )


def worker_running() -> bool:
    return bool(_worker_tasks) and all(not task.done() for task in _worker_tasks)


async def stop_worker() -> None:
    global _worker_tasks, _stop_event
    if _stop_event:
        _stop_event.set()
    if _worker_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*_worker_tasks, return_exceptions=True), timeout=2.0
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            for task in _worker_tasks:
                task.cancel()
    _worker_tasks = []
    _stop_event = None
