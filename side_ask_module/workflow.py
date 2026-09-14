"""Execute temporary Side Ask requests and explicitly selected transcript saves."""

from __future__ import annotations

from typing import Any
from amadeus_trace import TraceLogger
from storage import ChatHistoryMessage


class SideAskWorkflow:
    """Execute temporary Side Ask requests and explicitly selected transcript saves."""

    def __init__(
        self,
        *,
        chat_module_provider: Any,
        context_builder: Any,
        identity_prompt_builder: Any,
        side_ask_service: Any,
        chat_history_store: Any,
        responses: Any,
    ) -> None:
        """Receive the public services needed by this workflow."""
        self.chat_module_provider = chat_module_provider
        self.context_builder = context_builder
        self.identity_prompt_builder = identity_prompt_builder
        self.side_ask_service = side_ask_service
        self.chat_history_store = chat_history_store
        self.responses = responses

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
            return self.responses.build_response_payload(response, trace_logger)

        chat_module = self.chat_module_provider()
        if chat_module is None:
            response = "AMADEUS error: chat module is not registered."
            trace_logger.add_event("error", "Routing Error", "Core could not find the registered chat module.", level="error")
            return self.responses.build_response_payload(response, trace_logger)

        trace_logger.add_event(
            "routing",
            "Routing Decision",
            "Routing to Side Ask flow. The answer will not be saved unless Dato explicitly saves it.",
        )
        trace_logger.add_plan(
            source_module="side_ask_module",
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
        return self.responses.build_response_payload(response, trace_logger)

    def save_side_ask_to_chat(
        self,
        question: str,
        answer: str,
        selected_text: str = '',
    ) -> list[ChatHistoryMessage]:
        """Persist the latest Side Ask Q&A into the active chat and return new messages."""
        user_text, assistant_text = self.side_ask_service.build_chat_save_text(question, answer, selected_text)
        chat_id = self.chat_history_store.get_current_chat_id()
        self.chat_history_store.append_message("User", user_text, chat_id=chat_id)
        self.chat_history_store.append_message("AMADEUS", assistant_text, chat_id=chat_id)
        messages = self.chat_history_store.load_messages(chat_id=chat_id)
        return messages[-2:]
