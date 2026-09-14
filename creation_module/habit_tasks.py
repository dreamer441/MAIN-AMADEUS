"""Typed, persistence-free preparation of Flow Habit Tracker task requests."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HabitTaskProposal:
    """Validated task content passed to Habit Tracker only after Core approval."""

    title: str
    description: str | None = None


def propose_habit_task(title: str, description: str | None = None) -> HabitTaskProposal:
    """Reject empty task content before an owner action is prepared."""
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("Task title cannot be empty.")
    clean_description = description.strip() if isinstance(description, str) else ""
    return HabitTaskProposal(clean_title, clean_description or None)
