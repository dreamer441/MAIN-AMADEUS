"""GUI suggestion provider for step-by-step annotation building.

This service is intentionally separate from the GUI. The GUI only asks, “given
this input text, what choices should I show?” The annotation module owns the
knowledge of annotation paths, which lets `[file]`, `[sheet]`, `[memory]`, and
future annotations each grow their own guided flow without hardcoding it all in
the PyQt window.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from annotation_module.annotation_parser import AnnotationParser, ParsedAnnotation
from project_file_reader import (
    ProjectDirectoryNotFoundError,
    ProjectFileNotFoundError,
    ProjectFileReader,
    ProjectModuleNotFoundError,
    UnsafeProjectFileError,
)
from sheets_module import SheetService
from export_module import ChatExportService


@dataclass(frozen=True)
class AnnotationSuggestion:
    """One selectable GUI suggestion for the annotation popup."""

    label: str
    insert_text: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        """Return a GUI-friendly shape without exposing dataclasses to PyQt code."""
        return {"label": self.label, "insert_text": self.insert_text, "detail": self.detail}


class AnnotationSuggestionService:
    """Builds context-aware slash and bracket annotation suggestions."""

    def __init__(
        self,
        file_reader: ProjectFileReader,
        parser: AnnotationParser,
        sheet_service: SheetService | None = None,
        export_service: ChatExportService | None = None,
        current_chat_id_provider: Callable[[], str] | None = None,
    ) -> None:
        self.file_reader = file_reader
        self.parser = parser
        self.sheet_service = sheet_service
        self.export_service = export_service
        self.current_chat_id_provider = current_chat_id_provider

    def get_suggestions(self, text: str) -> list[dict[str, str]]:
        """Return suggestions for the current input text.

        The path is annotation-specific:
        - `/` shows main annotations.
        - `[file]` steps through project folders/files.
        - `[sheet]` steps through global/chat sheets.
        - `[memory]` steps through memory scope/list commands.
        """
        stripped = text.strip()
        if not stripped:
            return []

        if stripped == "/" or stripped.startswith("/"):
            return [suggestion.as_dict() for suggestion in self._main_annotation_suggestions(stripped)]

        parsed = self.parser.parse(stripped)
        if parsed is None:
            return []

        if parsed.annotation_name == "file":
            return [suggestion.as_dict() for suggestion in self._file_suggestions(parsed)]

        if parsed.annotation_name == "sheet":
            return [suggestion.as_dict() for suggestion in self._sheet_suggestions(parsed)]

        if parsed.annotation_name == "identity":
            return [suggestion.as_dict() for suggestion in self._identity_suggestions()]

        if parsed.annotation_name == "memory":
            return [suggestion.as_dict() for suggestion in self._memory_suggestions(parsed)]

        if parsed.annotation_name == "export":
            return [suggestion.as_dict() for suggestion in self._export_suggestions(parsed)]

        return []

    def _main_annotation_suggestions(self, text: str) -> list[AnnotationSuggestion]:
        """Show top-level annotations after the user types `/`."""
        query = text.lstrip("/").strip().lower()
        suggestions = [
            AnnotationSuggestion("[file]", "[file]", "Exact project file/folder access"),
            AnnotationSuggestion("[sheet]", "[sheet]", "Open/edit/inject AMADEUS sheets"),
            AnnotationSuggestion("[export]", "[export]", "Export/open chat references in Materials"),
            AnnotationSuggestion("[memory]", "[memory]", "Save/list explicit AMADEUS memory"),
            AnnotationSuggestion("[identity]", "[identity]", "Inspect AMADEUS identity charter/prompt"),
        ]
        if not query:
            return suggestions
        return [suggestion for suggestion in suggestions if query in suggestion.label.lower()]

    def _identity_suggestions(self) -> list[AnnotationSuggestion]:
        """Identity has a small fixed set of read-only views."""
        return [
            AnnotationSuggestion("[identity] status", "[identity]", "Identity module status"),
            AnnotationSuggestion("[identity][prompt]", "[identity][prompt]", "Compact identity prompt"),
            AnnotationSuggestion("[identity][project]", "[identity][project]", "Stronger project identity prompt"),
            AnnotationSuggestion("[identity][charter]", "[identity][charter]", "Full identity charter"),
        ]

    def _memory_suggestions(self, parsed: ParsedAnnotation) -> list[AnnotationSuggestion]:
        """Show the guided path for the `[memory]` annotation."""
        if not parsed.arguments:
            return [
                AnnotationSuggestion("[memory][global]", "[memory][global]", "Save cross-chat memory"),
                AnnotationSuggestion("[memory][chat]", "[memory][chat]", "Save memory for this chat only"),
                AnnotationSuggestion("[memory][list]", "[memory][list]", "Open Memory panel"),
            ]

        first_argument = self.parser.normalize_token(parsed.arguments[0])
        if first_argument == "list" and len(parsed.arguments) == 1:
            return [
                AnnotationSuggestion("[memory][list][all]", "[memory][list][all]", "Show global + chat memory"),
                AnnotationSuggestion("[memory][list][global]", "[memory][list][global]", "Show global memory only"),
                AnnotationSuggestion("[memory][list][chat]", "[memory][list][chat]", "Show current-chat memory only"),
            ]

        if first_argument in {"global", "chat"} and not parsed.content:
            return [
                AnnotationSuggestion(
                    "type memory text after this",
                    f"[memory][{first_argument}] ",
                    "Press after the bracket command and write what should be saved",
                )
            ]

        return []

    def _sheet_suggestions(self, parsed: ParsedAnnotation) -> list[AnnotationSuggestion]:
        """Show sheet commands and visible sheet names.

        Suggestions use real `sheets_module` storage. If no sheets exist yet, the
        GUI still shows scope/list commands so Dato can open the Sheets panel and
        create one there.
        """
        base_commands = [
            AnnotationSuggestion("[sheet][list]", "[sheet][list]", "Open all visible sheets"),
            AnnotationSuggestion("[sheet][chat]", "[sheet][chat]", "Open current-chat sheets"),
            AnnotationSuggestion("[sheet][global]", "[sheet][global]", "Open global sheets"),
        ]
        if self.sheet_service is None or self.current_chat_id_provider is None:
            return base_commands if not parsed.arguments else []

        chat_id = self.current_chat_id_provider()
        if not parsed.arguments:
            return base_commands + self._sheet_name_suggestions(chat_id=chat_id, scope="all")

        first = self.parser.normalize_token(parsed.arguments[0])
        if first == "list" and len(parsed.arguments) == 1:
            return [
                AnnotationSuggestion("[sheet][list][all]", "[sheet][list][all]", "Open all visible sheets"),
                AnnotationSuggestion("[sheet][list][chat]", "[sheet][list][chat]", "Open current-chat sheets"),
                AnnotationSuggestion("[sheet][list][global]", "[sheet][list][global]", "Open global sheets"),
            ]

        if first in {"chat", "global"} and len(parsed.arguments) == 1:
            return self._sheet_name_suggestions(chat_id=chat_id, scope=first)

        # Once a specific sheet is selected, suggest leaving a prompt after it.
        if len(parsed.arguments) >= 2 and not parsed.content:
            return [
                AnnotationSuggestion(
                    "type prompt after selected sheet",
                    f"[sheet][{parsed.arguments[0]}][{parsed.arguments[1]}] ",
                    "Ask AMADEUS to use this sheet as callable context",
                )
            ]

        return []

    def _sheet_name_suggestions(self, chat_id: str, scope: str) -> list[AnnotationSuggestion]:
        """Return suggestions for visible sheet titles in one scope."""
        suggestions: list[AnnotationSuggestion] = []
        for sheet in self.sheet_service.list_sheets(chat_id=chat_id, scope=scope):  # type: ignore[union-attr]
            insert_scope = sheet.scope
            suggestions.append(
                AnnotationSuggestion(
                    f"[sheet][{insert_scope}][{sheet.title}]",
                    f"[sheet][{insert_scope}][{sheet.title}]",
                    f"{sheet.scope} sheet",
                )
            )
        return suggestions


    def _export_suggestions(self, parsed: ParsedAnnotation) -> list[AnnotationSuggestion]:
        """Show the guided path for exported chat references.

        Export has two stable modes now:
        - `[export][open]...` opens export content in Materials.
        - `[export][use]... prompt` injects the selected exported messages.

        The older shorthand `[export][Chat Title][4-6]` still works, but the
        suggestions prefer the clearer mode-first structure so Dato can see
        exactly whether he is opening or using an export.
        """
        base = [
            AnnotationSuggestion("[export] current chat", "[export]", "Export/open the current chat"),
            AnnotationSuggestion("[export][list]", "[export][list]", "Open exported chats in Materials"),
            AnnotationSuggestion("[export][open]", "[export][open]", "Choose a chat to open in Materials"),
            AnnotationSuggestion("[export][use]", "[export][use]", "Choose a chat/range to inject as context"),
            AnnotationSuggestion("[export][help]", "[export][help]", "Show export annotation usage"),
        ]
        if self.export_service is None:
            return base if not parsed.arguments else []

        if not parsed.arguments:
            return base

        first = self.parser.normalize_token(parsed.arguments[0])
        if first in {"list", "help", "usage"}:
            return []

        if first in {"open", "use", "chat"}:
            mode = first
            if len(parsed.arguments) == 1:
                suggestions: list[AnnotationSuggestion] = []
                seen: set[str] = set()
                for record in self.export_service.list_exports():
                    key = record.chat_title.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    suggestions.append(
                        AnnotationSuggestion(
                            f"[{record.chat_title}]",
                            f"[export][{mode}][{record.chat_title}]",
                            f"Existing export • {record.message_count} messages",
                        )
                    )
                for chat in self.export_service.chat_history_store.list_chats():
                    key = chat.title.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    suggestions.append(
                        AnnotationSuggestion(
                            f"[{chat.title}]",
                            f"[export][{mode}][{chat.title}]",
                            "Export/open chat by title",
                        )
                    )
                return suggestions

            title = parsed.arguments[1]
            if len(parsed.arguments) == 2:
                return [
                    AnnotationSuggestion(
                        "[1-5] range example",
                        f"[export][{mode}][{title}][1-5]",
                        "Open/use a message range; edit numbers as needed",
                    ),
                    AnnotationSuggestion(
                        "type prompt after export",
                        f"[export][{mode}][{title}] ",
                        "Ask AMADEUS to use the full export as callable context",
                    ),
                ]

            if len(parsed.arguments) >= 3 and not parsed.content:
                range_token = parsed.arguments[2]
                return [
                    AnnotationSuggestion(
                        "type prompt after selected range",
                        f"[export][{mode}][{title}][{range_token}] ",
                        "Ask AMADEUS to use this exact exported segment",
                    )
                ]
            return []

        # Legacy shorthand support: `[export][Chat Title]`.
        if len(parsed.arguments) == 1:
            title = parsed.arguments[0]
            return [
                AnnotationSuggestion(
                    f"[export][{title}][1-5]",
                    f"[export][{title}][1-5]",
                    "Legacy range shortcut; edit numbers as needed",
                ),
                AnnotationSuggestion(
                    "use clearer structure",
                    f"[export][use][{title}] ",
                    "Preferred form for asking about this export",
                ),
            ]

        if len(parsed.arguments) >= 2 and not parsed.content:
            title = parsed.arguments[0]
            range_token = parsed.arguments[1]
            return [
                AnnotationSuggestion(
                    "type prompt after selected range",
                    f"[export][{title}][{range_token}] ",
                    "Ask AMADEUS to use this exact export segment",
                )
            ]

        return []

    def _file_suggestions(self, parsed: ParsedAnnotation) -> list[AnnotationSuggestion]:
        """Build the next `[file]` step from real filesystem state."""
        if not parsed.arguments:
            return [
                AnnotationSuggestion(f"[file][{module}]", f"[file][{module}]", "Module folder")
                for module in self.file_reader.list_module_names()
            ]

        requested_module = parsed.arguments[0]
        relative_path = "/".join(part.strip().strip("/") for part in parsed.arguments[1:] if part.strip())
        try:
            listing = self.file_reader.list_module_directory(requested_module, relative_path)
        except (ProjectModuleNotFoundError, ProjectDirectoryNotFoundError, ProjectFileNotFoundError, UnsafeProjectFileError, ValueError):
            return []

        base = f"[file][{listing.module_name}]"
        suggestions: list[AnnotationSuggestion] = []
        for folder in listing.folders:
            suggestions.append(
                AnnotationSuggestion(
                    f"{folder.relative_path}/",
                    f"{base}{self._path_to_brackets(folder.relative_path)}",
                    "Folder",
                )
            )
        for file_entry in listing.files:
            suggestions.append(
                AnnotationSuggestion(
                    file_entry.relative_path,
                    f"{base}{self._path_to_brackets(file_entry.relative_path)}",
                    f"File • {file_entry.size_bytes} bytes",
                )
            )
        return suggestions

    def _path_to_brackets(self, relative_path: str) -> str:
        """Convert `folder/file.py` into `[folder][file.py]` for insertion."""
        return "".join(f"[{part}]" for part in relative_path.split("/") if part)
