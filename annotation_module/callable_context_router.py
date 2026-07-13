"""Callable-context annotation routing for sheets and exported chats.

This router owns the feature-specific work required when an annotation selects a
stored object and supplies the remaining annotation text as a normal chat prompt.
Core supplies only public module APIs and response callbacks, keeping Core focused
on coordination rather than sheet/export interpretation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from amadeus_trace import TraceLogger
from annotation_module.annotation_parser import ParsedAnnotation


class CallableContextRouter:
    """Routes callable sheet and export annotations through injected public APIs."""

    def __init__(
        self,
        current_chat_id_provider: Callable[[], str],
        sheet_service: Any,
        export_service: Any,
        context_builder: Any,
        identity_prompt_builder: Any,
        chat_module_provider: Callable[[], Any],
        persist_exchange: Callable[[str, str], None],
        build_response: Callable[..., dict[str, Any]],
    ) -> None:
        self._current_chat_id_provider = current_chat_id_provider
        self._sheet_service = sheet_service
        self._export_service = export_service
        self._context_builder = context_builder
        self._identity_prompt_builder = identity_prompt_builder
        self._chat_module_provider = chat_module_provider
        self._persist_exchange = persist_exchange
        self._build_response = build_response

    def handle_sheet_prompt_request(
        self,
        annotation: ParsedAnnotation,
        original_message: str,
        trace_logger: TraceLogger,
    ) -> dict[str, Any]:
        """Answer a prompt with one exact sheet as callable context."""
        chat_id = self._current_chat_id_provider()
        sheet, problem, scope = self._sheet_service.resolve_annotation_target(annotation, chat_id)
        if problem is not None:
            trace_logger.add_event("module", "Sheet Module", f"Could not resolve requested sheet: {problem}", level="warning")
            return self._sheet_error(original_message, f"Could not use sheet context. {problem}", trace_logger, chat_id, scope)

        if sheet is None:
            return self._sheet_error(
                original_message,
                "No specific sheet was selected for injection. Choose a sheet like `[sheet][chat][Sheet Title] your question`.",
                trace_logger,
                chat_id,
                scope,
            )

        trace_logger.add_event("routing", "Routing Decision", "Sheet annotation with prompt detected. Routing to chat with callable sheet context.")
        trace_logger.add_event("module", "Sheet Module", f"Loaded sheet `{sheet.title}` as callable context for this request only.", level="success")
        chat_module = self._chat_module_provider()
        if chat_module is None:
            return self._routing_error(trace_logger)

        user_prompt = annotation.content.strip()
        context_bundle = self._context_builder.build_for_message(user_prompt)
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
        )
        self._persist_exchange(original_message, response)
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
        )

    def handle_export_prompt_request(
        self,
        annotation: ParsedAnnotation,
        original_message: str,
        trace_logger: TraceLogger,
    ) -> dict[str, Any]:
        """Answer a prompt with an exact exported-chat segment as callable context."""
        target, parse_problem = self._export_service.parse_annotation_target(annotation.arguments)
        if parse_problem is not None or target is None:
            trace_logger.add_event("module", "Export Module", f"Could not parse export annotation target: {parse_problem}", level="warning")
            return self._export_error(original_message, f"Could not use export context. {parse_problem}", trace_logger)

        if target.mode in {"help", "list"}:
            return self._export_error(
                original_message,
                "Export context needs a chat title and optional message range, for example `[export][use][Chat Title][4-6] your question`.",
                trace_logger,
            )

        selection, problem = self._export_service.resolve_selection(target.title_or_id, target.range_token)
        if problem is not None or selection is None:
            trace_logger.add_event("module", "Export Module", f"Could not resolve requested export context: {problem}", level="warning")
            return self._export_error(original_message, f"Could not use export context. {problem}", trace_logger)

        trace_logger.add_event("routing", "Routing Decision", "Export annotation with prompt detected. Routing to chat with callable export context.")
        trace_logger.add_event("module", "Export Module", f"Loaded export `{selection.record.chat_title}` range `{selection.range_label}` as callable context.", level="success")
        chat_module = self._chat_module_provider()
        if chat_module is None:
            return self._routing_error(trace_logger)

        user_prompt = annotation.content.strip()
        context_bundle = self._context_builder.build_for_message(user_prompt)
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
        )
        self._persist_exchange(original_message, response)
        trace_logger.add_event("output", "Output Ready", "Response returned to GUI with export context.", level="success")
        return self._build_response(
            response,
            trace_logger,
            side_panel=self._export_service.build_materials_panel_payload(selection),
        )

    def _sheet_error(self, original_message: str, response: str, trace_logger: TraceLogger, chat_id: str, scope: str) -> dict[str, Any]:
        """Persist and return a sheet-resolution response with the Sheets payload."""
        self._persist_exchange(original_message, response)
        trace_logger.add_event("output", "Output Ready", "Sheet resolution response returned to GUI.", level="warning")
        return self._build_response(
            response,
            trace_logger,
            side_panel=self._sheet_service.build_panel_payload(chat_id=chat_id, scope=scope),
        )

    def _export_error(self, original_message: str, response: str, trace_logger: TraceLogger) -> dict[str, Any]:
        """Persist and return an export-resolution response with Materials payload."""
        self._persist_exchange(original_message, response)
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
