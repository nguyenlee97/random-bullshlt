import asyncio

import pytest

import image_quota


@pytest.fixture(autouse=True)
def clear_memory_quota(monkeypatch):
    image_quota._mem_jobs.clear()
    image_quota._mem_ledgers.clear()

    async def no_mongo():
        return None, None

    monkeypatch.setattr(image_quota, "_collections", no_mongo)


@pytest.mark.asyncio
async def test_concurrent_reservations_never_exceed_twenty():
    actor = {"anonymous_id": "anon-concurrent"}
    reservations = await asyncio.gather(*(
        image_quota.reserve(actor, f"job-{index}", session_id="quota")
        for index in range(40)
    ))
    accepted = [item for item in reservations if item.get("ok")]
    assert len(accepted) == 20
    assert (await image_quota.status(actor))["remaining"] == 0


@pytest.mark.asyncio
async def test_success_charges_one_output_and_release_restores_one():
    actor = {"anonymous_id": "anon-lifecycle"}
    await image_quota.reserve(actor, "success", session_id="quota")
    await image_quota.succeed("success", {"request_id": "req_1"})
    await image_quota.reserve(actor, "failure", session_id="quota")
    await image_quota.release("failure", "definitive validation failure")
    current = await image_quota.status(actor)
    assert current["used"] == 1
    assert current["succeeded"] == 1
    assert current["reserved"] == 0
    assert current["remaining"] == 19


@pytest.mark.asyncio
async def test_ambiguous_timeout_keeps_reservation_for_reconciliation():
    actor = {"anonymous_id": "anon-ambiguous"}
    await image_quota.reserve(actor, "ambiguous", session_id="quota")
    await image_quota.mark_ambiguous("ambiguous", "timeout")
    current = await image_quota.status(actor)
    assert current["used"] == 1
    assert current["reserved"] == 1
    duplicate = await image_quota.reserve(actor, "ambiguous", session_id="quota")
    assert duplicate["duplicate"] is True


@pytest.mark.asyncio
async def test_login_uses_stricter_combined_anonymous_and_account_usage():
    anonymous = {"anonymous_id": "device-before-login"}
    for index in range(7):
        await image_quota.reserve(anonymous, f"anon-{index}", session_id="quota")
        await image_quota.succeed(f"anon-{index}")
    account = {"user_id": "user-1", "anonymous_id": "device-before-login"}
    assert (await image_quota.status(account))["remaining"] == 13
    accepted = []
    for index in range(20):
        accepted.append(await image_quota.reserve(account, f"user-{index}", session_id="quota"))
    assert sum(1 for item in accepted if item.get("ok")) == 13


@pytest.mark.asyncio
async def test_quota_is_shared_across_sessions_for_same_actor():
    actor = {"user_id": "same-user"}
    await image_quota.reserve(actor, "session-a-job", session_id="session-a")
    await image_quota.succeed("session-a-job")
    assert (await image_quota.status(actor))["remaining"] == 19

