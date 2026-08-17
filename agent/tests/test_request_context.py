from starlette.testclient import TestClient

from main import app
from request_context import get_request_id


def test_request_id_is_generated_and_returned():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert len(response.headers["X-Request-Id"]) == 16


def test_safe_request_id_is_preserved_but_invalid_value_is_replaced():
    with TestClient(app) as client:
        preserved = client.get("/health", headers={"X-Request-Id": "demo-trace_42"})
        replaced = client.get("/health", headers={"X-Request-Id": "bad id with spaces"})
    assert preserved.headers["X-Request-Id"] == "demo-trace_42"
    assert replaced.headers["X-Request-Id"] != "bad id with spaces"
    assert get_request_id() == "-"
