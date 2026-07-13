"""Practical keyboard tests for the annotation suggestion input."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from amadeus_gui.main.main_window import MessageInput


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


if __name__ == "__main__":
    unittest.main()
