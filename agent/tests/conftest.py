"""
Test bootstrap — runs before any test module imports app code.

Forces an unreachable MongoDB URI so session.py uses its in-memory fallback.
Why: Motor's client binds to the event loop it was created on; pytest-asyncio
creates a fresh loop per test, so a real Mongo connection from test #1 raises
"Event loop is closed" in test #2+. In-memory storage sidesteps loop binding
entirely — and the intercept-parity tests are about logic, not persistence.

NOTE: conftest.py IS imported before test modules, but Docker Compose sets
MONGODB_URI as an environment variable that may already be read at import time
by session.py. To guarantee the override wins, we patch session._sessions_col
to None so it reinitializes against our fake URI when first called.
"""
import os

# Override BEFORE any app import
os.environ["MONGODB_URI"] = "mongodb://127.0.0.1:1"   # unreachable → triggers in-memory fallback
os.environ.pop("LANGFUSE_PUBLIC_KEY", None)            # no tracing in tests
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest


@pytest.fixture(autouse=True)
def reset_session_col(monkeypatch):
    """
    Force session.py to re-initialize _sessions_col with the fake URI each test.
    Motor binds its internal thread executor to the loop it was created on.
    Resetting the module-level collection reference causes it to re-connect
    on the current test's loop (which points to the unreachable address → in-memory fallback).
    """
    import session
    # Never let unit tests reuse a Motor client/collection created on another
    # pytest event loop.  Mark Mongo unavailable instead of reconnecting: these
    # tests exercise agent logic, while Mongo integration is covered separately.
    client = getattr(session, "_client", None)
    if client is not None:
        client.close()
    monkeypatch.setattr(session, "_client", None, raising=False)
    monkeypatch.setattr(session, "_sessions_col", None, raising=False)
    monkeypatch.setattr(session, "_logs_col", None, raising=False)
    monkeypatch.setattr(session, "_mongo_ok", False, raising=False)
    monkeypatch.setattr(session, "_mem", {}, raising=False)
    monkeypatch.setattr(session, "_mem_logs", [], raising=False)
    try:
        from workspace import service as workspace_service
        workspace_client = getattr(workspace_service, "_client", None)
        if workspace_client is not None:
            workspace_client.close()
        monkeypatch.setattr(workspace_service, "_client", None, raising=False)
        monkeypatch.setattr(workspace_service, "_mongo_ok", False, raising=False)
        monkeypatch.setattr(workspace_service, "_mem_workspaces", {}, raising=False)
        monkeypatch.setattr(workspace_service, "_mem_proposals", {}, raising=False)
        monkeypatch.setattr(workspace_service, "_locks", {}, raising=False)
    except ImportError:
        pass
    try:
        from autopilot import service as autopilot_service
        monkeypatch.setattr(autopilot_service, "_mem_runs", {}, raising=False)
        monkeypatch.setattr(autopilot_service, "_mem_tasks", {}, raising=False)
        monkeypatch.setattr(autopilot_service, "_mem_events", [], raising=False)
        monkeypatch.setattr(autopilot_service, "_lock", __import__("asyncio").Lock(),
                            raising=False)
    except ImportError:
        pass
    yield
