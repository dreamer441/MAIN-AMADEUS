"""Persistence-focused tests for the independent Habit Tracker module."""

import tempfile
import unittest
from pathlib import Path

from habit_tracker.service import HabitTrackerService


class HabitTrackerServiceTests(unittest.TestCase):
    """Verify the ported task-manager behavior remains local and predictable."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.service = HabitTrackerService(Path(self.temporary_directory.name))

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_day_overview_tracks_routines_tasks_and_events(self) -> None:
        routine_id = self.service.add_routine_task("Brush teeth")
        self.service.add_routine_task("Water plants", repeat_type="custom_days", days_of_week="monday,wednesday")
        task_id = self.service.add_one_time_task("Buy groceries", "2026-08-03")
        self.service.add_calendar_event("Appointment", "2026-08-03", event_time="15:00")
        self.service.set_routine_completion(routine_id, "2026-08-03", True)
        self.service.set_one_time_completion(task_id, True)

        overview = self.service.day_overview("2026-08-03")

        self.assertEqual("monday", overview["weekday"])
        self.assertEqual(["Brush teeth", "Water plants"], [task["title"] for task in overview["routine_tasks"]])
        self.assertTrue(overview["routine_tasks"][0]["is_completed_today"])
        self.assertTrue(overview["one_time_tasks"][0]["is_completed"])
        self.assertEqual("Appointment", overview["calendar_events"][0]["title"])

    def test_weekday_routine_repeats_in_each_following_week(self) -> None:
        self.service.add_routine_task(
            "Review weekly plan",
            repeat_type="custom_days",
            days_of_week="monday,friday",
        )

        next_monday = self.service.day_overview("2026-08-10")
        next_tuesday = self.service.day_overview("2026-08-11")
        next_friday = self.service.day_overview("2026-08-14")

        self.assertEqual(["Review weekly plan"], [task["title"] for task in next_monday["routine_tasks"]])
        self.assertEqual([], next_tuesday["routine_tasks"])
        self.assertEqual(["Review weekly plan"], [task["title"] for task in next_friday["routine_tasks"]])

    def test_matrix_and_timer_operations_are_independent(self) -> None:
        matrix_id = self.service.add_matrix_task("Plan release", quadrant="urgent_important")
        timer_id = self.service.create_timer("Focus", 25)

        self.assertEqual(matrix_id, self.service.matrix_tasks()[0]["id"])
        self.assertEqual(timer_id, self.service.active_alarms()[0]["id"])

        self.service.delete_matrix_task(matrix_id)
        self.service.delete_alarm(timer_id)

        self.assertEqual([], self.service.matrix_tasks())
        self.assertEqual([], self.service.active_alarms())


if __name__ == "__main__":
    unittest.main()
