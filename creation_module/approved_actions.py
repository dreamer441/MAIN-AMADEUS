"""Translate approved records into the appropriate public creation operation."""

from typing import Any
from permissions import PendingAction


class ApprovedCreationActions:
    """Execute approved proposals through injected owners, without owning storage."""

    def __init__(self, *, lifecycle: Any, metadata: Any, creation: Any) -> None:
        self.lifecycle = lifecycle
        self.metadata = metadata
        self.creation = creation

    def create_chat(self, pending: PendingAction) -> Any:
        """Create a dedicated chat using the fields shown for approval."""
        fields = pending.fields
        return self.lifecycle.create_chat(
            title=fields.get('title'),
            description=fields.get('description'),
            priority=fields.get('priority', 'Normal'),
        )

    def create_workspace(self, pending: PendingAction) -> Any:
        """Create a sheet, comment or memory with its previously fixed scope."""
        request = pending.fields.get("request")
        if not isinstance(request, str) or not request.strip():
            raise ValueError("Pending workspace action has no creation request.")
        return self.creation.create_workspace_object(
            pending.kind,
            request,
            chat_id=pending.linked_chat_id or None,
            scope=pending.scope,
        )

    def create_export(self, pending: PendingAction) -> Any:
        """Delegate an explicit chat-analysis export to its metadata owner."""
        chat_id = pending.fields.get("chat_id")
        return self.metadata.create_chat_inner_brain_export(chat_id if isinstance(chat_id, str) else None)
