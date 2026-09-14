"""Persist dedicated-chat exchanges through the injected history store."""

from __future__ import annotations

from amadeus_trace import TraceLogger
from response_modes import ResponseModeDecision
from typing import Any


class ExchangePersistence:
    """Persist dedicated-chat exchanges through the injected history store."""

    def __init__(self, *, chat_history_store: Any) -> None:
        """Receive the public services needed by this workflow."""
        self.chat_history_store = chat_history_store

    def persist_exchange(
        self,
        user_message: str,
        response: str,
        response_decision: ResponseModeDecision | None = None,
        created_chat: dict[str, str] | None = None,
    ) -> None:
        """Persist the current user/AMADEUS exchange for later resume."""
        # Persistence happens after a module returns output, not before. This prevents half-handled
        # requests from becoming permanent conversation context if a route crashes early.
        self.chat_history_store.append_message("User", user_message)
        if response_decision is None or response_decision.policy.reply_required:
            self.chat_history_store.append_message("AMADEUS", response)

    def persist_completed_exchange(
        self,
        user_message: str,
        response: str,
        trace_logger: TraceLogger,
        response_decision: ResponseModeDecision | None = None,
    ) -> None:
        """Save an exchange, then report storage only after both records are written."""
        self.chat_history_store.append_message("User", user_message)
        if response_decision is None or response_decision.policy.reply_required:
            self.chat_history_store.append_message("AMADEUS", response)
            summary = "Stored the completed exchange in the active chat."
        else:
            summary = "Stored the user message; NONE mode intentionally omitted an assistant message."
        trace_logger.add_event("module", "Completed Exchange Stored", summary, level="success")
