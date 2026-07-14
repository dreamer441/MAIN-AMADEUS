"""Public service for simple AMADEUS comments."""

from __future__ import annotations

from pathlib import Path

from comments_module.comment_entry import CommentEntry
from comments_module.comment_store import CommentStore


class CommentService:
    """Small façade used by Core and the GUI for comment actions."""

    def __init__(self, project_root: Path) -> None:
        self.store = CommentStore(project_root)

    def add_comment(self, chat_id: str, comment: str, selected_text: str = "") -> CommentEntry:
        """Save one note against selected text in the current chat."""
        return self.store.add_comment(chat_id=chat_id, comment=comment, selected_text=selected_text)

    def list_for_chat(self, chat_id: str) -> list[CommentEntry]:
        """Return comments for the current chat."""
        return self.store.list_for_chat(chat_id)

    def get_comment(self, comment_id: str) -> CommentEntry | None:
        """Return one comment record for a UI selection."""
        return self.store.get_comment(comment_id)

    def update_comment(self, comment_id: str, comment: str) -> CommentEntry:
        """Update one comment's note text."""
        return self.store.update_comment(comment_id, comment)

    def delete_comment(self, comment_id: str) -> None:
        """Delete one comment record."""
        self.store.delete_comment(comment_id)

    def build_panel_payload(self, chat_id: str) -> dict:
        """Build a side-panel payload listing comments for one chat."""
        comments = self.list_for_chat(chat_id)
        rows = [entry.to_dict() for entry in comments]
        if comments:
            lines = []
            for entry in comments:
                # Show selection targets directly for future message-context work;
                # general annotations use A because they are not tied to a message.
                label = str(entry.message_number) if entry.comment_type == "selection" and entry.message_number is not None else "A"
                lines.append(f"Comment({label}) - {entry.comment}")
                if entry.comment_type == "selection" and entry.selected_text:
                    preview = entry.selected_text.replace("\n", " ")
                    if len(preview) > 240:
                        preview = preview[:237] + "..."
                    lines.append(f"Selection: {preview}")
                lines.append("")
            content = "\n".join(lines).strip()
        else:
            content = "No comments saved for this chat yet. Comments may be added with or without selected text."

        return {
            "type": "comments",
            "title": "AMADEUS Comments",
            "content": content,
            "metadata": {
                "chat_id": chat_id,
                "comment_count": len(comments),
                "comments": rows,
            },
        }
