"""Local multi-chat history storage for AMADEUS.

This module stores visible conversation history only. It is not long-term memory,
semantic memory, or autonomous reflection storage.

Storage shape:
- `data/chats/chats_index.json` stores chat metadata and the active chat id.
- `data/chats/<chat_id>.jsonl` stores the visible messages for one chat.

The important design boundary is that chat switching is a storage/UI concern. The
LLM should only receive the active chat's selected context through Context Builder,
not every conversation at once.
"""

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ChatHistoryMessage:
    """One persisted chat message displayed in the GUI.

    `message_number` is calculated from the JSONL row order when a chat is loaded.
    It is not trusted as permanent identity yet; it is a visible reference number
    for the current chat and a foundation for future `[current][number]` commands.
    """

    speaker: str
    message: str
    created_at: str
    message_number: int


@dataclass(frozen=True)
class ChatMetadata:
    """Small metadata record used by the GUI chat selector and context panels.

    Title/description are intentionally lightweight. Future chat modes such as
    coding/planning/brainstorming should only be added after reasoning profiles
    make those modes behaviorally real instead of simple labels.
    """

    chat_id: str
    title: str
    created_at: str
    updated_at: str
    description: str = ""
    summary: str = ""


class ChatHistoryStore:
    """JSONL-backed multi-chat storage for local AMADEUS conversations.

    This is intentionally simple. A future database can replace it later, but the
    public methods should stay similar: list chats, switch active chat, append
    visible messages, and load messages for the selected chat.
    """

    def __init__(self, project_root: Path, relative_directory: str = "data/chats") -> None:
        # Runtime chat data lives under `data/chats` so source modules stay clean.
        # Each conversation gets its own JSONL file; the index stores names/order.
        self.chat_directory = project_root.resolve() / relative_directory
        self.index_path = self.chat_directory / "chats_index.json"
        self.legacy_file_path = self.chat_directory / "current_chat.jsonl"
        self.chat_directory.mkdir(parents=True, exist_ok=True)

        # Startup always leaves storage in a valid state. GUI/Core code can assume
        # that at least one chat exists after this constructor finishes.
        self._ensure_index_exists()
        self._migrate_legacy_current_chat_if_needed()

    def list_chats(self) -> list[ChatMetadata]:
        """Return all known chats ordered newest-updated first."""
        index = self._read_index()
        chats = [self._metadata_from_raw(raw_chat) for raw_chat in index.get("chats", [])]
        valid_chats = [chat for chat in chats if chat is not None]

        # Newest updated chats are easiest to find near the top of the selector.
        valid_chats.sort(key=lambda chat: chat.updated_at, reverse=True)
        return valid_chats

    def get_current_chat_id(self) -> str:
        """Return the active chat id, repairing the index if needed."""
        index = self._read_index()
        current_chat_id = index.get("current_chat_id")
        chat_ids = {chat.chat_id for chat in self.list_chats()}
        if isinstance(current_chat_id, str) and current_chat_id in chat_ids:
            return current_chat_id

        # If the saved active chat was deleted/corrupted, pick the newest valid one.
        chats = self.list_chats()
        if chats:
            self.set_current_chat(chats[0].chat_id)
            return chats[0].chat_id

        return self.create_chat("Main Chat").chat_id

    def get_current_chat(self) -> ChatMetadata:
        """Return metadata for the active chat."""
        chat_id = self.get_current_chat_id()
        metadata = self.get_chat(chat_id)
        if metadata is not None:
            return metadata
        return self.create_chat("Main Chat")

    def set_current_chat(self, chat_id: str) -> ChatMetadata:
        """Switch the active chat used for loading, saving, and context building."""
        metadata = self.get_chat(chat_id)
        if metadata is None:
            raise ValueError(f"Unknown chat id: {chat_id}")

        index = self._read_index()
        index["current_chat_id"] = metadata.chat_id
        self._write_index(index)
        return metadata

    def get_chat(self, chat_id: str) -> ChatMetadata | None:
        """Return metadata for one chat id without loading its messages."""
        for chat in self.list_chats():
            if chat.chat_id == chat_id:
                return chat
        return None

    def create_chat(self, title: str | None = None, description: str | None = None) -> ChatMetadata:
        """Create a new empty chat and make it the active chat.

        The description is the first version of chat-level workspace context. It
        is active context for the current chat, but it is not a full generated
        summary and should not be treated as permanent global memory.
        """
        now = self._now()
        chat_id = self._new_chat_id()
        clean_title = (title or self._default_new_chat_title()).strip() or "New Chat"
        clean_description = (description or "").strip()
        metadata = ChatMetadata(
            chat_id=chat_id,
            title=clean_title,
            created_at=now,
            updated_at=now,
            description=clean_description,
            summary="",
        )

        index = self._read_index()
        raw_chats = [raw_chat for raw_chat in index.get("chats", []) if isinstance(raw_chat, dict)]
        raw_chats.append(self._metadata_to_raw(metadata))
        index["chats"] = raw_chats
        index["current_chat_id"] = chat_id
        self._write_index(index)

        # Touch the file immediately so it exists even before the first message.
        self._chat_file_path(chat_id).touch(exist_ok=True)
        return metadata

    def update_chat_metadata(
        self,
        chat_id: str,
        title: str | None = None,
        description: str | None = None,
        summary: str | None = None,
    ) -> ChatMetadata:
        """Update editable chat metadata fields.

        This method is intentionally small now, but it gives future UI actions a
        safe storage path for rename, summary updates, and callable metadata.
        """
        existing = self.get_chat(chat_id)
        if existing is None:
            raise ValueError(f"Unknown chat id: {chat_id}")

        updated = ChatMetadata(
            chat_id=existing.chat_id,
            title=(title if title is not None else existing.title).strip() or existing.title,
            description=(description if description is not None else existing.description).strip(),
            summary=(summary if summary is not None else existing.summary).strip(),
            created_at=existing.created_at,
            updated_at=self._now(),
        )
        self._replace_metadata(updated)
        return updated

    def delete_chat(self, chat_id: str) -> ChatMetadata:
        """Delete one chat file and switch to a remaining chat.

        Deleting the last chat automatically creates a fresh Main Chat. That keeps
        the GUI simple because it never has to handle a no-chat state.
        """
        index = self._read_index()
        raw_chats = [raw_chat for raw_chat in index.get("chats", []) if isinstance(raw_chat, dict)]
        remaining_raw_chats = [raw_chat for raw_chat in raw_chats if raw_chat.get("chat_id") != chat_id]
        if len(remaining_raw_chats) == len(raw_chats):
            raise ValueError(f"Unknown chat id: {chat_id}")

        chat_file = self._chat_file_path(chat_id)
        if chat_file.exists():
            chat_file.unlink()

        index["chats"] = remaining_raw_chats
        if remaining_raw_chats:
            remaining = [self._metadata_from_raw(raw_chat) for raw_chat in remaining_raw_chats]
            valid_remaining = [chat for chat in remaining if chat is not None]
            valid_remaining.sort(key=lambda chat: chat.updated_at, reverse=True)
            if valid_remaining:
                # Rewrite only parseable metadata so a corrupted row does not keep breaking startup.
                index["chats"] = [self._metadata_to_raw(chat) for chat in valid_remaining]
                index["current_chat_id"] = valid_remaining[0].chat_id
                self._write_index(index)
                return valid_remaining[0]

        # No valid chats left: write an empty index first, then create a clean default chat.
        index["chats"] = []
        index["current_chat_id"] = None
        self._write_index(index)
        return self.create_chat("Main Chat")

    def append_message(self, speaker: str, message: str, chat_id: str | None = None) -> None:
        """Persist one visible message to the selected chat file."""
        clean_speaker = speaker.strip()
        clean_message = message.strip()
        if not clean_speaker or not clean_message:
            return

        target_chat_id = chat_id or self.get_current_chat_id()
        record = {
            "speaker": clean_speaker,
            "message": clean_message,
            "created_at": self._now(),
        }

        # JSONL is append-friendly and easy to inspect manually while AMADEUS is young.
        with self._chat_file_path(target_chat_id).open("a", encoding="utf-8") as chat_file:
            chat_file.write(json.dumps(record, ensure_ascii=False) + "\n")

        self._touch_chat(target_chat_id)

    def load_messages(self, limit: int = 200, chat_id: str | None = None) -> list[ChatHistoryMessage]:
        """Load recent visible messages from one chat file.

        Message numbers are based on the full file order, not the sliced result,
        so if only the latest 20 messages are loaded they still show their real
        chat-local numbers.
        """
        target_chat_id = chat_id or self.get_current_chat_id()
        file_path = self._chat_file_path(target_chat_id)
        if not file_path.exists():
            return []

        messages: list[ChatHistoryMessage] = []
        for line_number, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            message = self._parse_line(line, message_number=line_number)
            if message is not None:
                messages.append(message)

        return messages[-limit:]

    def _ensure_index_exists(self) -> None:
        """Create a valid chat index when AMADEUS starts for the first time."""
        if self.index_path.exists():
            index = self._read_index()
            if self._index_has_chats(index):
                return

        now = self._now()
        metadata = ChatMetadata(chat_id="main", title="Main Chat", created_at=now, updated_at=now)
        self._write_index({"current_chat_id": metadata.chat_id, "chats": [self._metadata_to_raw(metadata)]})
        self._chat_file_path(metadata.chat_id).touch(exist_ok=True)

    def _migrate_legacy_current_chat_if_needed(self) -> None:
        """Move older single-chat history into the new `main` chat file.

        Earlier AMADEUS builds stored everything in `current_chat.jsonl`. This
        migration preserves that history without keeping two active storage paths.
        """
        main_chat_file = self._chat_file_path("main")
        if not self.legacy_file_path.exists() or main_chat_file.exists() and main_chat_file.stat().st_size > 0:
            return

        shutil.copyfile(self.legacy_file_path, main_chat_file)
        self._touch_chat("main")

    def _index_has_chats(self, index: dict[str, Any]) -> bool:
        """Return True when the index contains at least one parseable chat."""
        raw_chats = index.get("chats")
        if not isinstance(raw_chats, list):
            return False
        return any(self._metadata_from_raw(raw_chat) is not None for raw_chat in raw_chats)

    def _read_index(self) -> dict[str, Any]:
        """Read the metadata index while tolerating corruption."""
        try:
            raw_index: Any = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"current_chat_id": None, "chats": []}
        if not isinstance(raw_index, dict):
            return {"current_chat_id": None, "chats": []}
        raw_index.setdefault("chats", [])
        return raw_index

    def _write_index(self, index: dict[str, Any]) -> None:
        """Persist chat metadata in a human-readable JSON file."""
        self.chat_directory.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    def _metadata_from_raw(self, raw_chat: Any) -> ChatMetadata | None:
        """Parse one index row into safe metadata.

        The parser accepts older metadata rows that do not yet have description or
        summary fields. This keeps patch updates from breaking existing chats.
        """
        if not isinstance(raw_chat, dict):
            return None
        chat_id = raw_chat.get("chat_id")
        title = raw_chat.get("title")
        created_at = raw_chat.get("created_at")
        updated_at = raw_chat.get("updated_at")
        if not all(isinstance(value, str) and value for value in (chat_id, title, created_at, updated_at)):
            return None
        description = raw_chat.get("description") if isinstance(raw_chat.get("description"), str) else ""
        summary = raw_chat.get("summary") if isinstance(raw_chat.get("summary"), str) else ""
        return ChatMetadata(
            chat_id=chat_id,
            title=title,
            created_at=created_at,
            updated_at=updated_at,
            description=description,
            summary=summary,
        )

    def _metadata_to_raw(self, metadata: ChatMetadata) -> dict[str, str]:
        """Convert metadata to the JSON index shape."""
        return {
            "chat_id": metadata.chat_id,
            "title": metadata.title,
            "description": metadata.description,
            "summary": metadata.summary,
            "created_at": metadata.created_at,
            "updated_at": metadata.updated_at,
        }

    def _replace_metadata(self, metadata: ChatMetadata) -> None:
        """Replace one chat metadata row while preserving the rest of the index."""
        index = self._read_index()
        replaced = False
        raw_chats: list[dict[str, Any]] = []
        for raw_chat in index.get("chats", []):
            if not isinstance(raw_chat, dict):
                continue
            if raw_chat.get("chat_id") == metadata.chat_id:
                raw_chats.append(self._metadata_to_raw(metadata))
                replaced = True
            else:
                raw_chats.append(raw_chat)
        if not replaced:
            raise ValueError(f"Unknown chat id: {metadata.chat_id}")
        index["chats"] = raw_chats
        index["current_chat_id"] = metadata.chat_id
        self._write_index(index)

    def _touch_chat(self, chat_id: str) -> None:
        """Update the metadata timestamp after a message is saved."""
        index = self._read_index()
        now = self._now()
        for raw_chat in index.get("chats", []):
            if isinstance(raw_chat, dict) and raw_chat.get("chat_id") == chat_id:
                raw_chat["updated_at"] = now
                break
        index["current_chat_id"] = chat_id
        self._write_index(index)

    def _chat_file_path(self, chat_id: str) -> Path:
        """Return the JSONL path for one chat id after sanitizing the filename."""
        safe_chat_id = self._safe_chat_id(chat_id)
        return self.chat_directory / f"{safe_chat_id}.jsonl"

    def _safe_chat_id(self, chat_id: str) -> str:
        """Keep chat ids filename-safe because they become JSONL filenames."""
        safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", chat_id).strip("_")
        return safe_id or "chat"

    def _new_chat_id(self) -> str:
        """Create a unique local chat id from the current UTC timestamp."""
        base = datetime.now(timezone.utc).strftime("chat_%Y%m%d_%H%M%S_%f")
        existing_ids = {chat.chat_id for chat in self.list_chats()}
        chat_id = base
        counter = 2
        while chat_id in existing_ids or self._chat_file_path(chat_id).exists():
            chat_id = f"{base}_{counter}"
            counter += 1
        return chat_id

    def _default_new_chat_title(self) -> str:
        """Return a simple human title for a newly created chat."""
        return f"New Chat {len(self.list_chats()) + 1}"

    def _now(self) -> str:
        """Return one timestamp format for all chat metadata and messages."""
        return datetime.now(timezone.utc).isoformat()

    def _parse_line(self, line: str, message_number: int) -> ChatHistoryMessage | None:
        """Parse one JSONL row while tolerating corrupted lines."""
        try:
            raw_record: Any = json.loads(line)
        except json.JSONDecodeError:
            return None

        if not isinstance(raw_record, dict):
            return None

        speaker = raw_record.get("speaker")
        message = raw_record.get("message")
        created_at = raw_record.get("created_at")
        if not all(isinstance(value, str) for value in (speaker, message, created_at)):
            return None

        return ChatHistoryMessage(
            speaker=speaker,
            message=message,
            created_at=created_at,
            message_number=message_number,
        )
