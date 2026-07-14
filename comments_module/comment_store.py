"""JSON-backed storage for AMADEUS chat comments.

The first comment system is intentionally simple: Dato selects visible text,
adds a note, and AMADEUS stores it under the current chat. Later this can evolve
into comments on files, sheets, nodes, links, and materials.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from comments_module.comment_entry import CommentEntry


class CommentStore:
    """Persistent comment storage under `data/comments/comments.json`."""

    def __init__(self, project_root: Path, relative_path: str = "data/comments/comments.json") -> None:
        self.path = project_root.resolve() / relative_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_all([])

    def add_comment(self, chat_id: str, comment: str, selected_text: str = "") -> CommentEntry:
        """Create one comment attached to the current chat and selected text."""
        clean_comment = comment.strip()
        clean_selected = selected_text.strip()
        if not clean_comment:
            raise ValueError("Comment text cannot be empty.")

        existing = self.list_all()
        entry = CommentEntry(
            comment_id=self._new_comment_id(existing),
            chat_id=chat_id,
            comment=clean_comment,
            selected_text=clean_selected,
            created_at=self._now(),
            message_number=self._extract_message_number(clean_selected) if clean_selected else None,
            comment_type="selection" if clean_selected else "general",
        )
        self._write_all(self._read_raw_records() + [entry.to_dict()])
        return entry

    def get_comment(self, comment_id: str) -> CommentEntry | None:
        """Return one comment by id when its stored record is valid."""
        for entry in self.list_all():
            if entry.comment_id == comment_id:
                return entry
        return None

    def update_comment(self, comment_id: str, comment: str) -> CommentEntry:
        """Replace one comment's text while preserving its target metadata."""
        clean_comment = comment.strip()
        if not clean_comment:
            raise ValueError("Comment text cannot be empty.")

        records = self._read_raw_records()
        for index, raw in enumerate(records):
            entry = CommentEntry.from_dict(raw)
            if entry is not None and entry.comment_id == comment_id:
                updated = CommentEntry(
                    comment_id=entry.comment_id,
                    chat_id=entry.chat_id,
                    comment=clean_comment,
                    selected_text=entry.selected_text,
                    created_at=entry.created_at,
                    message_number=entry.message_number,
                    comment_type=entry.comment_type,
                    updated_at=self._now(),
                )
                records[index] = updated.to_dict()
                self._write_all(records)
                return updated
        raise ValueError("Unknown comment record.")

    def delete_comment(self, comment_id: str) -> None:
        """Remove exactly one comment record by id."""
        records = self._read_raw_records()
        for index, raw in enumerate(records):
            entry = CommentEntry.from_dict(raw)
            if entry is not None and entry.comment_id == comment_id:
                del records[index]
                self._write_all(records)
                return
        raise ValueError("Unknown comment record.")

    def list_for_chat(self, chat_id: str) -> list[CommentEntry]:
        """Return comments attached to one chat in creation order."""
        return [entry for entry in self.list_all() if entry.chat_id == chat_id]

    def list_all(self) -> list[CommentEntry]:
        """Read all parseable comments from JSON storage."""
        entries: list[CommentEntry] = []
        for raw in self._read_raw_records():
            parsed = CommentEntry.from_dict(raw)
            if parsed is not None:
                entries.append(parsed)
        return entries

    def _read_raw_records(self) -> list[dict[str, Any]]:
        """Read raw records so unmodified legacy comments remain byte-equivalent in meaning."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _write_all(self, records: list[dict[str, Any]]) -> None:
        """Persist raw records without enriching unmodified legacy comments."""
        self.path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    def _new_comment_id(self, existing: list[CommentEntry]) -> str:
        """Return a stable human-inspectable comment id."""
        return f"comment_{len(existing) + 1:04d}"

    def _now(self) -> str:
        """Return UTC timestamp for portable local JSON records."""
        return datetime.now(timezone.utc).isoformat()

    def _extract_message_number(self, selected_text: str) -> int | None:
        """Best-effort extraction from selected text like `[12] User: ...`.

        This is deliberately best-effort only. Message comments become more exact
        once `[current][number]` and structured message ids are implemented.
        """
        match = re.search(r"\[(\d+)\]\s+", selected_text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None
