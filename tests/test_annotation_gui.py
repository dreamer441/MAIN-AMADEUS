"""Practical keyboard tests for the annotation suggestion input."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QThread, Qt
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from amadeus_gui.main.main_window import AmadeusMainWindow, ChatResponseWorker, MessageInput
from amadeus_gui.side import RightPanelWidget


class MessageInputSuggestionKeyTests(unittest.TestCase):
    """Verify suggestion keys are consumed only when a list is visible."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.visible = True
        self.moves: list[int] = []
        self.applied = 0
        self.hidden = 0
        self.sent = 0
        self.input = MessageInput()
        self.input.configure_suggestion_keys(
            lambda: self.visible,
            self.moves.append,
            self._apply,
            self._hide,
        )
        self.input.send_requested.connect(self._send)

    def _apply(self) -> None:
        self.applied += 1

    def _hide(self) -> None:
        self.hidden += 1

    def _send(self) -> None:
        self.sent += 1

    def test_visible_suggestions_handle_navigation_insertion_and_escape(self) -> None:
        QTest.keyClick(self.input, Qt.Key.Key_Down)
        QTest.keyClick(self.input, Qt.Key.Key_Up)
        QTest.keyClick(self.input, Qt.Key.Key_Tab)
        QTest.keyClick(self.input, Qt.Key.Key_Escape)

        self.assertEqual([1, -1], self.moves)
        self.assertEqual(1, self.applied)
        self.assertEqual(1, self.hidden)
        self.assertEqual(0, self.sent)

    def test_closed_suggestions_preserve_enter_send_behavior(self) -> None:
        self.visible = False

        QTest.keyClick(self.input, Qt.Key.Key_Return)

        self.assertEqual(1, self.sent)
        self.assertEqual(0, self.applied)


class CodeViewerLineNumberTests(unittest.TestCase):
    """Verify Code Viewer preserves source text while exposing source line numbers."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_displayed_code_has_one_based_line_labels(self) -> None:
        panel = RightPanelWidget("Ready")

        self.assertEqual("1: first\n2: \n3: third", panel._line_labelled_code("first\n\nthird\n"))


class ProcessMonitorLiveEventTests(unittest.TestCase):
    """Verify normal chat lifecycle rows reach the GUI before its final payload."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_worker_forwards_events_before_finished(self) -> None:
        order: list[str] = []

        class Core:
            def handle_user_message(self, _message: str, event_listener=None) -> dict[str, str]:
                event_listener({"sequence": 1, "title": "Request Received", "summary": "Message received."})
                return {"response": "ok"}

        worker = ChatResponseWorker(Core(), "hello")
        received: list[dict[str, object]] = []
        worker.process_event.connect(lambda event: (received.append(event), order.append("event")))
        worker.finished.connect(lambda _result: order.append("finished"))

        worker.run()

        self.assertEqual("Request Received", received[0]["title"])
        self.assertEqual(["event", "finished"], order)

    def test_threaded_worker_delivers_live_event_before_final_payload_reconciliation(self) -> None:
        final_events = [
            {"sequence": 1, "title": "Request Received", "summary": "Message received."},
            {"sequence": 2, "title": "Response Returned", "summary": "Response returned to GUI."},
        ]
        order: list[str] = []

        class Core(FakeCommentCore):
            def handle_user_message(self, _message: str, event_listener=None) -> dict[str, object]:
                event_listener(final_events[0])
                return {"response": "ok", "trace_events": final_events}

        window = AmadeusMainWindow(Core())
        worker = ChatResponseWorker(window.core, "hello")
        thread = QThread()
        worker.moveToThread(thread)

        def receive_event(event: object) -> None:
            order.append("event")
            window._handle_process_event(event)

        def receive_finished(result: object) -> None:
            order.append("finished")
            window._handle_response(result)

        thread.started.connect(worker.run)
        worker.process_event.connect(receive_event)
        worker.finished.connect(receive_finished)
        worker.finished.connect(thread.quit)
        thread_finished = QSignalSpy(thread.finished)
        thread.start()

        self.assertTrue(thread_finished.wait(1000))

        self.assertEqual(["event", "finished"], order)
        self.assertEqual(final_events, window._latest_trace_events)
        self.assertIn("Response Returned", window.right_panel.process_monitor.toPlainText())
        window.close()

    def test_panel_renders_live_event_list(self) -> None:
        panel = RightPanelWidget("Ready")

        panel.render_trace_events([{"sequence": 1, "title": "Context Ready", "summary": "Selected context types: memory."}])

        self.assertIn("Context Ready", panel.process_monitor.toPlainText())


