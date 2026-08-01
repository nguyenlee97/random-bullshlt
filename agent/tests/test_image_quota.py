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
async def test_concurrent_reservations_never_exceed_daily_limit():
    actor = {"anonymous_id": "anon-concurrent"}
    reservations = await asyncio.gather(*(
        image_quota.reserve(actor, f"job-{index}", session_id="quota")
        for index in range(image_quota.DAILY_LIMIT + 20)
    ))
    accepted = [item for item in reservations if item.get("ok")]
    assert len(accepted) == image_quota.DAILY_LIMIT
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
    assert current["remaining"] == image_quota.DAILY_LIMIT - 1


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
    assert (
        await image_quota.status(account)
    )["remaining"] == image_quota.DAILY_LIMIT - 7
    accepted = []
    for index in range(image_quota.DAILY_LIMIT):
        accepted.append(await image_quota.reserve(account, f"user-{index}", session_id="quota"))
    assert sum(
        1 for item in accepted if item.get("ok")
    ) == image_quota.DAILY_LIMIT - 7


@pytest.mark.asyncio
async def test_quota_is_shared_across_sessions_for_same_actor():
    actor = {"user_id": "same-user"}
    await image_quota.reserve(actor, "session-a-job", session_id="session-a")
    await image_quota.succeed("session-a-job")
    assert (
        await image_quota.status(actor)
    )["remaining"] == image_quota.DAILY_LIMIT - 1


@pytest.mark.asyncio
async def test_generated_gallery_is_owner_and_session_scoped_and_keeps_final_crop():
    owner = {"user_id": "gallery-owner"}
    stranger = {"user_id": "gallery-stranger"}
    await image_quota.reserve(owner, "gallery-job", session_id="conversation-a", metadata={
        "format_id": "zuma-box", "width": 300, "height": 250,
    })
    await image_quota.succeed("gallery-job", {
        "raw_url": "https://example.test/uploads/raw.png", "width": 300, "height": 250,
    })

    jobs = await image_quota.list_session_jobs(owner, "conversation-a")
    assert [job["job_id"] for job in jobs] == ["gallery-job"]
    assert await image_quota.list_session_jobs(owner, "conversation-b") == []
    assert await image_quota.list_session_jobs(stranger, "conversation-a") == []
    assert "actor_key" not in jobs[0]
    assert (await image_quota.get_session_job(owner, "conversation-a", "gallery-job"))["job_id"] == "gallery-job"
    with pytest.raises(KeyError):
        await image_quota.get_session_job(stranger, "conversation-a", "gallery-job")

    finalized = await image_quota.merge_job_result(
        owner, "conversation-a", "gallery-job",
        {"final_url": "https://example.test/uploads/final.png"},
    )
    assert finalized["result"]["raw_url"].endswith("raw.png")
    assert finalized["result"]["final_url"].endswith("final.png")

    with pytest.raises(KeyError):
        await image_quota.merge_job_result(
            stranger, "conversation-a", "gallery-job", {"final_url": "bad"}
        )
