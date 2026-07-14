"""Validated, safe operational events for the AMADEUS Process Monitor."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Mapping


class BrainRole(str, Enum):
    """The operational area responsible for an event."""

    ACTIVE = "active"
    INNER = "inner"
    SYSTEM = "system"


class ProcessEventType(str, Enum):
    """The validated kinds of observable process activity."""

    RUN = "run"
    OBJECTIVE = "objective"
    PLAN = "plan"
    STEP = "step"
    DECISION = "decision"
    CONTEXT = "context"
    TOOL = "tool"
    VALIDATION = "validation"
    WARNING = "warning"
    ERROR = "error"
    RESULT = "result"


class ProcessEventStatus(str, Enum):
    """The lifecycle state represented by an event."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ProcessEvent:
    """One immutable, validated record of real operational activity."""

    event_id: str
    run_id: str
    sequence: int
    timestamp: datetime
    source_module: str
    brain_role: BrainRole
    event_type: ProcessEventType
    status: ProcessEventStatus
    title: str
    summary: str
    parent_event_id: str | None = None
    details: str | None = None
    progress: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject malformed records before they can enter a process stream."""
        for name in ("event_id", "run_id", "source_module", "title", "summary"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            object.__setattr__(self, name, value.strip())

        if self.parent_event_id is not None:
            if not isinstance(self.parent_event_id, str) or not self.parent_event_id.strip():
                raise ValueError("parent_event_id must be a non-empty string when provided")
            object.__setattr__(self, "parent_event_id", self.parent_event_id.strip())
        if self.details is not None:
            if not isinstance(self.details, str):
                raise ValueError("details must be a string when provided")
            object.__setattr__(self, "details", self.details.strip() or None)

        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 1:
            raise ValueError("sequence must be a positive integer")
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be a timezone-aware datetime")
        if self.timestamp.utcoffset() != timezone.utc.utcoffset(self.timestamp):
            raise ValueError("timestamp must use UTC")
        if not isinstance(self.brain_role, BrainRole):
            raise ValueError("brain_role must be a BrainRole")
        if not isinstance(self.event_type, ProcessEventType):
            raise ValueError("event_type must be a ProcessEventType")
        if not isinstance(self.status, ProcessEventStatus):
            raise ValueError("status must be a ProcessEventStatus")
        if self.progress is not None:
            if isinstance(self.progress, bool) or not isinstance(self.progress, (int, float)):
                raise ValueError("progress must be a number from 0.0 through 1.0")
            progress = float(self.progress)
            if not isfinite(progress) or not 0.0 <= progress <= 1.0:
                raise ValueError("progress must be a number from 0.0 through 1.0")
            object.__setattr__(self, "progress", progress)
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, object]:
        """Return structured data, including legacy display aliases."""
        category = _legacy_category(self)
        level = _legacy_level(self.status, self.event_type)
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "parent_event_id": self.parent_event_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "source_module": self.source_module,
            "brain_role": self.brain_role.value,
            "event_type": self.event_type.value,
            "status": self.status.value,
            "title": self.title,
            "summary": self.summary,
            "details": self.details,
            "progress": self.progress,
            "metadata": dict(self.metadata),
            # Existing Process Monitor callers consume these legacy field names.
            "category": category,
            "message": self.summary,
            "level": level,
        }

    def to_compact_text(self) -> str:
        """Return the established short Process Monitor rendering."""
        return f"[{self.title}]\n{self.summary}"

    def to_detailed_text(self) -> str:
        """Return the established detailed Process Monitor rendering."""
        return (
            f"[{self.title}]\n"
            f"Level: {_legacy_level(self.status, self.event_type)}\n"
            f"Category: {_legacy_category(self)}\n"
            f"Time: {self.timestamp.isoformat()}\n"
            f"{self.summary}"
        )


def _legacy_category(event: ProcessEvent) -> str:
    """Return a preserved legacy category or map a native event type safely."""
    legacy_category = event.metadata.get("legacy_category")
    if isinstance(legacy_category, str) and legacy_category in {
        "system",
        "input",
        "annotation",
        "routing",
        "file",
        "llm",
        "module",
        "output",
        "error",
    }:
        return legacy_category
    return {
        ProcessEventType.OBJECTIVE: "input",
        ProcessEventType.DECISION: "routing",
        ProcessEventType.CONTEXT: "module",
        ProcessEventType.TOOL: "llm",
        ProcessEventType.RESULT: "output",
        ProcessEventType.ERROR: "error",
        ProcessEventType.WARNING: "system",
    }.get(event.event_type, "system")


def _legacy_level(status: ProcessEventStatus, event_type: ProcessEventType) -> str:
    """Map validated statuses to the old Process Monitor levels."""
    if status is ProcessEventStatus.FAILED:
        return "error"
    if event_type is ProcessEventType.WARNING:
        return "warning"
    if status is ProcessEventStatus.COMPLETED:
        return "success"
    return "info"
