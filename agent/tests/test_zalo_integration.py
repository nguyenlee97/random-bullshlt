import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient


def _enable_login(monkeypatch):
    from config import config

    monkeypatch.setattr(config, "ZALO_LOGIN_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_APP_ID", "app-test-1")
    monkeypatch.setattr(config, "ZALO_APP_SECRET", "secret-test-1")
    monkeypatch.setattr(config, "ZALO_LOGIN_REDIRECT_URI", "https://example.test/callback")
    monkeypatch.setattr(config, "ZALO_LOGIN_PERMISSION_URL", "https://oauth.example.test/permission")


def _enable_oa(monkeypatch):
    from config import config

    monkeypatch.setattr(config, "ZALO_OA_ENABLED", True)
    monkeypatch.setattr(config, "ZALO_APP_ID", "app-test-1")
    monkeypatch.setattr(config, "ZALO_OA_ID", "oa-test-1")
    monkeypatch.setattr(config, "ZALO_OA_NAME", "IOT Generation Test")
    monkeypatch.setattr(config, "ZALO_OA_SECRET", "oa-secret-test-1")
    monkeypatch.setattr(config, "ZALO_WEBHOOK_MAX_SKEW_SECONDS", 600)


def _signed_event(
    *, text="hello", message_id="msg-1", uid="oa-user-1",
    event_name="user_send_text", user_id_by_app=None,
):
    from config import config

    body = {
        "app_id": config.ZALO_APP_ID,
        "event_name": event_name,
        "timestamp": str(int(time.time() * 1000)),
    }
    if event_name in {"follow", "unfollow"}:
        body.update({
            "oa_id": config.ZALO_OA_ID,
            "source": "testing_webhook",
            "follower": {"id": uid},
        })
    else:
        body.update({
            "sender": {"id": uid},
            "recipient": {"id": config.ZALO_OA_ID},
            "message": {"text": text, "msg_id": message_id},
        })
    if user_id_by_app:
        body["user_id_by_app"] = user_id_by_app
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    mac = hashlib.sha256(
        config.ZALO_APP_ID.encode()
        + raw
        + body["timestamp"].encode()
        + config.ZALO_OA_SECRET.encode()
    ).hexdigest()
    return body, raw, f"mac={mac}"


def test_channel_link_expiry_accepts_legacy_naive_mongo_datetimes():
    import zalo_channel

    assert zalo_channel._is_expired(datetime.utcnow() - timedelta(seconds=1)) is True
    assert zalo_channel._is_expired(
        datetime.now(timezone.utc) + timedelta(seconds=30)
    ) is False


