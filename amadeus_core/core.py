from pathlib import Path

from annotation_module import AnnotationContext, AnnotationParser, AnnotationRegistry
from annotation_module.annotations import FileAnnotation
from amadeus_chat import AmadeusChatModule
from amadeus_core.module_registry import ModuleRegistry
from llm_client import OllamaClient
from project_file_reader import ProjectFileReader


class AmadeusCore:
    """Lightweight coordinator for AMADEUS modules."""

    def __init__(self, llm_client: object | None = None, project_root: Path | None = None) -> None:
        # Core owns coordination and routing. Modules own their own behavior.
        self.project_root = project_root or Path(__file__).resolve().parents[1]
        self.module_registry = ModuleRegistry()
        self.llm_client = llm_client or OllamaClient()
        self.file_reader = ProjectFileReader(self.project_root)
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
        parsed_annotation = self.annotation_parser.parse(message)
        if parsed_annotation is not None:
            # Annotations are structured commands, so they bypass normal chat text handling.
            return self.annotation_registry.handle(parsed_annotation, self.annotation_context)

        chat_module = self.module_registry.get("chat")
        if chat_module is None:
            return "AMADEUS error: chat module is not registered."

        # Core routes the message but does not generate the chat response itself.
        return chat_module.handle_message(message)  # type: ignore[attr-defined]
