"""Local JSONL memory storage for AMADEUS.

Memory storage is deliberately boring and inspectable. Each memory is one JSON
line so Dato can open the files manually if something goes wrong. V1 does not
edit or delete entries yet; it only appends active memories and reads them back.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from memory_module.memory_entry import MemoryEntry


class MemoryStore:
    """Stores explicit global and per-chat memory entries on disk."""

    def __init__(self, project_root: Path, relative_directory: str = "data/memory") -> None:
        # Runtime memory lives under data/memory so source-controlled modules stay clean.
        self.memory_directory = project_root.resolve() / relative_directory
        self.chat_memory_directory = self.memory_directory / "chats"
        self.global_memory_path = self.memory_directory / "global_memory.jsonl"
        self.memory_directory.mkdir(parents=True, exist_ok=True)
        self.chat_memory_directory.mkdir(parents=True, exist_ok=True)
        self.global_memory_path.touch(exist_ok=True)

    def add_global_memory(self, content: str, source_chat_id: str | None = None) -> MemoryEntry:
        """Append one cross-chat memory entry."""
        return self._append_memory(scope="global", content=content, path=self.global_memory_path, source_chat_id=source_chat_id)

    def add_chat_memory(self, chat_id: str, content: str) -> MemoryEntry:
        """Append one memory entry that belongs only to a specific chat."""
        safe_chat_id = self._safe_chat_id(chat_id)
        path = self.chat_memory_directory / f"{safe_chat_id}.jsonl"
        path.touch(exist_ok=True)
        return self._append_memory(scope="chat", content=content, path=path, source_chat_id=chat_id)

    def list_global_memory(self) -> list[MemoryEntry]:
        """Return all active global memories in saved order."""
        return self._read_entries(self.global_memory_path)

    def list_chat_memory(self, chat_id: str) -> list[MemoryEntry]:
        """Return all active memories for one chat."""
        safe_chat_id = self._safe_chat_id(chat_id)
        return self._read_entries(self.chat_memory_directory / f"{safe_chat_id}.jsonl")

    def _append_memory(self, scope: str, content: str, path: Path, source_chat_id: str | None) -> MemoryEntry:
        """Write one memory entry as a JSONL row and return the parsed object."""
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Memory content cannot be empty.")

        now = self._now()
        entry = MemoryEntry(
            memory_id=f"mem_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            scope=scope,
            content=clean_content,
            created_at=now,
            updated_at=now,
            source_chat_id=source_chat_id,
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as memory_file:
            memory_file.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return entry

    def _read_entries(self, path: Path) -> list[MemoryEntry]:
        """Read active memory entries while tolerating corrupted JSONL rows."""
        if not path.exists():
            return []

        entries: list[MemoryEntry] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                raw: Any = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry = MemoryEntry.from_dict(raw)
            if entry is not None and entry.status == "active":
                entries.append(entry)
        return entries

    def _safe_chat_id(self, chat_id: str) -> str:
        """Keep chat ids safe because they become memory filenames."""
        safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", chat_id).strip("_")
        return safe_id or "chat"

    def _now(self) -> str:
        """Return a timezone-aware timestamp for memory auditing."""
        return datetime.now(timezone.utc).isoformat()
