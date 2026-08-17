import pytest
from fastapi import HTTPException


def test_autopilot_start_guard_rejects_disabled_worker(monkeypatch):
    import router

    monkeypatch.setattr(router._cfg, "USE_CAMPAIGN_AUTOPILOT", False)
    monkeypatch.setattr("autopilot.worker.worker_running", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        router._require_autopilot_worker()

    assert exc_info.value.status_code == 503


def test_autopilot_start_guard_rejects_dead_worker(monkeypatch):
    import router

    monkeypatch.setattr(router._cfg, "USE_CAMPAIGN_AUTOPILOT", True)
    monkeypatch.setattr("autopilot.worker.worker_running", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        router._require_autopilot_worker()

    assert exc_info.value.status_code == 503


def test_autopilot_start_guard_accepts_running_worker(monkeypatch):
    import router

    monkeypatch.setattr(router._cfg, "USE_CAMPAIGN_AUTOPILOT", True)
    monkeypatch.setattr("autopilot.worker.worker_running", lambda: True)

    router._require_autopilot_worker()
