"""Framework-independent lifecycle and live delivery for process events."""

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from amadeus_trace.process_event import BrainRole, ProcessEvent, ProcessEventStatus, ProcessEventType


class ProcessEventEmitter:
    """Own one request's ordered events and safely deliver them to listeners."""

    def __init__(self) -> None:
        self._run_id: str | None = None
        self._is_terminal = False
        self._events: list[ProcessEvent] = []
        self._listeners: list[Callable[[ProcessEvent], None]] = []

    @property
    def events(self) -> tuple[ProcessEvent, ...]:
        """Return an immutable snapshot of the active run's recorded events."""
        return tuple(self._events)

    def start_run(
        self,
        *,
        source_module: str,
        title: str,
        summary: str,
        brain_role: BrainRole = BrainRole.SYSTEM,
    ) -> str:
        """Start a fresh run and record its initial running event."""
        self._run_id = uuid4().hex
        self._is_terminal = False
        self._events = []
        self._record(
            source_module=source_module,
            brain_role=brain_role,
            event_type=ProcessEventType.RUN,
            status=ProcessEventStatus.RUNNING,
            title=title,
            summary=summary,
        )
        return self._run_id

    def emit(
        self,
        *,
        source_module: str,
        brain_role: BrainRole,
        event_type: ProcessEventType,
        status: ProcessEventStatus,
        title: str,
        summary: str,
        details: str | None = None,
        progress: float | None = None,
        metadata: dict[str, object] | None = None,
        parent_event_id: str | None = None,
    ) -> ProcessEvent:
        """Record and immediately deliver one validated operational event."""
        self._ensure_active_run()
        return self._record(
            source_module=source_module,
            brain_role=brain_role,
            event_type=event_type,
            status=status,
            title=title,
            summary=summary,
            details=details,
            progress=progress,
            metadata=metadata,
            parent_event_id=parent_event_id,
        )

    def complete_run(self, *, title: str, summary: str) -> ProcessEvent:
        """Record a successful terminal event for the active run."""
        self._ensure_active_run()
        return self._record(
            source_module="system",
            brain_role=BrainRole.SYSTEM,
            event_type=ProcessEventType.RUN,
            status=ProcessEventStatus.COMPLETED,
            title=title,
            summary=summary,
            terminal=True,
        )

    def fail_run(self, *, title: str, summary: str, details: str | None = None) -> ProcessEvent:
        """Record a failed terminal event for the active run."""
        self._ensure_active_run()
        return self._record(
            source_module="system",
            brain_role=BrainRole.SYSTEM,
            event_type=ProcessEventType.ERROR,
            status=ProcessEventStatus.FAILED,
            title=title,
            summary=summary,
            details=details,
            terminal=True,
        )

    def subscribe(self, listener: Callable[[ProcessEvent], None]) -> None:
        """Register a callback for future events without framework dependencies."""
        if not callable(listener):
            raise ValueError("listener must be callable")
        self._listeners.append(listener)

    def _ensure_active_run(self) -> None:
        """Reject work before a run starts or after its terminal event."""
        if self._run_id is None:
            raise RuntimeError("start_run must be called before emit")
        if self._is_terminal:
            raise RuntimeError("cannot emit after the run has reached a terminal state")

    def _record(self, *, terminal: bool = False, **fields: object) -> ProcessEvent:
        """Create, retain, and fault-isolated-deliver an event."""
        if self._run_id is None:
            raise RuntimeError("start_run must be called before recording events")
        event = ProcessEvent(
            event_id=uuid4().hex,
            run_id=self._run_id,
            sequence=len(self._events) + 1,
            timestamp=datetime.now(timezone.utc),
            metadata=dict(fields.pop("metadata", None) or {}),
            **fields,
        )
        self._events.append(event)
        # Set terminal state before listeners run to prevent re-entrant conflicts.
        self._is_terminal = terminal
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:
                # Monitoring must never stop recording or the request itself.
                continue
        return event
