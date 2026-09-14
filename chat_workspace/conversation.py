"""Execute dedicated-chat requests using injected annotation, context and persistence services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from annotation_module import ParsedAnnotationMessage, parse_creation_annotation
from amadeus_trace import TraceLogger
from response_modes import ResponseMode, ResponseModeDecision, resolve_response_mode
from annotation_module.annotation_result import unpack_annotation_output


class ChatConversation:
    """Execute dedicated-chat requests using injected annotation, context and persistence services."""

    def __init__(
        self,
        *,
        annotation_parser: Any,
        annotation_registry: Any,
        annotation_context: Any,
        callable_context_router: Any,
        context_builder: Any,
        identity_prompt_builder: Any,
        chat_module_provider: Any,
        advisor: Any,
        creation_requests: Any,
        exchanges: Any,
        responses: Any,
        metadata: Any,
        chat_history_store: Any,
        global_response_mode: Any,
    ) -> None:
        """Receive the public services needed by this workflow."""
        self.annotation_parser = annotation_parser
        self.annotation_registry = annotation_registry
        self.annotation_context = annotation_context
        self.callable_context_router = callable_context_router
        self.context_builder = context_builder
        self.identity_prompt_builder = identity_prompt_builder
        self.chat_module_provider = chat_module_provider
        self.advisor = advisor
        self.creation_requests = creation_requests
        self.exchanges = exchanges
        self.responses = responses
        self.metadata = metadata
        self.chat_history_store = chat_history_store
        self.global_response_mode = global_response_mode

    def handle_user_message(
        self,
        message: str,
        callable_context: str | None = None,
        event_listener: Callable[[dict[str, object]], None] | None = None,
        response_mode_override: ResponseMode | str | None = None,
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
            return self.responses.build_response_payload(response, trace_logger)

        try:
            creation_request = parse_creation_annotation(clean_message)
            if creation_request is not None:
                pending = self.creation_requests.create_pending_creation_action(creation_request, route="chat")
                self.exchanges.persist_completed_exchange(clean_message, "", trace_logger)
                payload = self.responses.build_response_payload("", trace_logger)
                payload["approval_request"] = pending.approval_payload()
                return payload
            if self.creation_requests.looks_like_creation_command(clean_message):
                return self.responses.build_response_payload("Invalid creation request.", trace_logger)
            # Annotation owns message-level block extraction. This workflow consumes
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
                # sheet from local storage, then this workflow sends its remaining prompt to Chat
                # with that sheet as callable context. This keeps sheets deterministic without
                # dumping them into always-active memory.
                if parsed_annotation.annotation_name == "sheet" and parsed_annotation.content.strip():
                    return self.callable_context_router.handle_sheet_prompt_request(
                        parsed_annotation,
                        clean_message,
                        trace_logger,
                        response_decision=self.resolve_response_mode(response_mode_override),
                    )

                # `[export][chat][range] prompt` is another callable-context route.
                # The export module selects exact numbered messages from the saved export,
                # then Chat answers using only that selected export segment as extra context.
                if parsed_annotation.annotation_name == "export" and parsed_annotation.content.strip():
                    return self.callable_context_router.handle_export_prompt_request(
                        parsed_annotation,
                        clean_message,
                        trace_logger,
                        response_decision=self.resolve_response_mode(response_mode_override),
                    )

                # Mind Map retrieval is always callable context, including an omitted question.
                # This keeps graph values out of deterministic annotation output and confines them
                # to one explicit LLM request.
                if parsed_annotation.annotation_name == "mindmap":
                    return self.callable_context_router.handle_mindmap_prompt_request(
                        parsed_annotation,
                        clean_message,
                        trace_logger,
                        response_decision=self.resolve_response_mode(response_mode_override),
                    )

                trace_logger.add_plan(
                    source_module="chat_workspace",
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
                response, side_panel = unpack_annotation_output(annotation_output)

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

                self.exchanges.persist_completed_exchange(clean_message, response, trace_logger)
                trace_logger.add_event(
                    "output",
                    "Output Ready",
                    "Annotation response returned to GUI.",
                    level="success",
                )
                return self.responses.build_response_payload(response, trace_logger, side_panel=side_panel)

            inferred_analysis = self.advisor.analyze_plain_message(clean_message)
            pending = self.creation_requests.pending_action_from_inference(inferred_analysis, clean_message, route="chat")
            if pending is not None:
                self.exchanges.persist_completed_exchange(clean_message, "", trace_logger)
                payload = self.responses.build_response_payload("", trace_logger)
                payload["approval_request"] = pending.approval_payload()
                return payload
            inferred_metadata = self.advisor.resolve_inferred_metadata(inferred_analysis)
            if inferred_metadata is not None and inferred_analysis.metadata_mode == "open":
                self.exchanges.persist_completed_exchange(clean_message, inferred_metadata.response, trace_logger)
                trace_logger.complete_run(
                    title="Metadata Opened",
                    summary="Verified module metadata was opened without a primary LLM request.",
                )
                return self.responses.build_response_payload(
                    inferred_metadata.response,
                    trace_logger,
                    side_panel=inferred_metadata.side_panel,
                )
            metadata_context = (
                inferred_metadata.side_panel.get("content")
                if inferred_metadata is not None and inferred_analysis.metadata_mode == "answer"
                else None
            )
            inferred_context = self.advisor.resolve_inferred_read_context(inferred_analysis)
            # Normal messages are no longer used for exact file opening. They can still receive
            # compact project overview context for summaries/explanations, but verified exact
            # file reads now live behind `[file]` to avoid fragile natural-language parsing.
            trace_logger.add_event(
                "routing",
                "Request Route",
                "Normal chat route selected.",
            )
            trace_logger.add_plan(
                source_module="chat_workspace",
                title="Normal Chat Work Plan",
                summary="Declared route: build eligible context, prepare an answer through the configured LLM, then store the completed exchange.",
                route_intent="normal_chat_context_llm_persist",
            )

            chat_module = self.chat_module_provider()
            if chat_module is None:
                # This should only happen if startup registration was broken or edited incorrectly.
                response = "AMADEUS error: chat module is not registered."
                trace_logger.fail_run(
                    title="Request Failed",
                    summary="The request could not be completed.",
                )
                return self.responses.build_response_payload(response, trace_logger)

            # Context Builder owns the decision about what history/files should enter the prompt.
            # This keeps prompt context policy out of Core and prevents Chat from reading files directly.
            context_bundle = self.context_builder.build_for_message(clean_message, trace_logger=trace_logger)

            # The injected Identity service gives every normal chat the same AMADEUS charter.
            # Project-related chats receive a stronger identity prompt because they affect AMADEUS herself.
            identity_prompt = self.identity_prompt_builder.build_for_chat(
                project_context_active=context_bundle.project_context_active,
            )
            # Chat owns prompt construction and generation; this workflow supplies selected context.
            response_decision = self.resolve_response_mode(response_mode_override)
            trace_logger.add_event(
                "routing",
                "Response Mode Resolved",
                f"Response mode '{response_decision.mode.value}' was fixed for this request.",
                metadata={"response_policy": response_decision.to_metadata()},
            )
            response = chat_module.handle_message(  # type: ignore[attr-defined]
                clean_message,
                recent_conversation=context_bundle.recent_conversation,
                project_context=context_bundle.project_context,
                memory_context=context_bundle.memory_context,
                chat_workspace_context=context_bundle.chat_workspace_context,
                callable_context=self.advisor.combine_callable_context(callable_context, metadata_context or inferred_context),
                identity_prompt=identity_prompt,
                trace_logger=trace_logger,
                response_decision=response_decision,
            )
            self.exchanges.persist_completed_exchange(clean_message, response, trace_logger, response_decision)
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
            payload = self.responses.build_response_payload(
                response,
                trace_logger,
                side_panel=inferred_metadata.side_panel if inferred_metadata is not None else None,
                response_decision=response_decision,
            )
            if inferred_analysis.suggested_write_actions:
                if inferred_metadata is None:
                    payload["side_panel"] = self.metadata.get_chat_data_panel_payload(inferred_analysis.suggested_write_actions)
            return payload

        except Exception as error:
            # Last-resort safety: the GUI should get an answer-shaped error instead of crashing.
            # The trace receives the error too, so Dato can see which stage failed.
            trace_logger.fail_run(
                title="Request Failed",
                summary="The request could not be completed.",
            )
            response = "AMADEUS could not complete that request. Please try again."
            return self.responses.build_response_payload(response, trace_logger)

    def _handle_annotation_blocks(
        self,
        parsed_message: ParsedAnnotationMessage,
        original_message: str,
        trace_logger: TraceLogger,
    ) -> dict[str, Any]:
        """Execute parser-extracted blocks and use their results as one callable context.

        This is deliberately limited to parser output and registry calls. Annotation
        grammar belongs to `annotation_module`; this workflow combines deterministic module
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
            response, block_panel = unpack_annotation_output(annotation_output)
            responses.append(response)
            if block_panel is not None:
                side_panel = block_panel

        if not parsed_message.normal_prompt:
            response = "\n\n---\n\n".join(responses)
            trace_logger.add_plan(
                source_module="chat_workspace",
                title="Annotation Block Work Plan",
                summary="Declared route: resolve annotation blocks in source order and store the completed exchange.",
                route_intent="annotation_blocks_resolve_persist",
            )
            self.exchanges.persist_completed_exchange(original_message, response, trace_logger)
            trace_logger.add_event("output", "Output Ready", "Annotation block results returned without a chat prompt.", level="success")
            return self.responses.build_response_payload(response, trace_logger, side_panel=side_panel)

        chat_module = self.chat_module_provider()
        if chat_module is None:
            response = "AMADEUS error: chat module is not registered."
            trace_logger.add_event("error", "Routing Error", "Core could not find the registered chat module.", level="error")
            return self.responses.build_response_payload(response, trace_logger, side_panel=side_panel)

        normal_prompt = parsed_message.normal_prompt
        callable_context = "Deterministic annotation results:\n\n" + "\n\n---\n\n".join(responses)
        context_bundle = self.context_builder.build_for_message(normal_prompt, trace_logger=trace_logger)
        trace_logger.add_event(
            "routing",
            "Routing Decision",
            "Annotation blocks resolved. Routing only outside-block text to chat with deterministic callable context.",
        )
        trace_logger.add_plan(
            source_module="chat_workspace",
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
        self.exchanges.persist_completed_exchange(original_message, response, trace_logger)
        trace_logger.add_event("output", "Output Ready", "Response returned with annotation block context.", level="success")
        return self.responses.build_response_payload(response, trace_logger, side_panel=side_panel)

    def resolve_response_mode(self, send_override: ResponseMode | str | None = None) -> ResponseModeDecision:
        """Resolve one dedicated-chat policy before mutable GUI state can change."""
        return resolve_response_mode(
            send_override=send_override,
            chat_mode=self.chat_history_store.get_current_chat().response_mode,
            global_mode=self.global_response_mode,
        )
