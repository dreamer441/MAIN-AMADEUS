"""Headless navigation and state-retention checks for the Flow Chat GUI shell."""

import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel

from amadeus_gui import AmadeusMainWindow
from amadeus_gui.flow_chat_view import FlowMessageInput
from amadeus_gui.main.main_window import NewChatDialog
from mindmap.gui import MindMapView
from mindmap.models import GraphNode, GraphSnapshot


class FakeFlowCore:
    """Core-shaped test double that keeps GUI tests independent of runtime data."""

    def list_chats(self) -> list[object]:
        return []

    def get_current_chat_id(self) -> str:
        return "main"

    def get_current_chat_metadata(self) -> SimpleNamespace:
        return SimpleNamespace(
            chat_id="main", title="Main Chat", description="", summary="", priority="Normal", purpose="General", scope="Local"
        )

    def load_chat_history(self) -> list[object]:
        return []

    def load_flow_history(self) -> list[object]:
        return [SimpleNamespace(speaker="AMADEUS", message="Welcome to Flow.")]

    def get_project_tree(self, _relative_path: str) -> dict:
        return {"path": "", "folders": [], "files": []}

    def get_comments_panel_payload(self) -> dict:
        return {"type": "comments", "title": "Comments", "content": "", "metadata": {"comments": []}}

    def __init__(self) -> None:
        self._mind_map_listeners = []
        self.mind_map_snapshot = GraphSnapshot(graph_id="main", nodes=(), links=())
        self.metadata_updates: list[dict[str, object]] = []
        self.created_chats: list[dict[str, object]] = []

    def create_chat(self, **fields: object) -> SimpleNamespace:
        self.created_chats.append(fields)
        return SimpleNamespace(chat_id="created", **fields)

    def update_chat_metadata(self, chat_id: str, **changes: object) -> SimpleNamespace:
        self.metadata_updates.append({"chat_id": chat_id, **changes})
        return SimpleNamespace(chat_id=chat_id, **changes)

    def get_mind_map_snapshot(self) -> GraphSnapshot:
        return self.mind_map_snapshot

    def subscribe_mind_map(self, listener) -> None:
        self._mind_map_listeners.append(listener)

    def publish_mind_map_change(self, node: GraphNode) -> None:
        self.mind_map_snapshot = GraphSnapshot(graph_id="main", nodes=(node,), links=())
        for listener in self._mind_map_listeners:
            listener({"event_type": "node_created", "entity_id": node.node_id})


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
        super().__init__()
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
        for label, view in (("Code", self.window.code_view), ("Habit Tracker", self.window.habit_tracker_view)):
            self.window.navigation_buttons[label].click()
            self.assertIs(view, self.window.views.currentWidget())
            self.assertEqual(label, view.module_name)
            self.assertIn("Foundation pending.", "\n".join(label.text() for label in view.findChildren(QLabel)))

    def test_mind_map_page_is_core_backed_and_receives_live_graph_changes(self) -> None:
        self.assertIsInstance(self.window.mind_map_view, MindMapView)
        self.window.navigation_buttons["Mind Map"].click()
        self.assertIs(self.window.mind_map_view, self.window.views.currentWidget())

        node = GraphNode(node_id="node-1", graph_id="main", node_type="idea", title="Live Node")
        self.window.core.publish_mind_map_change(node)
        self.assertTrue(wait_until(
            lambda: "node-1" in self.window.mind_map_view.node_items
            and "1 nodes" in self.window.mind_map_view.status_label.text()
        ))
        self.assertIn("1 nodes", self.window.mind_map_view.status_label.text())

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

    def test_chat_metadata_dialog_collects_and_prefills_typed_fields(self) -> None:
        dialog = NewChatDialog(
            suggested_title="Typed Chat", description="Workspace details", priority="Important", purpose="Study", scope="Global", editing=True
        )
        self.addCleanup(dialog.deleteLater)
        self.assertEqual("Edit Chat", dialog.windowTitle())
        self.assertEqual("Typed Chat", dialog.chat_title())
        self.assertEqual("Workspace details", dialog.chat_description())
        self.assertEqual(("Important", "Study", "Global"), (dialog.chat_priority(), dialog.chat_purpose(), dialog.chat_scope()))

    def test_edit_chat_uses_prefilled_dialog_and_keeps_history_visible(self) -> None:
        class AcceptedDialog:
            def __init__(self, **_kwargs) -> None:
                pass

            def exec(self):
                from PyQt6.QtWidgets import QDialog
                return QDialog.DialogCode.Accepted

            def chat_title(self) -> str:
                return "Renamed"

            def chat_description(self) -> str:
                return "Updated"

            def chat_priority(self) -> str:
                return "Critical"

            def chat_purpose(self) -> str:
                return "Development"

            def chat_scope(self) -> str:
                return "Project"

        self.window.chat_history.setPlainText("Existing visible history")
        with patch("amadeus_gui.main.main_window.NewChatDialog", AcceptedDialog):
            self.window._edit_current_chat()
        self.assertEqual("Existing visible history", self.window.chat_history.toPlainText())
        self.assertEqual(
            {
                "chat_id": "main", "title": "Renamed", "description": "Updated", "priority": "Critical",
                "purpose": "Development", "scope": "Project",
            },
            self.window.core.metadata_updates[-1],
        )

    def test_edit_chat_button_is_disabled_while_a_response_is_pending(self) -> None:
        self.window._set_waiting_for_response(True)
        self.assertFalse(self.window.edit_chat_button.isEnabled())
        self.window._set_waiting_for_response(False)
        self.assertTrue(self.window.edit_chat_button.isEnabled())

    def test_new_chat_forwards_all_typed_metadata_to_core(self) -> None:
        class AcceptedDialog:
            def __init__(self, **_kwargs) -> None:
                pass

            def exec(self):
                from PyQt6.QtWidgets import QDialog
                return QDialog.DialogCode.Accepted

            def chat_title(self) -> str:
                return "Created"

            def chat_description(self) -> str:
                return "New workspace"

            def chat_priority(self) -> str:
                return "Important"

            def chat_purpose(self) -> str:
                return "Project"

            def chat_scope(self) -> str:
                return "Global"

        with patch("amadeus_gui.main.main_window.NewChatDialog", AcceptedDialog):
            self.window._create_new_chat()
        self.assertEqual(
            {"title": "Created", "description": "New workspace", "priority": "Important", "purpose": "Project", "scope": "Global"},
            self.window.core.created_chats[-1],
        )

    def test_flow_input_sends_on_enter_and_keeps_shift_enter_for_newlines(self) -> None:
        input_widget = FlowMessageInput()
        self.addCleanup(input_widget.deleteLater)
        sent = []
        input_widget.send_requested.connect(lambda: sent.append(True))

        input_widget.setFocus()
        QTest.keyClick(input_widget, Qt.Key.Key_Return)
        self.assertEqual([True], sent)
        self.assertEqual("", input_widget.toPlainText())

        QTest.keyClick(input_widget, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual([True], sent)
        self.assertEqual("\n", input_widget.toPlainText())

    def test_side_panels_can_hide_and_restore_without_losing_state(self) -> None:
        flow_view = self.window.flow_chat_view
        flow_view.process_monitor.setPlainText("Flow event remains visible")
        flow_view.side_panel_toggle_button.click()
        self.assertTrue(flow_view.flow_side_panel.isHidden())
        self.assertEqual("<", flow_view.side_panel_toggle_button.text())
        flow_view.side_panel_toggle_button.click()
        self.assertFalse(flow_view.flow_side_panel.isHidden())
        self.assertIn("Flow event remains visible", flow_view.process_monitor.toPlainText())

        self.window.navigation_buttons["Chats"].click()
        self.window.right_panel.setCurrentIndex(self.window.right_panel.PROCESS_TAB_INDEX)
        self.window.side_panel_toggle_button.click()
        self.assertTrue(self.window.right_panel.isHidden())
        self.assertEqual("<", self.window.side_panel_toggle_button.text())
        self.window.side_panel_toggle_button.click()
        self.assertFalse(self.window.right_panel.isHidden())
        self.assertEqual(self.window.right_panel.PROCESS_TAB_INDEX, self.window.right_panel.currentIndex())


if __name__ == "__main__":
    unittest.main()
