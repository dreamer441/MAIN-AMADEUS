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

    def add_global_memory_with_id(self, memory_id: str, content: str, source_chat_id: str | None = None) -> MemoryEntry:
        """Append a caller-stable global entry for explicitly approved source memory."""
        clean_id = memory_id.strip()
        if not clean_id:
            raise ValueError("Memory id cannot be empty.")
        now = self._now()
        entry = MemoryEntry(clean_id, "global", content.strip(), now, now, source_chat_id)
        if not entry.content:
            raise ValueError("Memory content cannot be empty.")
        with self.global_memory_path.open("a", encoding="utf-8") as memory_file:
            memory_file.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return entry

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

    def list_all_memory(self) -> list[MemoryEntry]:
        """Return legacy entries, including soft-deleted rows, for safe migration."""
        entries: list[MemoryEntry] = []
        for path in self._memory_paths():
            entries.extend(self._read_entries(path, active_only=False))
        return entries

    def get_memory(self, memory_id: str) -> MemoryEntry | None:
        """Return one memory by stable id across global and chat scopes."""
        for path in self._memory_paths():
            for entry in self._read_entries(path, active_only=False):
                if entry.memory_id == memory_id:
                    return entry
        return None

    def update_memory(self, memory_id: str, content: str) -> MemoryEntry:
        """Update one memory in-place while preserving its stable identity."""
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Memory content cannot be empty.")
        return self._rewrite_memory(
            memory_id,
            lambda entry: MemoryEntry(
                memory_id=entry.memory_id,
                scope=entry.scope,
                content=clean_content,
                created_at=entry.created_at,
                updated_at=self._now(),
                source_chat_id=entry.source_chat_id,
                status=entry.status,
            ),
        )

    def delete_memory(self, memory_id: str) -> MemoryEntry:
        """Soft-delete one memory so JSONL audit history remains inspectable."""
        return self._rewrite_memory(
            memory_id,
            lambda entry: MemoryEntry(
                memory_id=entry.memory_id,
                scope=entry.scope,
                content=entry.content,
                created_at=entry.created_at,
                updated_at=self._now(),
                source_chat_id=entry.source_chat_id,
                status="deleted",
            ),
        )

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

    def _read_entries(self, path: Path, *, active_only: bool = True) -> list[MemoryEntry]:
        """Read memory entries while tolerating corrupted JSONL rows."""
        if not path.exists():
            return []

        entries: list[MemoryEntry] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                raw: Any = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry = MemoryEntry.from_dict(raw)
            if entry is not None and (not active_only or entry.status == "active"):
                entries.append(entry)
        return entries

    def _memory_paths(self) -> list[Path]:
        return [self.global_memory_path, *sorted(self.chat_memory_directory.glob("*.jsonl"))]

    def _rewrite_memory(self, memory_id: str, transform) -> MemoryEntry:
        clean_id = str(memory_id or "").strip()
        if not clean_id:
            raise ValueError("Memory id cannot be empty.")
        for path in self._memory_paths():
            if not path.exists():
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            rewritten: list[str] = []
            updated: MemoryEntry | None = None
            for line in lines:
                try:
                    raw: Any = json.loads(line)
                except json.JSONDecodeError:
                    rewritten.append(line)
                    continue
                entry = MemoryEntry.from_dict(raw)
                if entry is not None and entry.memory_id == clean_id:
                    updated = transform(entry)
                    rewritten.append(json.dumps(updated.to_dict(), ensure_ascii=False))
                else:
                    rewritten.append(line)
            if updated is not None:
                temporary = path.with_suffix(path.suffix + ".tmp")
                temporary.write_text("\n".join(rewritten) + ("\n" if rewritten else ""), encoding="utf-8")
                temporary.replace(path)
                return updated
        raise KeyError(f"Unknown memory id: {clean_id}")

    def _safe_chat_id(self, chat_id: str) -> str:
        """Keep chat ids safe because they become memory filenames."""
        safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", chat_id).strip("_")
        return safe_id or "chat"

    def _now(self) -> str:
        """Return a timezone-aware timestamp for memory auditing."""
        return datetime.now(timezone.utc).isoformat()
