"""Execute approved Habit Tracker actions through its shared public service."""

from __future__ import annotations

from typing import Any


class HabitActionExecutor:
    """Execute approved Habit Tracker actions through its shared public service."""

    def __init__(self, *, habit_tracker_service: Any) -> None:
        """Receive the public services needed by this workflow."""
        self.habit_tracker_service = habit_tracker_service

    def execute(self, fields: dict[str, Any]) -> Any:
        """Dispatch one approved typed request through Habit Tracker's public API."""
        kind = fields.pop("kind", "")
        if kind == "one_time":
            return self.habit_tracker_service.add_one_time_task(
                fields['title'],
                fields['date'],
                fields.get('description'),
            )
        if kind == "routine":
            return self.habit_tracker_service.add_routine_task(**fields)
        if kind == "event":
            return self.habit_tracker_service.add_calendar_event(
                fields['title'],
                fields['date'],
                fields.get('description'),
                fields.get('time'),
            )
        if kind == "matrix":
            task_id = self.habit_tracker_service.add_matrix_task(fields["title"], fields.get("description"), fields["quadrant"])
            if fields.get("scheduled_date"):
                self.habit_tracker_service.update_matrix_task(task_id, scheduled_date=fields["scheduled_date"], scheduled_time=fields.get("scheduled_time"))
            return task_id
        if kind == "matrix_update":
            return self.habit_tracker_service.update_matrix_task(fields.pop("id"), **fields)
        if kind == "matrix_complete":
            return self.habit_tracker_service.set_matrix_completion(fields["id"], fields["is_completed"])
        if kind == "matrix_delete":
            return self.habit_tracker_service.delete_matrix_task(fields["id"])
        if kind == "one_time_complete":
            return self.habit_tracker_service.set_one_time_completion(fields["id"], fields["is_completed"])
        if kind == "one_time_delete":
            return self.habit_tracker_service.delete_one_time_task(fields["id"])
        if kind == "routine_complete":
            return self.habit_tracker_service.set_routine_completion(
                fields['id'],
                fields['date'],
                fields['is_completed'],
            )
        if kind == "routine_archive":
            return self.habit_tracker_service.archive_routine_task(fields["id"])
        if kind == "event_delete":
            return self.habit_tracker_service.delete_calendar_event(fields["id"])
        if kind == "timer":
            return self.habit_tracker_service.create_timer(fields["title"], fields["minutes"])
        if kind == "alarm":
            return self.habit_tracker_service.create_alarm(fields["title"], fields["target_datetime"])
        if kind == "alarm_cancel":
            return self.habit_tracker_service.deactivate_alarm(fields["id"])
        if kind == "alarm_delete":
            return self.habit_tracker_service.delete_alarm(fields["id"])
        raise ValueError("Unsupported Habit Tracker action.")
