"""Dedicated JSONL persistence for the AMADEUS Flow Chat home conversation.

Flow history is intentionally separate from dedicated chats. It must not be
selected, deleted, or used as active-chat history by the existing chat workspace.
"""

import json
import msvcrt
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_path_locks: dict[Path, threading.Lock] = {}
_path_locks_guard = threading.Lock()


def _lock_for_path(path: Path) -> threading.Lock:
    """Return the shared in-process lock for one Flow history file."""
    with _path_locks_guard:
        return _path_locks.setdefault(path, threading.Lock())


@contextmanager
def _interprocess_lock(lock_path: Path) -> Any:
    """Hold a Windows byte-range lock until the protected file update completes."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        lock_file.seek(0)
        while True:
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.01)

        try:
            yield
        finally:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


@dataclass(frozen=True, slots=True)
class FlowChatMessage:
    """One persisted Flow Chat message in JSONL file order."""

    speaker: str
    message: str
    created_at: str


class FlowChatStore:
    """Store Flow Chat messages under the isolated ``data/flow_chat`` directory."""

    def __init__(self, project_root: Path, relative_directory: str = "data/flow_chat") -> None:
        # Flow history must remain outside data/chats so dedicated-chat actions cannot affect it.
        resolved_project_root = project_root.resolve()
        self.flow_chat_directory = (resolved_project_root / relative_directory).resolve()
        dedicated_chat_directory = (resolved_project_root / "data/chats").resolve()
        try:
            self.flow_chat_directory.relative_to(resolved_project_root)
        except ValueError as error:
            raise ValueError("Flow Chat storage must remain under the project root.") from error
        try:
            self.flow_chat_directory.relative_to(dedicated_chat_directory)
        except ValueError:
            pass
        else:
            raise ValueError("Flow Chat storage cannot use the dedicated chat directory.")
        self.messages_path = self.flow_chat_directory / "flow_messages.jsonl"
        self.lock_path = self.flow_chat_directory / "flow_messages.lock"
        self._messages_lock = _lock_for_path(self.messages_path)
        self.flow_chat_directory.mkdir(parents=True, exist_ok=True)

    def load_messages(self) -> list[FlowChatMessage]:
        """Return valid Flow messages in their persisted JSONL order.

        Missing files and malformed rows are ignored so local data damage cannot
        prevent Flow Chat from opening.
        """
        try:
            lines = self.messages_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

        messages: list[FlowChatMessage] = []
        for line in lines:
            message = self._parse_message(line)
            if message is not None:
                messages.append(message)
        return messages

    def append_message(self, speaker: str, message: str) -> None:
        """Persist one non-empty Flow message using an atomic file replacement."""
        record = self._build_record(speaker, message)
        if record is None:
            return

        self._append_records([record])

    def append_exchange(self, user_message: str, response: str) -> None:
        """Persist one complete Flow user/AMADEUS exchange in one file replacement."""
        user_record = self._build_record("User", user_message)
        response_record = self._build_record("AMADEUS", response)
        if user_record is None or response_record is None:
            return

        # Build both records before modifying storage so a second-record failure leaves no half exchange.
        self._append_records([user_record, response_record])

    def _build_record(self, speaker: str, message: str) -> dict[str, str] | None:
        """Validate and timestamp one local Flow record before it is written."""
        if not isinstance(speaker, str) or not isinstance(message, str):
            return None
        clean_speaker = speaker.strip()
        clean_message = message.strip()
        if not clean_speaker or not clean_message:
            return None
        return {
            "speaker": clean_speaker,
            "message": clean_message,
            "created_at": self._now(),
        }

    def _append_records(self, records: list[dict[str, str]]) -> None:
        """Append already-validated records while holding one atomic update boundary."""
        # Keep the read and replacement together across threads and AMADEUS processes.
        with self._messages_lock:
            with _interprocess_lock(self.lock_path):
                try:
                    existing = self.messages_path.read_text(encoding="utf-8", errors="replace")
                except FileNotFoundError:
                    existing = ""

                if existing and not existing.endswith("\n"):
                    existing += "\n"
                additions = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
                self._atomic_write(existing + additions)

    def _atomic_write(self, content: str) -> None:
        """Replace the small local JSONL file without leaving a partial record."""
        self.flow_chat_directory.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.flow_chat_directory,
                prefix=f".{self.messages_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.messages_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    # Do not hide a write failure when best-effort cleanup also fails.
                    pass

    def _parse_message(self, line: str) -> FlowChatMessage | None:
        """Parse a JSONL row without trusting hand-edited or damaged data."""
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
        return FlowChatMessage(speaker=speaker, message=message, created_at=created_at)

    def _now(self) -> str:
        """Return a timezone-aware timestamp consistent with the chat store."""
        return datetime.now(timezone.utc).isoformat()
