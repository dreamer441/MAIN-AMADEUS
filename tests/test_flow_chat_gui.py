"""Headless navigation and state-retention checks for the Flow Chat GUI shell."""

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QDialog

from amadeus_gui import AmadeusMainWindow
from amadeus_gui.flow_chat_view import FlowChatView, FlowMessageInput
from amadeus_gui.main.main_window import NewChatDialog
from canvas_module import CanvasModule, CanvasWorkspaceDescriptor
from canvas_module.gui import CanvasView
from habit_tracker import HabitTrackerService, HabitTrackerView
from mindmap.gui import MindMapView
from mindmap.models import GraphNode, GraphSnapshot


class FakeFlowCore:
    """Core-shaped test double that keeps GUI tests independent of runtime data."""

    def list_chats(self) -> list[object]:
        return self.chats

    def get_current_chat_id(self) -> str:
        return self.current_chat_id

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

    def get_canvas_workspace_descriptor(self) -> CanvasWorkspaceDescriptor:
        return CanvasWorkspaceDescriptor(
            workspace_id="main",
            title="AMADEUS Canvas",
            purpose="Spatial brainstorming test workspace.",
            status="foundation_ready",
        )

    def get_comments_panel_payload(self) -> dict:
        return {"type": "comments", "title": "Comments", "content": "", "metadata": {"comments": []}}

    def get_flow_annotation_suggestions(self, text: str) -> list[dict[str, str]]:
        if text.strip() == "/":
            return [{"label": "/create", "insert_text": "/create", "detail": "Create workspace"}]
        if text.strip() == "/create":
            return [{"label": "/create-sheet", "insert_text": "/create-sheet ", "detail": "Create Sheet"}]
        if text.strip() == "[memory]":
            return [{"label": "[memory][global]", "insert_text": "[memory][global]", "detail": "Save memory"}]
        return []

    def __init__(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        service_root = Path(self._temporary_directory.name)
        self.canvas = CanvasModule(service_root)
        self.habits = HabitTrackerService(service_root)
        self._mind_map_listeners = []
        self.mind_map_snapshot = GraphSnapshot(graph_id="main", nodes=(), links=())
        self.metadata_updates: list[dict[str, object]] = []
        self.created_chats: list[dict[str, object]] = []
        self.current_chat_id = "main"
        self.chats = [SimpleNamespace(chat_id="main", title="Main Chat")]

    def create_chat(self, **fields: object) -> SimpleNamespace:
        self.created_chats.append(fields)
        chat = SimpleNamespace(chat_id="created", **fields)
        self.chats.append(chat)
        self.current_chat_id = chat.chat_id
        return chat

    def switch_chat(self, chat_id: str) -> None:
        self.current_chat_id = chat_id

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

    def cleanup(self) -> None:
        """Release the isolated storage used by the real Canvas and Habit facades."""
        self._temporary_directory.cleanup()


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


def close_test_window(window) -> None:
    """Dispose fixture windows and timers before their temporary services."""
    if not wait_until(lambda: not window.mind_map_view.has_active_workers()
                      and not window.flow_chat_view.has_active_workers()):
        raise AssertionError("GUI workers did not finish during cleanup")
    window.close()
    window.mind_map_view.deleteLater()
    window.canvas_view.deleteLater()
    window.habit_tracker_view.deleteLater()
    for key in window.module_window_manager.registered_keys():
        module_window = window.module_window_manager.get_window(key)
        if module_window is not None:
            module_window.deleteLater()
    window.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


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
        self.core = FakeFlowCore()
        self.window = AmadeusMainWindow(self.core)

    def tearDown(self) -> None:
        close_test_window(self.window)
        self.core.cleanup()

    def test_flow_is_permanent_main_view_and_has_persisted_history(self) -> None:
        self.assertIs(self.window.flow_chat_view, self.window.centralWidget().findChild(FlowChatView))
        self.assertIn("Welcome to Flow.", self.window.flow_chat_view.flow_history.toPlainText())
        self.assertTrue(self.window.navigation_buttons["Flow Chat"].isChecked())

    def test_sidebar_has_all_six_navigation_labels(self) -> None:
        self.assertEqual(
            ["Flow Chat", "Chats", "Code", "Mind Map", "Canvas", "Habit Tracker"],
            list(self.window.navigation_buttons),
        )

    def test_several_module_windows_can_remain_open_in_parallel(self) -> None:
        self.window.navigation_buttons["Chats"].click()
        self.window.navigation_buttons["Mind Map"].click()
        self.window.navigation_buttons["Canvas"].click()

        self.assertTrue(self.window.module_window_manager.is_visible("chats"))
        self.assertTrue(self.window.module_window_manager.is_visible("mind_map"))
        self.assertTrue(self.window.module_window_manager.is_visible("canvas"))
        self.assertIsNot(
            self.window.module_window_manager.get_window("chats"),
            self.window.module_window_manager.get_window("canvas"),
        )

    def test_opening_module_windows_preserves_flow_and_reuses_views(self) -> None:
        flow_view = self.window.flow_chat_view
        flow_view.message_input.setPlainText("Keep this draft")

        self.window.navigation_buttons["Chats"].click()
        chats_window = self.window.module_window_manager.get_window("chats")
        self.assertIsNotNone(chats_window)
        self.assertIs(self.window.dedicated_chat_view, chats_window.centralWidget())

        self.window.navigation_buttons["Chats"].click()
        self.assertIs(chats_window, self.window.module_window_manager.get_window("chats"))
        self.window.navigation_buttons["Flow Chat"].click()
        self.assertEqual("Keep this draft", flow_view.message_input.toPlainText())

    def test_chats_code_and_habit_tracker_open_in_independent_windows(self) -> None:
        self.window.navigation_buttons["Chats"].click()
        chats_window = self.window.module_window_manager.get_window("chats")
        self.assertIs(self.window.dedicated_chat_view, chats_window.centralWidget())

        self.window.navigation_buttons["Code"].click()
        code_window = self.window.module_window_manager.get_window("code")
        self.assertIs(self.window.code_view, code_window.centralWidget())
        self.assertEqual("Code", self.window.code_view.module_name)
        self.assertIn("Foundation pending.", "\n".join(widget.text() for widget in self.window.code_view.findChildren(QLabel)))

        self.window.navigation_buttons["Habit Tracker"].click()
        habit_window = self.window.module_window_manager.get_window("habit_tracker")
        self.assertIs(self.window.habit_tracker_view, habit_window.centralWidget())
        self.assertIsInstance(self.window.habit_tracker_view, HabitTrackerView)

        self.assertTrue(self.window.module_window_manager.is_visible("chats"))
        self.assertTrue(self.window.module_window_manager.is_visible("code"))
        self.assertTrue(self.window.module_window_manager.is_visible("habit_tracker"))

    def test_mind_map_page_is_core_backed_and_receives_live_graph_changes(self) -> None:
        self.assertIsInstance(self.window.mind_map_view, MindMapView)
        self.window.navigation_buttons["Mind Map"].click()
        mind_map_window = self.window.module_window_manager.get_window("mind_map")
        self.assertIs(self.window.mind_map_view, mind_map_window.centralWidget())

        node = GraphNode(node_id="node-1", graph_id="main", node_type="idea", title="Live Node")
        self.window.core.publish_mind_map_change(node)
        self.assertTrue(wait_until(
            lambda: "node-1" in self.window.mind_map_view.node_items
            and "1 nodes" in self.window.mind_map_view.status_label.text()
        ))
        self.assertIn("1 nodes", self.window.mind_map_view.status_label.text())

    def test_canvas_page_is_a_persistent_core_backed_workspace(self) -> None:
        self.assertIsInstance(self.window.canvas_view, CanvasView)
        self.window.navigation_buttons["Canvas"].click()
        canvas_window = self.window.module_window_manager.get_window("canvas")
        self.assertIs(self.window.canvas_view, canvas_window.centralWidget())
        self.assertEqual("main", self.window.canvas_view.descriptor.workspace_id)
        self.assertEqual("Canvas", self.window.canvas_view.module_name)
        self.assertEqual("canvasSurface", self.window.canvas_view.surface.objectName())
        self.assertIn("loaded 0 blocks and 0 connectors", self.window.canvas_view.status_label.text().lower())

    def test_flow_worker_renders_live_event_before_final_payload_reconciliation(self) -> None:
        core = CoordinatedFlowCore()
        window = AmadeusMainWindow(core)
        self.addCleanup(core.cleanup)
        self.addCleanup(close_test_window, window)
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

    def test_flow_created_chat_refreshes_and_opens_dedicated_workspace(self) -> None:
        self.window.core.create_chat(title="Patch Review", description="Check patches", priority="Critical")

        self.window.flow_chat_view._handle_response(
            {"response": "Created.", "created_chat": {"chat_id": "created"}}
        )

        self.assertEqual("created", self.window.core.get_current_chat_id())
        self.assertEqual("Patch Review", self.window.chat_selector.currentText())
        self.assertTrue(self.window.module_window_manager.is_visible("chats"))

    def test_flow_approval_dialog_calls_core_only_after_mocked_approval(self) -> None:
        core = self.window.core
        core.approved_actions = []
        core.declined_actions = []
        core.approve_pending_action = lambda action_id: core.approved_actions.append(action_id) or SimpleNamespace()
        core.decline_pending_action = lambda action_id: core.declined_actions.append(action_id)
        request = {
            "action_id": "action-1",
            "kind": "habit_tracker",
            "display_fields": {"kind": "one_time", "title": "Buy groceries", "date": "2026-08-07"},
        }

        with patch("amadeus_gui.flow_chat_view.ActionApprovalDialog") as dialog_type:
            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
            self.window.flow_chat_view._handle_response({"response": "", "approval_request": request})

        dialog_type.assert_called_once()
        self.assertEqual(["action-1"], core.approved_actions)
        self.assertEqual([], core.declined_actions)
        self.assertNotIn("Approval required", self.window.flow_chat_view.flow_history.toPlainText())

    def test_dedicated_chat_approval_dialog_declines_without_owner_action(self) -> None:
        core = self.window.core
        core.approved_actions = []
        core.declined_actions = []
        core.approve_pending_action = lambda action_id: core.approved_actions.append(action_id)
        core.decline_pending_action = lambda action_id: core.declined_actions.append(action_id)
        request = {"action_id": "action-2", "kind": "memory", "display_fields": {"request": "Remember"}}

        with patch("amadeus_gui.main.main_window.ActionApprovalDialog") as dialog_type:
            dialog_type.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.window._handle_response({"response": "", "approval_request": request})

        dialog_type.assert_called_once()
        self.assertEqual([], core.approved_actions)
        self.assertEqual(["action-2"], core.declined_actions)

    def test_failed_flow_request_reenables_input_and_send_controls(self) -> None:
        core = FailingFlowCore()
        window = AmadeusMainWindow(core)
        self.addCleanup(core.cleanup)
        self.addCleanup(close_test_window, window)
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
        chats_window = self.window.module_window_manager.get_window("chats")
        self.assertIs(self.window.dedicated_chat_view, chats_window.centralWidget())
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

    def test_flow_annotation_popup_stages_commands_and_keeps_enter_send_when_closed(self) -> None:
        flow_view = self.window.flow_chat_view
        flow_view.message_input.setPlainText("/")
        self.assertFalse(flow_view.annotation_list.isHidden())
        flow_view._apply_selected_annotation()
        self.assertEqual("/create", flow_view.message_input.toPlainText())
        flow_view._apply_selected_annotation()
        self.assertEqual("/create-sheet ", flow_view.message_input.toPlainText())
        self.assertFalse(flow_view.annotation_list.isVisible())

        flow_view.message_input.setPlainText("[memory]")
        self.assertFalse(flow_view.annotation_list.isHidden())
        QTest.keyClick(flow_view.message_input, Qt.Key.Key_Escape)
        self.assertTrue(flow_view.annotation_list.isHidden())

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
