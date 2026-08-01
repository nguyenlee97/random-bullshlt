import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[2]


class _Metric:
    def __init__(self):
        self.events = []

    def labels(self, **labels):
        metric = self

        class _Child:
            def inc(self, amount=1):
                metric.events.append((labels, amount))

        return _Child()


class _Histogram:
    def __init__(self):
        self.values = []

    def observe(self, value):
        self.values.append(value)


def test_record_llm_call_exports_routing_tokens_and_duration(monkeypatch):
    import metrics

    calls = _Metric()
    providers = _Metric()
    tokens = _Metric()
    durations = _Histogram()
    monkeypatch.setattr(metrics, "LLM_CALLS", calls)
    monkeypatch.setattr(metrics, "LLM_PROVIDER_EVENTS", providers)
    monkeypatch.setattr(metrics, "LLM_TOKENS", tokens)
    monkeypatch.setattr(metrics, "SESSION_COST", durations)

    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=321, output_tokens=123),
    )
    metrics.record_llm_call(
        model="gpt-5.4-mini",
        handler="openai.turn_decision",
        provider="openai",
        outcome="ok",
        response=response,
        duration_seconds=1.25,
    )

    assert calls.events == [({
        "model": "gpt-5.4-mini",
        "handler": "openai.turn_decision",
        "outcome": "ok",
    }, 1)]
    assert providers.events == [({"provider": "openai", "outcome": "ok"}, 1)]
    assert tokens.events == [
        ({"model": "gpt-5.4-mini", "direction": "prompt"}, 321),
        ({"model": "gpt-5.4-mini", "direction": "completion"}, 123),
    ]
    assert durations.values == [1.25]


def test_agent_ops_dashboard_has_unique_panels_and_zero_safe_core_metrics():
    dashboard_path = (
        ROOT / "ops" / "grafana" / "provisioning" / "dashboards" / "agent-ops.json"
    )
    raw = dashboard_path.read_text(encoding="utf-8")
    dashboard = json.loads(raw)
    panels = dashboard["panels"]

    assert "â" not in raw
    assert len({panel["id"] for panel in panels}) == len(panels)
    assert dashboard["time"]["from"] == "now-1h"

    by_title = {panel["title"]: panel for panel in panels}
    expected_zero_safe = {
        "LLM call rate by outcome",
        "Fallback level fires — SLO: L3 < 2%",
        "Token burn (per direction)",
        "Tool calls by outcome",
        "Orders created vs rejected (24h)",
        "Model provider routing",
        "HTTP 5xx ratio (15m) — SLO < 0.5%",
        "Agent scrape health",
    }
    assert expected_zero_safe <= set(by_title)
    for title in expected_zero_safe:
        assert all(
            "vector(0)" in target["expr"]
            for target in by_title[title]["targets"]
        )

    assert "Agent process uptime" in by_title
