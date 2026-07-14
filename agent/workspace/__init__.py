"""Transactional campaign workspace foundation."""

from workspace.service import (
    WorkspaceConflict,
    apply_mutation,
    approve_proposal,
    create_proposal,
    get_workspace,
    list_pending_proposals,
    reject_proposal,
)

__all__ = [
    "WorkspaceConflict",
    "apply_mutation",
    "approve_proposal",
    "create_proposal",
    "get_workspace",
    "list_pending_proposals",
    "reject_proposal",
]
