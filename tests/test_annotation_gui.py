"""Practical keyboard tests for the annotation suggestion input."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from amadeus_gui.main.main_window import MessageInput
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


if __name__ == "__main__":
    unittest.main()
