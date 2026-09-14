"""Adapter boundary for a future disposable local vector index."""

from typing import Protocol


class VectorStore(Protocol):
    """Optional secondary index; structured SQLite search remains authoritative."""

    def upsert(self, memory_id: str, content: str) -> None:
        """Index one brick without becoming its canonical store."""

    def search(self, query: str, limit: int = 20) -> list[str]:
        """Return matching brick ids in relevance order."""


class NullVectorStore:
    """No-op implementation used until a local vector adapter is deliberately added."""

    def upsert(self, memory_id: str, content: str) -> None:
        return None

    def search(self, query: str, limit: int = 20) -> list[str]:
        return []
