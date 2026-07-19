import pytest
from starlette.requests import Request
from starlette.responses import Response


BRIEF = {
    "brand": "Mixifood",
    "objective": "consideration",
    "budget": 5,
    "kpi": "CTR > 1%",
    "startDate": "2026-07-18",
    "endDate": "2026-07-20",
    "notes": "Bán khô gà",
}


@pytest.mark.asyncio
async def test_anonymous_token_is_stable_and_not_exposed_on_resume():
    from identity import bootstrap_anonymous

    created = await bootstrap_anonymous()
    assert created["token"].startswith("aa_anon_")
    resumed = await bootstrap_anonymous(created["token"])
    assert resumed == {"identity_id": created["identity_id"], "is_new": False}


@pytest.mark.asyncio
async def test_http_bootstrap_issues_httponly_cookie_and_hides_raw_token():
    from router import anonymous_bootstrap

    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    response = Response()
    payload = await anonymous_bootstrap(request, response)

    cookie = response.headers["set-cookie"]
    assert "aa_anonymous=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "token" not in payload


@pytest.mark.asyncio
async def test_conversations_are_owned_and_archive_is_non_destructive():
    from identity import (
        archive_conversation,
        bootstrap_anonymous,
        create_conversation,
        get_conversation,
        list_conversations,
    )

    owner = await bootstrap_anonymous()
    stranger = await bootstrap_anonymous()
    conversation = await create_conversation(owner["identity_id"])

    with pytest.raises(KeyError):
        await get_conversation(stranger["identity_id"], conversation["conversation_id"])

    assert len(await list_conversations(owner["identity_id"])) == 1
    await archive_conversation(owner["identity_id"], conversation["conversation_id"])
    assert await list_conversations(owner["identity_id"]) == []
    archived = await list_conversations(owner["identity_id"], include_archived=True)
    assert archived[0]["session_id"] == conversation["session_id"]


@pytest.mark.asyncio
async def test_delete_conversation_removes_owned_history_and_session_artifacts():
    from identity import (
        bootstrap_anonymous,
        create_conversation,
        delete_conversation,
        get_conversation,
        list_conversations,
    )
    from session import add_message

    identity = await bootstrap_anonymous()
    removed = await create_conversation(identity["identity_id"], title="Remove me")
    kept = await create_conversation(identity["identity_id"], title="Keep me")
    await add_message(removed["session_id"], "user", "secret brief")

    result = await delete_conversation(
        identity["identity_id"], removed["conversation_id"]
    )

    assert result["ok"] is True
    assert result["orders_retained"] is True
    assert result["deleted_artifacts"]["agent_sessions"] == 1
    conversations = await list_conversations(identity["identity_id"])
    assert [item["conversation_id"] for item in conversations] == [kept["conversation_id"]]
    with pytest.raises(KeyError):
        await get_conversation(identity["identity_id"], removed["conversation_id"])


@pytest.mark.asyncio
async def test_delete_all_conversations_includes_archived_items():
    from identity import (
        archive_conversation,
        bootstrap_anonymous,
        create_conversation,
        delete_all_conversations,
        list_conversations,
    )

    identity = await bootstrap_anonymous()
    first = await create_conversation(identity["identity_id"])
    await create_conversation(identity["identity_id"])
    await archive_conversation(identity["identity_id"], first["conversation_id"])

    result = await delete_all_conversations(identity["identity_id"])

    assert result["deleted_count"] == 2
    assert result["orders_retained"] is True
    assert await list_conversations(identity["identity_id"], include_archived=True) == []


@pytest.mark.asyncio
async def test_delete_rejects_non_terminal_autopilot_run():
    from autopilot.service import create_run
    from identity import (
        ConversationRunActive,
        bootstrap_anonymous,
        create_conversation,
        delete_conversation,
        list_conversations,
    )
    from workspace.service import apply_mutation, get_workspace

    identity = await bootstrap_anonymous()
    conversation = await create_conversation(
        identity["identity_id"], experience_mode="autopilot"
    )
    workspace = await get_workspace(conversation["session_id"])
    await apply_mutation(
        conversation["session_id"], "brief", BRIEF,
        base_revision=workspace["revision"], actor="test",
        idempotency_key="delete-active-run:brief",
    )
    await create_run(
        conversation["session_id"], creative_source="ai_generate",
        idempotency_key="delete-active-run",
    )

    with pytest.raises(ConversationRunActive, match="Autopilot đang chạy"):
        await delete_conversation(identity["identity_id"], conversation["conversation_id"])
    assert len(await list_conversations(identity["identity_id"])) == 1


@pytest.mark.asyncio
async def test_explicit_homepage_mode_is_not_overwritten_by_legacy_workspace_default():
    from identity import bootstrap_anonymous, create_conversation, get_conversation

    identity = await bootstrap_anonymous()
    conversation = await create_conversation(
        identity["identity_id"], experience_mode="autopilot"
    )

    restored = await get_conversation(
        identity["identity_id"], conversation["conversation_id"]
    )
    assert restored["experience_mode"] == "autopilot"
    assert restored["workspace"]["experience_mode"] == "guided"


