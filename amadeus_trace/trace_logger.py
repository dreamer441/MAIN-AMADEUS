"""Safe façade for recording Process Monitor events.

Core and modules should use TraceLogger instead of touching TraceSession directly.
The logger intentionally swallows trace failures because diagnostics must never stop
AMADEUS from answering.
"""

from amadeus_trace.process_event import BrainRole, ProcessEventStatus, ProcessEventType
from amadeus_trace.process_event_emitter import ProcessEventEmitter
from amadeus_trace.trace_session import TraceSession


class TraceLogger:
    """Small façade used by Core and modules to record real execution events."""

    def __init__(self) -> None:
        self.emitter = ProcessEventEmitter()
        self.current_session: TraceSession | None = None

    def start_session(self) -> TraceSession:
        """Create a fresh trace session for the latest user message."""
        # A new session per message makes the right-side Process Monitor readable.
        # Later persistent logs can be added separately without changing this live view behavior.
        self.current_session = TraceSession()
        self.emitter.start_run(
            source_module="trace_logger",
            title="Trace Session Started",
            summary="Process Monitor session started.",
            # Legacy sessions were empty until their first explicit trace event.
            emit_initial=False,
        )
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
            event_type, status = self._map_legacy_event(category, level)
            clean_category = category.strip().lower()
            # Keep the historic public session object useful for direct consumers.
            self.current_session.add_event(category, title, message, level)
            self.emitter.emit(
                source_module=clean_category or "system",
                brain_role=BrainRole.SYSTEM,
                event_type=event_type,
                status=status,
                title=title,
                summary=message,
                metadata={"legacy_category": clean_category},
            )
        except Exception:
            # Trace is diagnostic only. AMADEUS must still answer if monitoring fails.
            return

    def get_trace_text(self, mode: str = "compact") -> str:
        """Return the latest session as readable monitor text."""
        try:
            if self.current_session is None:
                return "No trace session started."
            if not self.emitter.events:
                return "No trace events recorded."
            render = "to_detailed_text" if mode.strip().lower() == "detailed" else "to_compact_text"
            return "\n\n".join(getattr(event, render)() for event in self.emitter.events)
        except Exception as error:
            return f"Process Monitor error: {error}"

    def get_trace_events(self) -> list[dict[str, object]]:
        """Return structured events for GUI mode switching and future exports."""
        try:
            if self.current_session is None:
                return []
            return [event.to_dict() for event in self.emitter.events]
        except Exception:
            return []

    @staticmethod
    def _map_legacy_event(category: str, level: str) -> tuple[ProcessEventType, ProcessEventStatus]:
        """Translate tolerant legacy trace inputs to validated process fields."""
        clean_category = category.strip().lower()
        clean_level = level.strip().lower()
        event_type = {
            "input": ProcessEventType.OBJECTIVE,
            "annotation": ProcessEventType.STEP,
            "routing": ProcessEventType.DECISION,
            "file": ProcessEventType.TOOL,
            "llm": ProcessEventType.TOOL,
            "module": ProcessEventType.STEP,
            "output": ProcessEventType.RESULT,
            "error": ProcessEventType.ERROR,
        }.get(clean_category, ProcessEventType.STEP)
        if clean_level == "error":
            return ProcessEventType.ERROR, ProcessEventStatus.FAILED
        if clean_level == "warning":
            return ProcessEventType.WARNING, ProcessEventStatus.COMPLETED
        if clean_level == "success":
            return event_type, ProcessEventStatus.COMPLETED
        return event_type, ProcessEventStatus.RUNNING
