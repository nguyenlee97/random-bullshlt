import pytest

from workspace.dependencies import ARTIFACTS, build_recompute_plan, downstream
from workspace.service import (
    StaleTaskResult,
    apply_mutation,
    commit_artifact_result,
    get_recompute_plan,
    get_task_context,
    get_workspace,
)


def _synthetic_workspace(changed: str) -> dict:
    artifacts = {
        name: {
            "status": "approved",
            "revision": index + 1,
            "value": {"artifact": name},
        }
        for index, name in enumerate(ARTIFACTS)
    }
    for name in downstream(changed):
        artifacts[name].update({
            "status": "stale",
            "stale_at_revision": 99,
            "stale_reason": f"{changed} changed",
        })
    return {
        "workspace_id": "cw-test",
        "session_id": "nonlinear-plan",
        "revision": 99,
        "artifacts": artifacts,
    }


@pytest.mark.parametrize("changed", ARTIFACTS)
def test_recompute_plan_covers_dependency_closure_without_discarding_reuse(changed):
    workspace = _synthetic_workspace(changed)
    plan = build_recompute_plan(workspace)
    expected = downstream(changed)
    assert plan["recompute_order"] == expected
    assert {item["artifact"] for item in plan["reuse"]} == set(ARTIFACTS) - set(expected)
    assert all(item["has_previous_value"] for item in plan["recompute"])


@pytest.mark.asyncio
async def test_task_result_accepts_unrelated_workspace_revision_change():
    sid = "nonlinear-unrelated-change"
    await apply_mutation(
        sid, "creative", {"files": [{"id": "f1", "name": "hero.png"}]},
        base_revision=0, actor="operator",
    )
    context = await get_task_context(sid, "creative_verdict")
    assert context["input_revisions"] == {"creative": 1}

    # Targeting changes the global revision but is not an input to a creative verdict.
    await apply_mutation(
        sid, "targeting", {"age": ["25-34"]},
        base_revision=1, actor="operator",
    )
    result = await commit_artifact_result(
        sid,
        "creative_verdict",
        {"files": [{"id": "f1", "status": "auto_approved"}]},
        task_id="creative-review-1",
        input_revisions=context["input_revisions"],
        base_artifact_revision=context["artifact_revision"],
        actor="creative_worker",
    )
    assert result["workspace_revision"] == 3
    workspace = await get_workspace(sid)
    assert workspace["artifacts"]["creative_verdict"]["status"] == "approved"


@pytest.mark.asyncio
async def test_task_result_rejects_changed_dependency_without_mutation():
    sid = "nonlinear-stale-task"
    await apply_mutation(
        sid, "creative", {"files": [{"id": "f1", "name": "one.png"}]},
        base_revision=0, actor="operator",
    )
    context = await get_task_context(sid, "creative_verdict")
    await apply_mutation(
        sid, "creative", {"files": [{"id": "f2", "name": "two.png"}]},
        base_revision=1, actor="operator",
    )

    with pytest.raises(StaleTaskResult) as error:
        await commit_artifact_result(
            sid,
            "creative_verdict",
            {"files": [{"id": "f1", "status": "auto_approved"}]},
            task_id="creative-review-stale",
            input_revisions=context["input_revisions"],
            base_artifact_revision=context["artifact_revision"],
            actor="creative_worker",
        )
    assert "creative" in error.value.mismatches
    workspace = await get_workspace(sid)
    assert workspace["revision"] == 2
    assert workspace["artifacts"]["creative_verdict"]["value"] is None


@pytest.mark.asyncio
async def test_non_linear_edit_retains_values_and_exposes_ordered_recompute_plan():
    sid = "nonlinear-selective-plan"
    revision = 0
    for field, value in (
        ("creative", {"files": [{"id": "f1", "name": "hero.png"}]}),
        ("assignments", {"ZONE-A": 0}),
        ("targeting", {"age": ["25-34"]}),
    ):
        result = await apply_mutation(
            sid, field, value, base_revision=revision, actor="operator"
        )
        revision = result["workspace_revision"]

    context = await get_task_context(sid, "creative_verdict")
    result = await commit_artifact_result(
        sid, "creative_verdict", {"approved": True},
        task_id="creative-review-current",
        input_revisions=context["input_revisions"], actor="creative_worker",
        base_artifact_revision=context["artifact_revision"],
    )
    revision = result["workspace_revision"]
    await apply_mutation(
        sid,
        "creative",
        {"files": [{"id": "f2", "name": "replacement.png"}]},
        base_revision=revision,
        actor="operator",
    )

    plan = await get_recompute_plan(sid)
    assert plan["recompute_order"] == ["creative_verdict", "assignments"]
    assert "targeting" in {item["artifact"] for item in plan["reuse"]}
    workspace = await get_workspace(sid)
    assert workspace["artifacts"]["assignments"]["value"] == {"ZONE-A": 0}
    assert workspace["artifacts"]["assignments"]["status"] == "stale"


@pytest.mark.asyncio
async def test_task_result_commit_is_idempotent_by_task_id():
    sid = "nonlinear-task-idempotency"
    await apply_mutation(
        sid, "creative", {"files": [{"id": "f1"}]},
        base_revision=0, actor="operator",
    )
    context = await get_task_context(sid, "creative_verdict")
    first = await commit_artifact_result(
        sid, "creative_verdict", {"approved": True},
        task_id="same-task", input_revisions=context["input_revisions"],
        base_artifact_revision=context["artifact_revision"],
        actor="worker",
    )
    second = await commit_artifact_result(
        sid, "creative_verdict", {"approved": True},
        task_id="same-task", input_revisions=context["input_revisions"],
        base_artifact_revision=context["artifact_revision"],
        actor="worker",
    )
    assert first["workspace_revision"] == second["workspace_revision"] == 2
    assert second["duplicate"] is True


@pytest.mark.asyncio
async def test_second_worker_cannot_overwrite_newer_result_on_same_inputs():
    sid = "nonlinear-output-race"
    await apply_mutation(
        sid, "creative", {"files": [{"id": "f1"}]},
        base_revision=0, actor="operator",
    )
    context = await get_task_context(sid, "creative_verdict")
    await commit_artifact_result(
        sid, "creative_verdict", {"winner": "worker-a"},
        task_id="worker-a", input_revisions=context["input_revisions"],
        base_artifact_revision=context["artifact_revision"], actor="worker-a",
    )
    with pytest.raises(StaleTaskResult) as error:
        await commit_artifact_result(
            sid, "creative_verdict", {"winner": "worker-b"},
            task_id="worker-b", input_revisions=context["input_revisions"],
            base_artifact_revision=context["artifact_revision"], actor="worker-b",
        )
    assert "$output" in error.value.mismatches
    workspace = await get_workspace(sid)
    assert workspace["revision"] == 2
    assert workspace["artifacts"]["creative_verdict"]["value"] == {
        "winner": "worker-a"
    }
