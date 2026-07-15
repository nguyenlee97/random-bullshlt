import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from middleware.request_limits import RequestSizeLimitMiddleware
from security import REDACTED, redact_langfuse, redact_pii, redact_text


def test_redact_text_masks_pii_credentials_and_mongo_passwords():
    raw = (
        "email alice@example.com phone +84 912 345 678 "
        "Authorization: " + "Bear" + "er abcdefghijklmnopqrstuvwxyz "
        "key sk-proj-abcdefghijklmnop "
        "cccd 079203001234 db mongo" + "db://agent:supersecret@mongo:27017/camp_ads"
    )
    safe = redact_text(raw)
    assert "alice@example.com" not in safe
    assert "+84 912 345 678" not in safe
    assert "abcdefghijklmnopqrstuvwxyz" not in safe
    assert "sk-proj-abcdefghijklmnop" not in safe
    assert "supersecret" not in safe
    assert "079203001234" not in safe
    assert "[REDACTED_EMAIL]" in safe
    assert "[REDACTED_PHONE]" in safe


def test_redact_pii_recurses_and_masks_sensitive_keys():
    source = {
        "brief": {"notes": "Liên hệ bob@example.org", "brand": "Zuma"},
        "authorization": "Bearer should-never-leak",
        "nested": [{"api_key": "secret-value", "safe": 7}],
    }
    result = redact_pii(source)
    assert result["brief"]["brand"] == "Zuma"
    assert result["brief"]["notes"] == "Liên hệ [REDACTED_EMAIL]"
    assert result["authorization"] == REDACTED
    assert result["nested"][0]["api_key"] == REDACTED
    assert source["brief"]["notes"] == "Liên hệ bob@example.org"


def test_langfuse_mask_accepts_data_keyword():
    masked = redact_langfuse(data={"email": "person@example.com", "safe": "ok"})
    assert masked == {"email": REDACTED, "safe": "ok"}


def test_request_size_limit_rejects_content_length_before_handler():
    async def endpoint(request: Request):
        return JSONResponse({"size": len(await request.body())})

    app = RequestSizeLimitMiddleware(
        Starlette(routes=[Route("/payload", endpoint, methods=["POST"])]),
        max_bytes=16,
    )
    with TestClient(app) as client:
        assert client.post("/payload", content=b"small").status_code == 200
        response = client.post("/payload", content=b"x" * 17)
    assert response.status_code == 413
    assert response.json()["error"] == "payload_too_large"


@pytest.mark.asyncio
async def test_delete_session_data_cleans_in_memory_agent_artifacts_only():
    import session
    from autopilot import service as autopilot
    from creative_intel import service as creative
    from workspace import service as workspace

    sid = "delete_security_test"
    run_id = "run_delete_security_test"
    session._mem[sid] = session._default_session(sid)
    session._mem_logs.append({"session_id": sid, "type": "test", "data": {}})
    workspace._mem_workspaces[sid] = {"session_id": sid}
    workspace._mem_proposals["proposal_delete"] = {"session_id": sid}
    creative._mem["creative_delete"] = {"session_id": sid}
    autopilot._mem_runs[run_id] = {"run_id": run_id, "session_id": sid}
    autopilot._mem_tasks["task_delete"] = {"run_id": run_id}
    autopilot._mem_events.append({"run_id": run_id})

    deleted = await session.delete_session_data(sid)

    assert sid not in session._mem
    assert all(item.get("session_id") != sid for item in session._mem_logs)
    assert sid not in workspace._mem_workspaces
    assert "proposal_delete" not in workspace._mem_proposals
    assert "creative_delete" not in creative._mem
    assert run_id not in autopilot._mem_runs
    assert "task_delete" not in autopilot._mem_tasks
    assert all(item.get("run_id") != run_id for item in autopilot._mem_events)
    assert deleted["agent_runs"] == 1
