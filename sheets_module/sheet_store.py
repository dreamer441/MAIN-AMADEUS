"""Local JSON storage for AMADEUS sheets.

The first version uses one human-readable JSON file instead of a database. That is
intentional: Dato can inspect and back up the file easily while AMADEUS is still
small. The public methods are shaped so a database can replace this later without
changing Core or GUI behavior.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sheets_module.sheet_entry import SheetEntry


class SheetStore:
    """Persistence boundary for global and chat-local sheets."""

    def __init__(self, project_root: Path, relative_path: str = "data/sheets/sheets.json") -> None:
        self.project_root = project_root.resolve()
        self.storage_path = self.project_root / relative_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._write_all([])

    def list_sheets(self, chat_id: str | None = None, scope: str = "all") -> list[SheetEntry]:
        """Return sheets visible for a chat and scope.

        `all` returns global sheets plus sheets attached to the active chat. It
        deliberately does not return other chats' local sheets, because those are
        callable workspace context and should require explicit retrieval later.
        """
        normalized_scope = self._normalize_scope(scope)
        sheets = self._read_all()
        visible: list[SheetEntry] = []
        for sheet in sheets:
            if normalized_scope == "global" and sheet.scope != "global":
                continue
            if normalized_scope == "chat" and not (sheet.scope == "chat" and sheet.chat_id == chat_id):
                continue
            if normalized_scope == "all":
                if sheet.scope == "global" or sheet.chat_id == chat_id:
                    visible.append(sheet)
                continue
            visible.append(sheet)

        visible.sort(key=lambda entry: (entry.scope != "chat", entry.title.lower()))
        return visible

    def get_sheet(self, sheet_id: str) -> SheetEntry | None:
        """Return one sheet by id."""
        clean_id = sheet_id.strip()
        for sheet in self._read_all():
            if sheet.sheet_id == clean_id:
                return sheet
        return None

    def create_sheet(
        self,
        title: str,
        description: str = "",
        content: str = "",
        scope: str = "chat",
        chat_id: str | None = None,
    ) -> SheetEntry:
        """Create a new sheet and return the saved entry."""
        normalized_scope = self._normalize_scope(scope)
        clean_title = title.strip() or "New Sheet"
        clean_description = description.strip()
        clean_content = content
        effective_chat_id = chat_id if normalized_scope == "chat" else None
        if normalized_scope == "chat" and not effective_chat_id:
            raise ValueError("Chat-scoped sheets require a chat id.")

        now = self._now()
        sheet = SheetEntry(
            sheet_id=self._new_sheet_id(clean_title),
            title=clean_title,
            description=clean_description,
            scope=normalized_scope,
            chat_id=effective_chat_id,
            content=clean_content,
            created_at=now,
            updated_at=now,
        )
        sheets = self._read_all()
        sheets.append(sheet)
        self._write_all(sheets)
        return sheet

    def update_sheet(
        self,
        sheet_id: str,
        title: str | None = None,
        description: str | None = None,
        content: str | None = None,
        scope: str | None = None,
        chat_id: str | None = None,
    ) -> SheetEntry:
        """Update editable sheet fields."""
        sheets = self._read_all()
        updated_sheets: list[SheetEntry] = []
        updated_entry: SheetEntry | None = None
        for sheet in sheets:
            if sheet.sheet_id != sheet_id:
                updated_sheets.append(sheet)
                continue

            next_scope = self._normalize_scope(scope or sheet.scope)
            next_chat_id = chat_id if next_scope == "chat" else None
            if next_scope == "chat" and not next_chat_id:
                next_chat_id = sheet.chat_id
            if next_scope == "chat" and not next_chat_id:
                raise ValueError("Chat-scoped sheets require a chat id.")

            updated_entry = SheetEntry(
                sheet_id=sheet.sheet_id,
                title=(title if title is not None else sheet.title).strip() or sheet.title,
                description=(description if description is not None else sheet.description).strip(),
                scope=next_scope,
                chat_id=next_chat_id,
                content=content if content is not None else sheet.content,
                created_at=sheet.created_at,
                updated_at=self._now(),
            )
            updated_sheets.append(updated_entry)

        if updated_entry is None:
            raise ValueError(f"Unknown sheet id: {sheet_id}")

        self._write_all(updated_sheets)
        return updated_entry

    def delete_sheet(self, sheet_id: str) -> None:
        """Delete one sheet from local storage."""
        sheets = self._read_all()
        remaining = [sheet for sheet in sheets if sheet.sheet_id != sheet_id]
        if len(remaining) == len(sheets):
            raise ValueError(f"Unknown sheet id: {sheet_id}")
        self._write_all(remaining)

    def find_sheet(self, reference: str, chat_id: str | None = None, scope: str = "all") -> tuple[SheetEntry | None, str | None]:
        """Find a visible sheet by id or title.

        The return shape is `(sheet, problem)`. A problem string lets annotations
        report ambiguity or missing sheets without guessing.
        """
        clean_reference = reference.strip()
        if not clean_reference:
            return None, "No sheet title or id was provided."

        visible_sheets = self.list_sheets(chat_id=chat_id, scope=scope)
        for sheet in visible_sheets:
            if sheet.sheet_id == clean_reference:
                return sheet, None

        normalized_reference = self._normalize_title(clean_reference)
        matches = [sheet for sheet in visible_sheets if self._normalize_title(sheet.title) == normalized_reference]
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            options = ", ".join(f"{sheet.title} ({sheet.sheet_id})" for sheet in matches)
            return None, f"Multiple sheets matched `{clean_reference}`: {options}. Use the sheet id."

        partial_matches = [sheet for sheet in visible_sheets if normalized_reference in self._normalize_title(sheet.title)]
        if len(partial_matches) == 1:
            return partial_matches[0], None
        if len(partial_matches) > 1:
            options = ", ".join(f"{sheet.title} ({sheet.sheet_id})" for sheet in partial_matches)
            return None, f"Multiple partial sheet matches found for `{clean_reference}`: {options}."

        return None, f"No visible sheet matched `{clean_reference}`."

    def _read_all(self) -> list[SheetEntry]:
        """Read and parse all sheets while tolerating damaged rows."""
        try:
            raw_data: Any = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        if not isinstance(raw_data, list):
            return []
        parsed = [SheetEntry.from_dict(row) for row in raw_data]
        return [sheet for sheet in parsed if sheet is not None]

    def _write_all(self, sheets: list[SheetEntry]) -> None:
        """Persist all sheets in a readable JSON list."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        raw_data = [sheet.to_dict() for sheet in sheets]
        self.storage_path.write_text(json.dumps(raw_data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _new_sheet_id(self, title: str) -> str:
        """Create a stable local id from the title plus timestamp."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.lower()).strip("_") or "sheet"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        return f"sheet_{slug}_{timestamp}"

    def _normalize_title(self, title: str) -> str:
        """Normalize titles for forgiving annotation lookup."""
        normalized = title.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return " ".join(normalized.split())

    def _normalize_scope(self, scope: str) -> str:
        """Accept only supported sheet scopes."""
        normalized = scope.strip().lower()
        if normalized not in {"all", "chat", "global"}:
            raise ValueError(f"Unsupported sheet scope: {scope}")
        return normalized

    def _now(self) -> str:
        """Return one timestamp format for sheet metadata."""
        return datetime.now(timezone.utc).isoformat()
