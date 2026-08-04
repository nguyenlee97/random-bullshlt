import pytest
from fastapi import HTTPException
from pathlib import Path

from public_observability import (
    _filter_request,
    _observation,
    _public_response,
    _safe_value,
    _session_detail,
    _session_summary,
    _trace_summary,
)
from middleware.auth import _is_exempt_path


OBSERVABILITY_HTML = (
    Path(__file__).resolve().parents[2]
    / "agent_frontend"
    / "public"
    / "observability.html"
)


def test_public_observability_auth_exemption_is_narrow():
    assert _is_exempt_path("/api/public/observability")
    assert _is_exempt_path("/api/public/observability/traces")
    assert not _is_exempt_path("/api/public/observability-evil/traces")
    assert not _is_exempt_path("/api/agent/chat")


def test_safe_value_redacts_pii_credentials_and_internal_metadata():
    safe = _safe_value({
        "email": "judge@example.com",
        "authorization": "Bearer abcdefghijklmnopqrstuvwxyz",
        "scope.attributes.public_key": "pk-lf-should-not-leak",
        "resourceAttributes.service.instance.id": "internal-host-id",
        "resourceAttributes": {
            "service.instance.id": "nested-internal-host-id",
            "service.name": "advertising-agent",
        },
        "campaign": "Summer launch",
    })

    assert safe["email"] == "[REDACTED_EMAIL]"
    assert safe["authorization"] == "[REDACTED]"
    assert "scope.attributes.public_key" not in safe
    assert "resourceAttributes.service.instance.id" not in safe
    assert "service.instance.id" not in safe["resourceAttributes"]
    assert safe["resourceAttributes"]["service.name"] == "advertising-agent"
    assert safe["campaign"] == "Summer launch"


def test_trace_summary_is_a_bounded_presentation_model():
    trace = _trace_summary({
        "id": "a" * 32,
        "name": "agent.turn",
        "timestamp": "2026-08-04T00:00:00Z",
        "projectId": "private-project",
        "environment": "production",
        "userId": "judge@example.com",
        "observations": [{"id": "one"}, {"id": "two"}],
        "input": {"prompt": "hello"},
        "output": {"answer": "world"},
    })

    assert trace["id"] == "a" * 32
    assert trace["environment"] == "production"
    assert trace["userId"] == "[REDACTED_EMAIL]"
    assert trace["observationCount"] == 2
    assert "projectId" not in trace


def test_observation_only_keeps_public_detail_fields():
    result = _observation({
        "id": "obs",
        "traceId": "a" * 32,
        "type": "GENERATION",
        "model": "gpt-5-mini",
        "input": "Call me at 0901234567",
        "projectId": "private-project",
    })

    assert result["type"] == "GENERATION"
    assert result["input"] == "Call me at [REDACTED_PHONE]"
    assert "projectId" not in result


def test_session_summary_drops_project_identity():
    result = _session_summary({
        "id": "sess_demo",
        "createdAt": "2026-08-04T00:00:00Z",
        "environment": "production",
        "projectId": "private-project",
    })

    assert result == {
        "id": "sess_demo",
        "createdAt": "2026-08-04T00:00:00Z",
        "environment": "production",
    }


def test_session_detail_aggregates_traces_cost_usage_and_metadata():
    result = _session_detail(
        {"id": "sess_demo", "createdAt": "2026-08-04T00:00:00Z"},
        [
            {
                "id": "root-a", "traceId": "a" * 32, "name": "agent.turn",
                "traceName": "campaign-turn", "type": "AGENT",
                "isRootObservation": True, "startTime": "2026-08-04T00:00:00Z",
                "endTime": "2026-08-04T00:00:02Z", "totalCost": 0,
                "input": {"message": "hello"}, "output": {"answer": "world"},
                "metadata": {"request_id": "req-1"},
            },
            {
                "id": "gen-a", "traceId": "a" * 32, "parentObservationId": "root-a",
                "name": "openai.generate", "type": "GENERATION",
                "startTime": "2026-08-04T00:00:00.5Z",
                "endTime": "2026-08-04T00:00:01.5Z", "totalCost": 0.25,
                "usageDetails": {"input": 100, "output": 20, "total": 120},
                "providedModelName": "gpt-test", "version": "v2",
                "modelParameters": {"reasoning": {"effort": "low"}},
            },
            {
                "id": "root-b", "traceId": "b" * 32, "name": "tool.turn",
                "type": "AGENT", "startTime": "2026-08-04T00:00:03Z",
                "endTime": "2026-08-04T00:00:04Z", "totalCost": 0.05,
                "totalUsage": 10,
            },
        ],
    )

    assert result["traceCount"] == 2
    assert result["observationCount"] == 3
    assert result["totalCost"] == pytest.approx(0.30)
    assert result["totalUsage"] == 130
    assert result["models"] == ["gpt-test"]
    assert result["traces"][0]["name"] == "campaign-turn"
    assert result["traces"][0]["metadata"] == {"request_id": "req-1"}
    assert result["traces"][0]["modelParameters"]["reasoning"]["effort"] == "low"


def test_observation_filter_contract_supports_real_tracing_controls():
    filters = _filter_request(
        types="generation,tool",
        environments="production,default",
        level="error",
        root_only=True,
        min_latency=2,
        cost_only=True,
        search_field="name",
        search_value="openai",
    )

    assert filters[0]["column"] == "type"
    assert filters[0]["value"] == ["GENERATION", "TOOL"]
    assert any(item["column"] == "isRootObservation" for item in filters)
    assert any(item["column"] == "latency" for item in filters)
    assert any(item["column"] == "totalCost" for item in filters)
    assert filters[-1]["operator"] == "contains"


@pytest.mark.parametrize(
    ("field", "value"),
    (("types", "UNKNOWN"), ("environments", "Not Valid!"), ("level", "FATAL")),
)
def test_observation_filter_contract_rejects_unknown_values(field, value):
    kwargs = {
        "types": None,
        "environments": None,
        "level": None,
        "root_only": None,
        "min_latency": None,
        "cost_only": False,
        "search_field": None,
        "search_value": None,
    }
    kwargs[field] = value
    with pytest.raises(HTTPException):
        _filter_request(**kwargs)


def test_jsonp_fallback_validates_callback_and_escapes_script_content():
    response = _public_response(
        {"value": "</script><script>alert(1)</script>"},
        "__campAdsObservability42",
    )
    body = response.body.decode("utf-8")

    assert body.startswith("__campAdsObservability42(")
    assert "</script>" not in body
    assert "\\u003c/script>" in body

    with pytest.raises(HTTPException):
        _public_response({"ok": True}, "alert")


def test_trace_explorer_keeps_the_smooth_interaction_contract():
    source = OBSERVABILITY_HTML.read_text(encoding="utf-8")

    for contract in (
        'id="densityToggle"',
        'id="detailResize"',
        "campAdsObservabilityPreferencesV2",
        "new AbortController()",
        "function syncRoute(",
        "function restoreRoute(",
        "root?.traceName||root?.name||named?.traceName",
        "function sampledOverview(",
        "function restoreWorkspaceRoute(",
        "function renderSessionDetail(",
        "overscroll-behavior:contain",
        'id="sessionsNav"',
        "log-expanded-grid",
        "Keyboard shortcuts",
    ):
        assert contract in source

    # Public trace payloads are always rendered through DOM text nodes.
    assert ".innerHTML" not in source
    # The Cloud metrics query can block for over a minute; the public page uses
    # an explicitly labeled page sample instead of starting that request.
    assert "`${API}/overview?" not in source
