from pathlib import Path
from typing import Any

from annotation_module import AnnotationContext, AnnotationParser, AnnotationRegistry
from annotation_module.annotations import FileAnnotation, IdentityAnnotation
from amadeus_chat import AmadeusChatModule
from amadeus_core.module_registry import ModuleRegistry
from amadeus_trace import TraceLogger
from context_builder import ChatContextBuilder
from identity_module import IdentityPromptBuilder, IdentityService
from llm_client import OllamaClient
from project_file_reader import ProjectFileReader
from storage import ChatHistoryMessage, ChatHistoryStore


class AmadeusCore:
    """Lightweight coordinator for AMADEUS modules."""

    def __init__(self, llm_client: object | None = None, project_root: Path | None = None) -> None:
        # Core owns coordination and routing. Modules own their own behavior.
        self.project_root = project_root or Path(__file__).resolve().parents[1]
        self.module_registry = ModuleRegistry()
        self.llm_client = llm_client or OllamaClient()
        self.file_reader = ProjectFileReader(self.project_root)
        self.identity_service = IdentityService(self.project_root)
        self.identity_prompt_builder = IdentityPromptBuilder(self.identity_service)
        self.chat_history_store = ChatHistoryStore(self.project_root)
        self.context_builder = ChatContextBuilder(
            chat_history_store=self.chat_history_store,
            file_reader=self.file_reader,
        )
        self.annotation_parser = AnnotationParser()
        self.annotation_registry = AnnotationRegistry()
        self.annotation_context = AnnotationContext(
            project_root=self.project_root,
            file_reader=self.file_reader,
            identity_service=self.identity_service,
        )
        self._register_builtin_modules()
        self._register_annotations()

    def _register_builtin_modules(self) -> None:
        """Register the first built-in modules needed by the shell."""
        self.module_registry.register("chat", AmadeusChatModule(llm_client=self.llm_client))
        self.module_registry.register("identity", self.identity_service)
        self.module_registry.register("context_builder", self.context_builder)

    def _register_annotations(self) -> None:
        """Register structured annotation handlers Core can route to."""
        self.annotation_registry.register("file", FileAnnotation())
        self.annotation_registry.register("identity", IdentityAnnotation())

    def handle_user_message(self, message: str) -> dict[str, Any]:
        """Route user text and return both AMADEUS output and Process Monitor trace."""
        trace_logger = TraceLogger()
        trace_logger.start_session()

        clean_message = message.strip()
        trace_logger.add_event(
            "input",
            "Input Received",
            "Message received from GUI.",
        )

        if not clean_message:
            trace_logger.add_event(
                "system",
                "Empty Message",
                "No usable message text was provided.",
                level="warning",
            )
            response = "AMADEUS needs a message before she can respond."
            trace_logger.add_event(
                "output",
                "Output Ready",
                "Empty-message response returned to GUI.",
                level="success",
            )
            return self._build_response_payload(response, trace_logger)

        try:
            trace_logger.add_event(
                "annotation",
                "Annotation Check",
                "Checking if message starts with a registered annotation pattern.",
            )
            parsed_annotation = self.annotation_parser.parse(message)

            if parsed_annotation is not None:
                trace_logger.add_event(
                    "annotation",
                    "Annotation Detected",
                    f"Detected annotation: [{parsed_annotation.annotation_name}].",
                    level="success",
                )
                trace_logger.add_event(
                    "routing",
                    "Routing Decision",
                    "Annotation detected. Routing message to the annotation registry.",
                )
                trace_logger.add_event(
                    "module",
                    "Annotation Module",
                    f"Using annotation handler for [{parsed_annotation.annotation_name}] if registered.",
                )

                # Annotations are structured commands, so they bypass normal chat text handling.
                response = self.annotation_registry.handle(parsed_annotation, self.annotation_context)
                self._persist_exchange(clean_message, response)
                trace_logger.add_event(
                    "output",
                    "Output Ready",
                    "Annotation response returned to GUI.",
                    level="success",
                )
                return self._build_response_payload(response, trace_logger)

            trace_logger.add_event(
                "routing",
                "Routing Decision",
                "No annotation detected. Routing to chat module.",
            )

            chat_module = self.module_registry.get("chat")
            if chat_module is None:
                response = "AMADEUS error: chat module is not registered."
                trace_logger.add_event(
                    "error",
                    "Routing Error",
                    "Core could not find the registered chat module.",
                    level="error",
                )
                trace_logger.add_event(
                    "output",
                    "Output Ready",
                    "Error response returned to GUI.",
                    level="warning",
                )
                return self._build_response_payload(response, trace_logger)

            trace_logger.add_event(
                "module",
                "Chat Module Route",
                "Core routed the message to the chat module.",
            )
            trace_logger.add_event(
                "module",
                "Context Builder",
                "Building recent conversation and project context for this message.",
            )
            context_bundle = self.context_builder.build_for_message(clean_message)

            if context_bundle.recent_conversation:
                trace_logger.add_event(
                    "system",
                    "Conversation Context",
                    "Recent chat history was loaded for continuity.",
                    level="success",
                )
            else:
                trace_logger.add_event(
                    "system",
                    "Conversation Context",
                    "No recent chat history was available for this request.",
                )

            if context_bundle.project_context_active:
                trace_logger.add_event(
                    "file",
                    "Project File Reader",
                    "Project overview context was loaded because the message appears related to files/modules/project structure.",
                    level="success",
                )

            identity_prompt = self.identity_prompt_builder.build_for_chat(
                project_context_active=context_bundle.project_context_active,
            )
            trace_logger.add_event(
                "module",
                "Identity Module",
                "Global AMADEUS identity prompt was prepared for chat.",
                level="success",
            )

            # Core routes the message but does not build prompt text or generate the response itself.
            response = chat_module.handle_message(  # type: ignore[attr-defined]
                clean_message,
                recent_conversation=context_bundle.recent_conversation,
                project_context=context_bundle.project_context,
                identity_prompt=identity_prompt,
                trace_logger=trace_logger,
            )
            self._persist_exchange(clean_message, response)
            trace_logger.add_event(
                "output",
                "Output Ready",
                "Response returned to GUI.",
                level="success",
            )
            return self._build_response_payload(response, trace_logger)

        except Exception as error:
            trace_logger.add_event(
                "error",
                "Unhandled Error",
                f"Core caught an unexpected error: {error}",
                level="error",
            )
            response = f"AMADEUS error: {error}"
            trace_logger.add_event(
                "output",
                "Output Ready",
                "Error response returned to GUI.",
                level="warning",
            )
            return self._build_response_payload(response, trace_logger)

    def load_chat_history(self) -> list[ChatHistoryMessage]:
        """Load persisted chat messages for the GUI to display on startup."""
        return self.chat_history_store.load_messages()

    def _persist_exchange(self, user_message: str, response: str) -> None:
        """Persist the current user/AMADEUS exchange for later resume."""
        self.chat_history_store.append_message("User", user_message)
        self.chat_history_store.append_message("AMADEUS", response)

    def _build_response_payload(self, response: str, trace_logger: TraceLogger) -> dict[str, Any]:
        """Send both chat output and real execution trace back to the GUI."""
        return {
            "response": response,
            "trace": trace_logger.get_trace_text(mode="compact"),
            "trace_detailed": trace_logger.get_trace_text(mode="detailed"),
            "trace_events": trace_logger.get_trace_events(),
        }
