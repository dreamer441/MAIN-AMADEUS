"""Context selection for normal AMADEUS chat.

Context Builder is the place where AMADEUS decides what extra information enters a
prompt. This prevents Core from growing too much and prevents Chat from reading
files/storage/memory directly.
"""

from dataclasses import dataclass

from amadeus_trace import TraceLogger
from memory_module import MemoryService
from project_file_reader import ProjectFileReader
from storage import ChatHistoryStore


PROJECT_CONTEXT_KEYWORDS = (
    "file",
    "files",
    "folder",
    "folders",
    "module",
    "modules",
    "project",
    "readme",
    "features",
    "future_updates",
    "documentation",
    "structure",
)


@dataclass(frozen=True)
class ChatContextBundle:
    """Prompt context selected for one user message.

    `chat_workspace_context` is active only for the current chat. It contains the
    title/description Dato supplied when creating the workspace, not generated
    long-term memory.
    """

    recent_conversation: str | None
    project_context: str | None
    memory_context: str | None
    chat_workspace_context: str | None

    @property
    def project_context_active(self) -> bool:
        """Return True when project/file context is being injected."""
        return self.project_context is not None


class ChatContextBuilder:
    """Selects safe context for Chat without making Core or Chat own that logic."""

    def __init__(
        self,
        chat_history_store: ChatHistoryStore,
        file_reader: ProjectFileReader,
        memory_service: MemoryService | None = None,
        recent_message_limit: int = 18,
        max_history_characters: int = 4_000,
    ) -> None:
        # History context stays small so local models do not lose the current request.
        # This is a temporary character-based limit until a token-aware system exists.
        self.chat_history_store = chat_history_store
        self.file_reader = file_reader
        self.memory_service = memory_service
        self.recent_message_limit = recent_message_limit
        self.max_history_characters = max_history_characters

    def build_for_message(self, message: str, trace_logger: TraceLogger | None = None) -> ChatContextBundle:
        """Build the context bundle for the current user message."""
        if trace_logger is not None:
            trace_logger.add_event(
                "module",
                "Context Building",
                "Selecting applicable context for normal chat.",
            )
        current_chat_id = self.chat_history_store.get_current_chat_id()
        context_bundle = ChatContextBundle(
            recent_conversation=self._build_recent_conversation_context(),
            project_context=self._build_project_context_if_relevant(message),
            memory_context=self._build_memory_context(current_chat_id),
            chat_workspace_context=self._build_chat_workspace_context(current_chat_id),
        )
        if trace_logger is not None:
            selected_types = []
            if context_bundle.recent_conversation:
                selected_types.append("recent_conversation")
            if context_bundle.project_context:
                selected_types.append("project_overview")
            if context_bundle.memory_context:
                selected_types.append("memory")
            if context_bundle.chat_workspace_context:
                selected_types.append("chat_workspace")
            selected_summary = ", ".join(selected_types) if selected_types else "none"
            trace_logger.add_event(
                "module",
                "Context Ready",
                f"Selected context types: {selected_summary}.",
                level="success",
            )
        return context_bundle

    def _build_recent_conversation_context(self) -> str | None:
        """Return recent persisted messages for conversational continuity."""
        messages = self.chat_history_store.load_messages(limit=self.recent_message_limit)
        if not messages:
            return None

        formatted_lines: list[str] = []
        used_characters = 0

        # Keep the newest messages first while trimming, because recent context matters most.
        # After collecting enough lines, we reverse back to normal chronological reading order.
        for saved_message in reversed(messages):
            clean_speaker = saved_message.speaker.strip() or "Unknown"
            clean_message = self._clean_message_for_context(saved_message.message)
            if not clean_message:
                continue

            line = f"[{saved_message.message_number}] {clean_speaker}: {clean_message}"
            line_cost = len(line) + 1
            if formatted_lines and used_characters + line_cost > self.max_history_characters:
                break

            formatted_lines.append(line)
            used_characters += line_cost

        if not formatted_lines:
            return None

        formatted_lines.reverse()
        return "Recent conversation context from this chat:\n" + "\n".join(formatted_lines)

    def _build_project_context_if_relevant(self, message: str) -> str | None:
        """Build project overview only when the user's message asks for project structure."""
        if not self._message_needs_project_context(message):
            return None

        # The file reader still stays read-only. This context is a compact overview, not a deep scan.
        return self.file_reader.build_project_overview()


    def _build_chat_workspace_context(self, current_chat_id: str) -> str | None:
        """Return title/description for the active chat workspace.

        This is active context, but it is deliberately much smaller than a future
        generated chat summary. It helps AMADEUS understand what this chat is for
        without injecting older chats or callable archives.
        """
        metadata = self.chat_history_store.get_chat(current_chat_id)
        if metadata is None:
            return None

        lines = ["Current chat workspace metadata:", f"Title: {metadata.title}"]
        if metadata.description.strip():
            lines.append(f"Description: {metadata.description.strip()}")
        if metadata.summary.strip():
            lines.append("Callable summary exists, but full staged retrieval is not implemented yet.")
        return "\n".join(lines)

    def _build_memory_context(self, current_chat_id: str) -> str | None:
        """Return explicit global/chat memory for prompt injection.

        Memory is separate from recent conversation: conversation history is what
        happened recently; memory is what Dato intentionally marked as durable.
        """
        if self.memory_service is None:
            return None
        return self.memory_service.build_prompt_context(current_chat_id)

    def _message_needs_project_context(self, message: str) -> bool:
        """Detect lightweight project/file requests without making Core own keywords."""
        lowered_message = message.lower()
        return any(keyword in lowered_message for keyword in PROJECT_CONTEXT_KEYWORDS)

    def _clean_message_for_context(self, message: str) -> str:
        """Make one saved message compact enough for prompt context."""
        # Collapsing whitespace keeps JSONL history readable in prompt form and saves context space.
        return " ".join(message.strip().split())
