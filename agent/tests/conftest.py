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
os.environ["QUALITY_FEEDBACK_ALLOW_MEMORY_FALLBACK"] = "true"
os.environ.setdefault("AI_PLATFORM_API_KEY", "test-not-a-real-key")
os.environ["ALLOW_OFFSHORE_LLM_FALLBACK"] = "false"

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
    try:
        import identity
        monkeypatch.setattr(identity, "_mem_identities", {}, raising=False)
        monkeypatch.setattr(identity, "_mem_identity_by_hash", {}, raising=False)
        monkeypatch.setattr(identity, "_mem_conversations", {}, raising=False)
        monkeypatch.setattr(identity, "_claim_lock", __import__("asyncio").Lock(),
                            raising=False)
    except ImportError:
        pass
    try:
        import campaign_ownership
        monkeypatch.setattr(campaign_ownership, "_mem_campaigns", {}, raising=False)
        monkeypatch.setattr(
            campaign_ownership, "_mem_lock", __import__("asyncio").Lock(),
            raising=False,
        )
    except ImportError:
        pass
    try:
        import campaign_config
        monkeypatch.setattr(campaign_config, "_mem_revisions", {}, raising=False)
        monkeypatch.setattr(campaign_config, "_mem_requests", {}, raising=False)
        monkeypatch.setattr(campaign_config, "_locks", {}, raising=False)
    except ImportError:
        pass
    try:
        import accounts
        monkeypatch.setattr(accounts, "_mem_users", {}, raising=False)
        monkeypatch.setattr(accounts, "_mem_auth_identities", {}, raising=False)
        monkeypatch.setattr(accounts, "_mem_account_sessions", {}, raising=False)
        monkeypatch.setattr(accounts, "_mem_account_session_by_hash", {}, raising=False)
        monkeypatch.setattr(accounts, "_mem_auth_rate_limits", {}, raising=False)
        monkeypatch.setattr(accounts, "_mem_auth_audit_events", [], raising=False)
    except ImportError:
        pass
    try:
        import zalo_auth
        monkeypatch.setattr(zalo_auth, "_mem_attempts", {}, raising=False)
        monkeypatch.setattr(
            zalo_auth, "_attempt_lock", __import__("asyncio").Lock(), raising=False
        )
    except ImportError:
        pass
    try:
        import zalo_channel
        monkeypatch.setattr(zalo_channel, "_mem_links", {}, raising=False)
        monkeypatch.setattr(zalo_channel, "_mem_channel_identities", {}, raising=False)
        monkeypatch.setattr(zalo_channel, "_mem_events", {}, raising=False)
        monkeypatch.setattr(
            zalo_channel, "_mem_lock", __import__("asyncio").Lock(), raising=False
        )
    except ImportError:
        pass
    try:
        import zalo_oa_api
        zalo_oa_api.reset_oa_api_state_for_test()
        monkeypatch.setattr(
            zalo_oa_api, "_token_lock", __import__("asyncio").Lock(), raising=False
        )
        monkeypatch.setattr(
            zalo_oa_api, "_scan_lock", __import__("asyncio").Lock(), raising=False
        )
    except ImportError:
        pass
    try:
        import zalo_campaign_agent
        zalo_campaign_agent.reset_channel_agent_for_test()
        monkeypatch.setattr(
            zalo_campaign_agent, "_mem_lock", __import__("asyncio").Lock(), raising=False
        )
    except ImportError:
        pass
    try:
        import zalo_openai
        zalo_openai.reset_zalo_openai_for_test()
    except ImportError:
        pass
    try:
        from openai_campaign import client as openai_campaign_client
        openai_campaign_client.reset_for_test()
    except ImportError:
        pass
    try:
        from openai_campaign import audience_search
        audience_search.reset_audience_search_for_test()
    except ImportError:
        pass
    try:
        from quality import store as quality_store
        monkeypatch.setattr(quality_store, "_mem_interactions", {}, raising=False)
        monkeypatch.setattr(quality_store, "_mem_events", {}, raising=False)
        monkeypatch.setattr(quality_store, "_mem_feedback", {}, raising=False)
        monkeypatch.setattr(
            quality_store, "_mem_feedback_by_submission", {}, raising=False
        )
    except ImportError:
        pass
    try:
        import zalo_sessions
        zalo_sessions.reset_zalo_sessions_for_test()
        monkeypatch.setattr(
            zalo_sessions, "_mem_lock", __import__("asyncio").Lock(), raising=False
        )
    except ImportError:
        pass
    yield
