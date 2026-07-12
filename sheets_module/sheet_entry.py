"""Data model for AMADEUS sheets.

Sheets are editable text workspaces that sit beside chat. They are not raw chat
history and not global memory. A sheet is deliberate structured working context:
Dato can write plans, notes, project rules, drafts, or feature checklists and later
inject one sheet into a prompt with `[sheet]`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SheetEntry:
    """One editable AMADEUS sheet.

    Scope rules:
    - `global` sheets are available from every chat.
    - `chat` sheets belong to one chat workspace and should not leak into others
      unless Dato explicitly copies or promotes them later.
    """

    sheet_id: str
    title: str
    description: str
    scope: str
    chat_id: str | None
    content: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the sheet into the JSON storage shape."""
        return {
            "sheet_id": self.sheet_id,
            "title": self.title,
            "description": self.description,
            "scope": self.scope,
            "chat_id": self.chat_id,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "SheetEntry | None":
        """Parse one saved sheet safely.

        Returning None for bad rows keeps a partially corrupted sheet file from
        breaking the whole AMADEUS GUI at startup.
        """
        if not isinstance(raw, dict):
            return None

        sheet_id = raw.get("sheet_id")
        title = raw.get("title")
        description = raw.get("description")
        scope = raw.get("scope")
        chat_id = raw.get("chat_id")
        content = raw.get("content")
        created_at = raw.get("created_at")
        updated_at = raw.get("updated_at")

        if not isinstance(sheet_id, str) or not sheet_id.strip():
            return None
        if not isinstance(title, str) or not title.strip():
            return None
        if not isinstance(description, str):
            description = ""
        if scope not in {"chat", "global"}:
            return None
        if chat_id is not None and not isinstance(chat_id, str):
            return None
        if not isinstance(content, str):
            content = ""
        if not isinstance(created_at, str) or not created_at.strip():
            return None
        if not isinstance(updated_at, str) or not updated_at.strip():
            return None

        return cls(
            sheet_id=sheet_id.strip(),
            title=title.strip(),
            description=description.strip(),
            scope=scope,
            chat_id=chat_id,
            content=content,
            created_at=created_at,
            updated_at=updated_at,
        )
