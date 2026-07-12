"""Trace event model for the AMADEUS Process Monitor.

A TraceEvent is not a thought. It is a real execution marker created by code while
AMADEUS handles a user request. This boundary matters: the monitor helps debug the
system pipeline, but it must never pretend to reveal private reasoning.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


VALID_TRACE_LEVELS = {"info", "warning", "error", "success"}
VALID_TRACE_CATEGORIES = {
    "system",
    "input",
    "annotation",
    "routing",
    "file",
    "llm",
    "module",
    "output",
    "error",
}


@dataclass(frozen=True)
class TraceEvent:
    """One real execution event recorded while AMADEUS handles a message."""

    category: str
    title: str
    message: str
    level: str = "info"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        """Normalize trace fields without allowing invalid empty events."""
        clean_category = self.category.strip().lower() or "system"
        clean_level = self.level.strip().lower() or "info"
        clean_title = self.title.strip()
        clean_message = self.message.strip()

        # Unknown categories/levels are softened instead of rejected so a bad trace call
        # does not break the actual AMADEUS response path.
        if clean_category not in VALID_TRACE_CATEGORIES:
            clean_category = "system"
        if clean_level not in VALID_TRACE_LEVELS:
            clean_level = "info"
        if not clean_title:
            clean_title = "Trace Event"
        if not clean_message:
            clean_message = "No details provided."

        # The dataclass is frozen so outside code cannot accidentally mutate old trace events.
        object.__setattr__(self, "category", clean_category)
        object.__setattr__(self, "level", clean_level)
        object.__setattr__(self, "title", clean_title)
        object.__setattr__(self, "message", clean_message)

    def to_dict(self) -> dict[str, str]:
        """Return a structured shape the GUI can use for future debug views."""
        return {
            "category": self.category,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp,
            "level": self.level,
        }

    def to_compact_text(self) -> str:
        """Return the short display format for normal Process Monitor use."""
        return f"[{self.title}]\n{self.message}"

    def to_detailed_text(self) -> str:
        """Return the expanded display format for debugging routing and module flow."""
        return (
            f"[{self.title}]\n"
            f"Level: {self.level}\n"
            f"Category: {self.category}\n"
            f"Time: {self.timestamp}\n"
            f"{self.message}"
        )
