from pathlib import Path

from annotation_module import AnnotationContext, AnnotationParser, AnnotationRegistry
from annotation_module.annotations import FileAnnotation
from amadeus_chat import AmadeusChatModule
from amadeus_core.module_registry import ModuleRegistry
from llm_client import OllamaClient
from project_file_reader import ProjectFileReader
from storage import ChatHistoryMessage, ChatHistoryStore


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


class AmadeusCore:
    """Lightweight coordinator for AMADEUS modules."""

    def __init__(self, llm_client: object | None = None, project_root: Path | None = None) -> None:
        # Core owns coordination and routing. Modules own their own behavior.
        self.project_root = project_root or Path(__file__).resolve().parents[1]
        self.module_registry = ModuleRegistry()
        self.llm_client = llm_client or OllamaClient()
        self.file_reader = ProjectFileReader(self.project_root)
        self.chat_history_store = ChatHistoryStore(self.project_root)
        self.annotation_parser = AnnotationParser()
        self.annotation_registry = AnnotationRegistry()
        self.annotation_context = AnnotationContext(
            project_root=self.project_root,
            file_reader=self.file_reader,
        )
        self._register_builtin_modules()
        self._register_annotations()

    def _register_builtin_modules(self) -> None:
        """Register the first built-in modules needed by the shell."""
        self.module_registry.register("chat", AmadeusChatModule(llm_client=self.llm_client))

    def _register_annotations(self) -> None:
        """Register structured annotation handlers Core can route to."""
        self.annotation_registry.register("file", FileAnnotation())

    def handle_user_message(self, message: str) -> str:
        """Route user text to annotations first, otherwise normal chat."""
        clean_message = message.strip()
        if not clean_message:
            return "AMADEUS needs a message before she can respond."

        parsed_annotation = self.annotation_parser.parse(message)
        if parsed_annotation is not None:
            # Annotations are structured commands, so they bypass normal chat text handling.
            response = self.annotation_registry.handle(parsed_annotation, self.annotation_context)
            self._persist_exchange(clean_message, response)
            return response

        chat_module = self.module_registry.get("chat")
        if chat_module is None:
            return "AMADEUS error: chat module is not registered."

        context = self._build_context_for_message(clean_message)

        # Core routes the message but does not generate the chat response itself.
        response = chat_module.handle_message(clean_message, context=context)  # type: ignore[attr-defined]
        self._persist_exchange(clean_message, response)
        return response

    def load_chat_history(self) -> list[ChatHistoryMessage]:
        """Load persisted chat messages for the GUI to display on startup."""
        return self.chat_history_store.load_messages()

    def _build_context_for_message(self, message: str) -> str | None:
        """Build safe project context when the user asks about files or modules."""
        lowered_message = message.lower()
        if not any(keyword in lowered_message for keyword in PROJECT_CONTEXT_KEYWORDS):
            return None

        # Core decides when file context is relevant; Chat receives context but never reads files.
        return self.file_reader.build_project_overview()

    def _persist_exchange(self, user_message: str, response: str) -> None:
        """Persist the current user/AMADEUS exchange for later resume."""
        self.chat_history_store.append_message("User", user_message)
        self.chat_history_store.append_message("AMADEUS", response)
