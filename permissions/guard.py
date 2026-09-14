"""Validate single-use approvals and dispatch explicitly registered owner actions."""

from collections.abc import Callable
from typing import Any

from permissions.pending_actions import ALLOWED_PENDING_ACTION_KINDS, PendingAction, PendingActionService


class PermissionGuard:
    """Protect existing proposed writes; this is not a filesystem/shell sandbox."""

    def __init__(self, pending_actions: PendingActionService, current_chat_id_provider: Callable[[], str]) -> None:
        self.pending_actions = pending_actions
        self.current_chat_id_provider = current_chat_id_provider
        self._handlers: dict[str, Callable[[PendingAction], Any]] = {}

    def register_handler(self, kind: str, handler: Callable[[PendingAction], Any]) -> None:
        """Connect a known action kind to its owner at application startup."""
        if kind not in ALLOWED_PENDING_ACTION_KINDS or not callable(handler):
            raise ValueError("An approval handler requires an allowed kind and callable owner.")
        if kind in self._handlers:
            raise ValueError(f"Approval handler already registered: {kind}")
        self._handlers[kind] = handler

    def create_pending_action(
        self,
        *,
        kind: str,
        fields: dict[str, Any],
        scope: str = 'global',
        linked_chat_id: str = '',
    ) -> PendingAction:
        """Freeze the request and its chat scope before displaying approval."""
        if kind not in self._handlers:
            raise ValueError(f"Unsupported pending action kind: {kind}")
        if scope == "chat" and not linked_chat_id:
            linked_chat_id = self.current_chat_id_provider()
        return self.pending_actions.create(kind=kind, fields=fields, scope=scope, linked_chat_id=linked_chat_id)

    def approve_pending_action(self, action_id: str) -> Any:
        """Consume a verified request before executing its registered owner."""
        pending = self.pending_actions.consume(action_id)
        handler = self._handlers.get(pending.kind)
        if handler is None:
            raise ValueError("Unsupported pending action kind.")
        return handler(pending)

    def decline_pending_action(self, action_id: str) -> None:
        """Discard an action without invoking its owner."""
        self.pending_actions.decline(action_id)
