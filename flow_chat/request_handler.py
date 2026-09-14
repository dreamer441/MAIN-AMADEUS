"""Execute Flow commands and requests while retaining isolated history."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from annotation_module import parse_creation_annotation
from amadeus_trace import TraceLogger
from flow_chat import HabitApprovalRequest, HabitReadResponse, HabitValidationResponse
from inner_brain import InnerBrainAnalysis
from annotation_module.annotation_result import unpack_annotation_output


class FlowRequestHandler:
    """Execute Flow commands and requests while retaining isolated history."""

    def __init__(
        self,
        *,
        flow_habit_requests: Any,
        flow_chat_store: Any,
        flow_chat_service: Any,
        annotation_parser: Any,
        annotation_registry: Any,
        annotation_context: Any,
        permissions: Any,
        creation_requests: Any,
        advisor: Any,
        responses: Any,
    ) -> None:
        """Receive the public services needed by this workflow."""
        self.flow_habit_requests = flow_habit_requests
        self.flow_chat_store = flow_chat_store
        self.flow_chat_service = flow_chat_service
        self.annotation_parser = annotation_parser
        self.annotation_registry = annotation_registry
        self.annotation_context = annotation_context
        self.permissions = permissions
        self.creation_requests = creation_requests
        self.advisor = advisor
        self.responses = responses

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
            return self.responses.build_response_payload(response, trace_logger)

        try:
            habit_result = self.flow_habit_requests.handle(clean_message)
            if habit_result is not None:
                if isinstance(habit_result, (HabitReadResponse, HabitValidationResponse)):
                    self.flow_chat_store.append_exchange(clean_message, habit_result.response)
                    trace_logger.complete_run(title="Flow Output Returned", summary="Habit Tracker response returned to GUI.")
                    return self.responses.build_response_payload(habit_result.response, trace_logger)
                assert isinstance(habit_result, HabitApprovalRequest)
                pending = self.permissions.create_pending_action(kind="habit_tracker", fields=habit_result.fields)
                self.flow_chat_store.append_exchange(clean_message, "")
                payload = self.responses.build_response_payload("", trace_logger)
                payload["approval_request"] = pending.approval_payload()
                return payload
            creation_request = parse_creation_annotation(clean_message)
            if creation_request is not None:
                pending = self.creation_requests.create_pending_creation_action(creation_request, route="flow")
                self.flow_chat_store.append_exchange(clean_message, "")
                payload = self.responses.build_response_payload("", trace_logger)
                payload["approval_request"] = pending.approval_payload()
                return payload
            if self.creation_requests.looks_like_creation_command(clean_message):
                return self.responses.build_response_payload("Invalid creation request.", trace_logger)
            parsed_annotation = self.annotation_parser.parse(clean_message)
            if parsed_annotation is not None:
                if parsed_annotation.annotation_name == "metadata":
                    response = "Module metadata is available in dedicated chat, not Flow Chat."
                    self.flow_chat_store.append_exchange(clean_message, response)
                    return self.responses.build_response_payload(response, trace_logger)
                annotation_output = self.annotation_registry.handle(parsed_annotation, self.annotation_context)
                response, side_panel = unpack_annotation_output(annotation_output)
                self.flow_chat_store.append_exchange(clean_message, response)
                return self.responses.build_response_payload(response, trace_logger, side_panel=side_panel)
            inferred_analysis = (
                InnerBrainAnalysis()
                if clean_message.startswith("/review")
                else self.advisor.analyze_plain_message(clean_message, route="flow")
            )
            pending = self.creation_requests.pending_action_from_inference(inferred_analysis, clean_message, route="flow")
            if pending is not None:
                self.flow_chat_store.append_exchange(clean_message, "")
                payload = self.responses.build_response_payload("", trace_logger)
                payload["approval_request"] = pending.approval_payload()
                return payload
            trace_logger.add_plan(
                source_module="flow_chat",
                title="Flow Chat Work Plan",
                summary="Declared route: load eligible Flow context, prepare an answer through the configured LLM, then store the completed Flow exchange.",
                route_intent="flow_context_llm_persist",
            )
            execution = self.flow_chat_service.handle_message(clean_message, trace_logger)
            if not execution.succeeded:
                if isinstance(execution.error, ValueError):
                    trace_logger.complete_run(title="Flow Output Returned", summary="Flow command validation response returned to GUI.")
                    return self.responses.build_response_payload(str(execution.error), trace_logger)
                trace_logger.fail_run(title="Flow Request Failed", summary="The Flow request could not be completed.")
                response = "AMADEUS could not complete that Flow request. Please try again."
            else:
                trace_logger.complete_run(title="Flow Output Returned", summary="Flow response returned to GUI.")
                response = execution.response
            payload = self.responses.build_response_payload(response, trace_logger, created_chat=execution.created_chat)
            payload["proposal_ids"] = list(execution.proposal_ids)
            payload["created_workspace_ids"] = list(execution.created_workspace_ids)
            if execution.approval_request is not None:
                payload["approval_request"] = execution.approval_request
            return payload
        except Exception:
            trace_logger.fail_run(title="Flow Request Failed", summary="The Flow request could not be completed.")
            return self.responses.build_response_payload(
                "AMADEUS could not complete that Flow request. Please try again.",
                trace_logger,
            )

    def load_flow_history(self) -> list[Any]:
        """Return persisted Flow messages for the GUI without exposing Flow storage."""
        return self.flow_chat_store.load_messages()
