"""
Prometheus metrics (Phase 0 B4). Canonical metric names from
docs/production-plan/01 §B4 — Grafana dashboards + SLO alerts key off these.

Usage: main.py calls setup_metrics(app); llm.py / registry.py / handlers import
the counters. All no-op safely if prometheus_client is missing (dev machines).
"""
try:
    from prometheus_client import Counter, Histogram

    LLM_CALLS = Counter(
        "agent_llm_calls_total", "LLM calls", ["model", "handler", "outcome"])
    LLM_TOKENS = Counter(
        "agent_llm_tokens_total", "LLM tokens", ["model", "direction"])
    TOOL_CALLS = Counter(
        "agent_tool_calls_total", "Tool executions", ["tool", "outcome"])
    FALLBACK_LEVEL = Counter(
        "agent_fallback_level_total", "3-level fallback fires", ["level"])
    ORDERS_CREATED = Counter("agent_orders_created_total", "Orders created")
    ORDERS_REJECTED = Counter(
        "agent_orders_rejected_total", "Orders rejected by order_guard", ["reason"])
    RAG_REQUESTS = Counter(
        "agent_rag_requests_total", "RAG audience recommendations", ["outcome"])
    RAG_HALLUCINATED = Counter(
        "agent_rag_hallucinated_label_total", "LLM cited labels outside candidate set")
    RAG_GUARD_REJECTED = Counter(
        "agent_rag_guard_rejected_total", "Selected candidates rejected by deterministic guard",
        ["reason"])
    RAG_RERANK = Counter(
        "agent_rag_rerank_total", "RAG reranker outcomes", ["outcome"])
    RAG_STAGE_SECONDS = Histogram(
        "agent_rag_stage_seconds", "RAG stage duration seconds", ["stage"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60))
    RAG_CANDIDATES = Histogram(
        "agent_rag_candidates", "Candidates entering final RAG generation",
        buckets=(1, 5, 10, 15, 25, 50, 75, 100))
    VLM_CALLS = Counter(
        "agent_vlm_calls_total", "Creative VLM calls", ["model", "outcome"])
    VLM_SECONDS = Histogram(
        "agent_vlm_call_seconds", "Creative VLM call duration seconds", ["model"],
        buckets=(0.5, 1, 2, 4, 8, 15, 20, 30, 60))
    SESSION_COST = Histogram(
        "agent_llm_call_seconds", "LLM call duration seconds",
        buckets=(0.5, 1, 2, 4, 8, 15, 30, 60, 120))

    ENABLED = True
except ImportError:  # prometheus_client not installed — everything no-ops
    class _Noop:
        def labels(self, *a, **k): return self
        def inc(self, *a, **k): pass
        def observe(self, *a, **k): pass
    LLM_CALLS = LLM_TOKENS = TOOL_CALLS = FALLBACK_LEVEL = _Noop()
    ORDERS_CREATED = ORDERS_REJECTED = SESSION_COST = _Noop()
    RAG_REQUESTS = RAG_HALLUCINATED = RAG_GUARD_REJECTED = RAG_RERANK = _Noop()
    RAG_STAGE_SECONDS = RAG_CANDIDATES = _Noop()
    VLM_CALLS = VLM_SECONDS = _Noop()
    ENABLED = False


def setup_metrics(app) -> None:
    """Attach default HTTP metrics + /metrics endpoint. Call from main.py."""
    if not ENABLED:
        return
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator(
            should_group_status_codes=True,
            excluded_handlers=["/metrics", "/health", "/api/health", "/api/version"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    except ImportError:
        pass
