"""Data model for exported AMADEUS chats.

Exports are callable reference objects: they are not always-active memory, but
Dato can open them in the Materials panel or inject selected message ranges with
`[export][chat title][4-6]`. Keeping the model explicit now prepares the future
Mind Map to link to exported chats as stable sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExportedChatRecord:
    """Metadata for one exported chat reference."""

    export_id: str
    chat_id: str
    chat_title: str
    exported_at: str
    message_count: int
    txt_path: str
    md_path: str
    json_path: str

    @classmethod
    def from_raw(cls, raw: Any) -> "ExportedChatRecord | None":
        """Parse an index row while tolerating older/corrupted export records."""
        if not isinstance(raw, dict):
            return None
        required = [
            "export_id",
            "chat_id",
            "chat_title",
            "exported_at",
            "txt_path",
            "md_path",
            "json_path",
        ]
        if not all(isinstance(raw.get(key), str) and raw.get(key) for key in required):
            return None
        message_count = raw.get("message_count")
        if not isinstance(message_count, int):
            message_count = 0
        return cls(
            export_id=raw["export_id"],
            chat_id=raw["chat_id"],
            chat_title=raw["chat_title"],
            exported_at=raw["exported_at"],
            message_count=message_count,
            txt_path=raw["txt_path"],
            md_path=raw["md_path"],
            json_path=raw["json_path"],
        )

    def to_raw(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary for `exports_index.json`."""
        return {
            "export_id": self.export_id,
            "chat_id": self.chat_id,
            "chat_title": self.chat_title,
            "exported_at": self.exported_at,
            "message_count": self.message_count,
            "txt_path": self.txt_path,
            "md_path": self.md_path,
            "json_path": self.json_path,
        }
