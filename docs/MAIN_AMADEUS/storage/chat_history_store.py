import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ChatHistoryMessage:
    """One persisted chat message displayed in the GUI."""

    speaker: str
    message: str
    created_at: str


class ChatHistoryStore:
    """Append-only JSONL storage for the current local AMADEUS chat."""

    def __init__(self, project_root: Path, relative_path: str = "data/chats/current_chat.jsonl") -> None:
        # Chat persistence is local runtime data, not source code or module logic.
        self.file_path = project_root.resolve() / relative_path

    def append_message(self, speaker: str, message: str) -> None:
        """Persist one message to the current chat file."""
        clean_speaker = speaker.strip()
        clean_message = message.strip()
        if not clean_speaker or not clean_message:
            return

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "speaker": clean_speaker,
            "message": clean_message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with self.file_path.open("a", encoding="utf-8") as chat_file:
            chat_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_messages(self, limit: int = 200) -> list[ChatHistoryMessage]:
        """Load recent chat messages from disk for GUI resume."""
        if not self.file_path.exists():
            return []

        messages: list[ChatHistoryMessage] = []
        for line in self.file_path.read_text(encoding="utf-8").splitlines():
            message = self._parse_line(line)
            if message is not None:
                messages.append(message)

        return messages[-limit:]

    def _parse_line(self, line: str) -> ChatHistoryMessage | None:
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

        return ChatHistoryMessage(speaker=speaker, message=message, created_at=created_at)
