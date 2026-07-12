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

    def build_panel_payload(self, chat_id: str) -> dict:
        """Build a side-panel payload listing comments for one chat."""
        comments = self.list_for_chat(chat_id)
        if comments:
            lines = []
            for index, entry in enumerate(comments, start=1):
                # Display the target message number directly in the heading because
                # comments will later become useful context for `[current]`, Mind Map
                # evidence, and neighboring-message retrieval. If message detection
                # failed, keep that visible instead of pretending the target is known.
                message_label = str(entry.message_number) if entry.message_number is not None else "?"
                lines.append(f"{index}. comment({message_label}) — selected text")
                lines.append(f"ID: {entry.comment_id}")
                lines.append(f"Comment: {entry.comment}")
                if entry.selected_text:
                    preview = entry.selected_text.replace("\n", " ")
                    if len(preview) > 240:
                        preview = preview[:237] + "..."
                    lines.append(f"Selection: {preview}")
                lines.append("")
            content = "\n".join(lines).strip()
        else:
            content = "No comments saved for this chat yet. Select chat text and press Add Comment."

        return {
            "type": "comments",
            "title": "AMADEUS Comments",
            "content": content,
            "metadata": {
                "chat_id": chat_id,
                "comment_count": len(comments),
            },
        }
