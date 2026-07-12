"""Data model for simple AMADEUS comments.

Comments are lightweight notes attached to selected chat text. They are not
reward signals, importance markers, or memory updates yet. Keeping comments
separate gives Dato a safe way to annotate conversations before the future reward
and Mind Map systems exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CommentEntry:
    """One saved comment attached to selected text inside a chat."""

    comment_id: str
    chat_id: str
    comment: str
    selected_text: str
    created_at: str
    message_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the comment for JSON storage."""
        return {
            "comment_id": self.comment_id,
            "chat_id": self.chat_id,
            "comment": self.comment,
            "selected_text": self.selected_text,
            "created_at": self.created_at,
            "message_number": self.message_number,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CommentEntry | None":
        """Parse one JSON object into a safe comment entry."""
        try:
            comment_id = str(raw.get("comment_id") or "").strip()
            chat_id = str(raw.get("chat_id") or "").strip()
            comment = str(raw.get("comment") or "").strip()
            selected_text = str(raw.get("selected_text") or "").strip()
            created_at = str(raw.get("created_at") or "").strip()
            raw_number = raw.get("message_number")
            message_number = int(raw_number) if raw_number is not None else None
        except Exception:
            return None

        if not comment_id or not chat_id or not comment or not created_at:
            return None
        return cls(
            comment_id=comment_id,
            chat_id=chat_id,
            comment=comment,
            selected_text=selected_text,
            created_at=created_at,
            message_number=message_number,
        )
