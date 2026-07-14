"""Chat export service for AMADEUS.

Exported chats are the first real Materials objects. They give Dato a stable,
human-readable record of a chat while also giving AMADEUS future callable context
through exact message numbers.

Design boundary:
- Storage owns raw chat history.
- ExportService converts selected chats into TXT / Markdown / JSON files.
- Materials panel displays export text.
- The LLM only receives export content when Dato explicitly asks through `[export]`.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_module.export_record import ExportedChatRecord
from storage import ChatHistoryMessage, ChatHistoryStore, ChatMetadata


@dataclass(frozen=True, slots=True)
class ExportSelection:
    """Resolved export plus optional message range.

    `messages` contains the exact exported segment selected by message number. If
    no range is requested, it contains the full exported message list.
    """

    record: ExportedChatRecord
    messages: list[ChatHistoryMessage]
    range_label: str


@dataclass(frozen=True, slots=True)
class ExportAnnotationTarget:
    """Normalized meaning of an `[export]` annotation path.

    Export commands now have a clearer structured form while still supporting
    the original shorthand. Core and the direct annotation handler both use this
    object so `[export][open][Chat][4]` and `[export][Chat][4]` resolve through
    the same safe path instead of each caller guessing argument positions.
    """

    mode: str
    title_or_id: str | None
    range_token: str | None


class ChatExportService:
    """Creates, lists, opens, and formats exported chat references."""

    def __init__(self, project_root: Path, chat_history_store: ChatHistoryStore) -> None:
        self.project_root = project_root.resolve()
        self.chat_history_store = chat_history_store
        self.export_directory = self.project_root / "data" / "exports"
        self.index_path = self.export_directory / "exports_index.json"
        self.export_directory.mkdir(parents=True, exist_ok=True)
        self._ensure_index()


    def parse_annotation_target(self, arguments: list[str]) -> tuple[ExportAnnotationTarget | None, str | None]:
        """Parse `[export]` arguments into a clear target shape.

        Supported stable forms:
        - `[export]` -> current chat
        - `[export][list]` -> export list
        - `[export][help]` -> usage help
        - `[export][open][Chat Title][4-6]` -> open in Materials
        - `[export][use][Chat Title][4-6] prompt` -> use as callable context

        Backward-compatible shorthand is still allowed:
        - `[export][Chat Title][4-6]`

        The point of this method is to keep export annotations deterministic. If
        we let Core guess which bracket is the chat title and which is the range,
        AMADEUS can accidentally fall back to the current chat and confuse the
        export scope.
        """
        if not arguments:
            return ExportAnnotationTarget(mode="current", title_or_id="current", range_token=None), None

        first_raw = arguments[0].strip()
        first = self._normalize(first_raw)

        if first in {"help", "usage"}:
            return ExportAnnotationTarget(mode="help", title_or_id=None, range_token=None), None
        if first in {"list", "exports", "all"}:
            return ExportAnnotationTarget(mode="list", title_or_id=None, range_token=None), None
        if first in {"current", "active"}:
            range_token = arguments[1].strip() if len(arguments) >= 2 else None
            return ExportAnnotationTarget(mode="current", title_or_id="current", range_token=range_token), None

        if first in {"open", "use", "chat"}:
            if len(arguments) < 2 or not arguments[1].strip():
                return None, f"`[export][{first_raw}]` needs a chat title, for example `[export][open][Chat Title]`."
            title_or_id = arguments[1].strip()
            range_token = arguments[2].strip() if len(arguments) >= 3 else None
            return ExportAnnotationTarget(mode=first, title_or_id=title_or_id, range_token=range_token), None

        # Legacy shorthand: `[export][Chat Title]` or `[export][Chat Title][4-6]`.
        title_or_id = first_raw
        range_token = arguments[1].strip() if len(arguments) >= 2 else None
        return ExportAnnotationTarget(mode="open", title_or_id=title_or_id, range_token=range_token), None

    def export_chat(self, chat_id: str | None = None) -> ExportedChatRecord:
        """Export one chat to TXT, Markdown, and JSON.

        The export is deterministic and overwrite-friendly: re-exporting the same
        chat updates the existing files and index row. This avoids piling up many
        stale copies while AMADEUS is still early.
        """
        metadata = self._get_chat_or_current(chat_id)
        messages = self.chat_history_store.load_messages(limit=100000, chat_id=metadata.chat_id)
        exported_at = self._now()
        export_id = self._export_id_for_chat(metadata.chat_id)
        folder = self.export_directory / self._safe_filename(export_id)
        folder.mkdir(parents=True, exist_ok=True)
        stem = self._safe_filename(metadata.title) or metadata.chat_id

        txt_path = folder / f"{stem}.txt"
        md_path = folder / f"{stem}.md"
        json_path = folder / f"{stem}.json"

        txt_path.write_text(self.format_txt(metadata, messages, exported_at), encoding="utf-8")
        md_path.write_text(self.format_md(metadata, messages, exported_at), encoding="utf-8")
        json_path.write_text(self.format_json(metadata, messages, exported_at), encoding="utf-8")
        message_numbers = sorted(message.message_number for message in messages)

        record = ExportedChatRecord(
            export_id=export_id,
            chat_id=metadata.chat_id,
            chat_title=metadata.title,
            exported_at=exported_at,
            message_count=len(messages),
            txt_path=str(txt_path.relative_to(self.project_root)),
            md_path=str(md_path.relative_to(self.project_root)),
            json_path=str(json_path.relative_to(self.project_root)),
            first_message_number=message_numbers[0] if message_numbers else None,
            last_message_number=message_numbers[-1] if message_numbers else None,
        )
        self._upsert_record(record)
        return record

    def list_exports(self) -> list[ExportedChatRecord]:
        """Return known exports, newest first."""
        raw_index = self._read_index()
        records = [ExportedChatRecord.from_raw(raw) for raw in raw_index.get("exports", [])]
        valid_records = [record for record in records if record is not None]
        valid_records.sort(key=lambda record: record.exported_at, reverse=True)
        return valid_records

    def remove_export(self, export_id: str) -> None:
        """Remove one known export and its generated folder after explicit selection."""
        record = next((record for record in self.list_exports() if record.export_id == export_id), None)
        if record is None:
            raise ValueError("Unknown export record.")
        folder = (self.project_root / record.txt_path).resolve().parent
        if folder.parent != self.export_directory.resolve():
            raise ValueError("Export record points outside the managed export directory.")
        if folder.exists():
            shutil.rmtree(folder)
        index = self._read_index()
        index["exports"] = [raw for raw in index.get("exports", []) if raw.get("export_id") != export_id]
        self._write_index(index)

    def resolve_selection(
        self,
        title_or_id: str | None = None,
        range_token: str | None = None,
        export_missing_chat: bool = True,
    ) -> tuple[ExportSelection | None, str | None]:
        """Resolve an export and optional message range.

        If an export does not exist yet but a chat with that title/id exists,
        `export_missing_chat=True` creates the export on demand. This supports
        `[export][Chat Name]` without forcing Dato to run a separate export command first.
        """
        record, problem = self._resolve_record(title_or_id, export_missing_chat=export_missing_chat)
        if problem is not None:
            return None, problem
        if record is None:
            return None, "No export target was selected."

        messages = self._load_export_messages_from_json(record)
        if range_token:
            selected_messages, range_problem = self._select_range(messages, range_token)
            if range_problem is not None:
                return None, range_problem
            range_label = range_token.strip()
        else:
            selected_messages = messages
            range_label = "all"

        return ExportSelection(record=record, messages=selected_messages, range_label=range_label), None

    def build_materials_panel_payload(
        self,
        selection: ExportSelection | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Build a Materials panel payload for export lists or selected export text."""
        if selection is None:
            exports = self.list_exports()
            if not exports:
                content = (
                    "No exported chats yet.\n\n"
                    "Use `[export]` to export the current chat, or `[export][Chat Title]` "
                    "to export/open a specific chat."
                )
            else:
                lines = ["Exported chats:", ""]
                for index, record in enumerate(exports, start=1):
                    lines.append(
                        f"{index}. {record.chat_title}"
                        f"\n   id: {record.export_id}"
                        f"\n   messages: {record.message_count}"
                        f"\n   exported_at: {record.exported_at}"
                    )
                lines.append("")
                lines.append("Use `[export][chat title][4-6]` to open a numbered segment.")
                content = "\n".join(lines)
            return {
                "type": "materials",
                "title": title or "AMADEUS Materials - Exported Chats",
                "content": content,
                "metadata": {
                    "material_count": len(exports),
                    "status": "exports_ready",
                    "kind": "export_list",
                    "export_directory": str(self.export_directory),
                    "exports": [record.to_raw() for record in exports],
                },
            }

        content = self.format_txt_segment(selection.record, selection.messages, selection.range_label)
        return {
            "type": "materials",
            "title": title or f"Export: {selection.record.chat_title}",
            "content": content,
            "metadata": {
                "material_count": len(self.list_exports()),
                "status": "export_open",
                "kind": "chat_export",
                "export_id": selection.record.export_id,
                "chat_id": selection.record.chat_id,
                "chat_title": selection.record.chat_title,
                "range": selection.range_label,
                "selected_messages": [message.message_number for message in selection.messages],
                "txt_path": selection.record.txt_path,
                "md_path": selection.record.md_path,
                "json_path": selection.record.json_path,
            },
        }

    def build_prompt_context(self, selection: ExportSelection) -> str:
        """Return strict callable context for `[export][chat][range] prompt`.

        This block must be impossible for the LLM to confuse with metadata. It is
        the actual exported chat text selected by message number. Current-chat
        history is intentionally not part of this block; Core keeps export prompts
        scoped to the selected export so AMADEUS does not answer from the wrong chat.
        """
        lines = [
            "VERIFIED EXPORTED CHAT SEGMENT",
            "This is real exported chat text selected from AMADEUS local export storage.",
            "It is not metadata and not hidden reasoning.",
            "When the user asks about this message/segment/exported chat, answer from the messages below.",
            "Do not answer from the current chat transcript unless it is explicitly included below.",
            "If the selected message range is empty, say it is empty and do not guess.",
            "",
            f"Exported chat: {selection.record.chat_title}",
            f"Export id: {selection.record.export_id}",
            f"Selected message range: {selection.range_label}",
            f"Selected message numbers: {', '.join(str(message.message_number) for message in selection.messages) or 'none'}",
            "",
            "--- REAL EXPORTED MESSAGES ---",
            "",
        ]
        if not selection.messages:
            lines.append("No messages were selected.")
            return "\n".join(lines)

        for message in selection.messages:
            lines.append(f"[{message.message_number}] {message.speaker}:")
            lines.append(message.message)
            lines.append("")
        return "\n".join(lines).strip()

    def format_txt(self, metadata: ChatMetadata, messages: list[ChatHistoryMessage], exported_at: str) -> str:
        """Format a full chat export for human reading in the Materials panel."""
        lines = [
            f"Chat Export: {metadata.title}",
            f"Chat ID: {metadata.chat_id}",
            f"Description: {metadata.description or 'No description.'}",
            f"Exported At: {exported_at}",
            f"Messages: {len(messages)}",
            "",
            "--- Messages ---",
            "",
        ]
        for message in messages:
            lines.append(f"[{message.message_number}] {message.speaker}: {message.message}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def format_txt_segment(
        self,
        record: ExportedChatRecord,
        messages: list[ChatHistoryMessage],
        range_label: str,
    ) -> str:
        """Format only the selected messages for side-panel display."""
        lines = [
            "Verified Exported Chat Segment",
            f"Chat Export: {record.chat_title}",
            f"Export ID: {record.export_id}",
            f"Selected Range: {range_label}",
            f"Selected Messages: {len(messages)}",
            "Source Type: real exported chat text, not metadata",
            "",
            "--- Selected Messages ---",
            "",
        ]
        if not messages:
            lines.append("No messages in this selection.")
        for message in messages:
            lines.append(f"[{message.message_number}] {message.speaker}: {message.message}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def format_md(self, metadata: ChatMetadata, messages: list[ChatHistoryMessage], exported_at: str) -> str:
        """Format a Markdown export for future AMADEUS reference reading."""
        lines = [
            f"# Chat Export: {metadata.title}",
            "",
            f"- Chat ID: `{metadata.chat_id}`",
            f"- Description: {metadata.description or 'No description.'}",
            f"- Exported At: {exported_at}",
            f"- Messages: {len(messages)}",
            "",
            "## Messages",
            "",
        ]
        for message in messages:
            lines.append(f"### [{message.message_number}] {message.speaker}")
            lines.append("")
            lines.append(message.message)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def format_json(self, metadata: ChatMetadata, messages: list[ChatHistoryMessage], exported_at: str) -> str:
        """Format an exact JSON export for future tools and message-range retrieval."""
        payload = {
            "chat": {
                "chat_id": metadata.chat_id,
                "title": metadata.title,
                "description": metadata.description,
                "summary": metadata.summary,
                "created_at": metadata.created_at,
                "updated_at": metadata.updated_at,
            },
            "exported_at": exported_at,
            "messages": [
                {
                    "message_number": message.message_number,
                    "speaker": message.speaker,
                    "message": message.message,
                    "created_at": message.created_at,
                }
                for message in messages
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    def _resolve_record(
        self,
        title_or_id: str | None,
        export_missing_chat: bool,
    ) -> tuple[ExportedChatRecord | None, str | None]:
        """Resolve by export id, chat id, exact title, or normalized title."""
        target = (title_or_id or "current").strip()
        if not target or self._normalize(target) in {"current", "active"}:
            record = self.export_chat(self.chat_history_store.get_current_chat_id())
            return record, None

        records = self.list_exports()
        normalized_target = self._normalize(target)
        exact_matches = [
            record for record in records
            if target in {record.export_id, record.chat_id, record.chat_title}
        ]
        if len(exact_matches) == 1:
            return exact_matches[0], None
        normalized_matches = [
            record for record in records
            if normalized_target in {self._normalize(record.chat_title), self._normalize(record.export_id), self._normalize(record.chat_id)}
        ]
        if len(normalized_matches) == 1:
            return normalized_matches[0], None
        if len(exact_matches) > 1 or len(normalized_matches) > 1:
            return None, f"Multiple exported chats matched `{target}`. Use a more exact chat title or export id."

        if export_missing_chat:
            chat = self._resolve_chat(target)
            if chat is not None:
                return self.export_chat(chat.chat_id), None

        return None, f"No exported chat or existing chat matched `{target}`. Use `[export][list]` to see available exports."

    def _resolve_chat(self, target: str) -> ChatMetadata | None:
        """Find a chat by title/id so exports can be created on demand."""
        normalized_target = self._normalize(target)
        exact_matches = [
            chat for chat in self.chat_history_store.list_chats()
            if target in {chat.chat_id, chat.title}
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]
        normalized_matches = [
            chat for chat in self.chat_history_store.list_chats()
            if normalized_target in {self._normalize(chat.chat_id), self._normalize(chat.title)}
        ]
        if len(normalized_matches) == 1:
            return normalized_matches[0]
        return None

    def _load_export_messages_from_json(self, record: ExportedChatRecord) -> list[ChatHistoryMessage]:
        """Read exported messages from the JSON export, not from live chat history.

        This keeps `[export][chat][4-6]` tied to the exported reference object.
        Re-export the chat to refresh it with newer messages.
        """
        path = self.project_root / record.json_path
        try:
            raw_payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        raw_messages = raw_payload.get("messages") if isinstance(raw_payload, dict) else None
        if not isinstance(raw_messages, list):
            return []

        messages: list[ChatHistoryMessage] = []
        for index, raw_message in enumerate(raw_messages, start=1):
            if not isinstance(raw_message, dict):
                continue
            message_number = raw_message.get("message_number")
            speaker = raw_message.get("speaker")
            message = raw_message.get("message")
            created_at = raw_message.get("created_at")
            if not isinstance(message_number, int):
                message_number = index
            if not all(isinstance(value, str) for value in (speaker, message, created_at)):
                continue
            messages.append(
                ChatHistoryMessage(
                    speaker=speaker,
                    message=message,
                    created_at=created_at,
                    message_number=message_number,
                )
            )
        return messages

    def _select_range(self, messages: list[ChatHistoryMessage], range_token: str) -> tuple[list[ChatHistoryMessage], str | None]:
        """Select messages by visible message number using `4`, `4-6`, or `all`."""
        normalized_range = range_token.strip().lower()
        if normalized_range in {"all", "full", "everything"}:
            return messages, None

        single_match = re.fullmatch(r"(\d+)", normalized_range)
        if single_match:
            number = int(single_match.group(1))
            selected = [message for message in messages if message.message_number == number]
            if not selected:
                return [], f"Export has no message number {number}."
            return selected, None

        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", normalized_range)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start > end:
                start, end = end, start
            selected = [message for message in messages if start <= message.message_number <= end]
            if not selected:
                return [], f"Export has no messages in range {start}-{end}."
            return selected, None

        return [], f"Invalid export range `{range_token}`. Use a message number like `4` or a range like `4-6`."

    def _get_chat_or_current(self, chat_id: str | None) -> ChatMetadata:
        """Return metadata for one chat or the active chat."""
        target_chat_id = chat_id or self.chat_history_store.get_current_chat_id()
        metadata = self.chat_history_store.get_chat(target_chat_id)
        if metadata is None:
            raise ValueError(f"Unknown chat id for export: {target_chat_id}")
        return metadata

    def _ensure_index(self) -> None:
        """Create an empty export index if needed."""
        if not self.index_path.exists():
            self._write_index({"exports": []})

    def _read_index(self) -> dict[str, Any]:
        """Read `exports_index.json` while tolerating corruption."""
        try:
            raw: Any = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"exports": []}
        if not isinstance(raw, dict):
            return {"exports": []}
        if not isinstance(raw.get("exports"), list):
            raw["exports"] = []
        return raw

    def _write_index(self, index: dict[str, Any]) -> None:
        """Persist export metadata in readable JSON."""
        self.export_directory.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    def _upsert_record(self, record: ExportedChatRecord) -> None:
        """Insert or replace the export record for one chat."""
        index = self._read_index()
        raw_exports = [raw for raw in index.get("exports", []) if isinstance(raw, dict)]
        replaced = False
        new_exports: list[dict[str, Any]] = []
        for raw_export in raw_exports:
            if raw_export.get("export_id") == record.export_id:
                new_exports.append(record.to_raw())
                replaced = True
            else:
                new_exports.append(raw_export)
        if not replaced:
            new_exports.append(record.to_raw())
        index["exports"] = new_exports
        self._write_index(index)

    def _export_id_for_chat(self, chat_id: str) -> str:
        """Use a stable export id per chat so annotations can reference it later."""
        return f"export_{self._safe_filename(chat_id)}"

    def _safe_filename(self, text: str) -> str:
        """Make titles safe for Windows filenames."""
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text).strip("._-")
        return safe[:80] or "chat_export"

    def _normalize(self, text: str) -> str:
        """Normalize titles/ids for forgiving annotation matching."""
        return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")

    def _now(self) -> str:
        """Return one timestamp format for export files and metadata."""
        return datetime.now(timezone.utc).isoformat()