class MaterialsPanelTests(unittest.TestCase):
    """Verify exported chats have their own display-only controls and details."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_export_rows_disable_managed_file_actions_and_show_clean_details(self) -> None:
        panel = RightPanelWidget("Ready")

        panel.render_materials_payload({
            "type": "materials",
            "title": "AMADEUS Materials",
            "content": "",
            "metadata": {
                "material_count": 1,
                "materials": [{
                    "id": "export:export_chat_1",
                    "name": "Saved Chat",
                    "type": "chat_export",
                    "display_date": "13 July 2026",
                    "display_range": "Messages 4-18",
                    "metadata": {"txt_path": "data/exports/export_chat_1/Saved_Chat.txt"},
                }],
                "selected_material_id": "export:export_chat_1",
            },
        })

        self.assertEqual("Copy Path", panel.material_copy_button.text())
        self.assertEqual("Delete", panel.material_remove_button.text())
        self.assertEqual("Saved Chat", panel.materials_selector.itemText(1))
        self.assertFalse(panel.material_preview_button.isEnabled())
        self.assertFalse(panel.material_ask_button.isEnabled())
        self.assertTrue(panel.material_open_button.isEnabled())
        self.assertTrue(panel.material_use_button.isEnabled())
        self.assertEqual("13 July 2026\nMessages 4-18", panel.materials_details.text())


class CommentsPanelTests(unittest.TestCase):
    """Verify the Comments tab exposes actions for the selected comment."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_comments_panel_exposes_selected_comment_actions(self) -> None:
        panel = RightPanelWidget("Ready")

        panel.render_comments_payload({
            "type": "comments",
            "title": "AMADEUS Comments",
            "content": "Comment(12) - Review.",
            "metadata": {
                "comment_count": 1,
                "comments": [{
                    "comment_id": "comment_1",
                    "comment": "Review.",
                    "message_number": 12,
                    "comment_type": "selection",
                }],
            },
        })

        self.assertEqual("comment_1", panel.comments_selector.currentData())
        self.assertTrue(panel.comment_jump_button.isEnabled())

    def test_comment_actions_emit_only_for_valid_selected_rows(self) -> None:
        panel = RightPanelWidget("Ready")
        edits: list[str] = []
        deletes: list[str] = []
        jumps: list[int] = []
        panel.comment_edit_requested.connect(edits.append)
        panel.comment_delete_requested.connect(deletes.append)
        panel.comment_jump_requested.connect(jumps.append)
        panel.render_comments_payload({
            "type": "comments",
            "title": "AMADEUS Comments",
            "content": "",
            "metadata": {
                "comment_count": 2,
                "comments": [
                    {"comment_id": "comment_1", "comment": "General.", "comment_type": "general"},
                    {"comment_id": "comment_2", "comment": "Review.", "message_number": 12, "comment_type": "selection"},
                ],
            },
        })

        panel.comment_edit_button.click()
        panel.comment_delete_button.click()
        self.assertEqual(["comment_1"], edits)
        self.assertEqual(["comment_1"], deletes)
        self.assertFalse(panel.comment_jump_button.isEnabled())

        panel.comments_selector.setCurrentIndex(1)
        panel.comment_jump_button.click()
        self.assertEqual([12], jumps)

    def test_unknown_selection_uses_selection_label_details_and_no_jump(self) -> None:
        panel = RightPanelWidget("Ready")
        panel.render_comments_payload({
            "type": "comments",
            "title": "AMADEUS Comments",
            "content": "Comment(?) - Review.",
            "metadata": {
                "comment_count": 1,
                "comments": [{
                    "comment_id": "comment_1",
                    "comment": "Review.",
                    "comment_type": "selection",
                    "selected_text": "A selected fragment",
                    "message_number": None,
                }],
            },
        })

        self.assertEqual("Comment(?)", panel.comments_selector.currentText())
        self.assertIn("Target: Selected text (message unknown)", panel.comments_viewer.toPlainText())
        self.assertIn("Type: Selection", panel.comments_viewer.toPlainText())
        self.assertFalse(panel.comment_jump_button.isEnabled())


