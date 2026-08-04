import pytest
from fastapi import HTTPException

from public_observability import _observation, _public_response, _safe_value, _trace_summary
from middleware.auth import _is_exempt_path


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
        "campaign": "Summer launch",
    })

    assert safe["email"] == "[REDACTED_EMAIL]"
    assert safe["authorization"] == "[REDACTED]"
    assert "scope.attributes.public_key" not in safe
    assert "resourceAttributes.service.instance.id" not in safe
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
