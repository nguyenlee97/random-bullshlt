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
    # Reset both the collection reference and the in-memory store so tests are isolated
    monkeypatch.setattr(session, "_sessions_col", None, raising=False)
    monkeypatch.setattr(session, "_mem_store", {}, raising=False)
    yield
