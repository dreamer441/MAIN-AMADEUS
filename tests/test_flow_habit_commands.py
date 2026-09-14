"""Focused Flow-to-Habit Tracker command and approval tests."""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from amadeus_core.core import AmadeusCore
from flow_chat.habit_commands import FlowHabitCommandInterpreter
from habit_tracker.service import HabitTrackerService


class _FakeLLM:
    def __init__(self): self.prompts = []
    def generate(self, prompt, system_prompt=None):
        self.prompts.append(prompt)
        return "LLM response"


class FlowHabitCommandsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.core = AmadeusCore(llm_client=_FakeLLM(), project_root=self.root)

    def tearDown(self): self.temp.cleanup()

    def _approve(self, command):
        result = self.core.handle_flow_message(command)
        self.assertIn("approval_request", result)
        return self.core.approve_pending_action(result["approval_request"]["action_id"])

    def test_one_time_routine_event_and_read_are_owner_approved(self):
        self._approve("/habit add task Buy groceries; date: 2026-08-07; description: milk")
        self._approve("/habit add routine Stretch; repeat: monday,wednesday")
        self._approve("/habit add event Dentist; date: 2026-08-07; time: 14:30")
        read = self.core.handle_flow_message("/habit show; date: 2026-08-07")
        self.assertIn("Buy groceries", read["response"])
        self.assertIn("Dentist", read["response"])
        self.assertEqual([], self.core.llm_client.prompts)
        self.assertEqual(["Buy groceries"], [item["title"] for item in self.core.habit_tracker_service.day_overview("2026-08-07")["one_time_tasks"]])

    def test_matrix_priority_schedule_update_completion_and_delete(self):
        task_id = self._approve("/habit add matrix Release; urgent: yes; important: no; date: 2026-08-07; time: 09:30")
        task = self.core.habit_tracker_service.matrix_tasks()[0]
        self.assertEqual(("urgent_not_important", "2026-08-07", "09:30"), (task["quadrant"], task["scheduled_date"], task["scheduled_time"]))
        self._approve(f"/habit update matrix {task_id}; important: yes; date: 2026-08-08")
        self._approve(f"/habit complete matrix {task_id}")
        updated = self.core.habit_tracker_service.matrix_tasks()[0]
        self.assertEqual(("urgent_important", "2026-08-08", 1), (updated["quadrant"], updated["scheduled_date"], updated["is_completed"]))
        self._approve(f"/habit delete matrix {task_id}")
        self.assertEqual([], self.core.habit_tracker_service.matrix_tasks())

    def test_timer_alarm_read_and_cancel(self):
        timer_id = self._approve("/habit start timer Focus for 25 minutes")
        alarm_id = self._approve("/habit set alarm Stand up; date: 2026-08-07; time: 15:00")
        response = self.core.handle_flow_message("/habit show alarms")["response"]
        self.assertIn("Focus", response)
        self.assertIn("Stand up", response)
        self._approve(f"/habit cancel timer {timer_id}")
        self._approve(f"/habit cancel alarm {alarm_id}")
        self.assertEqual([], self.core.habit_tracker_service.active_alarms())

    def test_event_delete_is_approval_gated(self):
        event_id = self._approve("/habit add event Review; date: 2026-08-07")
        self._approve(f"/habit delete event {event_id}")
        self.assertEqual([], self.core.habit_tracker_service.day_overview("2026-08-07")["calendar_events"])

    def test_task_and_routine_complete_and_delete_actions(self):
        task_id = self._approve("/habit add task Wash car; date: 2026-08-07")
        routine_id = self._approve("/habit add routine Read; repeat: daily")
        self._approve(f"/habit complete task {task_id}")
        self._approve(f"/habit complete routine {routine_id}; date: 2026-08-07")
        overview = self.core.habit_tracker_service.day_overview("2026-08-07")
        self.assertTrue(overview["one_time_tasks"][0]["is_completed"])
        self.assertTrue(overview["routine_tasks"][0]["is_completed_today"])
        self._approve(f"/habit delete task {task_id}")
        self._approve(f"/habit archive routine {routine_id}")
        self.assertEqual([], self.core.habit_tracker_service.day_overview("2026-08-07")["one_time_tasks"])
        self.assertEqual([], self.core.habit_tracker_service.day_overview("2026-08-07")["routine_tasks"])

    def test_dates_times_empty_tasks_and_ambiguous_commands_are_safe(self):
        interpreter = FlowHabitCommandInterpreter(HabitTrackerService(self.root), today=lambda: date(2026, 8, 5))
        self.assertEqual("2026-08-10", interpreter._resolve_date("next monday"))
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            interpreter.execute("/habit add task Test; date: monday")
        with self.assertRaisesRegex(ValueError, "Time is ambiguous"):
            interpreter.execute("/habit set alarm Test; date: 2026-08-07; time: 3pm")
        with self.assertRaisesRegex(ValueError, "title cannot be empty"):
            interpreter.execute("/habit add task ; date: 2026-08-07")

    def test_non_habit_flow_isolation_remains_llm_routed(self):
        result = self.core.handle_flow_message("Explain my project")
        self.assertEqual("LLM response", result["response"])
        self.assertEqual(1, len(self.core.llm_client.prompts))

    def test_natural_habit_reads_bypass_inner_brain_llm_and_chat_data(self):
        inner = type("Inner", (), {"analyze_message": lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError())})()
        self.core = AmadeusCore(llm_client=_FakeLLM(), project_root=self.root, inner_brain_service=inner)
        self._approve("/habit add task Buy groceries; date: 2026-08-07")
        self._approve("/habit add event Dentist; date: 2026-08-07; time: 14:30")

        for request in (
            "What tasks do I have on 2026-08-07?",
            "Can you show my tasks for 2026-08-07?",
            "Show my calendar for 2026-08-07",
            "List my Eisenhower tasks",
            "What alarms and timers are active?",
            "Show my routines today",
            "What habits do I have today?",
        ):
            result = self.core.handle_flow_message(request)
            self.assertIsNone(result["side_panel"])
            self.assertNotEqual("Chat Data", result.get("side_panel", {}).get("title") if result.get("side_panel") else "")

        self.assertIn("Buy groceries", self.core.handle_flow_message("What tasks do I have on 2026-08-07?")["response"])
        self.assertIn("Dentist", self.core.handle_flow_message("Show my calendar for 2026-08-07")["response"])
        self.assertEqual([], self.core.llm_client.prompts)

    def test_natural_habit_actions_return_approval_not_llm_or_chat_data(self):
        inner = type("Inner", (), {"analyze_message": lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError())})()
        self.core = AmadeusCore(llm_client=_FakeLLM(), project_root=self.root, inner_brain_service=inner)

        for request in (
            "Add a task Buy groceries for 2026-08-07",
            "Create a calendar event Dentist on 2026-08-07 at 14:30",
            "Start a timer Focus for 25 minutes",
        ):
            result = self.core.handle_flow_message(request)
            self.assertIn("approval_request", result)
            self.assertEqual("habit_tracker", result["approval_request"]["kind"])
            self.assertEqual("", result["response"])
            self.assertIsNone(result["side_panel"])

        self.assertEqual([], self.core.llm_client.prompts)

    def test_task_creation_phrases_return_non_empty_approval_actions(self):
        expected_today = date.today().isoformat()
        cases = (
            ("/habit add task Buy groceries; date: 2026-08-07", "one_time", "Buy groceries", "2026-08-07"),
            ("create a task Buy groceries", "one_time", "Buy groceries", expected_today),
            ("add a task Buy groceries tomorrow", "one_time", "Buy groceries", (date.today() + timedelta(days=1)).isoformat()),
            ("create an Eisenhower task Buy groceries tomorrow; urgent: yes; important: no", "matrix", "Buy groceries", None),
        )

        for request, action_kind, title, task_date in cases:
            with self.subTest(request=request):
                result = self.core.handle_flow_message(request)
                approval = result.get("approval_request")
                self.assertIsInstance(approval, dict)
                assert isinstance(approval, dict)
                self.assertEqual("habit_tracker", approval["kind"])
                fields = approval["display_fields"]
                self.assertEqual((action_kind, title), (fields["kind"], fields["title"]))
                if task_date is not None:
                    self.assertEqual(task_date, fields["date"])
                else:
                    self.assertEqual(("urgent_not_important", (date.today() + timedelta(days=1)).isoformat()), (fields["quadrant"], fields["scheduled_date"]))
                self.assertEqual("", result["response"])
            self.assertIsNone(result["side_panel"])

    def test_public_flow_entrypoint_normalizes_task_forms_and_approval_persists(self):
        expected_today = date.today().isoformat()
        expected_tomorrow = (date.today() + timedelta(days=1)).isoformat()
        cases = (
            ("create a task Buy groceries", "one_time", "Buy groceries", expected_today),
            ("create a task Buy groceries tomorrow", "one_time", "Buy groceries", expected_tomorrow),
            ("add an urgent important task Submit report", "matrix", "Submit report", None),
            ("/habit create a task Plan trip tomorrow", "one_time", "Plan trip", expected_tomorrow),
            ("/habit add an urgent important task File taxes", "matrix", "File taxes", None),
        )

        for request, kind, title, task_date in cases:
            with self.subTest(request=request):
                result = self.core.handle_flow_message(request)
                approval = result.get("approval_request")
                self.assertIsInstance(approval, dict)
                assert isinstance(approval, dict)
                fields = approval["display_fields"]
                self.assertEqual((kind, title), (fields["kind"], fields["title"]))
                if task_date is not None:
                    self.assertEqual(task_date, fields["date"])
                else:
                    self.assertEqual("urgent_important", fields["quadrant"])
                self.core.approve_pending_action(approval["action_id"])

        self.assertEqual(
            ["Buy groceries"],
            [item["title"] for item in self.core.habit_tracker_service.day_overview(expected_today)["one_time_tasks"]],
        )
        self.assertEqual(
            ["Buy groceries", "Plan trip"],
            [item["title"] for item in self.core.habit_tracker_service.day_overview(expected_tomorrow)["one_time_tasks"]],
        )
        self.assertEqual(
            ["Submit report", "File taxes"],
            [item["title"] for item in self.core.habit_tracker_service.matrix_tasks()],
        )

    def test_public_flow_entrypoint_returns_each_habit_validation_error_without_fallback(self):
        cases = (
            ("/habit add task Test; date: monday", "Date is ambiguous"),
            ("/habit set alarm Test; date: 2026-08-07; time: 3pm", "Time is ambiguous"),
            ("/habit add task ; date: 2026-08-07", "Task title cannot be empty"),
            ("/habit make coffee", "Use /habit help"),
        )

        for request, expected_error in cases:
            with self.subTest(request=request):
                result = self.core.handle_flow_message(request)
                self.assertIn(expected_error, result["response"])
                self.assertNotIn("could not complete that Flow request", result["response"])
                self.assertNotIn("approval_request", result)

        self.assertEqual([], self.core.llm_client.prompts)

    def test_public_flow_entrypoint_contains_unexpected_habit_parser_failure(self):
        self.core.flow_habit_requests._interpreter = type(
            "BrokenInterpreter",
            (), {"execute": lambda *_args: (_ for _ in ()).throw(RuntimeError("private parser failure"))},
        )()

        result = self.core.handle_flow_message("/habit add task Buy groceries")

        self.assertEqual(
            "Habit request could not be validated. Use /habit help for supported commands.",
            result["response"],
        )
        self.assertNotIn("private parser failure", str(result))
        self.assertEqual([], self.core.llm_client.prompts)

    def test_explicit_and_natural_one_time_and_eisenhower_tasks_approve_and_persist(self):
        cases = (
            ("/habit create a one-time task Explicit task; date: 2026-08-07", "one_time", "Explicit task"),
            ("create a one-time task Natural task for 2026-08-08", "one_time", "Natural task"),
            ("/habit create an Eisenhower task Explicit matrix; urgent: yes; important: no", "matrix", "Explicit matrix"),
            ("create an Eisenhower task Natural matrix tomorrow; urgent: no; important: yes", "matrix", "Natural matrix"),
        )

        for request, action_kind, title in cases:
            with self.subTest(request=request):
                result = self.core.handle_flow_message(request)
                approval = result.get("approval_request")
                self.assertIsInstance(approval, dict)
                assert isinstance(approval, dict)
                self.assertEqual("habit_tracker", approval["kind"])
                self.assertEqual((action_kind, title), (approval["display_fields"]["kind"], approval["display_fields"]["title"]))
                self.core.approve_pending_action(approval["action_id"])

        self.assertEqual(
            ["Explicit task", "Natural task"],
            [item["title"] for item in self.core.habit_tracker_service.day_overview("2026-08-07")["one_time_tasks"]]
            + [item["title"] for item in self.core.habit_tracker_service.day_overview("2026-08-08")["one_time_tasks"]],
        )
        self.assertEqual(
            ["Natural matrix", "Explicit matrix"],
            [item["title"] for item in self.core.habit_tracker_service.matrix_tasks()],
        )


if __name__ == "__main__":
    unittest.main()
