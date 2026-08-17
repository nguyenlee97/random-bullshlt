import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient


EMAIL = "owner@example.com"
PASSWORD = "correct horse battery"


async def _account(email=EMAIL, name="Nguyen An"):
    from accounts import create_account_session, create_local_account
    from identity import resolve_actor

    user = await create_local_account(email, PASSWORD, name)
    session = await create_account_session(user["user_id"], user_agent_label="Browser B")
    actor = await resolve_actor(session["token"], None)
    return user, session, actor


@pytest.mark.asyncio
async def test_registration_stores_argon2id_and_never_plaintext_or_public_hashes():
    from accounts import create_local_account, get_account_storage_for_test

    user = await create_local_account("  Owner@Example.COM ", PASSWORD, "  Nguyen   An  ")
    stored = await get_account_storage_for_test()

    assert user["email"] == EMAIL
    assert user["display_name"] == "Nguyen An"
    assert "password" not in user
    assert stored["identities"][0]["password_hash"].startswith("$argon2id$")
    assert stored["identities"][0]["password_hash"] != PASSWORD
    assert PASSWORD not in repr(stored["sessions"])


@pytest.mark.asyncio
async def test_duplicate_email_normalization_and_generic_login_failures():
    from accounts import (
        AccountConflict,
        InvalidCredentials,
        authenticate_local_account,
        create_local_account,
    )

    await create_local_account(EMAIL, PASSWORD, "Owner")
    with pytest.raises(AccountConflict):
        await create_local_account(" OWNER@example.COM ", PASSWORD, "Duplicate")
    with pytest.raises(InvalidCredentials, match="invalid email or password"):
        await authenticate_local_account(EMAIL, "wrong password")
    with pytest.raises(InvalidCredentials, match="invalid email or password"):
        await authenticate_local_account("missing@example.com", "wrong password")


