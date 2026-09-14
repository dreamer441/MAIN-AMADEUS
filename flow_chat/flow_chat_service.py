"""Flow request execution using the shared AMADEUS chat module."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from amadeus_chat import AmadeusChatModule
from amadeus_trace import TraceLogger
from flow_chat.flow_chat_store import FlowChatStore
from flow_chat.flow_context_builder import FlowContextBuilder
from flow_chat.review_context_builder import FlowReviewRequest
from identity_module import IdentityPromptBuilder
from llm_client import OllamaClientError


@dataclass(frozen=True, slots=True)
class FlowExecutionResult:
    """The Flow execution outcome, independent of optional Process Monitor events."""

    response: str | None = None
    error: Exception | None = None
    created_chat: dict[str, str] | None = None
    proposal_ids: tuple[str, ...] = ()
    created_workspace_ids: tuple[str, ...] = ()
    approval_request: dict[str, Any] | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether Flow received a usable LLM response."""
        return self.error is None and self.response is not None


class FlowChatService:
    """Run Flow requests while keeping their persistence separate from normal chat."""

    def __init__(
        self,
        chat_module: AmadeusChatModule,
        flow_context_builder: FlowContextBuilder,
        flow_chat_store: FlowChatStore,
        identity_prompt_builder: IdentityPromptBuilder,
        create_pending_action: Callable[..., Any] | None = None,
        inferred_read_context_provider: Callable[[str], str | None] | None = None,
    ) -> None:
        self.chat_module = chat_module
        self.flow_context_builder = flow_context_builder
        self.flow_chat_store = flow_chat_store
        self.identity_prompt_builder = identity_prompt_builder
        self.create_pending_action = create_pending_action
        # Core owns inference and annotation handling; Flow receives only safe text context.
        self.inferred_read_context_provider = inferred_read_context_provider

    def handle_message(self, message: str, trace_logger: TraceLogger) -> FlowExecutionResult:
        """Build Flow context, call Chat, and atomically save a successful exchange."""
        try:
            review_request = FlowReviewRequest.parse(message)
        except ValueError as error:
            return FlowExecutionResult(error=error)
        inferred_read_context = (
            self.inferred_read_context_provider(message)
            if review_request is None and self.inferred_read_context_provider is not None
            else None
        )
        context_bundle = self.flow_context_builder.build_for_message(message, trace_logger=trace_logger)
        llm_message = review_request.question if review_request is not None else message
        try:
            response = self.chat_module.handle_message(
                llm_message,
                recent_conversation=self._combine_context(
                    context_bundle.recent_flow_history,
                    context_bundle.dedicated_chat_metadata,
                    context_bundle.review_context,
                    inferred_read_context,
                ),
                identity_prompt=self.identity_prompt_builder.build_for_chat(project_context_active=False),
                trace_logger=trace_logger,
                raise_llm_errors=True,
            )
        except OllamaClientError as error:
            return FlowExecutionResult(error=error)

        self.flow_chat_store.append_exchange(message, response)
        trace_logger.add_event("module", "Flow Response Stored", "Successful Flow exchange stored separately from dedicated chats.", level="success")
        return FlowExecutionResult(response=response)

    def _combine_context(self, recent_flow_history: str | None, dedicated_chat_metadata: str, review_context: str | None, inferred_read_context: str | None) -> str:
        """Keep Flow history and registry metadata visibly separate inside Chat context."""
        sections = [section for section in (recent_flow_history, dedicated_chat_metadata, review_context, inferred_read_context) if section]
        return "\n\n---\n\n".join(sections)
