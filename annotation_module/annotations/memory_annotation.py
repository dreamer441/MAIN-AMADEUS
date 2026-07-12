"""`[memory]` annotation handler for explicit AMADEUS memory.

Memory is intentionally annotation-driven in V1. Normal conversation does not
silently become long-term memory, which keeps AMADEUS's context cleaner and gives
Dato direct control over what becomes durable.
"""

import re

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation
from annotation_module.annotation_result import AnnotationResult


class MemoryAnnotation:
    """Handles scoped memory commands such as `[memory][global]` and `[memory][chat]`."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> AnnotationResult | str:
        """Save memory or open a memory list in the right panel."""
        if not annotation.arguments:
            return self._open_memory_panel(context, scope="all", response="Opened AMADEUS memory in the right panel.")

        command = self._normalize_token(annotation.arguments[0])
        chat_id = context.current_chat_id_provider()

        if command == "global":
            return self._save_memory(context, scope="global", chat_id=chat_id, content=annotation.content)

        if command == "chat":
            return self._save_memory(context, scope="chat", chat_id=chat_id, content=annotation.content)

        if command == "list":
            scope = self._normalize_token(annotation.arguments[1]) if len(annotation.arguments) > 1 else "all"
            if scope not in {"all", "global", "chat"}:
                return self._memory_help(f"Unknown memory list scope: `{annotation.arguments[1]}`")
            return self._open_memory_panel(context, scope=scope, response=f"Opened {scope} memory in the right panel.")

        if command in {"help", "status"}:
            return self._memory_help()

        return self._memory_help(f"Unknown memory command: `{annotation.arguments[0]}`")

    def _save_memory(self, context: AnnotationContext, scope: str, chat_id: str, content: str) -> AnnotationResult | str:
        """Save global or chat memory, then refresh the right-side Memory panel."""
        clean_content = content.strip()
        if not clean_content:
            return self._memory_help(f"No memory text was provided for `[memory][{scope}]`.")

        if scope == "global":
            entry = context.memory_service.save_global_memory(clean_content, source_chat_id=chat_id)
            response = (
                "Saved to global memory.\n"
                f"Memory id: `{entry.memory_id}`\n\n"
                "This memory will be injected across chats. The Memory panel was updated."
            )
            panel_scope = "global"
        else:
            entry = context.memory_service.save_chat_memory(chat_id, clean_content)
            response = (
                "Saved to chat memory.\n"
                f"Memory id: `{entry.memory_id}`\n\n"
                "This memory applies only to the current chat. The Memory panel was updated."
            )
            panel_scope = "chat"

        return AnnotationResult(
            response=response,
            side_panel=context.memory_service.build_panel_payload(
                chat_id=chat_id,
                scope=panel_scope,
                title=f"AMADEUS {scope.title()} Memory",
            ),
        )

    def _open_memory_panel(self, context: AnnotationContext, scope: str, response: str) -> AnnotationResult:
        """Open a read-only memory list in the right panel instead of dumping it into chat."""
        chat_id = context.current_chat_id_provider()
        title = "AMADEUS Memory" if scope == "all" else f"AMADEUS {scope.title()} Memory"
        return AnnotationResult(
            response=response,
            side_panel=context.memory_service.build_panel_payload(chat_id=chat_id, scope=scope, title=title),
        )

    def _memory_help(self, problem: str | None = None) -> str:
        """Return concise usage help when a memory command is incomplete or unknown."""
        prefix = f"{problem}\n\n" if problem else ""
        return (
            f"{prefix}Memory annotation commands:\n\n"
            "* `[memory][global] text` - save memory across all chats\n"
            "* `[memory][chat] text` - save memory only for this chat\n"
            "* `[memory][list]` - open all memory in the right panel\n"
            "* `[memory][list][global]` - open global memory\n"
            "* `[memory][list][chat]` - open chat memory\n\n"
            "Memory is explicit in V1. AMADEUS will not save normal conversation automatically."
        )

    def _normalize_token(self, token: str) -> str:
        """Normalize memory commands without affecting freeform memory content."""
        normalized = token.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_") or "all"