@pytest.mark.asyncio
async def test_resume_exposes_server_derived_guided_order_and_report_progress():
    from identity import bootstrap_anonymous, create_conversation, get_conversation
    from session import update_form_state, update_order_ids

    identity = await bootstrap_anonymous()
    conversation = await create_conversation(
        identity["identity_id"], experience_mode="guided"
    )
    session_id = conversation["session_id"]
    await update_order_ids(session_id, ["ORD-RESUME-001"])
    await update_form_state(
        session_id,
        "report_context",
        {"campaignId": "ORD-RESUME-001", "gen_status": "generating"},
        sync_workspace=False,
    )

    restored = await get_conversation(
        identity["identity_id"], conversation["conversation_id"]
    )
    assert restored["workflow_progress"] == {
        "order_created": True,
        "report_started": True,
        "report_campaign_id": "ORD-RESUME-001",
    }


@pytest.mark.asyncio
async def test_owned_session_rejects_missing_and_foreign_identity_tokens():
    from identity import (
        bootstrap_anonymous,
        create_conversation,
        require_session_access,
        resolve_actor,
    )

    owner = await bootstrap_anonymous()
    stranger = await bootstrap_anonymous()
    conversation = await create_conversation(owner["identity_id"])

    owner_actor = await resolve_actor(None, owner["token"])
    stranger_actor = await resolve_actor(None, stranger["token"])
    allowed = await require_session_access(owner_actor, conversation["session_id"])
    assert allowed["conversation_id"] == conversation["conversation_id"]
    with pytest.raises(PermissionError):
        await require_session_access(None, conversation["session_id"])
    with pytest.raises(PermissionError):
        await require_session_access(stranger_actor, conversation["session_id"])
    assert await require_session_access(None, "legacy-evaluator-session") is None


@pytest.mark.asyncio
async def test_resume_restores_full_transcript_workspace_pending_review_and_run():
    from autopilot.service import create_run
    from identity import bootstrap_anonymous, create_conversation, get_conversation
    from session import add_message, get_history
    from workspace.service import apply_mutation, create_proposal, get_workspace

    identity = await bootstrap_anonymous()
    conversation = await create_conversation(identity["identity_id"])
    sid = conversation["session_id"]

    workspace = await get_workspace(sid)
    await apply_mutation(
        sid, "brief", BRIEF, base_revision=workspace["revision"], actor="test",
        idempotency_key="identity-resume:brief",
    )
    run = await create_run(
        sid, creative_source="ai_generate", idempotency_key="identity-resume:run",
    )
    workspace = await get_workspace(sid)
    proposal = await create_proposal(
        sid, "brief.notes", "Ít cay", base_revision=workspace["revision"],
        actor="test", reason="User requested a change",
    )

    for index in range(25):
        await add_message(sid, "user" if index % 2 == 0 else "assistant", f"message {index}")

    # Model context stays bounded, while the UI transcript remains complete.
    assert len(await get_history(sid)) == 18
    restored = await get_conversation(identity["identity_id"], conversation["conversation_id"])
    assert len(restored["messages"]) == 25
    assert restored["workspace"]["artifacts"]["brief"]["value"]["brand"] == "Mixifood"
    assert restored["pending_proposals"][0]["proposal_id"] == proposal["proposal_id"]
    assert restored["latest_run"]["run_id"] == run["run_id"]
    assert restored["title"] == "Mixifood"


@pytest.mark.asyncio
async def test_history_includes_live_autopilot_summary_and_activity_ordering():
    from autopilot.service import _set_run, create_run
    from identity import bootstrap_anonymous, create_conversation, list_conversations
    from workspace.service import apply_mutation, get_workspace

    identity = await bootstrap_anonymous()
    autopilot = await create_conversation(
        identity["identity_id"], title="Zalo campaign", experience_mode="autopilot",
    )
    workspace = await get_workspace(autopilot["session_id"])
    await apply_mutation(
        autopilot["session_id"], "brief", BRIEF,
        base_revision=workspace["revision"], actor="zalo_campaign_operator",
        idempotency_key="history-zalo:brief",
    )
    run = await create_run(
        autopilot["session_id"], creative_source="ai_generate",
        idempotency_key="history-zalo:run",
    )
    later = await create_conversation(identity["identity_id"], title="Later campaign")

    await _set_run(run["run_id"], {"status": "running"})
    history = await list_conversations(identity["identity_id"])

    assert history[0]["conversation_id"] == autopilot["conversation_id"]
    summary = history[0]["latest_run_summary"]
    assert summary["run_id"] == run["run_id"]
    assert summary["status"] == "running"
    assert summary["task_total"] == 18
    assert summary["task_completed"] == 0
    assert "tasks" not in summary
    assert all(item["conversation_id"] != later["conversation_id"] for item in history[:1])
