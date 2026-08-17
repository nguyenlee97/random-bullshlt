import pytest


@pytest.mark.asyncio
async def test_new_conversation_persists_immutable_openai_model_fields():
    from campaign_models import OPENAI_GPT_5_4_MINI
    from identity import bootstrap_anonymous, create_conversation, get_conversation

    owner = await bootstrap_anonymous()
    created = await create_conversation(
        owner["identity_id"],
        experience_mode="guided",
        conversation_model=OPENAI_GPT_5_4_MINI,
    )
    restored = await get_conversation(owner["identity_id"], created["conversation_id"])

    assert restored["conversation_model"] == OPENAI_GPT_5_4_MINI
    assert restored["conversation_model_version"] == "gpt-5.4-mini"
    assert restored["conversation_model_locked_at"] is not None


@pytest.mark.asyncio
async def test_legacy_conversation_is_migration_locked_to_greennode():
    import identity
    from campaign_models import GREENNODE_MINIMAX
    from identity import (
        bootstrap_anonymous,
        create_conversation,
        get_conversation_model_for_session,
    )

    owner = await bootstrap_anonymous()
    created = await create_conversation(owner["identity_id"])
    private = identity._mem_conversations[created["conversation_id"]]
    private.pop("conversation_model", None)
    private.pop("conversation_model_version", None)
    private.pop("conversation_model_locked_at", None)

    lock = await get_conversation_model_for_session(created["session_id"])

    assert lock["conversation_model"] == GREENNODE_MINIMAX
    assert lock["legacy_session"] is True
    assert private["conversation_model"] == GREENNODE_MINIMAX


def test_conversation_model_rejects_unknown_value():
    from campaign_models import normalize_conversation_model

    with pytest.raises(ValueError, match="unsupported conversation_model"):
        normalize_conversation_model("silent-provider-fallback")


@pytest.mark.asyncio
async def test_dispatcher_calls_only_the_locked_engine():
    from campaign_engines.dispatcher import dispatch_freeform
    from campaign_models import GREENNODE_MINIMAX, OPENAI_GPT_5_4_MINI

    calls = []

    async def green(**kwargs):
        calls.append(("green", kwargs["message"]))
        return "green-result"

    async def openai(**kwargs):
        calls.append(("openai", kwargs["message"]))
        return "openai-result"

    assert await dispatch_freeform(
        GREENNODE_MINIMAX,
        greennode_handler=green,
        openai_handler=openai,
        message="first",
    ) == "green-result"
    assert calls == [("green", "first")]

    calls.clear()
    assert await dispatch_freeform(
        OPENAI_GPT_5_4_MINI,
        greennode_handler=green,
        openai_handler=openai,
        message="second",
    ) == "openai-result"
    assert calls == [("openai", "second")]


@pytest.mark.asyncio
async def test_openai_failure_never_falls_back_to_greennode():
    from campaign_engines.dispatcher import dispatch_freeform
    from campaign_models import OPENAI_GPT_5_4_MINI

    green_called = False

    async def green(**kwargs):
        nonlocal green_called
        green_called = True

    async def openai(**kwargs):
        raise RuntimeError("openai unavailable")

    with pytest.raises(RuntimeError, match="openai unavailable"):
        await dispatch_freeform(
            OPENAI_GPT_5_4_MINI,
            greennode_handler=green,
            openai_handler=openai,
            message="do not switch",
        )
    assert green_called is False


@pytest.mark.asyncio
async def test_autopilot_run_copies_conversation_model_lock():
    from autopilot.service import create_run
    from campaign_models import OPENAI_GPT_5_4_MINI
    from identity import bootstrap_anonymous, create_conversation
    from workspace.service import apply_mutation, get_workspace

    owner = await bootstrap_anonymous()
    conversation = await create_conversation(
        owner["identity_id"],
        experience_mode="autopilot",
        conversation_model=OPENAI_GPT_5_4_MINI,
    )
    workspace = await get_workspace(conversation["session_id"])
    await apply_mutation(
        conversation["session_id"],
        "brief",
        {
            "brand": "Model Lock",
            "objective": "awareness",
            "budget": 10,
            "kpi": "Reach",
            "startDate": "2026-07-22",
            "endDate": "2026-07-30",
            "notes": "",
        },
        base_revision=workspace["revision"],
        actor="test",
        idempotency_key="model-lock-brief",
    )

    run = await create_run(
        conversation["session_id"],
        creative_source="upload",
        idempotency_key="model-lock-run",
    )

    assert run["conversation_id"] == conversation["conversation_id"]
    assert run["conversation_model"] == OPENAI_GPT_5_4_MINI
    assert run["conversation_model_version"] == "gpt-5.4-mini"
