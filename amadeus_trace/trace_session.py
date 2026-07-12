"""Per-message trace session for AMADEUS.

One TraceSession equals one user request. Keeping sessions small and temporary makes
the Process Monitor easy to understand: it shows what happened for the latest message,
not an endless mixed log from old conversations.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from amadeus_trace.trace_event import TraceEvent


@dataclass
class TraceSession:
    """Trace container for one user request.

    A trace session is intentionally per-message, not global. This keeps the Process Monitor focused on
    what happened during the latest request and prevents old execution events from being confused with
    the current routing path.
    """

    session_id: str = field(default_factory=lambda: uuid4().hex)
    events: list[TraceEvent] = field(default_factory=list)

    def add_event(
        self,
        category: str,
        title: str,
        message: str,
        level: str = "info",
    ) -> TraceEvent:
        """Record one real execution event and return it for optional caller use."""
        # Event creation normalizes bad category/level values, so callers can stay simple.
        event = TraceEvent(category=category, title=title, message=message, level=level)
        self.events.append(event)
        return event

    def to_text(self, mode: str = "compact") -> str:
        """Return all events as readable text for the Process Monitor panel."""
        if not self.events:
            return "No trace events recorded."

        clean_mode = mode.strip().lower()
        if clean_mode == "detailed":
            return "\n\n".join(event.to_detailed_text() for event in self.events)

        return "\n\n".join(event.to_compact_text() for event in self.events)

    def to_list(self) -> list[dict[str, str]]:
        """Return structured events for future GUI filters, exports, or debug tools."""
        # Keep this structured representation even while the GUI mostly shows plain text.
        # It will matter later for filters like category=llm or level=error.
        return [event.to_dict() for event in self.events]
