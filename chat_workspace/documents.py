"""Coordinate active-chat sheets, comments and linked panel requests."""

from __future__ import annotations

from typing import Any


class WorkspaceDocuments:
    """Coordinate active-chat sheets, comments and linked panel requests."""

    def __init__(
        self,
        *,
        chat_history_store: Any,
        sheet_service: Any,
        comment_service: Any,
        mind_map_workspace_sync: Any,
    ) -> None:
        """Receive the public services needed by this workflow."""
        self.chat_history_store = chat_history_store
        self.sheet_service = sheet_service
        self.comment_service = comment_service
        self.mind_map_workspace_sync = mind_map_workspace_sync

    def add_comment(self, comment: str, selected_text: str = "") -> Any:
        """Save a comment and project it into the active chat's Mind Map."""
        saved = self.comment_service.add_comment(
            chat_id=self.chat_history_store.get_current_chat_id(),
            comment=comment,
            selected_text=selected_text,
        )
        self.mind_map_workspace_sync.sync_comment(saved)
        return saved

    def update_comment(self, comment_id: str, comment: str) -> Any:
        """Update one comment and its source-backed Mind Map node."""
        saved = self.comment_service.update_comment(comment_id, comment)
        self.mind_map_workspace_sync.sync_comment(saved)
        return saved

    def delete_comment(self, comment_id: str) -> None:
        """Delete one comment and its exact source-backed graph node."""
        self.comment_service.delete_comment(comment_id)
        self.mind_map_workspace_sync.delete_source_node("comment", comment_id)

    def get_comments_panel_payload(self) -> dict[str, Any]:
        """Return comments for the current chat as a right-panel payload."""
        return self.comment_service.build_panel_payload(self.chat_history_store.get_current_chat_id())

    def get_linked_mind_map_panel_payload(self) -> dict[str, Any]:
        """Return direct Mind Map neighbors active for the current chat."""
        return self.mind_map_workspace_sync.build_panel_payload(self.chat_history_store.get_current_chat_id())

    def list_sheets(self, scope: str = "all") -> list[Any]:
        """Return sheets visible from the current chat for GUI selectors."""
        return self.sheet_service.list_sheets(chat_id=self.chat_history_store.get_current_chat_id(), scope=scope)

    def create_sheet(
        self,
        title: str,
        description: str = "",
        content: str = "",
        scope: str = "chat",
    ) -> Any:
        """Create a sheet and project chat-scoped sheets into the Mind Map."""
        sheet = self.sheet_service.create_sheet(
            title=title,
            description=description,
            content=content,
            scope=scope,
            chat_id=self.chat_history_store.get_current_chat_id(),
        )
        self.mind_map_workspace_sync.sync_sheet(sheet)
        return sheet

    def update_sheet(
        self,
        sheet_id: str,
        title: str | None = None,
        description: str | None = None,
        content: str | None = None,
        scope: str | None = None,
    ) -> Any:
        """Update a sheet and refresh its source-backed Mind Map node."""
        sheet = self.sheet_service.update_sheet(
            sheet_id=sheet_id,
            title=title,
            description=description,
            content=content,
            scope=scope,
            chat_id=self.chat_history_store.get_current_chat_id(),
        )
        self.mind_map_workspace_sync.sync_sheet(sheet)
        return sheet

    def delete_sheet(self, sheet_id: str) -> None:
        """Delete one sheet and its exact source-backed graph node."""
        self.sheet_service.delete_sheet(sheet_id)
        self.mind_map_workspace_sync.delete_source_node("sheet", sheet_id)

    def get_sheets_panel_payload(self, scope: str = "all", selected_sheet_id: str | None = None) -> dict[str, Any]:
        """Return a side-panel payload for the current chat's visible sheets."""
        return self.sheet_service.build_panel_payload(
            chat_id=self.chat_history_store.get_current_chat_id(),
            scope=scope,
            selected_sheet_id=selected_sheet_id,
        )
