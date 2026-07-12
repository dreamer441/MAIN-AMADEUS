"""High-level memory service for AMADEUS.

The service is the boundary Core, Context Builder, and `[memory]` use. It keeps
formatting and prompt injection rules out of the raw storage class.
"""

from pathlib import Path

from memory_module.memory_entry import MemoryEntry
from memory_module.memory_store import MemoryStore


class MemoryService:
    """Coordinates explicit global and chat-scoped AMADEUS memory."""

    def __init__(self, project_root: Path) -> None:
        self.store = MemoryStore(project_root)

    def save_global_memory(self, content: str, source_chat_id: str | None = None) -> MemoryEntry:
        """Save memory that should travel across all chats."""
        return self.store.add_global_memory(content, source_chat_id=source_chat_id)

    def save_chat_memory(self, chat_id: str, content: str) -> MemoryEntry:
        """Save memory that should only affect the current chat."""
        return self.store.add_chat_memory(chat_id, content)

    def list_global_memory(self) -> list[MemoryEntry]:
        """List active global memory entries."""
        return self.store.list_global_memory()

    def list_chat_memory(self, chat_id: str) -> list[MemoryEntry]:
        """List active memory entries for one chat."""
        return self.store.list_chat_memory(chat_id)

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
