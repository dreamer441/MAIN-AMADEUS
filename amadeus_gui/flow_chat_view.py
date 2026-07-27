"""Persistent Flow Chat home view that delegates all work to Core."""

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from amadeus_core import AmadeusCore


class FlowChatResponseWorker(QObject):
    """Run a Flow request outside the Qt GUI thread and forward safe events."""

    finished = pyqtSignal(object)
    process_event = pyqtSignal(object)

    def __init__(self, core: AmadeusCore, message: str) -> None:
        super().__init__()
        self.core = core
        self.message = message

    def run(self) -> None:
        """Call Core's Flow route and always return an answer-shaped payload."""
        try:
            result = self.core.handle_flow_message(self.message, event_listener=self.process_event.emit)
        except Exception:
            result = {
                "response": "AMADEUS could not complete that Flow request. Please try again.",
                "trace": "Flow request failed before a trace was available.",
                "trace_detailed": "Flow request failed before a trace was available.",
                "trace_events": [],
            }
        self.finished.emit(result)


class FlowChatView(QWidget):
    """The persistent, history-backed Flow conversation without chat-management controls."""

    def __init__(self, core: AmadeusCore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.core = core
        self._active_threads: list[QThread] = []
        self._active_workers: list[FlowChatResponseWorker] = []
        self._latest_trace_events: list[dict[str, object]] = []
        self._latest_trace_text = "Process Monitor will show the latest Flow trace here."
        self._latest_trace_detailed = self._latest_trace_text
        self._build_ui()
        self._load_history()

    def _build_ui(self) -> None:
        """Build the Flow transcript, input, and persistent Process Monitor."""
        layout = QVBoxLayout(self)
        title = QLabel("AMADEUS Flow")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        identity = QLabel("Your persistent AMADEUS Flow conversation")
        identity.setStyleSheet("color: #666;")

        content = QHBoxLayout()
        self.flow_history = QTextEdit()
        self.flow_history.setReadOnly(True)
        self.flow_history.setPlaceholderText("Your Flow conversation will appear here.")
        monitor_column = QVBoxLayout()
        monitor_title = QLabel("Process Monitor")
        monitor_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.process_monitor = QTextEdit()
        self.process_monitor.setReadOnly(True)
        self.process_monitor.setPlainText(self._latest_trace_text)
        self.process_monitor.setPlaceholderText("Execution events for the latest Flow request will appear here.")
        monitor_note = QLabel("Shows real execution events only, not hidden thoughts.")
        monitor_note.setStyleSheet("color: #666; padding: 2px;")
        monitor_column.addWidget(monitor_title)
        monitor_column.addWidget(self.process_monitor)
        monitor_column.addWidget(monitor_note)
        content.addWidget(self.flow_history, stretch=3)
        content.addLayout(monitor_column, stretch=2)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; padding: 4px;")
        input_row = QHBoxLayout()
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Type a message for Flow...")
        self.message_input.setMinimumHeight(70)
        self.message_input.setMaximumHeight(130)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_row.addWidget(self.message_input)
        input_row.addWidget(self.send_button)

        layout.addWidget(title)
        layout.addWidget(identity)
        layout.addLayout(content)
        layout.addWidget(self.status_label)
        layout.addLayout(input_row)

    def _load_history(self) -> None:
        """Render Flow history supplied by Core, never by direct storage access."""
        self.flow_history.clear()
        try:
            messages = self.core.load_flow_history()
        except Exception:
            self.status_label.setText("Flow history could not be loaded.")
            return
        for message in messages:
            self._append_message(getattr(message, "speaker", "AMADEUS"), getattr(message, "message", ""))

    def send_message(self) -> None:
        """Submit a non-empty Flow request through its background worker."""
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        self.message_input.clear()
        self._append_message("User", message)
        self._set_waiting(True)
        self._latest_trace_events = []
        self.process_monitor.setPlainText("AMADEUS is preparing the Flow request...")
        self._start_worker(message)

    def _start_worker(self, message: str) -> None:
        thread = QThread(self)
        worker = FlowChatResponseWorker(self.core, message)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.process_event.connect(self._handle_process_event)
        worker.finished.connect(self._handle_response)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._remove_worker(thread, worker))
        self._active_threads.append(thread)
        self._active_workers.append(worker)
        thread.start()

    def _handle_process_event(self, event: object) -> None:
        if isinstance(event, dict):
            self._latest_trace_events.append(event)
            self._render_process_events(self._latest_trace_events)

    def _handle_response(self, result: object) -> None:
        response = "AMADEUS returned an unreadable Flow response."
        trace = "Process Monitor did not receive Flow trace data."
        detailed_trace = trace
        events: list[dict[str, object]] = []
        if isinstance(result, dict):
            response = result.get("response") if isinstance(result.get("response"), str) else response
            trace = result.get("trace") if isinstance(result.get("trace"), str) else trace
            detailed_trace = result.get("trace_detailed") if isinstance(result.get("trace_detailed"), str) else trace
            raw_events = result.get("trace_events")
            if isinstance(raw_events, list):
                events = [event for event in raw_events if isinstance(event, dict)]
        self._latest_trace_text = trace
        self._latest_trace_detailed = detailed_trace
        self._latest_trace_events = events
        self._append_message("AMADEUS", response)
        if events:
            self._render_process_events(events)
        else:
            self.process_monitor.setPlainText(detailed_trace)
        self._set_waiting(False)

    def _render_process_events(self, events: list[dict[str, object]]) -> None:
        """Render Core's safe event rows without exposing other workspace controls."""
        rows = []
        for event in events:
            sequence = event.get("sequence")
            prefix = f"[{sequence}] " if isinstance(sequence, int) else ""
            title = event.get("title") if isinstance(event.get("title"), str) else "Process Event"
            summary = event.get("summary") if isinstance(event.get("summary"), str) else ""
            rows.append(f"{prefix}{title}\n{summary}".strip())
        self.process_monitor.setPlainText("\n\n".join(rows))

    def _set_waiting(self, waiting: bool) -> None:
        self.message_input.setDisabled(waiting)
        self.send_button.setDisabled(waiting)
        self.status_label.setText("AMADEUS is thinking..." if waiting else "Ready")

    def _append_message(self, speaker: str, message: str) -> None:
        self.flow_history.append(f"{speaker}: {message}")

    def _remove_worker(self, thread: QThread, worker: FlowChatResponseWorker) -> None:
        if thread in self._active_threads:
            self._active_threads.remove(thread)
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def has_active_workers(self) -> bool:
        """Tell the shell whether closing would interrupt a Flow request."""
        return bool(self._active_threads)
