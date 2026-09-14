"""Independent local Habit Tracker module for AMADEUS."""

from habit_tracker.service import HabitTrackerService

__all__ = ["HabitTrackerView", "HabitTrackerService"]


def __getattr__(name: str):
    """Load the optional Qt view only when the desktop asks for it."""
    if name == "HabitTrackerView":
        from habit_tracker.view import HabitTrackerView
        return HabitTrackerView
    raise AttributeError(name)