@pytest.mark.asyncio
async def test_zalo_login_uses_one_time_pkce_and_existing_account_session(monkeypatch):
    _enable_login(monkeypatch)
    from accounts import create_account_session, get_account_storage_for_test, require_account_session
    from identity import bootstrap_anonymous, resolve_actor
    import zalo_auth

    anonymous = await bootstrap_anonymous()
    actor = await resolve_actor(None, anonymous["token"])
    started = await zalo_auth.start_user_oauth(actor, intent="login", return_to="/history")
    parsed = urlparse(started["authorization_url"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "oauth.example.test"
    assert query["app_id"] == ["app-test-1"]
    assert query["redirect_uri"] == ["https://example.test/callback"]
    assert len(query["code_challenge"][0]) >= 43
    assert query["code_challenge_method"] == ["S256"]
    state = query["state"][0]
    attempts = await zalo_auth.get_zalo_auth_storage_for_test()
    assert len(attempts) == 1
    assert state not in repr(attempts)

    async def fake_profile(code, verifier):
        assert code == "authorization-code"
        assert len(verifier) >= 43
        return {
            "subject": "zalo-subject-123",
            "display_name": "Nguyen Zalo",
            "avatar_url": "https://photo.example/avatar.jpg",
        }

    monkeypatch.setattr(zalo_auth, "_zalo_profile", fake_profile)
    completed = await zalo_auth.finish_user_oauth("authorization-code", state, actor)
    assert completed["intent"] == "login"
    assert completed["return_to"] == "/history"
    assert completed["user"]["providers"] == ["zalo"]
    assert completed["user"]["email"] is None
    session = await create_account_session(completed["user"]["user_id"])
    resolved = await require_account_session(session["token"])
    assert resolved["user"]["providers"] == ["zalo"]
    storage = await get_account_storage_for_test()
    assert "authorization-code" not in repr(storage)
    assert "access_token" not in repr(storage)
    with pytest.raises(zalo_auth.ZaloOAuthError, match="invalid or expired"):
        await zalo_auth.finish_user_oauth("authorization-code", state, actor)


@pytest.mark.asyncio
async def test_zalo_login_state_is_bound_to_browser_and_link_is_explicit(monkeypatch):
    _enable_login(monkeypatch)
    from accounts import create_account_session, create_local_account
    from identity import bootstrap_anonymous, resolve_actor
    import zalo_auth

    first = await bootstrap_anonymous()
    second = await bootstrap_anonymous()
    first_actor = await resolve_actor(None, first["token"])
    second_actor = await resolve_actor(None, second["token"])
    started = await zalo_auth.start_user_oauth(first_actor, intent="login")
    state = parse_qs(urlparse(started["authorization_url"]).query)["state"][0]
    with pytest.raises(zalo_auth.ZaloOAuthError, match="browser identity changed"):
        await zalo_auth.finish_user_oauth("code", state, second_actor)

    local = await create_local_account("local@example.com", "correct horse battery", "Local")
    local_session = await create_account_session(local["user_id"])
    local_actor = await resolve_actor(local_session["token"], first["token"])
    link_started = await zalo_auth.start_user_oauth(local_actor, intent="link")
    link_state = parse_qs(urlparse(link_started["authorization_url"]).query)["state"][0]

    async def fake_profile(code, verifier):
        return {"subject": "zalo-link-1", "display_name": "Zalo Name", "avatar_url": None}

    monkeypatch.setattr(zalo_auth, "_zalo_profile", fake_profile)
    linked = await zalo_auth.finish_user_oauth("code", link_state, local_actor)
    assert linked["user"]["user_id"] == local["user_id"]
    assert linked["user"]["providers"] == ["local", "zalo"]

    foreign = await create_local_account("foreign@example.com", "correct horse battery", "Foreign")
    foreign_session = await create_account_session(foreign["user_id"])
    foreign_actor = await resolve_actor(foreign_session["token"], second["token"])
    foreign_started = await zalo_auth.start_user_oauth(foreign_actor, intent="link")
    foreign_state = parse_qs(urlparse(foreign_started["authorization_url"]).query)["state"][0]
    from accounts import AccountConflict
    with pytest.raises(AccountConflict):
        await zalo_auth.finish_user_oauth("code", foreign_state, foreign_actor)


@pytest.mark.asyncio
async def test_signed_oa_link_message_links_once_and_replay_is_idempotent(monkeypatch):
    _enable_oa(monkeypatch)
    from accounts import create_local_account
    import zalo_channel

    user = await create_local_account("owner@example.com", "correct horse battery", "Owner")
    attempt = await zalo_channel.start_channel_link(user["user_id"])
    body, raw, signature = _signed_event(
        text=f"LINK {attempt['link_code']}", message_id="link-message-1"
    )
    zalo_channel.verify_webhook(raw, body, signature)
    event = zalo_channel.normalize_event(body, raw)
    first = await zalo_channel.record_event(event)
    second = await zalo_channel.record_event(event)
    assert first["duplicate"] is False
    assert first["link"]["status"] == "linked"
    assert second["duplicate"] is True
    status = await zalo_channel.get_channel_link(user["user_id"], attempt["attempt_id"])
    assert status["status"] == "linked"
    linked = await zalo_channel.get_linked_channel_for_user(user["user_id"])
    assert linked["status"] == "linked"
    storage = await zalo_channel.get_channel_storage_for_test()
    assert len(storage["events"]) == 1
    assert len(storage["identities"]) == 1
    assert attempt["link_code"] not in repr(storage["links"])


@pytest.mark.asyncio
async def test_signed_follow_links_only_matching_zalo_login_with_pending_attempt(monkeypatch):
    _enable_oa(monkeypatch)
    from accounts import authenticate_zalo_account
    import zalo_channel

    user = await authenticate_zalo_account("app-follow-user-1", "Follow User")
    attempt = await zalo_channel.start_channel_link(user["user_id"])
    assert attempt["oa_name"] == "IOT Generation Test"

    wrong_body, wrong_raw, wrong_signature = _signed_event(
        event_name="follow",
        message_id="follow-wrong-1",
        uid="oa-follow-user-1",
        user_id_by_app="untrusted-browser-value",
    )
    zalo_channel.verify_webhook(wrong_raw, wrong_body, wrong_signature)
    wrong = await zalo_channel.record_event(
        zalo_channel.normalize_event(wrong_body, wrong_raw)
    )
    assert wrong["link"] == {
        "status": "not_linked",
        "reason": "zalo_login_identity_not_found",
    }
    assert (await zalo_channel.get_channel_link(
        user["user_id"], attempt["attempt_id"]
    ))["status"] == "pending"

    body, raw, signature = _signed_event(
        event_name="follow",
        message_id="follow-valid-1",
        uid="oa-follow-user-1",
        user_id_by_app="app-follow-user-1",
    )
    zalo_channel.verify_webhook(raw, body, signature)
    result = await zalo_channel.record_event(zalo_channel.normalize_event(body, raw))
    assert result["link"] == {"status": "linked", "user_id": user["user_id"]}
    status = await zalo_channel.get_channel_link(user["user_id"], attempt["attempt_id"])
    assert status["status"] == "linked"
    assert status["link_method"] == "signed_follow"
    linked = await zalo_channel.get_linked_channel_for_user(user["user_id"])
    assert linked["status"] == "linked"


def test_follow_payload_uses_follower_id_and_top_level_oa_id(monkeypatch):
    _enable_oa(monkeypatch)
    import zalo_channel

    body, raw, _ = _signed_event(
        event_name="follow",
        message_id="unused-for-follow",
        uid="oa-follower-schema-1",
        user_id_by_app="app-follower-schema-1",
    )
    event = zalo_channel.normalize_event(body, raw)

    assert "sender" not in body
    assert "recipient" not in body
    assert body["follower"] == {"id": "oa-follower-schema-1"}
    assert event["external_uid"] == "oa-follower-schema-1"
    assert event["app_scoped_uid"] == "app-follower-schema-1"
    assert event["oa_id"] == "oa-test-1"

    body["oa_id"] = "another-oa"
    with pytest.raises(zalo_channel.ZaloSignatureError, match="OA does not match"):
        zalo_channel.normalize_event(body, raw)


@pytest.mark.asyncio
async def test_follow_without_cross_app_identity_stays_unlinked_with_reason(monkeypatch):
    _enable_oa(monkeypatch)
    from accounts import authenticate_zalo_account
    import zalo_channel

    user = await authenticate_zalo_account("app-follow-missing-1", "Missing Cross ID")
    attempt = await zalo_channel.start_channel_link(user["user_id"])
    body, raw, signature = _signed_event(
        event_name="follow",
        message_id="follow-missing-cross-id-1",
        uid="oa-follow-missing-1",
    )
    zalo_channel.verify_webhook(raw, body, signature)
    result = await zalo_channel.record_event(zalo_channel.normalize_event(body, raw))

    assert result["link"] == {
        "status": "not_linked",
        "reason": "missing_user_id_by_app",
    }
    assert (await zalo_channel.get_channel_link(
        user["user_id"], attempt["attempt_id"]
    ))["status"] == "pending"


@pytest.mark.asyncio
async def test_existing_follower_v3_mapping_links_pending_zalo_account(monkeypatch):
    _enable_oa(monkeypatch)
    from accounts import authenticate_zalo_account
    import zalo_channel
    import zalo_oa_api

    user = await authenticate_zalo_account("app-existing-follower-1", "Existing Follower")
    attempt = await zalo_channel.start_channel_link(user["user_id"])

    async def fake_find_existing_follower(app_scoped_uid):
        assert app_scoped_uid == "app-existing-follower-1"
        return {
            "external_uid": "oa-existing-follower-1",
            "app_scoped_uid": app_scoped_uid,
        }

    monkeypatch.setattr(
        zalo_oa_api, "find_existing_follower", fake_find_existing_follower
    )
    result = await zalo_channel.recover_existing_follower_link(
        user["user_id"], attempt["attempt_id"]
    )

    assert result == {"status": "linked", "user_id": user["user_id"]}
    status = await zalo_channel.get_channel_link(user["user_id"], attempt["attempt_id"])
    assert status["status"] == "linked"
    assert status["link_method"] == "oa_user_api"
    storage = await zalo_channel.get_channel_storage_for_test()
    assert storage["identities"][0]["external_uid"] == "oa-existing-follower-1"
    assert storage["identities"][0]["app_scoped_uid"] == "app-existing-follower-1"


@pytest.mark.asyncio
async def test_v3_follower_scan_matches_user_id_by_app(monkeypatch, tmp_path):
    _enable_oa(monkeypatch)
    from config import config
    import zalo_oa_api

    monkeypatch.setattr(config, "ZALO_OA_ACCESS_TOKEN", "access-test")
    monkeypatch.setattr(config, "ZALO_OA_REFRESH_TOKEN", "refresh-test")
    monkeypatch.setattr(config, "ZALO_APP_SECRET", "app-secret-test")
    monkeypatch.setattr(config, "ZALO_OA_TOKEN_STORE_PATH", str(tmp_path / "token.json"))
    monkeypatch.setattr(config, "ZALO_OA_RECOVERY_MAX_USERS", 50)

    async def fake_api_get(path, data, **_kwargs):
        if path == "user/getlist":
            return {
                "total": 2,
                "users": [{"user_id": "oa-other"}, {"user_id": "oa-match"}],
            }
        return {
            "user_id": data["user_id"],
            "user_id_by_app": (
                "app-existing-follower-2" if data["user_id"] == "oa-match" else "other-app"
            ),
            "user_is_follower": True,
        }

    monkeypatch.setattr(zalo_oa_api, "_api_get", fake_api_get)
    result = await zalo_oa_api.find_existing_follower("app-existing-follower-2")
    assert result == {
        "external_uid": "oa-match",
        "app_scoped_uid": "app-existing-follower-2",
    }


@pytest.mark.asyncio
async def test_v3_follower_scan_does_not_cache_transient_miss(monkeypatch, tmp_path):
    _enable_oa(monkeypatch)
    from config import config
    import zalo_oa_api

    monkeypatch.setattr(config, "ZALO_OA_ACCESS_TOKEN", "access-test")
    monkeypatch.setattr(config, "ZALO_OA_REFRESH_TOKEN", "refresh-test")
    monkeypatch.setattr(config, "ZALO_APP_SECRET", "app-secret-test")
    monkeypatch.setattr(config, "ZALO_OA_TOKEN_STORE_PATH", str(tmp_path / "token.json"))
    monkeypatch.setattr(config, "ZALO_OA_RECOVERY_MAX_USERS", 50)
    scans = 0

    async def fake_api_get(path, data, **_kwargs):
        nonlocal scans
        if path == "user/getlist":
            scans += 1
            return {"total": 1, "users": [{"user_id": "oa-match"}]}
        return {
            "user_id": data["user_id"],
            "user_id_by_app": (
                "app-retry-follower" if scans > 1 else "temporarily-unavailable"
            ),
            "user_is_follower": True,
        }

    monkeypatch.setattr(zalo_oa_api, "_api_get", fake_api_get)
    assert await zalo_oa_api.find_existing_follower("app-retry-follower") is None
    assert await zalo_oa_api.find_existing_follower("app-retry-follower") == {
        "external_uid": "oa-match",
        "app_scoped_uid": "app-retry-follower",
    }
    assert scans == 2


@pytest.mark.asyncio
async def test_oa_api_retries_provider_burst_limit(monkeypatch):
    import zalo_oa_api

    responses = [
        {"error": -32, "message": "rate limited"},
        {"error": 0, "message": "Success", "data": {"users": []}},
    ]
    sleeps = []

    class FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return FakeResponse(responses.pop(0))

    async def fake_access_token(**_kwargs):
        return "access-test"

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(zalo_oa_api.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(zalo_oa_api, "_access_token", fake_access_token)
    monkeypatch.setattr(zalo_oa_api.asyncio, "sleep", fake_sleep)

    assert await zalo_oa_api._api_get("user/getlist", {"offset": 0}) == {
        "users": [],
    }
    assert sleeps == [1.0]


@pytest.mark.asyncio
async def test_oa_signature_fails_closed_and_unlinked_events_remain_durable(monkeypatch):
    _enable_oa(monkeypatch)
    import zalo_channel

    body, raw, signature = _signed_event(message_id="normal-message-1")
    with pytest.raises(zalo_channel.ZaloSignatureError):
        zalo_channel.verify_webhook(raw, body, "mac=wrong")
    zalo_channel.verify_webhook(raw, body, signature)
    outcome = await zalo_channel.record_event(zalo_channel.normalize_event(body, raw))
    assert outcome == {"accepted": True, "duplicate": False, "link": None}
    stored = await zalo_channel.get_channel_storage_for_test()
    assert stored["events"][0]["status"] == "received"

    from config import config
    monkeypatch.setattr(config, "ZALO_OA_SECRET", "")
    with pytest.raises(zalo_channel.ZaloChannelError, match="not configured"):
        zalo_channel.verify_webhook(raw, body, signature)


def test_webhook_http_acknowledges_invalid_signature_without_creating_event(monkeypatch):
    _enable_oa(monkeypatch)
    from config import config
    from main import app

    body, raw, _ = _signed_event(message_id="http-invalid-1")
    headers = {
        "Content-Type": "application/json",
        "X-ZEvent-Signature": "mac=wrong",
        **({"X-API-Key": config.AGENT_API_KEY} if config.AGENT_API_KEY else {}),
    }
    client = TestClient(app)
    response = client.post("/api/agent/zalo/webhook", content=raw, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "accepted": False, "duplicate": False}

    import zalo_channel
    assert zalo_channel._mem_events == {}


def test_zalo_http_callback_sets_only_existing_opaque_account_cookie(monkeypatch):
    _enable_login(monkeypatch)
    from config import config
    from main import app
    import zalo_auth

    async def fake_profile(code, verifier):
        assert code == "http-authorization-code"
        return {"subject": "http-zalo-user", "display_name": "HTTP Zalo", "avatar_url": None}

    monkeypatch.setattr(zalo_auth, "_zalo_profile", fake_profile)
    api_headers = {"X-API-Key": config.AGENT_API_KEY} if config.AGENT_API_KEY else {}
    client = TestClient(app)
    assert client.post("/api/agent/auth/anonymous", headers=api_headers).status_code == 200
    blocked = client.post(
        "/api/agent/auth/zalo/start",
        headers=api_headers,
        json={"intent": "login", "return_to": "/"},
    )
    assert blocked.status_code == 403
    headers = {**api_headers, "X-CSRF-Token": client.cookies.get("aa_csrf")}
    started = client.post(
        "/api/agent/auth/zalo/start",
        headers=headers,
        json={"intent": "login", "return_to": "/"},
    )
    assert started.status_code == 200
    assert "access_token" not in started.text
    state = parse_qs(urlparse(started.json()["authorization_url"]).query)["state"][0]
    callback = client.get(
        "/api/agent/auth/zalo/callback",
        params={"code": "http-authorization-code", "state": state},
        headers=api_headers,
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"].endswith("?auth=zalo_success")
    cookies = callback.headers.get("set-cookie", "")
    assert "aa_account=" in cookies and "HttpOnly" in cookies
    assert "http-authorization-code" not in cookies
    assert "access_token" not in cookies
    me = client.get("/api/agent/auth/me", headers=api_headers).json()
    assert me["authenticated"] is True
    assert me["user"]["providers"] == ["zalo"]
