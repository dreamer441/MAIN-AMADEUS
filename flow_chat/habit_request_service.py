"""Safe Flow boundary for deterministic Habit Tracker requests.

This service accepts raw Flow text and prevents Habit command validation from
falling into the generic Flow failure path.  It prepares no persistence work;
Core remains responsible for registering and approving owner actions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from flow_chat.habit_commands import FlowHabitCommandInterpreter


@dataclass(frozen=True, slots=True)
class HabitReadResponse:
    """A deterministic response obtained through the Habit Tracker public API."""

    response: str


@dataclass(frozen=True, slots=True)
class HabitApprovalRequest:
    """A validated, non-persistent owner action ready for Core approval."""

    fields: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HabitValidationResponse:
    """A user-safe validation response for a recognized Habit request."""

    response: str


HabitRequestResult = HabitReadResponse | HabitApprovalRequest | HabitValidationResponse


class FlowHabitRequestService:
    """Own Flow's raw-text boundary for bounded Habit Tracker commands."""

    def __init__(self, habit_tracker: Any) -> None:
        self._interpreter = FlowHabitCommandInterpreter(habit_tracker)

    def handle(self, message: str) -> HabitRequestResult | None:
        """Return a typed result, or ``None`` when text is not a Habit request."""
        try:
            result = self._interpreter.execute(self._normalize_task_creation(message))
        except ValueError as error:
            # Parser and Creation validation errors are intentional user input feedback.
            return HabitValidationResponse(str(error))
        except Exception:
            # No Habit parser failure may reach Core's generic Flow fallback.
            return HabitValidationResponse(
                "Habit request could not be validated. Use /habit help for supported commands."
            )

        if result is None:
            return None
        if result.action is None:
            return HabitReadResponse(result.response)
        return HabitApprovalRequest(dict(result.action))

    @staticmethod
    def _normalize_task_creation(message: str) -> str:
        """Convert supported task phrases into the explicit parser grammar.

        This is deliberately limited to task creation. Other Habit commands keep
        their existing explicit grammar and are still validated by the interpreter.
        """
        clean = message.strip()
        if clean.lower().startswith("/habit"):
            if len(clean) > 6 and not clean[6].isspace():
                return message
            clean = clean[6:].strip()

        match = re.match(
            r"^(?:add|create)\s+(?:(?:a|an)\s+)?(?P<priority>(?:(?:urgent|important)\s+)*)"
            r"(?:(?:one[- ]time)\s+)?task\s+(?P<body>.+)$",
            clean,
            re.I,
        )
        if match is None:
            return message

        priority_words = match.group("priority").lower().split()
        title, separator, fields = match.group("body").partition(";")
        title, natural_date = FlowHabitRequestService._extract_tail_date(title)
        extra_fields = fields.strip()
        if natural_date:
            extra_fields = f"date: {natural_date}" + (f"; {extra_fields}" if extra_fields else "")

        if priority_words:
            kind = "matrix"
            priority_fields = [
                f"urgent: {'yes' if 'urgent' in priority_words else 'no'}",
                f"important: {'yes' if 'important' in priority_words else 'no'}",
            ]
            extra_fields = "; ".join(priority_fields + ([extra_fields] if extra_fields else []))
        else:
            kind = "task"

        # Explicit syntax prevents the legacy natural-language normalizer from
        # interpreting a ``date: tomorrow`` field as a second trailing date.
        normalized = f"/habit add {kind} {title.strip()}"
        return normalized + (f"; {extra_fields}" if separator or extra_fields else "")

    @staticmethod
    def _extract_tail_date(title: str) -> tuple[str, str | None]:
        """Move a bounded trailing natural date into the parser's date field."""
        match = re.match(
            r"^(?P<title>.*?)(?:\s+(?:for|on)?)?\s+(?P<date>today|tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|\d{4}-\d{2}-\d{2})\s*$",
            title,
            re.I,
        )
        if match is None:
            return title, None
        return match.group("title").strip(), match.group("date")
