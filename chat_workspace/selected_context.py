"""Conversation execution with explicitly selected sheets, exports, and graph context.

This router owns the feature-specific work required when an annotation selects a
stored object and supplies the remaining annotation text as a normal chat prompt.
Application setup supplies public owner APIs and response callbacks. Annotation
interprets selection syntax; Context Builder formats literal retrieved data.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from amadeus_trace import TraceLogger
from annotation_module.annotation_parser import ParsedAnnotation
from annotation_module.annotations.sheet_annotation import resolve_sheet_annotation_target
from context_builder.mindmap_context import format_mindmap_context


class SelectedContextConversation:
    """Routes callable sheet and export annotations through injected public APIs."""

    def __init__(
        self,
        current_chat_id_provider: Callable[[], str],
        sheet_service: Any,
        export_service: Any,
        mind_map_module: Any,
        context_builder: Any,
        identity_prompt_builder: Any,
        chat_module_provider: Callable[[], Any],
        persist_exchange: Callable[..., None],
        build_response: Callable[..., dict[str, Any]],
        response_decision_provider: Callable[[], Any] | None = None,
    ) -> None:
        self._current_chat_id_provider = current_chat_id_provider
        self._sheet_service = sheet_service
        self._export_service = export_service
        self._mind_map_module = mind_map_module
        self._context_builder = context_builder
        self._identity_prompt_builder = identity_prompt_builder
        self._chat_module_provider = chat_module_provider
        self._persist_exchange = persist_exchange
        self._build_response = build_response
        self._response_decision_provider = response_decision_provider

    def handle_sheet_prompt_request(
        self,
        annotation: ParsedAnnotation,
        original_message: str,
        trace_logger: TraceLogger,
        response_decision: Any = None,
    ) -> dict[str, Any]:
        """Answer a prompt with one exact sheet as callable context."""
        chat_id = self._current_chat_id_provider()
        sheet, problem, scope = resolve_sheet_annotation_target(self._sheet_service, annotation, chat_id)
        if problem is not None:
            trace_logger.add_event("module", "Sheet Module", "Could not resolve the requested sheet.", level="warning")
            return self._sheet_error(
                original_message,
                f'Could not use sheet context. {problem}',
                trace_logger,
                chat_id,
                scope,
            )

        if sheet is None:
            return self._sheet_error(
                original_message,
                "No specific sheet was selected for injection. Choose a sheet like `[sheet][chat][Sheet Title] your question`.",
                trace_logger,
                chat_id,
                scope,
            )

        trace_logger.add_event("routing", "Routing Decision", "Sheet annotation with prompt detected. Routing to chat with callable sheet context.")
        trace_logger.add_event("module", "Sheet Module", "Loaded the selected sheet as callable context for this request only.", level="success")
        trace_logger.add_plan(
            source_module="chat_workspace",
            title="Sheet Context Work Plan",
            summary="Declared route: use the selected sheet as callable context, prepare an answer through the configured LLM, then store the completed exchange.",
            route_intent="sheet_context_llm_persist",
        )
        chat_module = self._chat_module_provider()
        if chat_module is None:
            return self._routing_error(trace_logger)

        user_prompt = annotation.content.strip()
        response_decision = response_decision or (self._response_decision_provider() if self._response_decision_provider else None)
        context_bundle = self._context_builder.build_for_message(user_prompt, trace_logger=trace_logger)
        response = chat_module.handle_message(
            user_prompt,
            recent_conversation=context_bundle.recent_conversation,
            project_context=context_bundle.project_context,
            memory_context=context_bundle.memory_context,
            chat_workspace_context=context_bundle.chat_workspace_context,
            callable_context=self._sheet_service.build_prompt_context(sheet),
            identity_prompt=self._identity_prompt_builder.build_for_chat(
                project_context_active=context_bundle.project_context_active,
            ),
            trace_logger=trace_logger,
            response_decision=response_decision,
        )
        self._persist_completed_exchange(original_message, response, trace_logger, response_decision)
        trace_logger.add_event("output", "Output Ready", "Response returned to GUI with sheet context.", level="success")
        return self._build_response(
            response,
            trace_logger,
            side_panel=self._sheet_service.build_panel_payload(
                chat_id=chat_id,
                scope=sheet.scope,
                selected_sheet_id=sheet.sheet_id,
                title=f"Sheet: {sheet.title}",
            ),
            response_decision=response_decision,
        )

    def handle_export_prompt_request(
        self,
        annotation: ParsedAnnotation,
        original_message: str,
        trace_logger: TraceLogger,
        response_decision: Any = None,
    ) -> dict[str, Any]:
        """Answer a prompt with an exact exported-chat segment as callable context."""
        target, parse_problem = self._export_service.parse_annotation_target(annotation.arguments)
        if parse_problem is not None or target is None:
            trace_logger.add_event("module", "Export Module", "Could not parse the export request.", level="warning")
            return self._export_error(
                original_message,
                f'Could not use export context. {parse_problem}',
                trace_logger,
            )

        if target.mode in {"help", "list"}:
            return self._export_error(
                original_message,
                "Export context needs a chat title and optional message range, for example `[export][use][Chat Title][4-6] your question`.",
                trace_logger,
            )

        selection, problem = self._export_service.resolve_selection(target.title_or_id, target.range_token)
        if problem is not None or selection is None:
            trace_logger.add_event("module", "Export Module", "Could not resolve the requested export context.", level="warning")
            return self._export_error(original_message, f"Could not use export context. {problem}", trace_logger)

        trace_logger.add_event("routing", "Routing Decision", "Export annotation with prompt detected. Routing to chat with callable export context.")
        if getattr(selection, "persisted_during_request", False):
            trace_logger.add_event("module", "Export Saved", "Export files were saved for the requested context.", level="success")
        trace_logger.add_event("module", "Export Module", "Loaded the selected export segment as callable context.", level="success")
        trace_logger.add_plan(
            source_module="chat_workspace",
            title="Export Context Work Plan",
            summary="Declared route: use the selected export segment as callable context, prepare an answer through the configured LLM, then store the completed exchange.",
            route_intent="export_context_llm_persist",
        )
        chat_module = self._chat_module_provider()
        if chat_module is None:
            return self._routing_error(trace_logger)

        user_prompt = annotation.content.strip()
        response_decision = response_decision or (self._response_decision_provider() if self._response_decision_provider else None)
        context_bundle = self._context_builder.build_for_message(user_prompt, trace_logger=trace_logger)
        trace_logger.add_event(
            "system",
            "Export Scope Lock",
            "Current chat transcript/workspace context was intentionally not injected; the selected exported segment is the primary source.",
            level="success",
        )
        response = chat_module.handle_message(
            user_prompt,
            recent_conversation=None,
            project_context=None,
            memory_context=context_bundle.memory_context,
            chat_workspace_context=None,
            callable_context=self._export_service.build_prompt_context(selection),
            identity_prompt=self._identity_prompt_builder.build_for_chat(project_context_active=False),
            trace_logger=trace_logger,
            response_decision=response_decision,
        )
        self._persist_completed_exchange(original_message, response, trace_logger, response_decision)
        trace_logger.add_event("output", "Output Ready", "Response returned to GUI with export context.", level="success")
        return self._build_response(
            response,
            trace_logger,
            side_panel=self._export_service.build_materials_panel_payload(selection),
            response_decision=response_decision,
        )

    def handle_mindmap_prompt_request(
        self,
        annotation: ParsedAnnotation,
        original_message: str,
        trace_logger: TraceLogger,
        response_decision: Any = None,
    ) -> dict[str, Any]:
        """Answer with bounded explicit Mind Map retrieval as callable context."""
        trace_logger.add_event(
            "module",
            "Mind Map Query Started",
            "Started bounded retrieval from the AMADEUS Mind Map.",
        )
        try:
            query = annotation.arguments[0].strip() if annotation.arguments else ""
            build_context = getattr(self._mind_map_module, "build_context_package", None)
            if callable(build_context):
                context_package = build_context(query, limit=8, depth=1, max_nodes=28)
                nodes = list(context_package.nodes)
                links = list(context_package.links)
                seed_node_ids = tuple(context_package.seed_node_ids)
            else:
                # Compatibility path for tests and older injected Mind Map facades.
                if query:
                    nodes = self._mind_map_module.search_nodes(query, limit=10)
                else:
                    nodes = self._mind_map_module.list_recent_nodes(limit=10)
                links = []
                seed_node_ids = tuple(node.node_id for node in nodes)
        except Exception:
            trace_logger.add_event(
                "error",
                "Mind Map Query Failed",
                "Mind Map retrieval could not be completed.",
                level="error",
            )
            response = "AMADEUS could not retrieve Mind Map context for that request. Please try again."
            self._persist_completed_exchange(original_message, response, trace_logger)
            trace_logger.add_event("output", "Output Ready", "Mind Map retrieval failure returned to GUI.", level="warning")
            return self._build_response(response, trace_logger)

        if nodes:
            trace_logger.add_event(
                "module",
                "Mind Map Results Retrieved",
                "Retrieved bounded Mind Map node context for this request.",
                level="success",
            )
        else:
            trace_logger.add_event(
                "module",
                "Mind Map No Matches",
                "No Mind Map nodes matched the requested retrieval.",
                level="warning",
            )

        trace_logger.add_plan(
            source_module="chat_workspace",
            title="Mind Map Context Work Plan",
            summary="Declared route: retrieve bounded Mind Map context, prepare an answer through the configured LLM, then store the completed exchange.",
            route_intent="mindmap_context_llm_persist",
        )
        chat_module = self._chat_module_provider()
        if chat_module is None:
            return self._routing_error(trace_logger)

        user_prompt = annotation.content.strip() or "Report the retrieved AMADEUS Mind Map context."
        response_decision = response_decision or (self._response_decision_provider() if self._response_decision_provider else None)
        context_bundle = self._context_builder.build_for_message(user_prompt, trace_logger=trace_logger)
        response = chat_module.handle_message(
            user_prompt,
            recent_conversation=context_bundle.recent_conversation,
            project_context=context_bundle.project_context,
            memory_context=context_bundle.memory_context,
            chat_workspace_context=context_bundle.chat_workspace_context,
            callable_context=format_mindmap_context(
                nodes, links=links, seed_node_ids=seed_node_ids
            ),
            identity_prompt=self._identity_prompt_builder.build_for_chat(
                project_context_active=context_bundle.project_context_active,
            ),
            trace_logger=trace_logger,
            response_decision=response_decision,
        )
        self._persist_completed_exchange(original_message, response, trace_logger, response_decision)
        trace_logger.add_event("output", "Output Ready", "Response returned to GUI with Mind Map context.", level="success")
        return self._build_response(response, trace_logger, response_decision=response_decision)


    def _sheet_error(
        self,
        original_message: str,
        response: str,
        trace_logger: TraceLogger,
        chat_id: str,
        scope: str,
    ) -> dict[str, Any]:
        """Persist and return a sheet-resolution response with the Sheets payload."""
        self._persist_completed_exchange(original_message, response, trace_logger)
        trace_logger.add_event("output", "Output Ready", "Sheet resolution response returned to GUI.", level="warning")
        return self._build_response(
            response,
            trace_logger,
            side_panel=self._sheet_service.build_panel_payload(chat_id=chat_id, scope=scope),
        )

    def _export_error(self, original_message: str, response: str, trace_logger: TraceLogger) -> dict[str, Any]:
        """Persist and return an export-resolution response with Materials payload."""
        self._persist_completed_exchange(original_message, response, trace_logger)
        return self._build_response(
            response,
            trace_logger,
            side_panel=self._export_service.build_materials_panel_payload(),
        )

    def _routing_error(self, trace_logger: TraceLogger) -> dict[str, Any]:
        """Return the shared response when the chat module is unavailable."""
        response = "AMADEUS error: chat module is not registered."
        trace_logger.add_event("error", "Routing Error", "Core could not find the registered chat module.", level="error")
        return self._build_response(response, trace_logger)

    def _persist_completed_exchange(
        self,
        original_message: str,
        response: str,
        trace_logger: TraceLogger,
        response_decision: Any = None,
    ) -> None:
        """Save an exchange, then report storage only after the save succeeds."""
        self._persist_exchange(original_message, response, response_decision)
        trace_logger.add_event("module", "Completed Exchange Stored", "Stored the completed exchange in the active chat.", level="success")
