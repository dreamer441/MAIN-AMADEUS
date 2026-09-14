"""Persistent Flow Chat home view that delegates all work to Core."""

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QTextEdit, QVBoxLayout, QWidget

from amadeus_core import AmadeusCore
from amadeus_gui.approval_dialog import ActionApprovalDialog


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


class FlowMessageInput(QTextEdit):
    """Multiline Flow input that sends on Enter and keeps Shift+Enter for newlines."""

    send_requested = pyqtSignal()

    def configure_suggestion_keys(self, is_visible, move_selection, apply_selection, hide_suggestions) -> None:
        """Use the dedicated Chat popup key contract without coupling GUI views."""
        self._suggestions_visible = is_visible
        self._move_suggestion_selection = move_selection
        self._apply_suggestion_selection = apply_selection
        self._hide_suggestions = hide_suggestions

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt uses camelCase names.
        if hasattr(self, "_suggestions_visible") and self._suggestions_visible():
            if event.key() == Qt.Key.Key_Down:
                self._move_suggestion_selection(1)
                event.accept()
                return
            if event.key() == Qt.Key.Key_Up:
                self._move_suggestion_selection(-1)
                event.accept()
                return
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                self._apply_suggestion_selection()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Escape:
                self._hide_suggestions()
                event.accept()
                return
        is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        has_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if is_enter and not has_shift:
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class FlowChatView(QWidget):
    """The persistent, history-backed Flow conversation without chat-management controls."""

    chat_created = pyqtSignal(str)
    approval_completed = pyqtSignal(object)

    def __init__(self, core: AmadeusCore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.core = core
        self._active_threads: list[QThread] = []
        self._active_workers: list[FlowChatResponseWorker] = []
        self._latest_trace_events: list[dict[str, object]] = []
        self._latest_trace_text = "Process Monitor will show the latest Flow trace here."
        self._latest_trace_detailed = self._latest_trace_text
        self._applying_suggestion = False
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
        self.side_panel_toggle_button = QPushButton(">")
        self.side_panel_toggle_button.setAccessibleName("Toggle Flow side panel")
        self.side_panel_toggle_button.setFixedWidth(28)
        self.side_panel_toggle_button.clicked.connect(self._toggle_side_panel)

        self.flow_side_panel = QWidget()
        monitor_column = QVBoxLayout(self.flow_side_panel)
        monitor_header = QHBoxLayout()
        monitor_title = QLabel("Process Monitor")
        monitor_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.process_monitor = QTextEdit()
        self.process_monitor.setReadOnly(True)
        self.process_monitor.setPlainText(self._latest_trace_text)
        self.process_monitor.setPlaceholderText("Execution events for the latest Flow request will appear here.")
        monitor_note = QLabel("Shows real execution events only, not hidden thoughts.")
        monitor_note.setStyleSheet("color: #666; padding: 2px;")
        monitor_header.addWidget(monitor_title)
        monitor_header.addStretch()
        monitor_column.addLayout(monitor_header)
        monitor_column.addWidget(self.process_monitor)
        monitor_column.addWidget(monitor_note)
        content.addWidget(self.flow_history, stretch=3)
        content.addWidget(self.side_panel_toggle_button)
        content.addWidget(self.flow_side_panel, stretch=2)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; padding: 4px;")
        input_row = QHBoxLayout()
        self.message_input = FlowMessageInput()
        self.message_input.setPlaceholderText("Type a message for Flow... Enter = send, Shift+Enter = new line, / = annotations")
        self.message_input.setMinimumHeight(70)
        self.message_input.setMaximumHeight(130)
        self.message_input.send_requested.connect(self.send_message)
        self.message_input.textChanged.connect(self._update_annotation_suggestions)
        self.annotation_list = QListWidget()
        self.annotation_list.setMaximumHeight(130)
        self.annotation_list.hide()
        self.annotation_list.itemClicked.connect(self._apply_annotation_suggestion)
        self.message_input.configure_suggestion_keys(
            lambda: not self.annotation_list.isHidden(),
            self._move_annotation_suggestion,
            self._apply_selected_annotation,
            self.annotation_list.hide,
        )
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_row.addWidget(self.message_input)
        input_row.addWidget(self.send_button)

        layout.addWidget(title)
        layout.addWidget(identity)
        layout.addLayout(content)
        layout.addWidget(self.status_label)
        layout.addWidget(self.annotation_list)
        layout.addLayout(input_row)

    def _update_annotation_suggestions(self) -> None:
        """Populate Flow's shared annotation popup through the Core facade."""
        if self._applying_suggestion:
            return
        suggestions = self.core.get_flow_annotation_suggestions(self.message_input.toPlainText())
        self.annotation_list.clear()
        if not suggestions:
            self.annotation_list.hide()
            return
        for suggestion in suggestions:
            label = suggestion.get("label", "")
            detail = suggestion.get("detail", "")
            item = QListWidgetItem(f"{label} - {detail}" if detail else label)
            item.setData(Qt.ItemDataRole.UserRole, suggestion.get("insert_text", label))
            self.annotation_list.addItem(item)
        self.annotation_list.setCurrentRow(0)
        self.annotation_list.show()

    def _move_annotation_suggestion(self, direction: int) -> None:
        """Move popup selection while keeping the input cursor in place."""
        count = self.annotation_list.count()
        if count:
            self.annotation_list.setCurrentRow((max(self.annotation_list.currentRow(), 0) + direction) % count)

    def _apply_selected_annotation(self) -> None:
        """Insert the keyboard-selected Flow suggestion."""
        item = self.annotation_list.currentItem()
        if item is not None:
            self._apply_annotation_suggestion(item)

    def _apply_annotation_suggestion(self, item: QListWidgetItem) -> None:
        """Insert one Flow suggestion and show its next guided step."""
        insert_text = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(insert_text, str):
            return
        self._applying_suggestion = True
        try:
            self.message_input.setPlainText(insert_text)
            self.message_input.moveCursor(QTextCursor.MoveOperation.End)
        finally:
            self._applying_suggestion = False
        self._update_annotation_suggestions()
        self.message_input.setFocus()

    def _toggle_side_panel(self) -> None:
        """Hide or restore Flow's monitor without discarding its latest event state."""
        is_hidden = self.flow_side_panel.isHidden()
        self.flow_side_panel.setVisible(is_hidden)
        self.side_panel_toggle_button.setText(">" if is_hidden else "<")

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
        if response:
            self._append_message("AMADEUS", response)
        if events:
            self._render_process_events(events)
        else:
            self.process_monitor.setPlainText(detailed_trace)
        self._set_waiting(False)
        if isinstance(result, dict):
            created_chat = result.get("created_chat")
            chat_id = created_chat.get("chat_id") if isinstance(created_chat, dict) else None
            if isinstance(chat_id, str) and chat_id:
                self.chat_created.emit(chat_id)
            approval_request = result.get("approval_request")
            if isinstance(approval_request, dict):
                self._handle_approval_request(approval_request)

    def _handle_approval_request(self, approval_request: dict[str, object]) -> None:
        """Ask on the GUI thread before Core is allowed to consume the pending ID."""
        action_id = approval_request.get("action_id")
        if not isinstance(action_id, str) or not action_id:
            return
        dialog = ActionApprovalDialog(approval_request, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            try:
                self.core.decline_pending_action(action_id)
                self._append_message("AMADEUS", "Action declined. Nothing was created.")
            except Exception as error:
                self._append_message("AMADEUS", f"Could not decline action: {error}")
            return
        try:
            created = self.core.approve_pending_action(action_id)
            chat_id = getattr(created, "chat_id", "")
            if isinstance(chat_id, str) and chat_id:
                self.chat_created.emit(chat_id)
            self.approval_completed.emit(getattr(created, "created_ids", ()))
            self._append_message("AMADEUS", "Action approved and completed.")
        except Exception as error:
            self._append_message("AMADEUS", f"Could not complete approved action: {error}")

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
        """Append a transcript message with clear visual separation from the prior one."""
        if not self.flow_history.document().isEmpty():
            self.flow_history.append("")
            self.flow_history.append("")
        heading_format = QTextCharFormat()
        heading_format.setFontWeight(QFont.Weight.Bold)
        cursor = QTextCursor(self.flow_history.document().lastBlock())
        cursor.insertText(f"{speaker}: ", heading_format)
        body_format = QTextCharFormat()
        body_format.setFontWeight(QFont.Weight.Normal)
        cursor.insertText(message, body_format)

    def _remove_worker(self, thread: QThread, worker: FlowChatResponseWorker) -> None:
        if thread in self._active_threads:
            self._active_threads.remove(thread)
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def has_active_workers(self) -> bool:
        """Tell the shell whether closing would interrupt a Flow request."""
        return bool(self._active_threads)
