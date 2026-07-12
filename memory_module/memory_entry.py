"""Memory entry model for AMADEUS.

This file defines the smallest durable unit of AMADEUS memory. Memory is kept
separate from chat history because chat history is a transcript, while memory is
selected context that should intentionally guide future conversations.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryEntry:
    """One explicit memory saved by Dato through the `[memory]` annotation.

    V1 memory is intentionally not autonomous. AMADEUS only writes memory when
    Dato marks it with `[memory][global]` or `[memory][chat]`. That prevents noisy
    automatic memory pollution while the system is still young.
    """

    memory_id: str
    scope: str
    content: str
    created_at: str
    updated_at: str
    source_chat_id: str | None = None
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the memory entry into a stable JSON shape."""
        return {
            "memory_id": self.memory_id,
            "scope": self.scope,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_chat_id": self.source_chat_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "MemoryEntry | None":
        """Parse a JSON object into a safe MemoryEntry, or ignore bad rows."""
        if not isinstance(raw, dict):
            return None

        memory_id = raw.get("memory_id")
        scope = raw.get("scope")
        content = raw.get("content")
        created_at = raw.get("created_at")
        updated_at = raw.get("updated_at")
        source_chat_id = raw.get("source_chat_id")
        status = raw.get("status", "active")

        if not all(isinstance(value, str) and value for value in (memory_id, scope, content, created_at, updated_at)):
            return None
        if source_chat_id is not None and not isinstance(source_chat_id, str):
            source_chat_id = None
        if not isinstance(status, str) or not status:
            status = "active"

        return cls(
            memory_id=memory_id,
            scope=scope,
            content=content,
            created_at=created_at,
            updated_at=updated_at,
            source_chat_id=source_chat_id,
            status=status,
        )
