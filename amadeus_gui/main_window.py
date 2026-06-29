from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from amadeus_core import AmadeusCore


class AmadeusMainWindow(QMainWindow):
    """Main desktop window for the first AMADEUS feedback loop."""

    def __init__(self, core: AmadeusCore) -> None:
        super().__init__()
        self.core = core

        self.setWindowTitle("AMADEUS")
        self.resize(800, 600)

        self._build_ui()

    def _build_ui(self) -> None:
        """Create the chat history, input box, and send button."""
        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("AMADEUS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 8px;")

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Conversation will appear here.")

        input_row = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message to AMADEUS...")
        self.message_input.returnPressed.connect(self.send_message)

        send_button = QPushButton("Send")
        send_button.clicked.connect(self.send_message)

        input_row.addWidget(self.message_input)
        input_row.addWidget(send_button)

        layout.addWidget(title)
        layout.addWidget(self.chat_history)
        layout.addLayout(input_row)

        self.setCentralWidget(root)

    def send_message(self) -> None:
        """Send user text through Core and display the response."""
        message = self.message_input.text().strip()
        if not message:
            return

        self.message_input.clear()
        self._append_message("User", message)

        # GUI talks to Core only. Core decides which module handles the message.
        response = self.core.handle_user_message(message)
        self._append_message("AMADEUS", response)

    def _append_message(self, speaker: str, message: str) -> None:
        """Append one speaker line to the chat history."""
        self.chat_history.append(f"{speaker}: {message}")
