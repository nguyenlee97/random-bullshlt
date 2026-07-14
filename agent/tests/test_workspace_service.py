import pytest

from workspace import dependencies
from workspace import service


@pytest.fixture(autouse=True)
def isolated_workspace_store(monkeypatch):
    monkeypatch.setattr(service, "_mongo_ok", False)
    service._mem_workspaces.clear()
    service._mem_proposals.clear()
    service._locks.clear()


def test_dependency_closure_is_selective_and_deterministic():
    assert dependencies.downstream("audience") == [
        "targeting", "forecast", "order_draft", "order", "report"
    ]
    assert "creative" not in dependencies.downstream("audience")


@pytest.mark.asyncio
async def test_stale_revision_cannot_overwrite_newer_workspace():
    initial = await service.get_workspace("ws-conflict")
    first = await service.apply_mutation(
        "ws-conflict", "brief", {"brand": "A"}, base_revision=initial["revision"],
        actor="user", idempotency_key="first",
    )
    assert first["workspace_revision"] == 1

    with pytest.raises(service.WorkspaceConflict) as error:
        await service.apply_mutation(
            "ws-conflict", "brief", {"brand": "B"}, base_revision=0,
            actor="user", idempotency_key="second",
        )
    assert error.value.actual == 1
    workspace = await service.get_workspace("ws-conflict")
    assert workspace["artifacts"]["brief"]["value"] == {"brand": "A"}


@pytest.mark.asyncio
async def test_nested_field_mutation_preserves_the_rest_of_the_artifact():
    await service.apply_mutation(
        "ws-nested", "brief", {"brand": "A", "budget": 10},
        base_revision=0, actor="user", idempotency_key="whole",
    )
    await service.apply_mutation(
        "ws-nested", "brief.budget", 20,
        base_revision=1, actor="user", idempotency_key="budget",
    )
    workspace = await service.get_workspace("ws-nested")
    assert workspace["artifacts"]["brief"]["value"] == {
        "brand": "A", "budget": 20,
    }


@pytest.mark.asyncio
async def test_mutation_is_idempotent_and_invalidates_only_existing_dependents():
    initial = await service.get_workspace("ws-idempotent")
    one = await service.apply_mutation(
        "ws-idempotent", "segment", {"attrs": [{"_id": "x"}]},
        base_revision=initial["revision"], actor="user", idempotency_key="same",
    )
    duplicate = await service.apply_mutation(
        "ws-idempotent", "segment", {"attrs": [{"_id": "x"}]},
        base_revision=initial["revision"], actor="user", idempotency_key="same",
    )
    assert duplicate["workspace_revision"] == one["workspace_revision"]
    assert duplicate["duplicate"] is True


@pytest.mark.asyncio
async def test_proposal_approval_uses_proposal_revision_and_is_idempotent():
    workspace = await service.get_workspace("ws-proposal")
    proposal = await service.create_proposal(
        "ws-proposal", "brief", {"brand": "Approved"},
        base_revision=workspace["revision"], actor="copilot", reason="requested edit",
    )
    first = await service.approve_proposal(proposal["proposal_id"], actor="user")
    second = await service.approve_proposal(proposal["proposal_id"], actor="user")
    assert first["workspace_revision"] == second["workspace_revision"] == 1
    assert second["duplicate"] is True


@pytest.mark.asyncio
async def test_rejected_proposal_never_mutates_workspace():
    workspace = await service.get_workspace("ws-reject")
    proposal = await service.create_proposal(
        "ws-reject", "brief", {"brand": "Do not apply"},
        base_revision=0, actor="copilot", reason="proposal",
    )
    await service.reject_proposal(proposal["proposal_id"], actor="user", reason="wrong brand")
    with pytest.raises(ValueError):
        await service.approve_proposal(proposal["proposal_id"], actor="user")
    latest = await service.get_workspace("ws-reject")
    assert latest["revision"] == workspace["revision"] == 0


@pytest.mark.asyncio
async def test_graph_context_uses_canonical_artifacts_for_stale_client_snapshot():
    from graph.nodes.agent_node import context_node

    await service.apply_mutation(
        "ws-context", "brief", {"brand": "Server New"},
        base_revision=0, actor="user", idempotency_key="server",
    )
    result = await context_node({
        "session_id": "ws-context",
        "step": 0,
        "user_message": "brand hiện tại là gì?",
        "workspace": {"brief": {"brand": "Client Old"}},
        "workspace_revision": 0,
        "confirmed_steps": [],
        "workspace_events": [],
    })

    assert result["workspace_revision"] == 1
    assert result["workspace"]["brief"]["brand"] == "Server New"
    assert "Client snapshot is stale" in result["messages"][1]["content"]


@pytest.mark.asyncio
async def test_graph_context_keeps_unsaved_client_edits_at_current_revision():
    from graph.nodes.agent_node import context_node

    await service.apply_mutation(
        "ws-current-context", "brief", {"brand": "Server"},
        base_revision=0, actor="user", idempotency_key="server",
    )
    result = await context_node({
        "session_id": "ws-current-context",
        "step": 0,
        "user_message": "đổi brand",
        "workspace": {"brief": {"brand": "Unsaved Client Edit"}},
        "workspace_revision": 1,
        "confirmed_steps": [],
        "workspace_events": ["brand edited locally"],
    })

    assert result["workspace"]["brief"]["brand"] == "Unsaved Client Edit"
