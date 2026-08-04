"""Read-only, redacted Langfuse data for the public observability showcase.

This module intentionally exposes a small presentation model rather than the
Langfuse API itself. Credentials remain server-side, sensitive values are
redacted, and a stale cache keeps the demo useful during a Cloud API timeout.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import re
import threading
import time
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ratelimit import limiter
from security import REDACTED, redact_pii


public_observability_router = APIRouter(tags=["public-observability"])

_TRACE_ID = re.compile(r"^[a-fA-F0-9]{32}$")
_CALLBACK = re.compile(r"^__campAdsObservability[0-9]{1,8}$")
_FRESH_SECONDS = 20.0
_STALE_SECONDS = 300.0
_MAX_STRING = 24_000
_MAX_LIST = 250
_MAX_DEPTH = 12
_OBSERVATION_FIELDS = (
    "core,basic,time,io,metadata,model,usage,prompt,metrics,trace_context"
)
_OBSERVATION_TYPES = {
    "AGENT", "CHAIN", "EMBEDDING", "EVALUATOR", "EVENT", "GENERATION",
    "GUARDRAIL", "RETRIEVER", "SPAN", "TOOL",
}
_LEVELS = {"DEBUG", "DEFAULT", "WARNING", "ERROR"}
_SEARCH_FIELDS = {"name", "input", "output", "traceName"}

_client: Any | None = None
_client_initialized = False
_client_lock = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()

_DROP_KEYS = {
    "projectid",
    "project_id",
    "publickey",
    "public_key",
    "secretkey",
    "secret_key",
}
_DROP_METADATA_KEYS = {
    "resourceattributes.service.instance.id",
    "resourceattributes.telemetry.sdk.language",
    "resourceattributes.telemetry.sdk.name",
    "resourceattributes.telemetry.sdk.version",
    "scope.attributes.public_key",
    "service.instance.id",
    "telemetry.sdk.language",
    "telemetry.sdk.name",
    "telemetry.sdk.version",
}
_SENSITIVE_MARKERS = (
    "authorization",
    "password",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "cookie",
)


def _get_client() -> Any:
    """Create the read client lazily so missing credentials do not break boot."""
    global _client, _client_initialized
    if _client_initialized:
        if _client is None:
            raise RuntimeError("Langfuse is not configured")
        return _client
    with _client_lock:
        if not _client_initialized:
            _client_initialized = True
            if not (
                os.getenv("LANGFUSE_PUBLIC_KEY")
                and os.getenv("LANGFUSE_SECRET_KEY")
            ):
                _client = None
            else:
                from langfuse import Langfuse

                _client = Langfuse(timeout=12)
    if _client is None:
        raise RuntimeError("Langfuse is not configured")
    return _client


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if hasattr(value, "dict"):
        try:
            return value.dict(by_alias=True, exclude_none=True)
        except TypeError:
            return value.dict()
    return value


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    """Return JSON-safe public data with credentials, PII and extremes bounded."""
    if depth > _MAX_DEPTH:
        return "[TRUNCATED_DEPTH]"
    value = _dump(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        redacted = redact_pii(value)
        if len(redacted) > _MAX_STRING:
            return redacted[:_MAX_STRING] + "\n[TRUNCATED]"
        return redacted
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            dotted = key.lower()
            if normalized in _DROP_KEYS or dotted in _DROP_METADATA_KEYS:
                continue
            if any(marker in normalized for marker in _SENSITIVE_MARKERS):
                result[key] = REDACTED
            else:
                result[key] = _safe_value(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        result = [_safe_value(item, depth=depth + 1) for item in items[:_MAX_LIST]]
        if len(items) > _MAX_LIST:
            result.append(f"[TRUNCATED_{len(items) - _MAX_LIST}_ITEMS]")
        return result
    return _safe_value(str(value), depth=depth + 1)


def _pick(source: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in source:
            return source[key]
    return default


def _trace_summary(raw: Any) -> dict[str, Any]:
    item = _dump(raw) or {}
    safe_input = _safe_value(_pick(item, "input"))
    safe_output = _safe_value(_pick(item, "output"))
    observations = _pick(item, "observations", default=[]) or []
    return {
        "id": _pick(item, "id"),
        "timestamp": _pick(item, "timestamp", "createdAt", "created_at"),
        "name": _pick(item, "name", default="Unnamed trace"),
        "sessionId": _safe_value(_pick(item, "sessionId", "session_id")),
        "userId": _safe_value(_pick(item, "userId", "user_id")),
        "environment": _pick(item, "environment", default="default"),
        "tags": _safe_value(_pick(item, "tags", default=[])),
        "latency": _pick(item, "latency"),
        "totalCost": _pick(item, "totalCost", "total_cost"),
        "version": _pick(item, "version"),
        "release": _pick(item, "release"),
        "bookmarked": bool(_pick(item, "bookmarked", default=False)),
        "observationCount": len(observations),
        "input": safe_input,
        "output": safe_output,
    }


def _observation(raw: Any) -> dict[str, Any]:
    item = _dump(raw) or {}
    allowed = (
        "id", "traceId", "parentObservationId", "name", "type", "startTime",
        "endTime", "completionStartTime", "input", "output", "metadata",
        "model", "modelParameters", "usageDetails", "costDetails", "level",
        "statusMessage", "version", "environment", "latency", "totalCost",
        "isRootObservation", "providedModelName", "totalUsage", "inputUsage",
        "outputUsage", "timeToFirstToken", "traceName", "tags", "release",
        "promptName", "promptVersion", "bookmarked", "public", "sessionId",
        "userId", "createdAt", "updatedAt",
    )
    result = {key: _safe_value(item[key]) for key in allowed if key in item}
    # Older SDKs serialize these names in snake_case.
    for snake, camel in (
        ("trace_id", "traceId"),
        ("parent_observation_id", "parentObservationId"),
        ("start_time", "startTime"),
        ("end_time", "endTime"),
        ("completion_start_time", "completionStartTime"),
        ("model_parameters", "modelParameters"),
        ("usage_details", "usageDetails"),
        ("cost_details", "costDetails"),
        ("status_message", "statusMessage"),
        ("total_cost", "totalCost"),
        ("is_root_observation", "isRootObservation"),
        ("provided_model_name", "providedModelName"),
        ("total_usage", "totalUsage"),
        ("input_usage", "inputUsage"),
        ("output_usage", "outputUsage"),
        ("time_to_first_token", "timeToFirstToken"),
        ("trace_name", "traceName"),
    ):
        if camel not in result and snake in item:
            result[camel] = _safe_value(item[snake])
    return result


def _observation_filters(
    *,
    types: tuple[str, ...],
    environments: tuple[str, ...],
    level: str | None,
    root_only: bool | None,
    min_latency: float | None,
    cost_only: bool,
    search_field: str | None,
    search_value: str | None,
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    if types:
        filters.append({
            "type": "stringOptions", "column": "type",
            "operator": "any of", "value": list(types),
        })
    if environments:
        filters.append({
            "type": "stringOptions", "column": "environment",
            "operator": "any of", "value": list(environments),
        })
    if level:
        filters.append({
            "type": "string", "column": "level", "operator": "=", "value": level,
        })
    if root_only is not None:
        filters.append({
            "type": "boolean", "column": "isRootObservation",
            "operator": "=", "value": root_only,
        })
    if min_latency is not None:
        filters.append({
            "type": "number", "column": "latency",
            "operator": ">", "value": min_latency,
        })
    if cost_only:
        filters.append({
            "type": "number", "column": "totalCost", "operator": ">", "value": 0,
        })
    if search_field and search_value:
        filters.append({
            "type": "string", "column": search_field,
            "operator": "matches" if search_field in {"input", "output"} else "contains",
            "value": search_value,
        })
    return filters


def _fetch_observations(
    *,
    limit: int,
    cursor: str | None,
    from_timestamp: datetime | None,
    to_timestamp: datetime | None,
    filters: list[dict[str, Any]],
) -> dict[str, Any]:
    client = _get_client()
    kwargs: dict[str, Any] = {
        "limit": limit,
        "fields": _OBSERVATION_FIELDS,
    }
    if cursor:
        kwargs["cursor"] = cursor
    if from_timestamp:
        kwargs["from_start_time"] = from_timestamp
    if to_timestamp:
        kwargs["to_start_time"] = to_timestamp
    if filters:
        kwargs["filter"] = json.dumps(filters, separators=(",", ":"))
    response = client.api.observations.get_many(**kwargs)
    payload = _dump(response) or {}
    meta = _dump(_pick(payload, "meta", default={})) or {}
    return {
        "data": [_observation(item) for item in (_pick(payload, "data", default=[]) or [])],
        "meta": {"cursor": _pick(meta, "cursor")},
    }


def _metrics_query(
    *,
    filters: list[dict[str, Any]],
    from_timestamp: datetime,
    to_timestamp: datetime,
    dimensions: list[dict[str, str]],
    metrics: list[dict[str, str]],
    time_dimension: dict[str, str] | None = None,
    order_by: list[dict[str, str]] | None = None,
    row_limit: int = 100,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {
        "view": "observations",
        "metrics": metrics,
        "dimensions": dimensions,
        "filters": filters,
        "fromTimestamp": from_timestamp.isoformat(),
        "toTimestamp": to_timestamp.isoformat(),
        "config": {"row_limit": row_limit},
    }
    if time_dimension:
        query["timeDimension"] = time_dimension
    if order_by:
        query["orderBy"] = order_by
    response = _get_client().api.metrics.metrics(
        query=json.dumps(query, separators=(",", ":")),
    )
    payload = _dump(response) or {}
    return _safe_value(_pick(payload, "data", default=[]) or [])


def _fetch_overview(
    *,
    from_timestamp: datetime | None,
    to_timestamp: datetime | None,
    filters: list[dict[str, Any]],
) -> dict[str, Any]:
    end = to_timestamp or datetime.now(timezone.utc)
    start = from_timestamp or datetime(2020, 1, 1, tzinfo=timezone.utc)
    granularity = "hour" if end - start <= timedelta(days=3) else "day"
    count_metrics = [
        {"measure": "count", "aggregation": "count"},
        {"measure": "totalCost", "aggregation": "sum"},
        {"measure": "latency", "aggregation": "p95"},
    ]
    with ThreadPoolExecutor(max_workers=5) as pool:
        timeline_future = pool.submit(
            _metrics_query,
            filters=filters, from_timestamp=start, to_timestamp=end,
            dimensions=[], metrics=count_metrics,
            time_dimension={"granularity": granularity},
            order_by=[{"field": "time_dimension", "direction": "asc"}],
            row_limit=1000,
        )
        type_future = pool.submit(
            _metrics_query,
            filters=filters, from_timestamp=start, to_timestamp=end,
            dimensions=[{"field": "type"}],
            metrics=[{"measure": "count", "aggregation": "count"}],
            order_by=[{"field": "count_count", "direction": "desc"}],
        )
        environment_future = pool.submit(
            _metrics_query,
            filters=filters, from_timestamp=start, to_timestamp=end,
            dimensions=[{"field": "environment"}],
            metrics=[{"measure": "count", "aggregation": "count"}],
            order_by=[{"field": "count_count", "direction": "desc"}],
        )
        name_future = pool.submit(
            _metrics_query,
            filters=filters, from_timestamp=start, to_timestamp=end,
            dimensions=[{"field": "name"}],
            metrics=[{"measure": "count", "aggregation": "count"}],
            order_by=[{"field": "count_count", "direction": "desc"}],
            row_limit=40,
        )
        trace_name_future = pool.submit(
            _metrics_query,
            filters=filters, from_timestamp=start, to_timestamp=end,
            dimensions=[{"field": "traceName"}],
            metrics=[{"measure": "count", "aggregation": "count"}],
            order_by=[{"field": "count_count", "direction": "desc"}],
            row_limit=40,
        )
        timeline = timeline_future.result()
        types = type_future.result()
        environments = environment_future.result()
        names = name_future.result()
        trace_names = trace_name_future.result()
    return {
        "timeline": timeline,
        "facets": {
            "types": types,
            "environments": environments,
            "names": names,
            "traceNames": trace_names,
        },
        "summary": {
            "count": sum(int(float(row.get("count_count") or 0)) for row in timeline),
            "cost": sum(float(row.get("sum_totalCost") or 0) for row in timeline),
            "p95Latency": max(
                (float(row.get("p95_latency") or 0) for row in timeline),
                default=0,
            ) / 1000,
        },
        "granularity": granularity,
    }


def _fetch_page(
    *,
    page: int,
    limit: int,
    environment: str | None,
    from_timestamp: datetime | None,
    to_timestamp: datetime | None,
) -> dict[str, Any]:
    client = _get_client()
    kwargs: dict[str, Any] = {
        "page": page,
        "limit": limit,
        "fields": "core,basic,usage,io",
    }
    if environment:
        kwargs["environment"] = environment
    if from_timestamp:
        kwargs["from_timestamp"] = from_timestamp
    if to_timestamp:
        kwargs["to_timestamp"] = to_timestamp

    if hasattr(getattr(client, "api", None), "trace"):
        response = client.api.trace.list(**kwargs)
    else:  # Langfuse Python SDK v2 compatibility
        kwargs.pop("fields", None)
        response = client.fetch_traces(**kwargs)

    payload = _dump(response) or {}
    raw_data = _pick(payload, "data", default=[]) or []
    meta = _dump(_pick(payload, "meta", default={})) or {}
    return {
        "data": [_trace_summary(item) for item in raw_data],
        "meta": {
            "page": _pick(meta, "page", default=page),
            "limit": _pick(meta, "limit", default=limit),
            "totalItems": _pick(meta, "totalItems", "total_items", default=len(raw_data)),
            "totalPages": _pick(meta, "totalPages", "total_pages", default=1),
        },
    }


def _fetch_detail(trace_id: str) -> dict[str, Any]:
    client = _get_client()
    if hasattr(getattr(client, "api", None), "trace"):
        trace = client.api.trace.get(trace_id, fields="core,basic,usage,io")
        observations_response = client.api.observations.get_many(
            trace_id=trace_id,
            fields=_OBSERVATION_FIELDS,
            limit=1000,
        )
        observations_payload = _dump(observations_response) or {}
        observations = _pick(observations_payload, "data", default=[]) or []
        try:
            scores_response = client.api.scores.get_many(trace_id=trace_id, limit=100)
            scores_payload = _dump(scores_response) or {}
            scores = _pick(scores_payload, "data", default=[]) or []
        except Exception:
            scores = []
    else:  # Langfuse Python SDK v2 compatibility
        trace = client.fetch_trace(trace_id)
        trace_dump = _dump(trace) or {}
        observations = _pick(trace_dump, "observations", default=[]) or []
        scores = _pick(trace_dump, "scores", default=[]) or []

    trace_dump = _dump(trace) or {}
    summary = _trace_summary(trace_dump)
    summary.update({
        "input": _safe_value(_pick(trace_dump, "input")),
        "output": _safe_value(_pick(trace_dump, "output")),
        "metadata": _safe_value(_pick(trace_dump, "metadata", default={})),
        "scores": _safe_value(scores or _pick(trace_dump, "scores", default=[])),
        "observations": [_observation(item) for item in observations],
    })
    return summary


async def _cached(key: str, loader: Callable[[], Any]) -> tuple[Any, bool]:
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
    if cached and now - cached[0] <= _FRESH_SECONDS:
        return cached[1], False
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            value = await asyncio.to_thread(loader)
            break
        except Exception as exc:
            last_error = exc
    else:
        if cached and now - cached[0] <= _STALE_SECONDS:
            return cached[1], True
        # Do not leak upstream URLs, credentials, or internal exception details.
        raise HTTPException(
            status_code=503,
            detail="Trace data is temporarily unavailable. Please retry shortly.",
        ) from last_error
    with _cache_lock:
        _cache[key] = (time.monotonic(), value)
    return value, False


def _public_response(payload: dict[str, Any], callback: str | None):
    """Return JSON, or a validated JSONP fallback for restricted demo browsers."""
    if not callback:
        return payload
    if not _CALLBACK.fullmatch(callback):
        raise HTTPException(status_code=400, detail="Invalid callback")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Prevent a payload string from ending the script element early.
    encoded = encoded.replace("<", "\\u003c")
    return Response(
        content=f"{callback}({encoded});",
        media_type="application/javascript",
        headers={"Cache-Control": "private, max-age=20"},
    )


def _filter_request(
    *,
    types: str | None,
    environments: str | None,
    level: str | None,
    root_only: bool | None,
    min_latency: float | None,
    cost_only: bool,
    search_field: str | None,
    search_value: str | None,
) -> list[dict[str, Any]]:
    parsed_types = tuple(
        item.strip().upper() for item in (types or "").split(",") if item.strip()
    )
    if any(item not in _OBSERVATION_TYPES for item in parsed_types):
        raise HTTPException(status_code=422, detail="Unknown observation type")
    parsed_environments = tuple(
        item.strip().lower() for item in (environments or "").split(",") if item.strip()
    )
    if any(not re.fullmatch(r"[a-z0-9_-]{1,40}", item) for item in parsed_environments):
        raise HTTPException(status_code=422, detail="Invalid environment")
    normalized_level = level.upper() if level else None
    if normalized_level and normalized_level not in _LEVELS:
        raise HTTPException(status_code=422, detail="Unknown log level")
    if search_field and search_field not in _SEARCH_FIELDS:
        raise HTTPException(status_code=422, detail="Unknown search field")
    return _observation_filters(
        types=parsed_types,
        environments=parsed_environments,
        level=normalized_level,
        root_only=root_only,
        min_latency=min_latency,
        cost_only=cost_only,
        search_field=search_field,
        search_value=search_value,
    )


@public_observability_router.get("/observations")
@limiter.limit("45/minute")
async def list_public_observations(
    request: Request,
    limit: int = Query(50, ge=10, le=100),
    cursor: str | None = Query(None, max_length=2048),
    types: str | None = Query(None, max_length=200),
    environments: str | None = Query(None, max_length=200),
    level: str | None = Query(None, max_length=16),
    root_only: bool | None = None,
    min_latency: float | None = Query(None, ge=0, le=3600),
    cost_only: bool = False,
    search_field: str | None = Query(None, max_length=32),
    search_value: str | None = Query(None, max_length=200),
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    callback: str | None = Query(None, max_length=64),
):
    """List redacted observations with the real Langfuse tracing filters."""
    filters = _filter_request(
        types=types, environments=environments, level=level,
        root_only=root_only, min_latency=min_latency, cost_only=cost_only,
        search_field=search_field, search_value=search_value,
    )
    key = "observations:" + repr((
        limit, cursor, filters, from_timestamp, to_timestamp,
    ))
    value, stale = await _cached(
        key,
        lambda: _fetch_observations(
            limit=limit, cursor=cursor, from_timestamp=from_timestamp,
            to_timestamp=to_timestamp, filters=filters,
        ),
    )
    return _public_response(
        {**value, "stale": stale, "refreshedAt": datetime.now().astimezone().isoformat()},
        callback,
    )


@public_observability_router.get("/overview")
@limiter.limit("20/minute")
async def public_observability_overview(
    request: Request,
    types: str | None = Query(None, max_length=200),
    environments: str | None = Query(None, max_length=200),
    level: str | None = Query(None, max_length=16),
    root_only: bool | None = None,
    min_latency: float | None = Query(None, ge=0, le=3600),
    cost_only: bool = False,
    search_field: str | None = Query(None, max_length=32),
    search_value: str | None = Query(None, max_length=200),
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    callback: str | None = Query(None, max_length=64),
):
    """Return histogram, totals, and real facets for the tracing workspace."""
    filters = _filter_request(
        types=types, environments=environments, level=level,
        root_only=root_only, min_latency=min_latency, cost_only=cost_only,
        search_field=search_field, search_value=search_value,
    )
    key = "overview:" + repr((filters, from_timestamp, to_timestamp))
    value, stale = await _cached(
        key,
        lambda: _fetch_overview(
            from_timestamp=from_timestamp, to_timestamp=to_timestamp,
            filters=filters,
        ),
    )
    return _public_response(
        {**value, "stale": stale, "refreshedAt": datetime.now().astimezone().isoformat()},
        callback,
    )


@public_observability_router.get("/traces")
@limiter.limit("30/minute")
async def list_public_traces(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=10, le=100),
    environment: str | None = Query(None, max_length=64),
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    callback: str | None = Query(None, max_length=64),
):
    """List redacted trace summaries from the configured Langfuse project."""
    key = "page:" + repr((page, limit, environment, from_timestamp, to_timestamp))
    value, stale = await _cached(
        key,
        lambda: _fetch_page(
            page=page,
            limit=limit,
            environment=environment,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
        ),
    )
    return _public_response(
        {**value, "stale": stale, "refreshedAt": datetime.now().astimezone().isoformat()},
        callback,
    )


@public_observability_router.get("/traces/{trace_id}")
@limiter.limit("60/minute")
async def get_public_trace(
    request: Request,
    trace_id: str,
    callback: str | None = Query(None, max_length=64),
):
    """Return one redacted trace and its observations for the detail pane."""
    if not _TRACE_ID.fullmatch(trace_id):
        raise HTTPException(status_code=404, detail="Trace not found")
    value, stale = await _cached(
        f"detail:{trace_id}",
        lambda: _fetch_detail(trace_id),
    )
    return _public_response(
        {**value, "stale": stale, "refreshedAt": datetime.now().astimezone().isoformat()},
        callback,
    )
