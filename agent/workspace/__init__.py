"""Transactional campaign workspace foundation."""

from workspace.service import (
    WorkspaceConflict,
    StaleTaskResult,
    apply_mutation,
    approve_proposal,
    commit_artifact_result,
    create_proposal,
    get_recompute_plan,
    get_task_context,
    get_workspace,
    list_pending_proposals,
    reject_proposal,
)

__all__ = [
    "WorkspaceConflict",
    "StaleTaskResult",
    "apply_mutation",
    "approve_proposal",
    "commit_artifact_result",
    "create_proposal",
    "get_recompute_plan",
    "get_task_context",
    "get_workspace",
    "list_pending_proposals",
    "reject_proposal",
]
