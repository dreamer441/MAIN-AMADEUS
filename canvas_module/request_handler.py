"""Execute Canvas requests and return their committed scene objects."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from amadeus_trace import TraceLogger


class CanvasRequestHandler:
    """Execute Canvas requests and return their committed scene objects."""

    def __init__(self, *, canvas_conversation_service: Any, identity_prompt_builder: Any, responses: Any) -> None:
        """Receive the public services needed by this workflow."""
        self.canvas_conversation_service = canvas_conversation_service
        self.identity_prompt_builder = identity_prompt_builder
        self.responses = responses

    def handle_canvas_message(
        self,
        *,
        instruction: str = "",
        context_mode: str = "viewport",
        visible_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_connector_ids: list[str] | tuple[str, ...] | set[str] = (),
        branch_root_id: str | None = None,
        model_weight: str = "normal",
        event_listener: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        """Route one structured Canvas request and return committed scene objects."""

        trace_logger = TraceLogger()
        trace_logger.start_session()
        if event_listener is not None:
            trace_logger.emitter.subscribe(lambda event: event_listener(event.to_dict()))
        trace_logger.add_event(
            "input",
            "Canvas Request Received",
            "Canvas send request received from GUI.",
        )
        trace_logger.add_plan(
            source_module="canvas_module",
            title="Canvas Request Work Plan",
            summary=(
                "Declared route: build target-focused Canvas context, request one response through "
                "the configured LLM, then atomically store the response and sent baseline."
            ),
            route_intent="canvas_context_llm_atomic_commit",
        )
        run_id = trace_logger.emitter.events[0].run_id if trace_logger.emitter.events else ""
        try:
            execution = self.canvas_conversation_service.handle_request(
                instruction=instruction,
                context_mode=context_mode,
                visible_object_ids=visible_object_ids,
                selected_object_ids=selected_object_ids,
                selected_connector_ids=selected_connector_ids,
                branch_root_id=branch_root_id,
                identity_prompt=self.identity_prompt_builder.build_for_chat(
                    project_context_active=False
                ),
                trace_logger=trace_logger,
                process_run_id=run_id,
                model_weight=model_weight,
            )
            if not execution.succeeded:
                trace_logger.fail_run(
                    title="Canvas Request Failed",
                    summary="The Canvas request could not be completed.",
                )
                safe_error = (
                    str(execution.error)
                    if isinstance(execution.error, (ValueError, RuntimeError))
                    else "AMADEUS could not complete that Canvas request. Please try again."
                )
                return self.responses.build_response_payload(safe_error, trace_logger)

            trace_logger.complete_run(
                title="Canvas Response Returned",
                summary="Canvas response was stored and returned to GUI.",
            )
            payload = self.responses.build_response_payload(execution.response or "", trace_logger)
            payload.update(
                {
                    "canvas_response_block": execution.response_block.to_dict()
                    if execution.response_block is not None
                    else None,
                    "canvas_response_connector": execution.response_connector.to_dict()
                    if execution.response_connector is not None
                    else None,
                    "canvas_send_operation": execution.send_operation.to_dict()
                    if execution.send_operation is not None
                    else None,
                }
            )
            return payload
        except Exception:
            trace_logger.fail_run(
                title="Canvas Request Failed",
                summary="The Canvas request could not be completed.",
            )
            return self.responses.build_response_payload(
                "AMADEUS could not complete that Canvas request. Please try again.",
                trace_logger,
            )
