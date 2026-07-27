"""Headless navigation and state-retention checks for the Flow Chat GUI shell."""

import os
import threading
import time
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel

from amadeus_gui import AmadeusMainWindow


class FakeFlowCore:
    """Core-shaped test double that keeps GUI tests independent of runtime data."""

    def list_chats(self) -> list[object]:
        return []

    def get_current_chat_id(self) -> str:
        return "main"

    def get_current_chat_metadata(self) -> SimpleNamespace:
        return SimpleNamespace(title="Main Chat", description="", summary="")

    def load_chat_history(self) -> list[object]:
        return []

    def load_flow_history(self) -> list[object]:
        return [SimpleNamespace(speaker="AMADEUS", message="Welcome to Flow.")]

    def get_project_tree(self, _relative_path: str) -> dict:
        return {"path": "", "folders": [], "files": []}

    def get_comments_panel_payload(self) -> dict:
        return {"type": "comments", "title": "Comments", "content": "", "metadata": {"comments": []}}


def wait_until(predicate, timeout_ms: int = 1000) -> bool:
    """Pump queued Qt signals until a GUI condition settles or its deadline expires."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        QTest.qWait(10)
    QApplication.processEvents()
    return predicate()


class CoordinatedFlowCore(FakeFlowCore):
    """Fake Core that pauses after a live event so tests can observe it first."""

    def __init__(self) -> None:
        self.live_event_sent = threading.Event()
        self.allow_final_payload = threading.Event()

    def handle_flow_message(self, _message: str, event_listener=None) -> dict[str, object]:
        event_listener({"sequence": 1, "title": "Request Received", "summary": "Flow started."})
        self.live_event_sent.set()
        self.allow_final_payload.wait()
        return {
            "response": "Flow complete.",
            "trace_events": [
                {"sequence": 1, "title": "Request Received", "summary": "Flow started."},
                {"sequence": 2, "title": "Response Returned", "summary": "Flow complete."},
            ],
        }


class FailingFlowCore(FakeFlowCore):
    """Fake Core that exercises the worker's exception-safe completion path."""

    def handle_flow_message(self, _message: str, event_listener=None) -> dict[str, object]:
        raise RuntimeError("simulated Flow failure")


class FlowChatShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = AmadeusMainWindow(FakeFlowCore())

    def tearDown(self) -> None:
        self.window.close()

    def test_flow_is_default_and_has_persisted_history(self) -> None:
        self.assertIs(self.window.flow_chat_view, self.window.views.currentWidget())
        self.assertIn("Welcome to Flow.", self.window.flow_chat_view.flow_history.toPlainText())

    def test_sidebar_has_all_five_navigation_labels(self) -> None:
        self.assertEqual(
            ["Flow Chat", "Chats", "Code", "Mind Map", "Habit Tracker"],
            list(self.window.navigation_buttons),
        )

    def test_switching_preserves_existing_view_widgets_and_state(self) -> None:
        flow_view = self.window.flow_chat_view
        flow_view.message_input.setPlainText("Keep this draft")
        self.window.navigation_buttons["Chats"].click()
        self.assertIs(self.window.dedicated_chat_view, self.window.views.currentWidget())
        self.window.navigation_buttons["Flow Chat"].click()
        self.assertIs(flow_view, self.window.views.currentWidget())
        self.assertEqual("Keep this draft", flow_view.message_input.toPlainText())

    def test_chats_and_named_placeholders_are_accessible(self) -> None:
        self.window.navigation_buttons["Chats"].click()
        self.assertIs(self.window.dedicated_chat_view, self.window.views.currentWidget())
        for label, view in (("Code", self.window.code_view), ("Mind Map", self.window.mind_map_view), ("Habit Tracker", self.window.habit_tracker_view)):
            self.window.navigation_buttons[label].click()
            self.assertIs(view, self.window.views.currentWidget())
            self.assertEqual(label, view.module_name)
            self.assertIn("Foundation pending.", "\n".join(label.text() for label in view.findChildren(QLabel)))

    def test_flow_worker_renders_live_event_before_final_payload_reconciliation(self) -> None:
        core = CoordinatedFlowCore()
        window = AmadeusMainWindow(core)
        self.addCleanup(window.close)
        self.addCleanup(core.allow_final_payload.set)
        flow_view = window.flow_chat_view

        flow_view.message_input.setPlainText("Start Flow")
        flow_view.send_button.click()

        self.assertTrue(core.live_event_sent.wait(500))
        self.assertTrue(wait_until(lambda: "Request Received" in flow_view.process_monitor.toPlainText()))
        self.assertNotIn("Response Returned", flow_view.process_monitor.toPlainText())
        self.assertFalse(flow_view.message_input.isEnabled())

        core.allow_final_payload.set()

        self.assertTrue(wait_until(lambda: flow_view.message_input.isEnabled() and not flow_view.has_active_workers()))
        self.assertIn("Response Returned", flow_view.process_monitor.toPlainText())
        self.assertIn("Flow complete.", flow_view.flow_history.toPlainText())

    def test_failed_flow_request_reenables_input_and_send_controls(self) -> None:
        window = AmadeusMainWindow(FailingFlowCore())
        self.addCleanup(window.close)
        flow_view = window.flow_chat_view

        flow_view.message_input.setPlainText("Fail Flow")
        flow_view.send_button.click()

        self.assertTrue(wait_until(
            lambda: flow_view.message_input.isEnabled()
            and flow_view.send_button.isEnabled()
            and not flow_view.has_active_workers()
        ))
        self.assertIn("could not complete that Flow request", flow_view.flow_history.toPlainText())
        self.assertEqual("Ready", flow_view.status_label.text())

    def test_chats_controls_and_right_panel_remain_usable_after_flow_switches(self) -> None:
        chat_input = self.window.message_input
        right_panel = self.window.right_panel

        self.window.navigation_buttons["Chats"].click()
        chat_input.setPlainText("Keep this Chats draft")
        right_panel.setCurrentIndex(right_panel.PROCESS_TAB_INDEX)
        self.assertTrue(self.window.new_chat_button.isEnabled())
        self.assertTrue(self.window.add_comment_button.isEnabled())
        self.assertIs(right_panel, self.window.dedicated_chat_view.findChild(type(right_panel)))

        self.window.navigation_buttons["Flow Chat"].click()
        self.window.navigation_buttons["Chats"].click()

        self.assertIs(chat_input, self.window.message_input)
        self.assertEqual("Keep this Chats draft", chat_input.toPlainText())
        self.assertTrue(chat_input.isEnabled())
        self.assertTrue(self.window.send_button.isEnabled())
        self.assertEqual(right_panel.PROCESS_TAB_INDEX, right_panel.currentIndex())


if __name__ == "__main__":
    unittest.main()
