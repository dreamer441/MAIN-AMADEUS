"""Manage dedicated-chat lifecycle and notify the explicit workspace integration."""

from __future__ import annotations

from response_modes import ResponseMode
from storage import ChatHistoryMessage, ChatMetadata, ChatPriority, ChatPurpose, ChatScope
from typing import Any


class ChatLifecycle:
    """Manage dedicated-chat lifecycle and notify the explicit workspace integration."""

    def __init__(self, *, chat_history_store: Any, mind_map_workspace_sync: Any) -> None:
        """Receive the public services needed by this workflow."""
        self.chat_history_store = chat_history_store
        self.mind_map_workspace_sync = mind_map_workspace_sync

    def list_chats(self) -> list[ChatMetadata]:
        """Return known chats for the GUI selector.

        Core exposes chat metadata instead of letting the GUI touch storage
        directly. That keeps the GUI as a surface layer and leaves persistence
        rules inside Storage.
        """
        return self.chat_history_store.list_chats()

    def get_current_chat_id(self) -> str:
        """Return the currently active chat id for GUI selection state."""
        return self.chat_history_store.get_current_chat_id()

    def get_current_chat_metadata(self) -> ChatMetadata:
        """Return metadata for the active chat workspace."""
        return self.chat_history_store.get_current_chat()

    def create_chat(
        self,
        title: str | None = None,
        description: str | None = None,
        priority: ChatPriority = "Normal",
        purpose: ChatPurpose = "General",
        scope: ChatScope = "Local",
        response_mode: ResponseMode | str = ResponseMode.NORMAL,
    ) -> ChatMetadata:
        """Create a new chat, make it active, and create its Mind Map node."""
        chat = self.chat_history_store.create_chat(
            title=title, description=description, priority=priority, purpose=purpose, scope=scope, response_mode=response_mode
        )
        self.mind_map_workspace_sync.sync_chat(chat)
        return chat

    def update_chat_metadata(
        self,
        chat_id: str,
        title: str | None = None,
        description: str | None = None,
        summary: str | None = None,
        priority: ChatPriority | None = None,
        purpose: ChatPurpose | None = None,
        scope: ChatScope | None = None,
        response_mode: ResponseMode | str | None = None,
    ) -> ChatMetadata:
        """Update chat metadata and refresh its source-backed graph node."""
        chat = self.chat_history_store.update_chat_metadata(
            chat_id=chat_id,
            title=title,
            description=description,
            summary=summary,
            priority=priority,
            purpose=purpose,
            scope=scope,
            response_mode=response_mode,
        )
        self.mind_map_workspace_sync.sync_chat(chat)
        return chat

    def delete_chat(self, chat_id: str | None = None) -> ChatMetadata:
        """Delete a chat, preserve its graph record as missing, and sync the active chat."""
        target_chat_id = chat_id or self.chat_history_store.get_current_chat_id()
        active = self.chat_history_store.delete_chat(target_chat_id)
        self.mind_map_workspace_sync.mark_chat_missing(target_chat_id)
        self.mind_map_workspace_sync.sync_chat(active)
        return active

    def switch_chat(self, chat_id: str) -> ChatMetadata:
        """Switch active chat for future saves and context building."""
        return self.chat_history_store.set_current_chat(chat_id)

    def load_chat_history(self, chat_id: str | None = None) -> list[ChatHistoryMessage]:
        """Load persisted messages for the selected or active chat."""
        return self.chat_history_store.load_messages(chat_id=chat_id)
