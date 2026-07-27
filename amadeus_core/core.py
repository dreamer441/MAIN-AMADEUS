"""AMADEUS Core coordinator.

Core is intentionally the narrow middle layer of AMADEUS. It should know that
modules exist and decide where a request goes, but it should not contain the full
logic of chat, storage, identity, file reading, tracing, or future reasoning.

Current request flow:
GUI -> Core -> Annotation check OR Chat route -> Context Builder / Identity -> Chat -> LLM Client -> GUI
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from annotation_module import AnnotationContext, AnnotationParser, AnnotationRegistry, AnnotationResult, AnnotationSuggestionService, CallableContextRouter, ParsedAnnotation, ParsedAnnotationMessage
from annotation_module.annotations import ExportAnnotation, FileAnnotation, IdentityAnnotation, MemoryAnnotation, SheetAnnotation
from amadeus_chat import AmadeusChatModule
from amadeus_core.module_registry import ModuleRegistry
from amadeus_trace import TraceLogger
from chat_registry import ChatRegistry
from context_builder import ChatContextBuilder
from identity_module import IdentityPromptBuilder, IdentityService
from export_module import ChatExportService
from flow_chat import FlowChatService, FlowChatStore, FlowContextBuilder
from llm_client import OllamaClient
from materials_module import MaterialsService
from memory_module import MemoryService
from mindmap import MindMapModule
from comments_module import CommentService
from side_ask_module import SideAskService
from project_file_reader import ProjectFileContent, ProjectFileReader
from sheets_module import SheetService
from storage import ChatHistoryMessage, ChatHistoryStore, ChatMetadata, ChatPriority, ChatPurpose, ChatScope


class AmadeusCore:
    """Lightweight coordinator for AMADEUS modules.

    Core owns routing and composition only. When this file starts growing with
    feature-specific logic, that is a sign a new module or service boundary is
    needed. This protects the long-term modular structure of AMADEUS.
    """

    def __init__(self, llm_client: object | None = None, project_root: Path | None = None) -> None:
        # project_root is resolved once and then shared with modules that need safe local paths.
        # This keeps path logic centralized instead of each module guessing where AMADEUS lives.
        self.project_root = project_root or Path(__file__).resolve().parents[1]

        # The registry lets Core route by stable module names without importing feature internals later.
        self.module_registry = ModuleRegistry()

        # The LLM client is injected so tests can replace Ollama with a fake client.
        self.llm_client = llm_client or OllamaClient()

        # Read-only project file access is its own module. Core may ask for approved context,
        # but Core must not become a general file browser/editor.
        self.file_reader = ProjectFileReader(self.project_root)

        # Identity is global AMADEUS self-definition. It is not a temporary reasoning mode.
        self.identity_service = IdentityService(self.project_root)
        self.identity_prompt_builder = IdentityPromptBuilder(self.identity_service)

        # Storage persists visible chat history. Memory is intentionally separate because
        # memory is selected durable context, not a raw transcript.
        self.chat_history_store = ChatHistoryStore(self.project_root)

        # Flow has isolated history and can see dedicated-chat metadata only through the registry.
        self.flow_chat_store = FlowChatStore(self.project_root)
        self.chat_registry = ChatRegistry(self.chat_history_store)
        self.flow_context_builder = FlowContextBuilder(self.flow_chat_store, self.chat_registry)

        # Memory V1 is explicit only: Dato uses [memory] to decide what becomes durable.
        self.memory_service = MemoryService(self.project_root)

        # Sheets are editable side-panel documents and callable context feeders.
        # They are separate from memory because sheets are workspace documents, not always-active facts.
        self.sheet_service = SheetService(self.project_root)

        # Exported chats are the first real Materials objects. They are callable
        # references: visible in the Materials panel and injectable with [export].
        self.export_service = ChatExportService(self.project_root, self.chat_history_store)

        # Materials owns managed references and composes Export's public API.
        self.materials_service = MaterialsService(self.project_root, self.export_service)

        # Side Ask is a temporary secondary Q&A flow. It does not persist into the
        # main chat unless Dato explicitly presses Save to Chat or New Chat.
        self.side_ask_service = SideAskService()

        # Comments are lightweight notes attached to selected chat text. They are
        # deliberately separate from reward/importance/memory until those systems are designed.
        self.comment_service = CommentService(self.project_root)

        # Mind Map owns local graph persistence and validation. Core exposes its
        # facade so GUI and future source adapters never access SQLite directly.
        self.mind_map_module = MindMapModule(self.project_root)

        # Context Builder decides which history/project/memory context enters the prompt.
        self.context_builder = ChatContextBuilder(
            chat_history_store=self.chat_history_store,
            file_reader=self.file_reader,
            memory_service=self.memory_service,
        )

        # Annotation parsing and handling are separate so Chat does not need to understand bracket commands.
        self.annotation_parser = AnnotationParser()
        self.annotation_registry = AnnotationRegistry()

        # The GUI asks this service for slash-popup and step-by-step annotation suggestions.
        # Keeping suggestion logic out of the GUI lets each annotation own its own path later.
        self.annotation_suggestion_service = AnnotationSuggestionService(
            file_reader=self.file_reader,
            parser=self.annotation_parser,
            sheet_service=self.sheet_service,
            export_service=self.export_service,
            current_chat_id_provider=self.chat_history_store.get_current_chat_id,
        )

        self.annotation_context = AnnotationContext(
            project_root=self.project_root,
            file_reader=self.file_reader,
            identity_service=self.identity_service,
            memory_service=self.memory_service,
            sheet_service=self.sheet_service,
            export_service=self.export_service,
            annotation_parser=self.annotation_parser,
            current_chat_id_provider=self.chat_history_store.get_current_chat_id,
        )

        # Callable annotation routes interpret sheets/exports inside Annotation Module.
        # Core only supplies module public APIs and keeps ownership of response delivery.
        self.callable_context_router = CallableContextRouter(
            current_chat_id_provider=self.chat_history_store.get_current_chat_id,
            sheet_service=self.sheet_service,
            export_service=self.export_service,
            context_builder=self.context_builder,
            identity_prompt_builder=self.identity_prompt_builder,
            chat_module_provider=lambda: self.module_registry.get("chat"),
            persist_exchange=self._persist_exchange,
            build_response=self._build_response_payload,
        )

        self._register_builtin_modules()
        self._register_annotations()

    def _register_builtin_modules(self) -> None:
        """Register the first built-in modules needed by the shell."""
        # Core stores module entry points, not implementation details. Future modules should be
        # registered here or by a later plugin loader, then called through their public API only.
        chat_module = AmadeusChatModule(llm_client=self.llm_client)
        self.flow_chat_service = FlowChatService(
            chat_module=chat_module,
            flow_context_builder=self.flow_context_builder,
            flow_chat_store=self.flow_chat_store,
            identity_prompt_builder=self.identity_prompt_builder,
        )
        self.module_registry.register("chat", chat_module)
        self.module_registry.register("flow_chat", self.flow_chat_service)
        self.module_registry.register("flow_context_builder", self.flow_context_builder)
        self.module_registry.register("chat_registry", self.chat_registry)
        self.module_registry.register("identity", self.identity_service)
        self.module_registry.register("memory", self.memory_service)
        self.module_registry.register("sheets", self.sheet_service)
        self.module_registry.register("materials", self.materials_service)
        self.module_registry.register("exports", self.export_service)
        self.module_registry.register("side_ask", self.side_ask_service)
        self.module_registry.register("comments", self.comment_service)
        self.module_registry.register("mind_map", self.mind_map_module)
        self.module_registry.register("context_builder", self.context_builder)

    def _register_annotations(self) -> None:
        """Register structured annotation handlers Core can route to."""
        # Annotation names stay short because the user types them directly, e.g. [file].
        self.annotation_registry.register("file", FileAnnotation())
        self.annotation_registry.register("identity", IdentityAnnotation())
        self.annotation_registry.register("memory", MemoryAnnotation())
        self.annotation_registry.register("sheet", SheetAnnotation())
        self.annotation_registry.register("export", ExportAnnotation())

    def handle_user_message(
        self,
        message: str,
        callable_context: str | None = None,
        event_listener: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        """Route user text and return both AMADEUS output and Process Monitor trace.

        This method is the main request pipeline. Keep it readable: each trace event
        corresponds to a real stage of execution that the Process Monitor can show.
        """
        trace_logger = TraceLogger()
        trace_logger.start_session()
        if event_listener is not None:
            # Core publishes plain event rows so UI adapters never enter the backend.
            trace_logger.emitter.subscribe(lambda event: event_listener(event.to_dict()))

        clean_message = message.strip()
        trace_logger.add_event(
            "input",
            "Request Received",
            "Message received from GUI.",
        )

        if not clean_message:
            # Empty messages are handled before routing because no module should waste work on them.
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
            # Annotation Module owns message-level block extraction. Core only consumes
            # its structured result and never searches for `[end]` syntax itself.
            parsed_message = self.annotation_parser.parse_message(message)
            if parsed_message.blocks and not parsed_message.is_legacy_leading_annotation:
                return self._handle_annotation_blocks(parsed_message, clean_message, trace_logger)

            parsed_annotation = self.annotation_parser.parse(message)

            if parsed_annotation is not None:
                trace_logger.add_event(
                    "annotation",
                    "Annotation Detected",
                    f"Detected annotation: [{parsed_annotation.annotation_name}].",
                    level="success",
                )
                # `[sheet][... ] prompt` is a hybrid route: the annotation selects an exact
                # sheet from local storage, then Core sends the remaining prompt to normal chat
                # with that sheet as callable context. This keeps sheets deterministic without
                # dumping them into always-active memory.
                if parsed_annotation.annotation_name == "sheet" and parsed_annotation.content.strip():
                    return self.callable_context_router.handle_sheet_prompt_request(parsed_annotation, clean_message, trace_logger)

                # `[export][chat][range] prompt` is another callable-context route.
                # The export module selects exact numbered messages from the saved export,
                # then Chat answers using only that selected export segment as extra context.
                if parsed_annotation.annotation_name == "export" and parsed_annotation.content.strip():
                    return self.callable_context_router.handle_export_prompt_request(parsed_annotation, clean_message, trace_logger)

                trace_logger.add_plan(
                    source_module="core",
                    title="Annotation Work Plan",
                    summary="Declared route: resolve the requested annotation, return its deterministic result, then store the completed exchange.",
                    route_intent="annotation_resolve_persist",
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

                # Annotations are direct module requests. `[file]` may also return a side-panel
                # payload so exact code can appear in Code Viewer instead of polluting chat.
                annotation_output = self.annotation_registry.handle(parsed_annotation, self.annotation_context)
                response, side_panel = self._unpack_annotation_output(annotation_output)

                if (
                    parsed_annotation.annotation_name == "export"
                    and side_panel is not None
                    and side_panel.get("metadata", {}).get("persisted_during_request") is True
                ):
                    trace_logger.add_event(
                        "module",
                        "Export Saved",
                        "Export files were saved for the requested context.",
                        level="success",
                    )

                if side_panel is not None:
                    trace_logger.add_event(
                        "module",
                        "Side Panel Payload",
                        f"Annotation prepared a {side_panel.get('type', 'unknown')} panel update.",
                        level="success",
                    )

                if parsed_annotation.annotation_name == "memory":
                    trace_logger.add_event(
                        "module",
                        "Memory Module",
                        "Memory annotation was handled by explicit memory storage/listing logic.",
                        level="success",
                    )

                if parsed_annotation.annotation_name == "export":
                    trace_logger.add_event(
                        "module",
                        "Export Module",
                        "Export annotation was handled as a deterministic chat/material reference action.",
                        level="success",
                    )

                self._persist_completed_exchange(clean_message, response, trace_logger)
                trace_logger.add_event(
                    "output",
                    "Output Ready",
                    "Annotation response returned to GUI.",
                    level="success",
                )
                return self._build_response_payload(response, trace_logger, side_panel=side_panel)

            # Normal messages are no longer used for exact file opening. They can still receive
            # compact project overview context for summaries/explanations, but verified exact
            # file reads now live behind `[file]` to avoid fragile natural-language parsing.
            trace_logger.add_event(
                "routing",
                "Request Route",
                "Normal chat route selected.",
            )
            trace_logger.add_plan(
                source_module="core",
                title="Normal Chat Work Plan",
                summary="Declared route: build eligible context, prepare an answer through the configured LLM, then store the completed exchange.",
                route_intent="normal_chat_context_llm_persist",
            )

            chat_module = self.module_registry.get("chat")
            if chat_module is None:
                # This should only happen if startup registration was broken or edited incorrectly.
                response = "AMADEUS error: chat module is not registered."
                trace_logger.fail_run(
                    title="Request Failed",
                    summary="The request could not be completed.",
                )
                return self._build_response_payload(response, trace_logger)

            # Context Builder owns the decision about what history/files should enter the prompt.
            # This keeps prompt context policy out of Core and prevents Chat from reading files directly.
            context_bundle = self.context_builder.build_for_message(clean_message, trace_logger=trace_logger)

            # Identity is prepared at Core level so every normal chat starts from the same AMADEUS charter.
            # Project-related chats receive a stronger identity prompt because they affect AMADEUS herself.
            identity_prompt = self.identity_prompt_builder.build_for_chat(
                project_context_active=context_bundle.project_context_active,
            )
            # Core routes the message but does not build prompt text or generate the response itself.
            response = chat_module.handle_message(  # type: ignore[attr-defined]
                clean_message,
                recent_conversation=context_bundle.recent_conversation,
                project_context=context_bundle.project_context,
                memory_context=context_bundle.memory_context,
                chat_workspace_context=context_bundle.chat_workspace_context,
                callable_context=callable_context,
                identity_prompt=identity_prompt,
                trace_logger=trace_logger,
            )
            self._persist_completed_exchange(clean_message, response, trace_logger)
            if trace_logger.has_failed_event():
                trace_logger.fail_run(
                    title="Request Failed",
                    summary="The request could not be completed.",
                )
            else:
                trace_logger.complete_run(
                    title="Response Returned",
                    summary="Response returned to GUI.",
                )
            return self._build_response_payload(response, trace_logger)

        except Exception as error:
            # Last-resort safety: the GUI should get an answer-shaped error instead of crashing.
            # The trace receives the error too, so Dato can see which stage failed.
            trace_logger.fail_run(
                title="Request Failed",
                summary="The request could not be completed.",
            )
            response = "AMADEUS could not complete that request. Please try again."
            return self._build_response_payload(response, trace_logger)


    def handle_flow_message(
        self,
        message: str,
        event_listener: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        """Handle the isolated Flow home conversation without changing normal chat routing."""
        trace_logger = TraceLogger()
        trace_logger.start_session()
        if event_listener is not None:
            trace_logger.emitter.subscribe(lambda event: event_listener(event.to_dict()))

        clean_message = message.strip()
        trace_logger.add_event("input", "Flow Request Received", "Flow message received from GUI.")
        if not clean_message:
            response = "AMADEUS needs a message before she can respond."
            trace_logger.complete_run(title="Flow Output Returned", summary="Empty Flow response returned to GUI.")
            return self._build_response_payload(response, trace_logger)

        try:
            trace_logger.add_plan(
                source_module="core",
                title="Flow Chat Work Plan",
                summary="Declared route: load eligible Flow context, prepare an answer through the configured LLM, then store the completed Flow exchange.",
                route_intent="flow_context_llm_persist",
            )
            execution = self.flow_chat_service.handle_message(clean_message, trace_logger)
            if not execution.succeeded:
                trace_logger.fail_run(title="Flow Request Failed", summary="The Flow request could not be completed.")
                response = "AMADEUS could not complete that Flow request. Please try again."
            else:
                trace_logger.complete_run(title="Flow Output Returned", summary="Flow response returned to GUI.")
                response = execution.response
            return self._build_response_payload(response, trace_logger)
        except Exception:
            trace_logger.fail_run(title="Flow Request Failed", summary="The Flow request could not be completed.")
            return self._build_response_payload(
                "AMADEUS could not complete that Flow request. Please try again.",
                trace_logger,
            )

    def load_flow_history(self) -> list[Any]:
        """Return persisted Flow messages for the GUI without exposing Flow storage."""
        return self.flow_chat_store.load_messages()

    def subscribe_mind_map(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        """Subscribe a GUI or adapter to completed graph changes through Core."""
        if not callable(listener):
            raise ValueError("listener must be callable")

        def publish_safe_event(event: dict[str, Any]) -> None:
            listener({
                key: event[key]
                for key in ("event_type", "entity_type", "entity_id", "graph_id", "created_at")
                if key in event
            })

        return self.mind_map_module.subscribe(publish_safe_event)

    def get_mind_map_snapshot(self) -> Any:
        """Return the active graph snapshot for a Core-mediated view refresh."""
        return self.mind_map_module.get_snapshot()

    def create_mind_map_node(self, **fields: Any) -> Any:
        """Create one validated graph node through the Mind Map module."""
        return self.mind_map_module.create_node(**fields)

    def update_mind_map_node(self, node_id: str, **changes: Any) -> Any:
        """Update one graph node through the Mind Map module."""
        return self.mind_map_module.update_node(node_id, **changes)

    def move_mind_map_node(self, node_id: str, position_x: float, position_y: float, **fields: Any) -> Any:
        """Persist a graph node position without exposing graph storage to the GUI."""
        return self.mind_map_module.move_node(node_id, position_x, position_y, **fields)

    def move_mind_map_nodes(self, positions: dict[str, tuple[float, float]]) -> None:
        """Persist a complete layout projection in one graph transaction."""
        self.mind_map_module.move_nodes(positions)

    def delete_mind_map_node(self, node_id: str, **fields: Any) -> None:
        """Delete one node and its connected links through the Mind Map module."""
        self.mind_map_module.delete_node(node_id, **fields)

    def create_mind_map_link(self, **fields: Any) -> Any:
        """Create one validated graph relationship through the Mind Map module."""
        return self.mind_map_module.create_link(**fields)

    def update_mind_map_link(self, link_id: str, **changes: Any) -> Any:
        """Update one graph relationship through the Mind Map module."""
        return self.mind_map_module.update_link(link_id, **changes)

    def delete_mind_map_link(self, link_id: str, **fields: Any) -> None:
        """Delete one graph relationship through the Mind Map module."""
        self.mind_map_module.delete_link(link_id, **fields)

    def search_mind_map_nodes(self, query: str, limit: int = 50) -> list[Any]:
        """Search graph nodes through the module's validated retrieval API."""
        return self.mind_map_module.search_nodes(query, limit=limit)

    def get_mind_map_neighborhood(self, root_node_id: str, depth: int = 1) -> Any:
        """Return a bounded graph neighborhood through the Mind Map module."""
        return self.mind_map_module.get_neighborhood(root_node_id, depth=depth)

    def upsert_mind_map_source_node(self, **fields: Any) -> Any:
        """Create or refresh a graph node for a future AMADEUS source adapter."""
        return self.mind_map_module.upsert_source_node(**fields)

    def export_mind_map(self, destination: Path | str) -> Path:
        """Export the active graph as portable JSON through the Mind Map module."""
        return self.mind_map_module.export_to_json(destination)

    def import_mind_map(self, source: Path | str, *, replace_graph: bool = False) -> Any:
        """Import portable graph JSON through the Mind Map module."""
        return self.mind_map_module.import_from_json(source, replace_graph=replace_graph)


    def _handle_sheet_prompt_request(
        self,
        parsed_annotation: ParsedAnnotation,
        original_message: str,
        trace_logger: TraceLogger,
    ) -> dict[str, Any]:
        """Route `[sheet][... ] prompt` into normal chat with exact sheet context.

        This is the first callable-context route. The sheet is loaded directly from
        `sheets_module`, then the user's text after the annotation becomes the real
        prompt. The main chat receives only AMADEUS's answer; the sheet itself is
        shown/kept in the right-side Sheets panel.
        """
        chat_id = self.chat_history_store.get_current_chat_id()
        sheet, problem, scope = self.sheet_service.resolve_annotation_target(parsed_annotation, chat_id)
        if problem is not None:
            trace_logger.add_event(
                "module",
                "Sheet Module",
                "Could not resolve the requested sheet.",
                level="warning",
            )
            response = f"Could not use sheet context. {problem}"
            self._persist_completed_exchange(original_message, response, trace_logger)
            trace_logger.add_event("output", "Output Ready", "Sheet resolution error returned to GUI.", level="warning")
            return self._build_response_payload(
                response,
                trace_logger,
                side_panel=self.sheet_service.build_panel_payload(chat_id=chat_id, scope=scope),
            )

        if sheet is None:
            response = "No specific sheet was selected for injection. Choose a sheet like `[sheet][chat][Sheet Title] your question`."
            self._persist_completed_exchange(original_message, response, trace_logger)
            trace_logger.add_event("output", "Output Ready", "Sheet usage help returned to GUI.", level="warning")
            return self._build_response_payload(
                response,
                trace_logger,
                side_panel=self.sheet_service.build_panel_payload(chat_id=chat_id, scope=scope),
            )

        trace_logger.add_event(
            "routing",
            "Routing Decision",
            "Sheet annotation with prompt detected. Routing to chat with callable sheet context.",
        )
        trace_logger.add_event(
            "module",
            "Sheet Module",
            "Loaded the selected sheet as callable context for this request only.",
            level="success",
        )

        chat_module = self.module_registry.get("chat")
        if chat_module is None:
            response = "AMADEUS error: chat module is not registered."
            trace_logger.add_event("error", "Routing Error", "Core could not find the registered chat module.", level="error")
            return self._build_response_payload(response, trace_logger)

        user_prompt = parsed_annotation.content.strip()
        context_bundle = self.context_builder.build_for_message(user_prompt)
        identity_prompt = self.identity_prompt_builder.build_for_chat(
            project_context_active=context_bundle.project_context_active,
        )
        callable_context = self.sheet_service.build_prompt_context(sheet)

        response = chat_module.handle_message(  # type: ignore[attr-defined]
            user_prompt,
            recent_conversation=context_bundle.recent_conversation,
            project_context=context_bundle.project_context,
            memory_context=context_bundle.memory_context,
            chat_workspace_context=context_bundle.chat_workspace_context,
            callable_context=callable_context,
            identity_prompt=identity_prompt,
            trace_logger=trace_logger,
        )
        self._persist_completed_exchange(original_message, response, trace_logger)
        trace_logger.add_event("output", "Output Ready", "Response returned to GUI with sheet context.", level="success")
        return self._build_response_payload(
            response,
            trace_logger,
            side_panel=self.sheet_service.build_panel_payload(
                chat_id=chat_id,
                scope=sheet.scope,
                selected_sheet_id=sheet.sheet_id,
                title=f"Sheet: {sheet.title}",
            ),
        )


    def _handle_export_prompt_request(
        self,
        parsed_annotation: ParsedAnnotation,
        original_message: str,
        trace_logger: TraceLogger,
    ) -> dict[str, Any]:
        """Route `[export][chat][range] prompt` into chat with export context.

        Export context is callable, not active memory. The service resolves the
        exported chat and exact message range, then Chat receives only that segment
        as an explicit context block. This keeps large exported chats out of every
        normal prompt.
        """
        target, parse_problem = self.export_service.parse_annotation_target(parsed_annotation.arguments)
        if parse_problem is not None or target is None:
            trace_logger.add_event(
                "module",
                "Export Module",
                "Could not parse the export request.",
                level="warning",
            )
            response = f"Could not use export context. {parse_problem}"
            self._persist_completed_exchange(original_message, response, trace_logger)
            return self._build_response_payload(
                response,
                trace_logger,
                side_panel=self.export_service.build_materials_panel_payload(),
            )

        if target.mode in {"help", "list"}:
            response = "Export context needs a chat title and optional message range, for example `[export][use][Chat Title][4-6] your question`."
            self._persist_completed_exchange(original_message, response, trace_logger)
            return self._build_response_payload(
                response,
                trace_logger,
                side_panel=self.export_service.build_materials_panel_payload(),
            )

        selection, problem = self.export_service.resolve_selection(target.title_or_id, target.range_token)
        if problem is not None or selection is None:
            trace_logger.add_event(
                "module",
                "Export Module",
                "Could not resolve the requested export context.",
                level="warning",
            )
            response = f"Could not use export context. {problem}"
            self._persist_completed_exchange(original_message, response, trace_logger)
            return self._build_response_payload(
                response,
                trace_logger,
                side_panel=self.export_service.build_materials_panel_payload(),
            )

        trace_logger.add_event(
            "routing",
            "Routing Decision",
            "Export annotation with prompt detected. Routing to chat with callable export context.",
        )
        if getattr(selection, "persisted_during_request", False):
            trace_logger.add_event(
                "module",
                "Export Saved",
                "Export files were saved for the requested context.",
                level="success",
            )
        trace_logger.add_event(
            "module",
            "Export Module",
            "Loaded the selected export segment as callable context.",
            level="success",
        )

        chat_module = self.module_registry.get("chat")
        if chat_module is None:
            response = "AMADEUS error: chat module is not registered."
            trace_logger.add_event("error", "Routing Error", "Core could not find the registered chat module.", level="error")
            return self._build_response_payload(response, trace_logger)

        user_prompt = parsed_annotation.content.strip()
        context_bundle = self.context_builder.build_for_message(user_prompt)
        identity_prompt = self.identity_prompt_builder.build_for_chat(
            project_context_active=False,
        )
        callable_context = self.export_service.build_prompt_context(selection)

        trace_logger.add_event(
            "system",
            "Export Scope Lock",
            "Current chat transcript/workspace context was intentionally not injected; the selected exported segment is the primary source.",
            level="success",
        )

        response = chat_module.handle_message(  # type: ignore[attr-defined]
            user_prompt,
            recent_conversation=None,
            project_context=None,
            memory_context=context_bundle.memory_context,
            chat_workspace_context=None,
            callable_context=callable_context,
            identity_prompt=identity_prompt,
            trace_logger=trace_logger,
        )
        self._persist_completed_exchange(original_message, response, trace_logger)
        trace_logger.add_event("output", "Output Ready", "Response returned to GUI with export context.", level="success")
        return self._build_response_payload(
            response,
            trace_logger,
            side_panel=self.export_service.build_materials_panel_payload(selection),
        )


    def handle_side_ask(self, question: str, selected_text: str = "") -> dict[str, Any]:
        """Answer a Side Ask question without saving it to visible chat history.

        Side Ask is intentionally separate from normal chat. It can use selected
        visible text as temporary callable context, but it only becomes part of the
        transcript if Dato clicks Save to Chat or creates a new chat from it.
        """
        trace_logger = TraceLogger()
        trace_logger.start_session()

        clean_question = question.strip()
        clean_selected = selected_text.strip()
        trace_logger.add_event("input", "Side Ask Received", "Side Ask question received from GUI.")

        if not clean_question:
            response = "Side Ask needs a question before AMADEUS can answer."
            trace_logger.add_event("output", "Output Ready", "Empty Side Ask response returned.", level="warning")
            return self._build_response_payload(response, trace_logger)

        chat_module = self.module_registry.get("chat")
        if chat_module is None:
            response = "AMADEUS error: chat module is not registered."
            trace_logger.add_event("error", "Routing Error", "Core could not find the registered chat module.", level="error")
            return self._build_response_payload(response, trace_logger)

        trace_logger.add_event(
            "routing",
            "Routing Decision",
            "Routing to Side Ask flow. The answer will not be saved unless Dato explicitly saves it.",
        )
        trace_logger.add_plan(
            source_module="core",
            title="Side Ask Work Plan",
            summary="Declared route: load eligible context and prepare an answer through the configured LLM without storing an exchange.",
            route_intent="side_ask_context_llm_no_persist",
        )
        if clean_selected:
            trace_logger.add_event(
                "input",
                "Selected Text Context",
                "Selected visible chat text was attached as temporary Side Ask context.",
                level="success",
            )

        context_bundle = self.context_builder.build_for_message(clean_question, trace_logger=trace_logger)
        identity_prompt = self.identity_prompt_builder.build_for_chat(
            project_context_active=context_bundle.project_context_active,
        )
        callable_context = self.side_ask_service.build_callable_context(clean_selected)

        response = chat_module.handle_message(  # type: ignore[attr-defined]
            clean_question,
            recent_conversation=None,
            project_context=context_bundle.project_context,
            memory_context=context_bundle.memory_context,
            chat_workspace_context=context_bundle.chat_workspace_context,
            callable_context=callable_context,
            identity_prompt=identity_prompt,
            trace_logger=trace_logger,
        )
        trace_logger.add_event("output", "Output Ready", "Side Ask answer returned to GUI without transcript save.", level="success")
        return self._build_response_payload(response, trace_logger)

    def get_project_tree(self, relative_path: str = "") -> dict[str, Any]:
        """Return a verified direct project-root tree listing for the Code Viewer."""
        listing = self.file_reader.list_project_directory(relative_path)
        return {
            "path": listing.requested_path,
            "folders": [entry.__dict__ for entry in listing.folders],
            "files": [entry.__dict__ for entry in listing.files],
        }

    def open_project_file(self, relative_path: str) -> dict[str, Any]:
        """Open one verified project file through the trusted reader only."""
        content = self.file_reader.read_project_file(relative_path)
        return self._build_project_file_panel_payload(content)

    def ask_about_project_file(
        self, relative_path: str, question: str, include_context: bool = False, line_range: str = ""
    ) -> dict[str, Any]:
        """Ask a direct question, adding verified selected-file context only when enabled."""
        context = self.file_reader.build_project_file_context(relative_path, line_range) if include_context else None
        return self.handle_user_message(question, callable_context=context)

    def _build_project_file_panel_payload(self, content: ProjectFileContent) -> dict[str, Any]:
        """Create the shared Code Viewer payload for GUI project-tree file opens."""
        return {
            "type": "code",
            "title": content.relative_path,
            "content": content.content,
            "metadata": {
                "relative_path": content.relative_path,
                "lines": content.total_lines,
                "characters_read": len(content.content),
                "total_characters": content.total_characters,
                "size_bytes": content.size_bytes,
                "encoding": content.encoding,
                "truncated": content.truncated,
            },
        }

    def save_side_ask_to_chat(self, question: str, answer: str, selected_text: str = "") -> list[ChatHistoryMessage]:
        """Persist the latest Side Ask Q&A into the active chat and return new messages."""
        user_text, assistant_text = self.side_ask_service.build_chat_save_text(question, answer, selected_text)
        chat_id = self.chat_history_store.get_current_chat_id()
        self.chat_history_store.append_message("User", user_text, chat_id=chat_id)
        self.chat_history_store.append_message("AMADEUS", assistant_text, chat_id=chat_id)
        messages = self.chat_history_store.load_messages(chat_id=chat_id)
        return messages[-2:]

    def add_comment(self, comment: str, selected_text: str = "") -> Any:
        """Save a simple comment attached to selected chat text."""
        return self.comment_service.add_comment(
            chat_id=self.chat_history_store.get_current_chat_id(),
            comment=comment,
            selected_text=selected_text,
        )

    def update_comment(self, comment_id: str, comment: str) -> Any:
        """Update one comment through the Comments module."""
        return self.comment_service.update_comment(comment_id, comment)

    def delete_comment(self, comment_id: str) -> None:
        """Delete one comment through the Comments module."""
        self.comment_service.delete_comment(comment_id)

    def get_comments_panel_payload(self) -> dict[str, Any]:
        """Return comments for the current chat as a right-panel payload."""
        return self.comment_service.build_panel_payload(self.chat_history_store.get_current_chat_id())

    def get_annotation_suggestions(self, current_input: str) -> list[dict[str, str]]:
        """Return GUI suggestions for slash/annotation building.

        Suggestions are read-only and quick. If something goes wrong, Core returns
        an empty list so the chat window remains usable.
        """
        try:
            return self.annotation_suggestion_service.get_suggestions(current_input)
        except Exception:
            return []

    def _handle_annotation_blocks(
        self,
        parsed_message: ParsedAnnotationMessage,
        original_message: str,
        trace_logger: TraceLogger,
    ) -> dict[str, Any]:
        """Execute parser-extracted blocks and use their results as one callable context.

        This is deliberately limited to parser output and registry calls. Annotation
        grammar belongs to `annotation_module`; Core coordinates deterministic module
        results with the one remaining normal-chat prompt.
        """
        responses: list[str] = []
        side_panel: dict[str, Any] | None = None
        for block in parsed_message.blocks:
            annotation = block.annotation
            trace_logger.add_event(
                "annotation",
                "Annotation Block Detected",
                f"Executing annotation block: [{annotation.annotation_name}].",
                level="success",
            )
            annotation_output = self.annotation_registry.handle(annotation, self.annotation_context)
            response, block_panel = self._unpack_annotation_output(annotation_output)
            responses.append(response)
            if block_panel is not None:
                side_panel = block_panel

        if not parsed_message.normal_prompt:
            response = "\n\n---\n\n".join(responses)
            trace_logger.add_plan(
                source_module="core",
                title="Annotation Block Work Plan",
                summary="Declared route: resolve annotation blocks in source order and store the completed exchange.",
                route_intent="annotation_blocks_resolve_persist",
            )
            self._persist_completed_exchange(original_message, response, trace_logger)
            trace_logger.add_event("output", "Output Ready", "Annotation block results returned without a chat prompt.", level="success")
            return self._build_response_payload(response, trace_logger, side_panel=side_panel)

        chat_module = self.module_registry.get("chat")
        if chat_module is None:
            response = "AMADEUS error: chat module is not registered."
            trace_logger.add_event("error", "Routing Error", "Core could not find the registered chat module.", level="error")
            return self._build_response_payload(response, trace_logger, side_panel=side_panel)

        normal_prompt = parsed_message.normal_prompt
        callable_context = "Deterministic annotation results:\n\n" + "\n\n---\n\n".join(responses)
        context_bundle = self.context_builder.build_for_message(normal_prompt, trace_logger=trace_logger)
        trace_logger.add_event(
            "routing",
            "Routing Decision",
            "Annotation blocks resolved. Routing only outside-block text to chat with deterministic callable context.",
        )
        trace_logger.add_plan(
            source_module="core",
            title="Annotation Context Work Plan",
            summary="Declared route: use resolved annotation results as callable context, prepare an answer through the configured LLM, then store the completed exchange.",
            route_intent="annotation_context_llm_persist",
        )
        response = chat_module.handle_message(  # type: ignore[attr-defined]
            normal_prompt,
            recent_conversation=context_bundle.recent_conversation,
            project_context=context_bundle.project_context,
            memory_context=context_bundle.memory_context,
            chat_workspace_context=context_bundle.chat_workspace_context,
            callable_context=callable_context,
            identity_prompt=self.identity_prompt_builder.build_for_chat(
                project_context_active=context_bundle.project_context_active,
            ),
            trace_logger=trace_logger,
        )
        self._persist_completed_exchange(original_message, response, trace_logger)
        trace_logger.add_event("output", "Output Ready", "Response returned with annotation block context.", level="success")
        return self._build_response_payload(response, trace_logger, side_panel=side_panel)

    def _unpack_annotation_output(self, annotation_output: object) -> tuple[str, dict[str, Any] | None]:
        """Normalize annotation handler output into chat text plus optional panel data."""
        if isinstance(annotation_output, AnnotationResult):
            return annotation_output.response, annotation_output.side_panel
        if isinstance(annotation_output, str):
            return annotation_output, None
        return "AMADEUS annotation error: handler returned an unreadable result.", None

    def list_chats(self) -> list[ChatMetadata]:
        """Return known chats for the GUI selector.

        Core exposes chat metadata instead of letting the GUI touch storage
        directly. That keeps the GUI as a surface layer and leaves persistence
        rules inside Storage.
        """
        return self.chat_history_store.list_chats()

    def get_current_chat_id(self) -> str:
        """Return the currently active chat id for GUI selection state."""
        return self.chat_history_store.get_current_chat_id()

    def get_current_chat_metadata(self) -> ChatMetadata:
        """Return metadata for the active chat workspace."""
        return self.chat_history_store.get_current_chat()

    def create_chat(
        self,
        title: str | None = None,
        description: str | None = None,
        priority: ChatPriority = "Normal",
        purpose: ChatPurpose = "General",
        scope: ChatScope = "Local",
    ) -> ChatMetadata:
        """Create a new chat and make it active."""
        return self.chat_history_store.create_chat(
            title=title, description=description, priority=priority, purpose=purpose, scope=scope
        )

    def update_chat_metadata(
        self,
        chat_id: str,
        title: str | None = None,
        description: str | None = None,
        summary: str | None = None,
        priority: ChatPriority | None = None,
        purpose: ChatPurpose | None = None,
        scope: ChatScope | None = None,
    ) -> ChatMetadata:
        """Update editable title, description, summary, priority, purpose, and scope metadata."""
        return self.chat_history_store.update_chat_metadata(
            chat_id=chat_id,
            title=title,
            description=description,
            summary=summary,
            priority=priority,
            purpose=purpose,
            scope=scope,
        )

    def delete_chat(self, chat_id: str | None = None) -> ChatMetadata:
        """Delete a chat and return the chat that became active afterward."""
        target_chat_id = chat_id or self.chat_history_store.get_current_chat_id()
        return self.chat_history_store.delete_chat(target_chat_id)

    def switch_chat(self, chat_id: str) -> ChatMetadata:
        """Switch active chat for future saves and context building."""
        return self.chat_history_store.set_current_chat(chat_id)

    def load_chat_history(self, chat_id: str | None = None) -> list[ChatHistoryMessage]:
        """Load persisted messages for the selected or active chat."""
        return self.chat_history_store.load_messages(chat_id=chat_id)


    def list_sheets(self, scope: str = "all") -> list[Any]:
        """Return sheets visible from the current chat for GUI selectors."""
        return self.sheet_service.list_sheets(chat_id=self.get_current_chat_id(), scope=scope)

    def create_sheet(
        self,
        title: str,
        description: str = "",
        content: str = "",
        scope: str = "chat",
    ) -> Any:
        """Create a sheet from the right panel."""
        return self.sheet_service.create_sheet(
            title=title,
            description=description,
            content=content,
            scope=scope,
            chat_id=self.get_current_chat_id(),
        )

    def update_sheet(
        self,
        sheet_id: str,
        title: str | None = None,
        description: str | None = None,
        content: str | None = None,
        scope: str | None = None,
    ) -> Any:
        """Update an existing sheet from the right panel."""
        return self.sheet_service.update_sheet(
            sheet_id=sheet_id,
            title=title,
            description=description,
            content=content,
            scope=scope,
            chat_id=self.get_current_chat_id(),
        )

    def delete_sheet(self, sheet_id: str) -> None:
        """Delete one sheet from the right panel."""
        self.sheet_service.delete_sheet(sheet_id)

    def get_sheets_panel_payload(self, scope: str = "all", selected_sheet_id: str | None = None) -> dict[str, Any]:
        """Return a side-panel payload for the current chat's visible sheets."""
        return self.sheet_service.build_panel_payload(
            chat_id=self.get_current_chat_id(),
            scope=scope,
            selected_sheet_id=selected_sheet_id,
        )

    def get_materials_panel_payload(self) -> dict[str, Any]:
        """Return material rows without opening or injecting a selected reference."""
        return self.materials_service.build_panel_payload()

    def list_materials(self) -> list[dict[str, Any]]:
        """Return material metadata for non-GUI callers through Materials only."""
        return self.materials_service.list_materials()

    def preview_material(self, material_id: str) -> dict[str, Any]:
        """Preview one explicitly selected Materials record through its module API."""
        return self.materials_service.preview_material(material_id)

    def open_material(self, material_id: str) -> dict[str, Any]:
        """Open one explicitly selected Materials record without injecting it."""
        return self.materials_service.open_material(material_id)

    def get_material_reference(self, material_id: str) -> str:
        """Return a selected stable material reference for GUI clipboard actions."""
        return self.materials_service.material_reference(material_id)

    def get_material_copy_text(self, material_id: str) -> str:
        """Return the selected material's Core-owned clipboard text."""
        return self.materials_service.material_copy_text(material_id)

    def remove_material(self, material_id: str) -> None:
        """Remove one explicitly selected Materials record where supported."""
        self.materials_service.remove_material(material_id)

    def handle_material_message(
        self,
        material_id: str,
        message: str,
        event_listener: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        """Use one selected material as callable context for this one chat request."""
        return self.handle_user_message(
            message,
            callable_context=self.materials_service.build_callable_context(material_id),
            event_listener=event_listener,
        )

    def _persist_exchange(self, user_message: str, response: str) -> None:
        """Persist the current user/AMADEUS exchange for later resume."""
        # Persistence happens after a module returns output, not before. This prevents half-handled
        # requests from becoming permanent conversation context if a route crashes early.
        self.chat_history_store.append_message("User", user_message)
        self.chat_history_store.append_message("AMADEUS", response)

    def _persist_completed_exchange(self, user_message: str, response: str, trace_logger: TraceLogger) -> None:
        """Save an exchange, then report storage only after both records are written."""
        self._persist_exchange(user_message, response)
        trace_logger.add_event("module", "Completed Exchange Stored", "Stored the completed exchange in the active chat.", level="success")

    def _build_response_payload(
        self,
        response: str,
        trace_logger: TraceLogger,
        side_panel: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send both chat output and real execution trace back to the GUI."""
        # The GUI uses text fields today, but trace_events is already structured for future filters/export.
        trace_logger.finalize_if_active(title="Response Returned", summary="Response returned to GUI.")
        return {
            "response": response,
            "trace": trace_logger.get_trace_text(mode="compact"),
            "trace_detailed": trace_logger.get_trace_text(mode="detailed"),
            "trace_events": trace_logger.get_trace_events(),
            "side_panel": side_panel,
        }
