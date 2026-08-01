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
    LLM_PROVIDER_EVENTS = Counter(
        "agent_llm_provider_events_total", "Model provider routing events",
        ["provider", "outcome"])
    INJECTION_FLAGGED = Counter(
        "agent_prompt_injection_flagged_total", "Prompt injection detections",
        ["surface", "rule"])
    GUARDRAIL_DECISIONS = Counter(
        "agent_guardrail_decisions_total", "Guardrail decisions",
        ["surface", "mode", "decision", "severity"])
    GUARDRAIL_PROTECTED_STATE = Counter(
        "agent_guardrail_protected_state_total",
        "Protected state observed after guardrail decisions",
        ["surface", "workspace_mutated", "order_created"])
    FEEDBACK = Counter(
        "agent_feedback_total", "User feedback", ["sentiment", "surface"])
    FEEDBACK_REASONS = Counter(
        "agent_feedback_reason_total", "Negative feedback reasons",
        ["reason_code", "surface"])
    FEEDBACK_WRITES = Counter(
        "agent_feedback_write_total", "Feedback persistence", ["outcome"])
    QUALITY_EVENT_WRITES = Counter(
        "agent_quality_event_write_total", "Quality event persistence",
        ["event_type", "outcome"])
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
    LLM_CALLS = LLM_TOKENS = LLM_PROVIDER_EVENTS = INJECTION_FLAGGED = TOOL_CALLS = FALLBACK_LEVEL = _Noop()
    GUARDRAIL_DECISIONS = GUARDRAIL_PROTECTED_STATE = _Noop()
    FEEDBACK = FEEDBACK_REASONS = FEEDBACK_WRITES = QUALITY_EVENT_WRITES = _Noop()
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


def _usage_tokens(response, *names: str) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0
    for name in names:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        if value is not None:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                return 0
    return 0


def record_llm_call(
    *,
    model: str,
    handler: str,
    outcome: str,
    provider: str,
    response=None,
    duration_seconds: float | None = None,
) -> None:
    """Record one provider call across legacy, Responses, and Zalo paths."""
    LLM_CALLS.labels(
        model=str(model or "unknown"),
        handler=str(handler or "unknown"),
        outcome=str(outcome or "unknown"),
    ).inc()
    LLM_PROVIDER_EVENTS.labels(
        provider=str(provider or "unknown"),
        outcome=str(outcome or "unknown"),
    ).inc()
    if response is not None:
        LLM_TOKENS.labels(
            model=str(model or "unknown"), direction="prompt",
        ).inc(_usage_tokens(response, "input_tokens", "prompt_tokens"))
        LLM_TOKENS.labels(
            model=str(model or "unknown"), direction="completion",
        ).inc(_usage_tokens(response, "output_tokens", "completion_tokens"))
    if duration_seconds is not None:
        SESSION_COST.observe(max(0.0, float(duration_seconds)))


def record_tool_call(*, tool: str, outcome: str) -> None:
    """Record one server-owned tool or Autopilot capability execution."""
    TOOL_CALLS.labels(
        tool=str(tool or "unknown"),
        outcome=str(outcome or "unknown"),
    ).inc()
