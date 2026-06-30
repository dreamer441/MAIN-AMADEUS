from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
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

    finished = pyqtSignal(object)

    def __init__(self, core: AmadeusCore, message: str) -> None:
        super().__init__()
        self.core = core
        self.message = message

    def run(self) -> None:
        """Call Core and emit a response payload that the GUI can display safely."""
        try:
            result = self.core.handle_user_message(self.message)
            if isinstance(result, str):
                # Backward safety if Core temporarily returns the older string shape.
                result = {"response": result, "trace": "Process Monitor did not receive trace data."}
        except Exception as error:
            result = {
                "response": f"AMADEUS error: {error}",
                "trace": f"[Error]\nGUI worker caught an error while calling Core: {error}",
                "trace_detailed": f"[Error]\nGUI worker caught an error while calling Core: {error}",
                "trace_events": [],
            }

        self.finished.emit(result)


class AmadeusMainWindow(QMainWindow):
    """Main desktop window for the first AMADEUS feedback loop."""

    def __init__(self, core: AmadeusCore) -> None:
        super().__init__()
        self.core = core
        self._active_threads: list[QThread] = []
        self._active_workers: list[ChatResponseWorker] = []
        self._latest_trace_text = "Process Monitor will show the latest message trace here."
        self._latest_trace_detailed = self._latest_trace_text
        self._latest_trace_events: list[dict[str, str]] = []

        self.setWindowTitle("AMADEUS")
        self.resize(1100, 650)

        self._build_ui()
        self._load_existing_chat_history()

    def _build_ui(self) -> None:
        """Create chat controls and the Process Monitor panel."""
        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("AMADEUS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 8px;")

        main_row = QHBoxLayout()

        chat_column = QVBoxLayout()
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Conversation will appear here.")
        chat_column.addWidget(self.chat_history)

        monitor_column = QVBoxLayout()
        monitor_header = QHBoxLayout()
        monitor_title = QLabel("AMADEUS Process Monitor")
        monitor_title.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.trace_mode_selector = QComboBox()
        self.trace_mode_selector.addItems(["Compact", "Detailed"])
        self.trace_mode_selector.currentTextChanged.connect(self._render_latest_trace)

        monitor_header.addWidget(monitor_title)
        monitor_header.addStretch()
        monitor_header.addWidget(self.trace_mode_selector)

        self.process_monitor = QTextEdit()
        self.process_monitor.setReadOnly(True)
        self.process_monitor.setPlaceholderText("Execution trace for the latest message will appear here.")
        self.process_monitor.setPlainText(self._latest_trace_text)

        monitor_note = QLabel("Shows real execution events only, not hidden thoughts.")
        monitor_note.setStyleSheet("color: #666; padding: 2px;")

        monitor_column.addLayout(monitor_header)
        monitor_column.addWidget(self.process_monitor)
        monitor_column.addWidget(monitor_note)

        # The chat remains primary, while the monitor stays visible for debugging routing and modules.
        main_row.addLayout(chat_column, stretch=3)
        main_row.addLayout(monitor_column, stretch=2)

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
        layout.addLayout(main_row)
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
        self.process_monitor.setPlainText("[Input Sent]\nWaiting for Core trace...")

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

    def _handle_response(self, result: object) -> None:
        """Display the finished AMADEUS response and latest Process Monitor trace."""
        response = "AMADEUS returned an unreadable response."
        trace = "Process Monitor did not receive trace data."
        trace_detailed = trace
        trace_events: list[dict[str, str]] = []

        if isinstance(result, dict):
            raw_response = result.get("response")
            raw_trace = result.get("trace")
            raw_trace_detailed = result.get("trace_detailed")
            raw_trace_events = result.get("trace_events")

            if isinstance(raw_response, str):
                response = raw_response
            if isinstance(raw_trace, str):
                trace = raw_trace
            if isinstance(raw_trace_detailed, str):
                trace_detailed = raw_trace_detailed
            if isinstance(raw_trace_events, list):
                trace_events = [event for event in raw_trace_events if isinstance(event, dict)]
        elif isinstance(result, str):
            response = result

        self._latest_trace_text = trace
        self._latest_trace_detailed = trace_detailed
        self._latest_trace_events = trace_events

        self._append_message("AMADEUS", response)
        self._render_latest_trace()
        self._set_waiting_for_response(False)

    def _render_latest_trace(self) -> None:
        """Render the latest trace in the selected monitor mode."""
        mode = self.trace_mode_selector.currentText().lower() if hasattr(self, "trace_mode_selector") else "compact"
        if mode == "detailed":
            self.process_monitor.setPlainText(self._latest_trace_detailed)
        else:
            self.process_monitor.setPlainText(self._latest_trace_text)

    def _set_waiting_for_response(self, waiting: bool) -> None:
        """Toggle input controls while AMADEUS is generating a response."""
        self.message_input.setDisabled(waiting)
        self.send_button.setDisabled(waiting)
        self.status_label.setText("AMADEUS is thinking..." if waiting else "Ready")

    def _load_existing_chat_history(self) -> None:
        """Load saved chat messages through Core when the GUI starts."""
        if not hasattr(self.core, "load_chat_history"):
            return

        for saved_message in self.core.load_chat_history():
            self._append_message(saved_message.speaker, saved_message.message)

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
