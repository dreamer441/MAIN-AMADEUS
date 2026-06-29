from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
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


class ChatResponseWorker(QObject):
    """Runs a Core chat request away from the GUI thread."""

    finished = pyqtSignal(str)

    def __init__(self, core: AmadeusCore, message: str) -> None:
        super().__init__()
        self.core = core
        self.message = message

    def run(self) -> None:
        """Call Core and emit a response that the GUI can display safely."""
        try:
            response = self.core.handle_user_message(self.message)
        except Exception as error:
            response = f"AMADEUS error: {error}"

        self.finished.emit(response)


class AmadeusMainWindow(QMainWindow):
    """Main desktop window for the first AMADEUS feedback loop."""

    def __init__(self, core: AmadeusCore) -> None:
        super().__init__()
        self.core = core
        self._active_threads: list[QThread] = []
        self._active_workers: list[ChatResponseWorker] = []

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

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; padding: 4px;")

        input_row.addWidget(self.message_input)
        input_row.addWidget(self.send_button)

        layout.addWidget(title)
        layout.addWidget(self.chat_history)
        layout.addWidget(self.status_label)
        layout.addLayout(input_row)

        self.setCentralWidget(root)

    def send_message(self) -> None:
        """Send user text through Core and display the response."""
        message = self.message_input.text().strip()
        if not message:
            return

        self.message_input.clear()
        self._append_message("User", message)
        self._set_waiting_for_response(True)

        # GUI talks to Core only. Core decides which module handles the message.
        self._start_response_worker(message)

    def _start_response_worker(self, message: str) -> None:
        """Start a background worker so Ollama calls do not freeze the window."""
        thread = QThread(self)
        worker = ChatResponseWorker(self.core, message)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_response)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._remove_worker(thread, worker))

        self._active_threads.append(thread)
        self._active_workers.append(worker)
        thread.start()

    def _handle_response(self, response: str) -> None:
        """Display the finished AMADEUS response and re-enable input."""
        self._append_message("AMADEUS", response)
        self._set_waiting_for_response(False)

    def _set_waiting_for_response(self, waiting: bool) -> None:
        """Toggle input controls while AMADEUS is generating a response."""
        self.message_input.setDisabled(waiting)
        self.send_button.setDisabled(waiting)
        self.status_label.setText("AMADEUS is thinking..." if waiting else "Ready")

    def _remove_worker(self, thread: QThread, worker: ChatResponseWorker) -> None:
        """Forget a completed worker so Qt and Python can clean it up."""
        if thread in self._active_threads:
            self._active_threads.remove(thread)
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def closeEvent(self, event) -> None:
        """Prevent closing while a background chat request is still running."""
        if self._active_threads:
            self.status_label.setText("AMADEUS is still thinking. Wait for the response before closing.")
            event.ignore()
            return

        super().closeEvent(event)

    def _append_message(self, speaker: str, message: str) -> None:
        """Append one speaker line to the chat history."""
        self.chat_history.append(f"{speaker}: {message}")
