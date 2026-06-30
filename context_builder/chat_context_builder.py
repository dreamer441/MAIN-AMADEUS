from dataclasses import dataclass

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
    """Prompt context selected for one user message."""

    recent_conversation: str | None
    project_context: str | None

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
        recent_message_limit: int = 18,
        max_history_characters: int = 4_000,
    ) -> None:
        # History context stays small so local models do not lose the current request.
        self.chat_history_store = chat_history_store
        self.file_reader = file_reader
        self.recent_message_limit = recent_message_limit
        self.max_history_characters = max_history_characters

    def build_for_message(self, message: str) -> ChatContextBundle:
        """Build the context bundle for the current user message."""
        return ChatContextBundle(
            recent_conversation=self._build_recent_conversation_context(),
            project_context=self._build_project_context_if_relevant(message),
        )

    def _build_recent_conversation_context(self) -> str | None:
        """Return recent persisted messages for conversational continuity."""
        messages = self.chat_history_store.load_messages(limit=self.recent_message_limit)
        if not messages:
            return None

        formatted_lines: list[str] = []
        used_characters = 0

        # Keep the newest messages first, then reverse them back to normal reading order.
        for saved_message in reversed(messages):
            clean_speaker = saved_message.speaker.strip() or "Unknown"
            clean_message = self._clean_message_for_context(saved_message.message)
            if not clean_message:
                continue

            line = f"{clean_speaker}: {clean_message}"
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

        return self.file_reader.build_project_overview()

    def _message_needs_project_context(self, message: str) -> bool:
        """Detect lightweight project/file requests without making Core own keywords."""
        lowered_message = message.lower()
        return any(keyword in lowered_message for keyword in PROJECT_CONTEXT_KEYWORDS)

    def _clean_message_for_context(self, message: str) -> str:
        """Make one saved message compact enough for prompt context."""
        return " ".join(message.strip().split())
