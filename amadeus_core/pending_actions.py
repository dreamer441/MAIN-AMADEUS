"""Compatibility exports; approval records are owned by Permissions."""
from permissions.pending_actions import ALLOWED_PENDING_ACTION_KINDS, PendingAction, PendingActionService
__all__ = ["ALLOWED_PENDING_ACTION_KINDS", "PendingAction", "PendingActionService"]
