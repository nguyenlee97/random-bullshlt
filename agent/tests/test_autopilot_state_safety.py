from unittest.mock import AsyncMock

import pytest

from autopilot import service
from workspace.service import apply_mutation, get_workspace, set_preferences


BRIEF = {
    "brand": "State Safety",
    "objective": "awareness",
    "budget": 20,
    "startDate": "2026-08-01",
    "endDate": "2026-08-10",
}


async def _confirm_brief(session_id: str) -> None:
    workspace = await get_workspace(session_id)
    await apply_mutation(
        session_id,
        "brief",
        BRIEF,
        base_revision=workspace["revision"],
        actor="test",
        idempotency_key=f"{session_id}:brief",
    )


@pytest.mark.asyncio
async def test_creative_source_requires_a_confirmed_brief():
    with pytest.raises(ValueError, match="brief must be confirmed"):
        await set_preferences(
            "creative-before-brief",
            experience_mode="autopilot",
            approval_policy="critical_only",
            creative_source="upload",
        )


@pytest.mark.asyncio
async def test_uploaded_creative_cannot_use_fully_automatic_policy():
    await _confirm_brief("upload-policy")
    with pytest.raises(ValueError, match="auto_build_draft"):
        await set_preferences(
            "upload-policy",
            experience_mode="autopilot",
            approval_policy="auto_build_draft",
            creative_source="upload",
        )
    with pytest.raises(ValueError, match="auto_build_draft"):
        await service.create_run(
            "upload-policy",
            approval_policy="auto_build_draft",
            creative_source="upload",
        )


@pytest.mark.asyncio
async def test_fully_automatic_default_uses_ai_generated_creative():
    await _confirm_brief("automatic-default")
    run = await service.create_run(
        "automatic-default",
        approval_policy="auto_build_draft",
        idempotency_key="automatic-default",
    )
    assert run["creative_source"] == "ai_generate"


@pytest.mark.asyncio
async def test_run_milestone_is_durable_and_idempotent(monkeypatch):
    await _confirm_brief("milestone")
    run = await service.create_run(
        "milestone",
        creative_source="ai_generate",
        idempotency_key="milestone",
    )
    add_message = AsyncMock()
    monkeypatch.setattr("session.add_message", add_message)

    first = await service.record_milestone(
        run["run_id"],
        "audience:1",
        "Audience selected",
        metadata={"kind": "audience_selected"},
    )
    duplicate = await service.record_milestone(
        run["run_id"],
        "audience:1",
        "Audience selected",
        metadata={"kind": "audience_selected"},
    )
    refreshed = await service.get_run(run["run_id"])

    assert first["key"] == "audience:1"
    assert duplicate is None
    assert [item["key"] for item in refreshed["milestones"]] == ["audience:1"]
    add_message.assert_awaited_once_with(
        "milestone", "assistant", "Audience selected",
    )
