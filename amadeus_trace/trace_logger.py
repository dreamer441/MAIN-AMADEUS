"""Safe façade for recording Process Monitor events.

Core and modules should use TraceLogger instead of touching TraceSession directly.
The logger intentionally swallows trace failures because diagnostics must never stop
AMADEUS from answering.
"""

from amadeus_trace.trace_session import TraceSession


class TraceLogger:
    """Small façade used by Core and modules to record real execution events."""

    def __init__(self) -> None:
        self.current_session: TraceSession | None = None

    def start_session(self) -> TraceSession:
        """Create a fresh trace session for the latest user message."""
        # A new session per message makes the right-side Process Monitor readable.
        # Later persistent logs can be added separately without changing this live view behavior.
        self.current_session = TraceSession()
        return self.current_session

    def add_event(
        self,
        category: str,
        title: str,
        message: str,
        level: str = "info",
    ) -> None:
        """Add an event without allowing trace failures to break AMADEUS chat."""
        try:
            if self.current_session is None:
                self.start_session()
            self.current_session.add_event(category, title, message, level)
        except Exception:
            # Trace is diagnostic only. AMADEUS must still answer if monitoring fails.
            return

    def get_trace_text(self, mode: str = "compact") -> str:
        """Return the latest session as readable monitor text."""
        try:
            if self.current_session is None:
                return "No trace session started."
            return self.current_session.to_text(mode=mode)
        except Exception as error:
            return f"Process Monitor error: {error}"

    def get_trace_events(self) -> list[dict[str, str]]:
        """Return structured events for GUI mode switching and future exports."""
        try:
            if self.current_session is None:
                return []
            return self.current_session.to_list()
        except Exception:
            return []
