"""Flow-specific prompt context selection.

Flow history and dedicated-chat metadata are deliberately separate prompt sections.
The registry supplies metadata only, so this module never receives dedicated-chat
message bodies.
"""

from dataclasses import dataclass

from amadeus_trace import TraceLogger
from chat_registry import ChatMetadata, ChatRegistry
from flow_chat.flow_chat_store import FlowChatMessage, FlowChatStore


@dataclass(frozen=True, slots=True)
class FlowContextBundle:
    """The two context layers available to one Flow request."""

    recent_flow_history: str | None
    dedicated_chat_metadata: str


class FlowContextBuilder:
    """Build Flow-only history and metadata context without reading chat bodies."""

    def __init__(
        self,
        flow_chat_store: FlowChatStore,
        chat_registry: ChatRegistry,
        recent_message_limit: int = 18,
        max_history_characters: int = 4_000,
    ) -> None:
        self.flow_chat_store = flow_chat_store
        self.chat_registry = chat_registry
        self.recent_message_limit = recent_message_limit
        self.max_history_characters = max_history_characters

    def build_for_message(self, message: str, trace_logger: TraceLogger | None = None) -> FlowContextBundle:
        """Build isolated Flow context for the current message.

        ``message`` remains part of the public context-builder shape used by normal
        chat, though Flow V1 does not use it to select additional context.
        """
        del message
        self._trace(trace_logger, "Flow Context Started", "Selecting Flow history and dedicated-chat metadata.")
        recent_flow_history = self._build_recent_flow_history()
        if recent_flow_history:
            self._trace(trace_logger, "Flow History Loaded", "Loaded recent Flow history.", level="success")

        self._trace(trace_logger, "Dedicated Chat Registry Requested", "Requesting dedicated-chat metadata only.")
        metadata = self.chat_registry.get_relevant_chat_metadata()
        self._trace(trace_logger, "Dedicated Chat Registry Loaded", "Dedicated-chat metadata loaded without chat message bodies.", level="success")

        context_bundle = FlowContextBundle(
            recent_flow_history=recent_flow_history,
            dedicated_chat_metadata=self._format_dedicated_chat_metadata(metadata),
        )
        self._trace(trace_logger, "Flow Context Complete", "Flow history and dedicated-chat metadata context are ready.", level="success")
        return context_bundle

    def _build_recent_flow_history(self) -> str | None:
        """Format bounded persisted Flow messages in chronological order."""
        messages = self.flow_chat_store.load_messages()
        if not messages:
            return None

        selected_lines: list[str] = []
        used_characters = 0
        for saved_message in reversed(messages[-self.recent_message_limit :]):
            line = self._format_flow_message(saved_message)
            if not line:
                continue
            line_cost = len(line) + 1
            if selected_lines and used_characters + line_cost > self.max_history_characters:
                break
            selected_lines.append(line)
            used_characters += line_cost

        if not selected_lines:
            return None
        selected_lines.reverse()
        return "[RECENT FLOW HISTORY]\n" + "\n".join(selected_lines)

    def _format_flow_message(self, saved_message: FlowChatMessage) -> str:
        """Keep one persisted Flow message compact enough for prompt context."""
        speaker = " ".join(saved_message.speaker.strip().split()) or "Unknown"
        message = " ".join(saved_message.message.strip().split())
        return f"{speaker}: {message}" if message else ""

    def _format_dedicated_chat_metadata(self, metadata: list[ChatMetadata]) -> str:
        """Render the registry's metadata-only view without accepting message content."""
        lines = [
            "[AVAILABLE DEDICATED CHATS]",
            "These are metadata records only: chat id, title, and description.",
            "They are not chat history. Do not claim to know, read, or have access to any dedicated chat's full contents.",
        ]
        if not metadata:
            lines.append("- No dedicated chats are currently available.")
            return "\n".join(lines)

        for chat in metadata:
            lines.extend(
                (
                    f"- id: {chat.chat_id}",
                    f"  title: {chat.title}",
                    f"  description: {chat.description}",
                )
            )
        return "\n".join(lines)

    def _trace(self, trace_logger: TraceLogger | None, title: str, message: str, level: str = "info") -> None:
        """Record real Flow-context boundaries only when Core supplied tracing."""
        if trace_logger is not None:
            trace_logger.add_event("module", title, message, level)
