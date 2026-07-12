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
            message_number=self._extract_message_number(clean_selected),
        )
        self._write_all(existing + [entry])
        return entry

    def list_for_chat(self, chat_id: str) -> list[CommentEntry]:
        """Return comments attached to one chat in creation order."""
        return [entry for entry in self.list_all() if entry.chat_id == chat_id]

    def list_all(self) -> list[CommentEntry]:
        """Read all parseable comments from JSON storage."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            raw = []
        if not isinstance(raw, list):
            return []

        entries: list[CommentEntry] = []
        for item in raw:
            if isinstance(item, dict):
                parsed = CommentEntry.from_dict(item)
                if parsed is not None:
                    entries.append(parsed)
        return entries

    def _write_all(self, entries: list[CommentEntry]) -> None:
        """Persist the full comment list as readable JSON."""
        payload = [entry.to_dict() for entry in entries]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

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
