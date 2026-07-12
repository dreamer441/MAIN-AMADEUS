"""Public service layer for AMADEUS sheets.

Core, annotations, and GUI use this service instead of touching JSON storage
inside their own code. That keeps sheets as a real module: editable side-panel
workspace now, future Mind Map feeder later.
"""

from __future__ import annotations

from pathlib import Path

from annotation_module.annotation_parser import ParsedAnnotation
from sheets_module.sheet_entry import SheetEntry
from sheets_module.sheet_store import SheetStore


class SheetService:
    """Coordinates sheet storage, panel payloads, and prompt-context formatting."""

    def __init__(self, project_root: Path) -> None:
        self.store = SheetStore(project_root)

    def list_sheets(self, chat_id: str | None = None, scope: str = "all") -> list[SheetEntry]:
        """Return sheets visible from the active chat."""
        return self.store.list_sheets(chat_id=chat_id, scope=scope)

    def create_sheet(
        self,
        title: str,
        description: str = "",
        content: str = "",
        scope: str = "chat",
        chat_id: str | None = None,
    ) -> SheetEntry:
        """Create a global or current-chat sheet."""
        return self.store.create_sheet(title=title, description=description, content=content, scope=scope, chat_id=chat_id)

    def update_sheet(
        self,
        sheet_id: str,
        title: str | None = None,
        description: str | None = None,
        content: str | None = None,
        scope: str | None = None,
        chat_id: str | None = None,
    ) -> SheetEntry:
        """Update a sheet edited in the side panel."""
        return self.store.update_sheet(
            sheet_id=sheet_id,
            title=title,
            description=description,
            content=content,
            scope=scope,
            chat_id=chat_id,
        )

    def delete_sheet(self, sheet_id: str) -> None:
        """Delete one sheet."""
        self.store.delete_sheet(sheet_id)

    def build_panel_payload(
        self,
        chat_id: str | None,
        scope: str = "all",
        selected_sheet_id: str | None = None,
        title: str = "AMADEUS Sheets",
    ) -> dict:
        """Build a right-panel payload with visible sheet metadata and content."""
        sheets = self.list_sheets(chat_id=chat_id, scope=scope)
        selected = self._select_sheet(sheets, selected_sheet_id)
        return {
            "type": "sheets",
            "title": title,
            "content": selected.content if selected is not None else "",
            "metadata": {
                "scope": scope,
                "selected_sheet_id": selected.sheet_id if selected is not None else "",
                "selected_sheet": self._sheet_to_panel_dict(selected) if selected is not None else None,
                "sheets": [self._sheet_to_panel_dict(sheet) for sheet in sheets],
                "sheet_count": len(sheets),
            },
        }

    def resolve_annotation_target(
        self,
        annotation: ParsedAnnotation,
        chat_id: str,
    ) -> tuple[SheetEntry | None, str | None, str]:
        """Resolve `[sheet]` bracket arguments into a visible sheet.

        Returns `(sheet, problem, scope)`. The scope is useful even when no sheet
        was selected because `[sheet][chat]` should list only chat sheets.
        """
        if not annotation.arguments:
            return None, None, "all"

        first = annotation.normalized_arguments[0] if annotation.normalized_arguments else ""
        if first == "list":
            scope = annotation.normalized_arguments[1] if len(annotation.normalized_arguments) > 1 else "all"
            if scope not in {"all", "chat", "global"}:
                return None, f"Unknown sheet list scope: `{annotation.arguments[1]}`", "all"
            return None, None, scope

        if first in {"chat", "global"}:
            scope = first
            if len(annotation.arguments) == 1:
                return None, None, scope
            reference = annotation.arguments[1]
        else:
            scope = "all"
            reference = annotation.arguments[0]

        sheet, problem = self.store.find_sheet(reference=reference, chat_id=chat_id, scope=scope)
        return sheet, problem, scope

    def build_prompt_context(self, sheet: SheetEntry) -> str:
        """Format one sheet as explicit callable prompt context.

        This context is only injected when Dato uses `[sheet]`. Sheets are not
        constantly active memory, which keeps normal chat context clean.
        """
        lines = [
            "Callable sheet context requested by [sheet]:",
            f"Title: {sheet.title}",
            f"Scope: {sheet.scope}",
        ]
        if sheet.description.strip():
            lines.append(f"Description: {sheet.description.strip()}")
        lines.extend(["", "Sheet content:", sheet.content])
        return "\n".join(lines).strip()

    def _select_sheet(self, sheets: list[SheetEntry], selected_sheet_id: str | None) -> SheetEntry | None:
        """Pick the sheet the panel should display."""
        if selected_sheet_id:
            for sheet in sheets:
                if sheet.sheet_id == selected_sheet_id:
                    return sheet
        return sheets[0] if sheets else None

    def _sheet_to_panel_dict(self, sheet: SheetEntry | None) -> dict | None:
        """Convert a SheetEntry into GUI-safe metadata."""
        if sheet is None:
            return None
        return {
            "sheet_id": sheet.sheet_id,
            "title": sheet.title,
            "description": sheet.description,
            "scope": sheet.scope,
            "chat_id": sheet.chat_id,
            "content": sheet.content,
            "created_at": sheet.created_at,
            "updated_at": sheet.updated_at,
        }