@pytest.mark.asyncio
async def test_disabled_user_cannot_login_and_sessions_are_hashed_revocable_and_expiring():
    from accounts import (
        AccountDisabled,
        authenticate_local_account,
        create_account_session,
        create_local_account,
        get_account_storage_for_test,
        require_account_session,
        revoke_account_session,
    )

    user = await create_local_account(EMAIL, PASSWORD, "Owner")
    session = await create_account_session(user["user_id"])
    stored = await get_account_storage_for_test()
    stored_session = stored["sessions"][0]
    assert session["token"].startswith("aa_acct_")
    assert stored_session["token_hash"] != session["token"]
    assert session["token"] not in repr(stored_session)
    assert (await require_account_session(session["token"]))["user"]["user_id"] == user["user_id"]

    assert await revoke_account_session(user["user_id"], session["session_id"])
    with pytest.raises(PermissionError):
        await require_account_session(session["token"])

    fresh = await create_account_session(user["user_id"])
    refreshed_storage = await get_account_storage_for_test()
    next(item for item in refreshed_storage["sessions"] if item["session_id"] == fresh["session_id"])["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(PermissionError):
        await require_account_session(fresh["token"])

    enabled_session = await create_account_session(user["user_id"])
    next(item for item in stored["users"] if item["user_id"] == user["user_id"])["status"] = "disabled"
    with pytest.raises(AccountDisabled):
        await authenticate_local_account(EMAIL, PASSWORD)
    with pytest.raises(PermissionError):
        await require_account_session(enabled_session["token"])


@pytest.mark.asyncio
async def test_second_session_can_be_listed_and_revoked_without_revoking_current():
    from accounts import (
        create_account_session,
        create_local_account,
        list_account_sessions,
        require_account_session,
        revoke_account_session,
    )

    user = await create_local_account(EMAIL, PASSWORD, "Owner")
    current = await create_account_session(user["user_id"], user_agent_label="Browser A")
    other = await create_account_session(user["user_id"], user_agent_label="Browser B")
    sessions = await list_account_sessions(
        user["user_id"], current_session_id=current["session_id"]
    )
    assert {item["session_id"] for item in sessions} == {
        current["session_id"], other["session_id"],
    }
    assert next(item for item in sessions if item["session_id"] == current["session_id"])["current"] is True
    assert await revoke_account_session(user["user_id"], other["session_id"])
    with pytest.raises(PermissionError):
        await require_account_session(other["token"])
    assert (await require_account_session(current["token"]))["user"]["user_id"] == user["user_id"]


@pytest.mark.asyncio
async def test_explicit_claim_preserves_ids_transcript_workspace_proposal_job_and_run():
    from accounts import create_account_session, create_local_account
    from autopilot.service import create_run
    from creative_intel.service import enqueue_analysis
    from identity import (
        bootstrap_anonymous,
        claim_conversation,
        create_conversation,
        get_conversation,
        require_session_access,
        resolve_actor,
    )
    from session import add_message
    from workspace.service import apply_mutation, create_proposal, get_workspace

    anonymous = await bootstrap_anonymous()
    anon_actor = await resolve_actor(None, anonymous["token"])
    conversation = await create_conversation(anon_actor, experience_mode="autopilot")
    sid = conversation["session_id"]
    await add_message(sid, "user", "preserve this transcript")
    workspace = await get_workspace(sid)
    brief = {
        "brand": "Claimed Campaign", "objective": "awareness", "budget": 5,
        "startDate": "2026-07-18", "endDate": "2026-07-20", "kpi": "Reach",
    }
    await apply_mutation(
        sid, "brief", brief, base_revision=workspace["revision"], actor="test",
        idempotency_key="claim:brief",
    )
    workspace = await get_workspace(sid)
    run = await create_run(sid, creative_source="upload", idempotency_key="claim:run")
    workspace = await get_workspace(sid)
    proposal = await create_proposal(
        sid, "brief.notes", "Keep proposal", base_revision=workspace["revision"],
        actor="test", reason="claim preservation",
    )
    jobs = await enqueue_analysis(sid, [{
        "id": "creative-claim", "name": "claim.png", "type": "image/png",
        "size": 123, "width": 300, "height": 250,
        "url": "http://backend:3000/uploads/claim.png",
    }])
    user = await create_local_account(EMAIL, PASSWORD, "Owner")
    account_session = await create_account_session(user["user_id"])
    claim_actor = await resolve_actor(account_session["token"], anonymous["token"])
    claimed = await claim_conversation(claim_actor, conversation["conversation_id"])

    assert claimed["conversation_id"] == conversation["conversation_id"]
    assert claimed["session_id"] == sid
    assert claimed["ownership"] == "account"
    assert claimed["can_claim"] is False
    restored = await get_conversation(claim_actor, conversation["conversation_id"])
    assert restored["messages"][0]["content"] == "preserve this transcript"
    assert restored["workspace"]["revision"] == workspace["revision"]
    assert restored["pending_proposals"][0]["proposal_id"] == proposal["proposal_id"]
    assert restored["latest_run"]["run_id"] == run["run_id"]
    assert jobs[0]["session_id"] == sid

    with pytest.raises(PermissionError):
        await require_session_access(anon_actor, sid)
    with pytest.raises(KeyError):
        await get_conversation(anon_actor, conversation["conversation_id"])


@pytest.mark.asyncio
async def test_cross_device_resume_and_foreign_account_claim_read_mutation_are_denied():
    from accounts import create_account_session, create_local_account
    from identity import (
        archive_conversation,
        bootstrap_anonymous,
        claim_conversation,
        create_conversation,
        get_conversation,
        resolve_actor,
    )

    anonymous = await bootstrap_anonymous()
    anon_actor = await resolve_actor(None, anonymous["token"])
    conversation = await create_conversation(anon_actor, experience_mode="guided")
    owner = await create_local_account(EMAIL, PASSWORD, "Owner")
    owner_a = await create_account_session(owner["user_id"])
    claim_actor = await resolve_actor(owner_a["token"], anonymous["token"])
    await claim_conversation(claim_actor, conversation["conversation_id"])

    owner_b = await create_account_session(owner["user_id"])
    browser_b = await resolve_actor(owner_b["token"], None)
    restored = await get_conversation(browser_b, conversation["conversation_id"])
    assert restored["session_id"] == conversation["session_id"]

    foreign = await create_local_account("foreign@example.com", PASSWORD, "Foreign")
    foreign_session = await create_account_session(foreign["user_id"])
    foreign_actor = await resolve_actor(foreign_session["token"], anonymous["token"])
    with pytest.raises(KeyError):
        await claim_conversation(foreign_actor, conversation["conversation_id"])
    with pytest.raises(KeyError):
        await get_conversation(foreign_actor, conversation["conversation_id"])
    with pytest.raises(KeyError):
        await archive_conversation(foreign_actor, conversation["conversation_id"])


@pytest.mark.asyncio
async def test_claim_race_has_one_owner_and_same_owner_retry_is_idempotent():
    from accounts import create_account_session, create_local_account
    from identity import bootstrap_anonymous, claim_conversation, create_conversation, resolve_actor

    anonymous = await bootstrap_anonymous()
    anon_actor = await resolve_actor(None, anonymous["token"])
    conversation = await create_conversation(anon_actor)
    first, first_session, _ = await _account(EMAIL, "First")
    second = await create_local_account("second@example.com", PASSWORD, "Second")
    second_session = await create_account_session(second["user_id"])
    actor_one = await resolve_actor(first_session["token"], anonymous["token"])
    actor_two = await resolve_actor(second_session["token"], anonymous["token"])

    results = await asyncio.gather(
        claim_conversation(actor_one, conversation["conversation_id"]),
        claim_conversation(actor_two, conversation["conversation_id"]),
        return_exceptions=True,
    )
    winners = [item for item in results if isinstance(item, dict)]
    losers = [item for item in results if isinstance(item, Exception)]
    assert len(winners) == 1
    assert len(losers) == 1 and isinstance(losers[0], KeyError)
    winner_actor = actor_one if not isinstance(results[0], Exception) else actor_two
    retried = await claim_conversation(winner_actor, conversation["conversation_id"])
    assert retried["conversation_id"] == conversation["conversation_id"]


def test_http_auth_cookies_csrf_logout_and_generic_login_errors():
    from config import config
    from main import app

    api_headers = {"X-API-Key": config.AGENT_API_KEY} if config.AGENT_API_KEY else {}
    client = TestClient(app)
    bootstrap = client.post("/api/agent/auth/anonymous", headers=api_headers)
    assert bootstrap.status_code == 200
    csrf = client.cookies.get("aa_csrf")
    assert csrf
    assert "aa_anonymous=" in bootstrap.headers.get("set-cookie", "")

    blocked = client.post(
        "/api/agent/auth/register",
        headers={**api_headers, "X-CSRF-Token": "stale-browser-token"},
        json={"email": EMAIL, "password": PASSWORD, "display_name": "Owner"},
    )
    assert blocked.status_code == 403
    refreshed_csrf = client.cookies.get("aa_csrf")
    assert refreshed_csrf and refreshed_csrf != csrf
    assert "aa_csrf=" in blocked.headers.get("set-cookie", "")

    headers = {**api_headers, "X-CSRF-Token": refreshed_csrf}
    registered = client.post(
        "/api/agent/auth/register",
        headers=headers,
        json={"email": EMAIL, "password": PASSWORD, "display_name": "Owner"},
    )
    assert registered.status_code == 201
    assert "aa_account=" in registered.headers.get("set-cookie", "")
    assert "HttpOnly" in registered.headers.get("set-cookie", "")
    assert "token" not in registered.text
    assert "password" not in registered.text
    me = client.get("/api/agent/auth/me", headers=api_headers)
    assert me.json()["authenticated"] is True

    logout = client.post("/api/agent/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert client.get("/api/agent/auth/me", headers=api_headers).json()["authenticated"] is False

    wrong = client.post(
        "/api/agent/auth/login", headers=headers,
        json={"email": EMAIL, "password": "wrong password"},
    )
    missing = client.post(
        "/api/agent/auth/login", headers=headers,
        json={"email": "missing@example.com", "password": "wrong password"},
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
