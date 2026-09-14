"""Provide read-only Code Viewer operations and explicitly selected question context."""

from __future__ import annotations

from typing import Any
from project_file_reader import ProjectFileContent


class ProjectFileWorkspace:
    """Provide read-only Code Viewer operations and explicitly selected question context."""

    def __init__(self, *, file_reader: Any, handle_user_message: Any) -> None:
        """Receive the public services needed by this workflow."""
        self.file_reader = file_reader
        self.handle_user_message = handle_user_message

    def get_project_tree(self, relative_path: str = "") -> dict[str, Any]:
        """Return a verified direct project-root tree listing for the Code Viewer."""
        listing = self.file_reader.list_project_directory(relative_path)
        return {
            "path": listing.requested_path,
            "folders": [entry.__dict__ for entry in listing.folders],
            "files": [entry.__dict__ for entry in listing.files],
        }

    def open_project_file(self, relative_path: str) -> dict[str, Any]:
        """Open one verified project file through the trusted reader only."""
        content = self.file_reader.read_project_file(relative_path)
        return self._build_project_file_panel_payload(content)

    def ask_about_project_file(
        self, relative_path: str, question: str, include_context: bool = False, line_range: str = ""
    ) -> dict[str, Any]:
        """Ask a direct question, adding verified selected-file context only when enabled."""
        context = self.file_reader.build_project_file_context(relative_path, line_range) if include_context else None
        return self.handle_user_message(question, callable_context=context)

    def _build_project_file_panel_payload(self, content: ProjectFileContent) -> dict[str, Any]:
        """Create the shared Code Viewer payload for GUI project-tree file opens."""
        return {
            "type": "code",
            "title": content.relative_path,
            "content": content.content,
            "metadata": {
                "relative_path": content.relative_path,
                "lines": content.total_lines,
                "characters_read": len(content.content),
                "total_characters": content.total_characters,
                "size_bytes": content.size_bytes,
                "encoding": content.encoding,
                "truncated": content.truncated,
            },
        }