class FakeCommentCore:
    """Small Core substitute that records MainWindow comment delegation."""

    def __init__(self) -> None:
        self.add_calls: list[tuple[str, str]] = []
        self.update_calls: list[tuple[str, str]] = []
        self.delete_calls: list[str] = []
        self.comments = [{
            "comment_id": "comment_1",
            "comment": "Review this.",
            "message_number": 12,
            "comment_type": "selection",
        }]

    def list_chats(self) -> list[object]:
        return []

    def get_current_chat_id(self) -> str:
        return "chat_1"

    def get_current_chat_metadata(self) -> SimpleNamespace:
        return SimpleNamespace(title="Test Chat", description="", summary="")

    def load_chat_history(self) -> list[object]:
        return []

    def get_project_tree(self, _relative_path: str) -> dict:
        return {"path": "", "folders": [], "files": []}

    def get_comments_panel_payload(self) -> dict:
        return {
            "type": "comments",
            "title": "AMADEUS Comments",
            "content": "",
            "metadata": {"comment_count": len(self.comments), "comments": self.comments},
        }

    def add_comment(self, comment: str, selected_text: str) -> SimpleNamespace:
        self.add_calls.append((comment, selected_text))
        return SimpleNamespace(comment_id="comment_2")

    def update_comment(self, comment_id: str, comment: str) -> None:
        self.update_calls.append((comment_id, comment))

    def delete_comment(self, comment_id: str) -> None:
        self.delete_calls.append(comment_id)


class MainWindowCommentActionTests(unittest.TestCase):
    """Verify Comments controls delegate to Core through the real window wiring."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.core = FakeCommentCore()
        self.window = AmadeusMainWindow(self.core)

    def tearDown(self) -> None:
        self.window.close()

    def test_add_comment_without_selection_delegates_an_empty_selection(self) -> None:
        with patch("amadeus_gui.main.main_window.QInputDialog.getMultiLineText", return_value=("General note", True)) as dialog:
            self.window.add_comment_button.click()

        self.assertEqual([("General note", "")], self.core.add_calls)
        self.assertEqual("General comment for this chat:", dialog.call_args.args[2])

    def test_edit_selected_comment_delegates_and_keeps_comments_tab_active(self) -> None:
        self.window.right_panel.setCurrentIndex(self.window.right_panel.PROCESS_TAB_INDEX)
        with patch("amadeus_gui.main.main_window.QInputDialog.getMultiLineText", return_value=("Updated note", True)):
            self.window.right_panel.comment_edit_button.click()

        self.assertEqual([("comment_1", "Updated note")], self.core.update_calls)
        self.assertEqual(self.window.right_panel.COMMENTS_TAB_INDEX, self.window.right_panel.currentIndex())

    def test_delete_selected_comment_confirms_then_delegates_and_refreshes(self) -> None:
        self.window.right_panel.setCurrentIndex(self.window.right_panel.PROCESS_TAB_INDEX)
        with patch("amadeus_gui.main.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.window.right_panel.comment_delete_button.click()

        self.assertEqual(["comment_1"], self.core.delete_calls)
        self.assertEqual(self.window.right_panel.COMMENTS_TAB_INDEX, self.window.right_panel.currentIndex())

    def test_jump_from_comment_finds_visible_message_and_reports_missing_messages(self) -> None:
        self.window._append_message("User", "Visible message", message_number=12)

        self.window.right_panel.comment_jump_button.click()
        self.assertEqual("Jumped to message 12.", self.window.status_label.text())

        self.window._jump_to_message(99)
        self.assertEqual("Message 99 is not visible in this chat.", self.window.status_label.text())

    def test_jump_ignores_message_number_text_inside_earlier_content(self) -> None:
        self.window._append_message("User", "This content misleadingly includes [12] before its header.", message_number=1)
        self.window._append_message("AMADEUS", "The actual target.", message_number=12)

        self.window._jump_to_message(12)

        self.assertEqual("Jumped to message 12.", self.window.status_label.text())
        self.assertTrue(self.window.chat_history.textCursor().block().text().startswith("[12] "))


if __name__ == "__main__":
    unittest.main()
