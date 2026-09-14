"""Workspace integration adapter for approved Creation workspace proposals."""

from typing import Any

from creation_module.workspace_models import WorkspaceCreationRequest


class WorkspaceCreationAdapter:
    """Call owner services and synchronize each persisted record into Mind Map."""

    def __init__(self, *, sheet_service: Any, comment_service: Any, memory_service: Any, workspace_sync: Any) -> None:
        self._sheets = sheet_service
        self._comments = comment_service
        self._memory = memory_service
        self._workspace_sync = workspace_sync

    def create_sheet(self, request: WorkspaceCreationRequest) -> object:
        sheet = self._sheets.create_sheet(title=request.title, description=request.description, content=request.content, scope=request.scope, chat_id=request.chat_id)
        self._workspace_sync.sync_sheet(sheet)
        return sheet

    def create_comment(self, request: WorkspaceCreationRequest) -> object:
        comment = self._comments.add_comment(chat_id=request.chat_id, comment=request.content, selected_text=request.selected_text, scope=request.scope)
        self._workspace_sync.sync_comment(comment)
        return comment

    def create_memory(self, request: WorkspaceCreationRequest) -> object:
        memory = self._memory.save_chat_memory(request.chat_id, request.content) if request.scope == "chat" else self._memory.save_global_memory(request.content)
        self._workspace_sync.sync_memory(memory)
        return memory
