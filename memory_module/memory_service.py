"""High-level memory service for AMADEUS.

The service is the boundary Core, Context Builder, and `[memory]` use. It keeps
formatting and prompt injection rules out of the raw storage class.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from memory_module.memory_entry import MemoryEntry
from memory_module.memory_store import MemoryStore
from memory_module.models import KnowledgeLayer, KnowledgeSource, MemoryBrick
from memory_module.repository import SQLiteMemoryRepository


class MemoryService:
    """Coordinates explicit global and chat-scoped AMADEUS memory."""

    def __init__(self, project_root: Path) -> None:
        self.store = MemoryStore(project_root)
        # JSONL remains the legacy compatibility store; SQLite adds structured metadata.
        self.repository = SQLiteMemoryRepository(project_root)
        self._migrate_legacy_memory()

    def save_global_memory(self, content: str, source_chat_id: str | None = None) -> MemoryEntry:
        """Save memory that should travel across all chats."""
        entry = self.store.add_global_memory(content, source_chat_id=source_chat_id)
        self._sync_legacy_entry(entry, creation_source="explicit_user_action")
        return entry

    def save_chat_memory(self, chat_id: str, content: str) -> MemoryEntry:
        """Save memory that should only affect the current chat."""
        entry = self.store.add_chat_memory(chat_id, content)
        self._sync_legacy_entry(entry, creation_source="explicit_user_action")
        return entry

    def list_global_memory(self) -> list[MemoryEntry]:
        """List active global memory entries."""
        return self.store.list_global_memory()

    def list_chat_memory(self, chat_id: str) -> list[MemoryEntry]:
        """List active memory entries for one chat."""
        return self.store.list_chat_memory(chat_id)

    def get_memory(self, memory_id: str) -> MemoryEntry | None:
        """Return one explicit memory by stable id."""
        return self.store.get_memory(memory_id)

    def update_memory(self, memory_id: str, content: str) -> MemoryEntry:
        """Update one explicit memory while preserving its id and scope."""
        entry = self.store.update_memory(memory_id, content)
        self._sync_legacy_entry(entry, creation_source="explicit_user_action")
        return entry

    def delete_memory(self, memory_id: str) -> MemoryEntry:
        """Soft-delete one explicit memory."""
        entry = self.store.delete_memory(memory_id)
        self._sync_legacy_entry(entry, creation_source="explicit_user_action")
        return entry

    def create_memory_brick(
        self,
        content: str,
        *,
        domains: Iterable[str] = ("user",),
        kinds: Iterable[str] = ("fact",),
        categories: Iterable[str] = ("Uncategorized",),
        scope_level: str = "global",
        scope_ref: str | None = None,
        evidence: dict[str, Any] | None = None,
        importance: float = 0.5,
        confidence: float = 1.0,
        creation_source: str = "explicit_user_action",
        extra: dict[str, Any] | None = None,
        memory_id: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        status: str = "active",
    ) -> MemoryBrick:
        """Create a structured brick without altering legacy prompt behavior."""
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("Memory content cannot be empty.")
        if scope_level not in {"global", "chat", "module"}:
            raise ValueError("Memory scope must be global, chat, or module.")
        now = self._now()
        brick = MemoryBrick(
            memory_id=memory_id or f"brick_{uuid4().hex}", content=clean_content,
            domains=self._clean_labels(domains, "user"), kinds=self._clean_labels(kinds, "fact"),
            categories=self._clean_labels(categories, "Uncategorized"), scope_level=scope_level,
            scope_ref=scope_ref, evidence=dict(evidence or {}),
            importance=self._score(importance, "importance"), confidence=self._score(confidence, "confidence"),
            creation_source=creation_source, extra=dict(extra or {}), created_at=created_at or now,
            updated_at=updated_at or now, status=status,
        )
        return self.repository.upsert_brick(brick)

    def get_memory_brick(self, memory_id: str) -> MemoryBrick | None:
        """Return structured metadata for an explicit or future memory brick."""
        return self.repository.get_brick(memory_id)

    def search_memory_bricks(self, query: str = "", **filters: Any) -> list[MemoryBrick]:
        """Search structured memory through FTS, falling back to parameterized LIKE."""
        return self.repository.search_bricks(query, **filters)

    def register_knowledge_source(
        self, *, source_type: str, owner_module: str, title: str, raw_locator: str,
        content_hash: str | None = None, source_id: str | None = None, raw_content: str = "",
    ) -> KnowledgeSource:
        """Register caller-supplied source content without reading its raw locator."""
        clean_type = source_type.strip()
        clean_owner = owner_module.strip()
        clean_locator = raw_locator.strip()
        if not all((clean_type, clean_owner, clean_locator)):
            raise ValueError("Source type, owner module, and raw locator are required.")
        clean_content = raw_content.strip()
        now = self._now()
        stable_id = source_id or "source_" + hashlib.sha256(
            f"{clean_owner}\0{clean_type}\0{clean_locator}".encode("utf-8")
        ).hexdigest()[:24]
        return self.repository.register_source(KnowledgeSource(
            source_id=stable_id, source_type=clean_type, owner_module=clean_owner,
            title=title.strip() or clean_locator, raw_locator=clean_locator,
            content_hash=content_hash or (hashlib.sha256(clean_content.encode("utf-8")).hexdigest() if clean_content else None),
            created_at=now, updated_at=now, raw_content=clean_content,
        ))

    def create_approved_source_memory(self, proposal: Any) -> MemoryBrick:
        """Persist one explicitly approved proposal through JSONL and structured storage."""
        source_id = str(proposal.source_id).strip()
        content = str(proposal.content).strip()
        if not source_id or not content:
            raise ValueError("Approved source memory requires a source id and content.")
        scope = str(proposal.scope).strip()
        if scope not in {"global", "chat", "module"}:
            raise ValueError("Approved source memory scope must be global, chat, or module.")
        stable_id = "mem_source_" + hashlib.sha256(f"{source_id}\0{content.casefold()}".encode("utf-8")).hexdigest()[:24]
        existing = self.store.get_memory(stable_id)
        if existing is None:
            entry = self.store.add_global_memory_with_id(stable_id, content, source_chat_id=None)
        else:
            entry = existing
        return self.create_memory_brick(
            entry.content, domains=proposal.domains, kinds=proposal.kinds, categories=proposal.categories,
            scope_level=scope, scope_ref=source_id if scope == "module" else None,
            evidence={"source_id": source_id, "source_hash": proposal.source_hash, "evidence": proposal.evidence},
            importance=proposal.importance, confidence=proposal.confidence, creation_source="approved_creation_proposal",
            extra={"proposal_id": proposal.proposal_id, "rationale": proposal.rationale, "legacy_jsonl": True},
            memory_id=entry.memory_id, created_at=entry.created_at, updated_at=entry.updated_at,
        )

    def list_knowledge_layers(self, source_id: str) -> list[KnowledgeLayer]:
        """Expose pending derived layers without generating any of them."""
        return self.repository.list_layers(source_id)

    def mark_source_layers_stale(self, source_id: str, content_hash: str | None) -> list[KnowledgeLayer]:
        """Compare a caller-supplied hash and mark derived layers stale when changed."""
        return self.repository.stale_layers(source_id, content_hash)

    def build_prompt_context(self, chat_id: str, max_entries_per_scope: int = 12, max_characters: int = 6_000) -> str | None:
        """Build compact memory context for the LLM prompt.

        Global memory enters every chat. Chat memory enters only the active chat.
        This is still explicit memory, not hidden reasoning and not automatic recall.
        """
        global_entries = self.list_global_memory()[-max_entries_per_scope:]
        chat_entries = self.list_chat_memory(chat_id)[-max_entries_per_scope:]
        if not global_entries and not chat_entries:
            return None

        sections: list[str] = [
            "Saved AMADEUS memory. These are explicit memories Dato marked with [memory].",
            "Use them for continuity, but do not treat them as a new user message.",
        ]

        if global_entries:
            sections.append("Global memory:")
            sections.extend(self._format_entry_for_prompt(entry) for entry in global_entries)

        if chat_entries:
            sections.append("Chat memory for this chat:")
            sections.extend(self._format_entry_for_prompt(entry) for entry in chat_entries)

        text = "\n".join(sections)
        if len(text) <= max_characters:
            return text
        return text[:max_characters] + "\n[Memory context truncated for prompt safety.]"

    def build_panel_text(self, chat_id: str, scope: str = "all") -> str:
        """Format memory for the right-side Memory panel."""
        normalized_scope = scope.strip().lower() or "all"
        include_global = normalized_scope in {"all", "global"}
        include_chat = normalized_scope in {"all", "chat"}

        lines: list[str] = []
        if include_global:
            global_entries = self.list_global_memory()
            lines.append(f"Global Memory ({len(global_entries)})")
            lines.extend(self._format_entries_for_panel(global_entries))
            lines.append("")

        if include_chat:
            chat_entries = self.list_chat_memory(chat_id)
            lines.append(f"Chat Memory ({len(chat_entries)})")
            lines.extend(self._format_entries_for_panel(chat_entries))

        if not lines:
            return "Unknown memory scope. Use global, chat, or all."
        return "\n".join(lines).strip()

    def build_panel_payload(self, chat_id: str, scope: str = "all", title: str | None = None) -> dict[str, object]:
        """Return a GUI side-panel payload for the Memory tab."""
        normalized_scope = scope.strip().lower() or "all"
        global_count = len(self.list_global_memory())
        chat_count = len(self.list_chat_memory(chat_id))
        return {
            "type": "memory",
            "title": title or "AMADEUS Memory",
            "content": self.build_panel_text(chat_id, normalized_scope),
            "metadata": {
                "scope": normalized_scope,
                "global_count": global_count,
                "chat_count": chat_count,
            },
        }

    def _format_entry_for_prompt(self, entry: MemoryEntry) -> str:
        """Keep prompt memory compact and readable for local models."""
        return f"- {entry.content}"

    def _format_entries_for_panel(self, entries: list[MemoryEntry]) -> list[str]:
        """Return readable panel lines with ids so future delete/update can target them."""
        if not entries:
            return ["No saved memory in this scope."]

        lines: list[str] = []
        for index, entry in enumerate(entries, start=1):
            lines.append(f"{index}. {entry.content}")
            lines.append(f"   id: {entry.memory_id}")
        return lines

    def _migrate_legacy_memory(self) -> None:
        """Idempotently mirror existing JSONL entries with non-authoritative legacy metadata."""
        for entry in self.store.list_all_memory():
            self._sync_legacy_entry(entry, creation_source="legacy_jsonl_migration")

    def _sync_legacy_entry(self, entry: MemoryEntry, *, creation_source: str) -> MemoryBrick:
        """Map an existing JSONL record to a same-id brick without changing JSONL."""
        domain = "user" if entry.scope == "global" else "chat"
        existing = self.repository.get_brick(entry.memory_id)
        return self.create_memory_brick(
            entry.content, domains=(domain,), kinds=("fact",), categories=("Uncategorized",),
            scope_level=entry.scope, scope_ref=entry.source_chat_id if entry.scope == "chat" else None,
            evidence={"source_chat_id": entry.source_chat_id, "legacy_memory_id": entry.memory_id},
            importance=0.5, confidence=1.0, creation_source=creation_source,
            extra={"legacy_jsonl": True, "legacy_scope": entry.scope}, memory_id=entry.memory_id,
            created_at=existing.created_at if existing else entry.created_at, updated_at=entry.updated_at,
            status=entry.status,
        )

    @staticmethod
    def _clean_labels(labels: Iterable[str], fallback: str) -> tuple[str, ...]:
        clean = tuple(dict.fromkeys(str(value).strip() for value in labels if str(value).strip()))
        return clean or (fallback,)

    @staticmethod
    def _score(value: float, name: str) -> float:
        score = float(value)
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"Memory {name} must be between 0 and 1.")
        return score

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
