"""PyQt6 desktop GUI for AMADEUS.

The GUI is intentionally a surface layer. It displays chat text, accepts user
input, and delegates right-side workspace tabs to `RightPanelWidget`. Routing
decisions still belong to Core; panel payload/state concepts live in the
`side_panel` module.
"""

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from amadeus_core import AmadeusCore
from amadeus_gui.right_panel_widget import RightPanelWidget


class MessageInput(QTextEdit):
    """Multiline chat input with AMADEUS-style send behavior.

    Enter sends the message because that is fastest for chat. Shift+Enter inserts
    a new line so Dato can write longer prompts, annotations, or code snippets
    without needing a separate editor.
    """

    send_requested = pyqtSignal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt uses camelCase names.
        """Send on Enter, keep Shift+Enter as newline."""
        is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        has_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if is_enter and not has_shift:
            self.send_requested.emit()
            event.accept()
            return

        super().keyPressEvent(event)


class ChatResponseWorker(QObject):
    """Runs a Core chat request away from the GUI thread.

    Local LLM calls can take many seconds. If they run on the main Qt thread, the
    AMADEUS window freezes. This worker keeps the interface responsive while Core
    handles the request.
    """

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
            # Worker-level error handling protects the window from crashing if Core raises unexpectedly.
            result = {
                "response": f"AMADEUS error: {error}",
                "trace": f"[Error]\nGUI worker caught an error while calling Core: {error}",
                "trace_detailed": f"[Error]\nGUI worker caught an error while calling Core: {error}",
                "trace_events": [],
                "side_panel": None,
            }

        self.finished.emit(result)



class SideAskWorker(QObject):
    """Runs a Side Ask request without freezing the PyQt window."""

    finished = pyqtSignal(object)

    def __init__(self, core: AmadeusCore, question: str, selected_text: str) -> None:
        super().__init__()
        self.core = core
        self.question = question
        self.selected_text = selected_text

    def run(self) -> None:
        """Call Core's Side Ask route and emit the result payload."""
        try:
            result = self.core.handle_side_ask(self.question, selected_text=self.selected_text)
            if isinstance(result, str):
                result = {"response": result, "trace": "Side Ask did not receive trace data."}
        except Exception as error:
            result = {
                "response": f"AMADEUS Side Ask error: {error}",
                "trace": f"[Error]\nGUI worker caught a Side Ask error: {error}",
                "trace_detailed": f"[Error]\nGUI worker caught a Side Ask error: {error}",
                "trace_events": [],
                "side_panel": None,
            }
        self.finished.emit(result)


class NewChatDialog(QDialog):
    """Small creation dialog for chat workspace metadata.

    AMADEUS chat workspaces now start with a title and optional description. The
    description is active chat context and appears in the right-side Memory panel,
    but it is not the same as global memory or a generated chat summary.
    """

    def __init__(self, suggested_title: str = "New Chat", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create New Chat")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_input = QLineEdit()
        self.title_input.setText(suggested_title)
        self.title_input.selectAll()

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Optional: what this chat is mainly about. This becomes active context for this chat."
        )
        self.description_input.setMinimumHeight(90)
        self.description_input.setMaximumHeight(140)

        form.addRow("Title:", self.title_input)
        form.addRow("Description:", self.description_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def chat_title(self) -> str:
        """Return the title chosen by Dato, with a safe fallback."""
        return self.title_input.text().strip() or "New Chat"

    def chat_description(self) -> str:
        """Return the optional description chosen by Dato."""
        return self.description_input.toPlainText().strip()


class AmadeusMainWindow(QMainWindow):
    """Main desktop window for the first AMADEUS feedback loop."""

    def __init__(self, core: AmadeusCore) -> None:
        super().__init__()
        self.core = core

        # Active threads/workers are kept in lists so Python does not garbage-collect them mid-request.
        self._active_threads: list[QThread] = []
        self._active_workers: list[ChatResponseWorker] = []

        # The latest trace is cached in both modes so switching Compact/Detailed does not call Core again.
        self._latest_trace_text = "Process Monitor will show the latest message trace here."
        self._latest_trace_detailed = self._latest_trace_text
        self._latest_trace_events: list[dict[str, str]] = []

        # Suggestions are rebuilt on input changes. The flag prevents recursive updates when clicking one.
        self._applying_suggestion = False

        # The chat selector is populated from Core/Storage. This flag prevents the
        # population process itself from triggering an unwanted chat switch.
        self._refreshing_chat_selector = False

        # Visible message numbers are chat-local. They make conversations easier
        # to read now and give future `[current][number]` annotations a stable UI target.
        self._visible_message_count = 0

        self.setWindowTitle("AMADEUS")
        self.resize(1250, 720)

        self._build_ui()
        self._refresh_chat_selector()
        self._load_existing_chat_history()
        self._refresh_sheets_panel(switch_to_tab=False)
        self._refresh_materials_panel(switch_to_tab=False)
        self._refresh_comments_panel(switch_to_tab=False)

    def _build_ui(self) -> None:
        """Create chat controls, right-side tabs, annotation suggestions, and input."""
        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("AMADEUS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 8px;")

        main_row = QHBoxLayout()

        # Left side: normal conversation. Large code/file content should not be dumped here.
        chat_column = QVBoxLayout()
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Conversation will appear here.")
        chat_column.addWidget(self.chat_history)

        # Right side: a reusable workspace panel. Its PyQt tab rendering now lives in
        # `amadeus_gui.right_panel_widget`, while logical payload/state concepts live in
        # the `side_panel` module. This keeps MainWindow focused on whole-window coordination.
        self.right_panel = RightPanelWidget(initial_trace_text=self._latest_trace_text)
        self.right_panel.sheet_save_requested.connect(self._save_sheet_from_panel)
        self.right_panel.sheet_delete_requested.connect(self._delete_sheet_from_panel)
        self.right_panel.side_ask_requested.connect(self._start_side_ask)
        self.right_panel.side_ask_save_requested.connect(self._save_side_ask_to_chat)
        self.right_panel.side_ask_new_chat_requested.connect(self._create_chat_from_side_ask)

        main_row.addLayout(chat_column, stretch=3)
        main_row.addWidget(self.right_panel, stretch=2)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; padding: 4px;")

        # Suggestion box sits above the input like a small command palette.
        self.annotation_suggestion_box = QListWidget()
        self.annotation_suggestion_box.setMaximumHeight(130)
        self.annotation_suggestion_box.hide()
        self.annotation_suggestion_box.itemClicked.connect(self._apply_annotation_suggestion)

        input_row = QHBoxLayout()
        self.message_input = MessageInput()
        self.message_input.setPlaceholderText("Type a message to AMADEUS...  Enter = send, Shift+Enter = new line, / = annotations")
        self.message_input.setMinimumHeight(70)
        self.message_input.setMaximumHeight(130)
        self.message_input.send_requested.connect(self.send_message)
        self.message_input.textChanged.connect(self._update_annotation_suggestions)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)

        input_row.addWidget(self.message_input)
        input_row.addWidget(self.send_button)

        layout.addWidget(title)
        layout.addLayout(self._build_chat_control_row())
        layout.addLayout(main_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.annotation_suggestion_box)
        layout.addLayout(input_row)

        self.setCentralWidget(root)


    def _build_chat_control_row(self) -> QHBoxLayout:
        """Create the simple multi-chat controls above the conversation.

        This is intentionally not a full workspace system yet. It gives AMADEUS a
        safe first multi-chat foundation: select chat, create chat, delete chat.
        Per-chat history is handled by Storage, not by the GUI widgets.
        """
        controls = QHBoxLayout()

        label = QLabel("Chat:")
        self.chat_selector = QComboBox()
        self.chat_selector.setMinimumWidth(260)
        self.chat_selector.currentIndexChanged.connect(self._on_chat_selected)

        self.new_chat_button = QPushButton("New Chat")
        self.new_chat_button.clicked.connect(self._create_new_chat)

        self.delete_chat_button = QPushButton("Delete Chat")
        self.delete_chat_button.clicked.connect(self._delete_current_chat)

        self.add_comment_button = QPushButton("Add Comment")
        self.add_comment_button.clicked.connect(self._add_comment_from_selection)

        controls.addWidget(label)
        controls.addWidget(self.chat_selector)
        controls.addWidget(self.new_chat_button)
        controls.addWidget(self.delete_chat_button)
        controls.addWidget(self.add_comment_button)
        controls.addStretch()
        return controls

    def send_message(self) -> None:
        """Send user text through Core and display the response."""
        message = self.message_input.toPlainText().strip()
        if not message:
            return

        self.message_input.clear()
        self.annotation_suggestion_box.hide()
        self._append_message("User", message)
        self._set_waiting_for_response(True)

        # This temporary monitor text is a GUI event, not Core trace. The real trace replaces it later.
        self.right_panel.show_waiting_trace()

        # GUI talks to Core only. Core decides which module handles the message.
        self._start_response_worker(message)

    def _start_response_worker(self, message: str) -> None:
        """Start a background worker so Ollama calls do not freeze the window."""
        thread = QThread(self)
        worker = ChatResponseWorker(self.core, message)
        worker.moveToThread(thread)

        # Qt signal wiring: thread starts worker, worker returns result, then thread shuts down cleanly.
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_response)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._remove_worker(thread, worker))

        self._active_threads.append(thread)
        self._active_workers.append(worker)
        thread.start()


    def _start_side_ask(self, question: str, manual_context: str = "") -> None:
        """Start a Side Ask request using selected and/or manually pasted context.

        Side Ask now has a dedicated context box in addition to text selection.
        MainWindow combines both visible sources into one temporary context block
        before sending it to Core. This is still read-only/context-only: nothing is
        persisted unless Dato clicks Save to Chat or New Chat.
        """
        clean_question = question.strip()
        if not clean_question:
            self.status_label.setText("Side Ask needs a question.")
            return

        selected_text = self._selected_chat_text()
        manual_context = manual_context.strip()
        combined_context_parts = []
        if selected_text:
            combined_context_parts.append("Selected chat text:\n" + selected_text)
        if manual_context:
            combined_context_parts.append("Manual context box:\n" + manual_context)

        self._latest_side_ask_question = clean_question
        self._latest_side_ask_selected_text = "\n\n---\n\n".join(combined_context_parts)
        self._latest_side_ask_answer = ""
        self.right_panel.show_side_ask_waiting()
        self.right_panel.set_side_ask_busy(True)
        self.status_label.setText("AMADEUS is answering Side Ask...")

        thread = QThread(self)
        worker = SideAskWorker(self.core, clean_question, self._latest_side_ask_selected_text)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_side_ask_response)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._remove_worker(thread, worker))

        self._active_threads.append(thread)
        self._active_workers.append(worker)
        thread.start()

    def _handle_side_ask_response(self, result: object) -> None:
        """Display a Side Ask answer in the right panel instead of main chat."""
        answer = "AMADEUS returned an unreadable Side Ask response."
        trace = "Side Ask did not receive trace data."
        trace_detailed = trace
        trace_events: list[dict[str, str]] = []

        if isinstance(result, dict):
            raw_answer = result.get("response")
            raw_trace = result.get("trace")
            raw_trace_detailed = result.get("trace_detailed")
            raw_trace_events = result.get("trace_events")
            if isinstance(raw_answer, str):
                answer = raw_answer
            if isinstance(raw_trace, str):
                trace = raw_trace
            if isinstance(raw_trace_detailed, str):
                trace_detailed = raw_trace_detailed
            if isinstance(raw_trace_events, list):
                trace_events = [event for event in raw_trace_events if isinstance(event, dict)]

        self._latest_trace_text = trace
        self._latest_trace_detailed = trace_detailed
        self._latest_trace_events = trace_events
        self._latest_side_ask_answer = answer
        self.right_panel.render_side_ask_answer(
            self._latest_side_ask_question,
            answer,
            self._latest_side_ask_selected_text,
        )
        self._render_latest_trace()
        self.right_panel.set_side_ask_busy(False)
        self.status_label.setText("Side Ask ready.")

    def _handle_response(self, result: object) -> None:
        """Display the finished AMADEUS response, trace, and optional side-panel result."""
        response = "AMADEUS returned an unreadable response."
        trace = "Process Monitor did not receive trace data."
        trace_detailed = trace
        trace_events: list[dict[str, str]] = []
        side_panel: object | None = None

        if isinstance(result, dict):
            # Core returns a dictionary so GUI can show chat text, trace data, and side panels separately.
            raw_response = result.get("response")
            raw_trace = result.get("trace")
            raw_trace_detailed = result.get("trace_detailed")
            raw_trace_events = result.get("trace_events")
            side_panel = result.get("side_panel")

            if isinstance(raw_response, str):
                response = raw_response
            if isinstance(raw_trace, str):
                trace = raw_trace
            if isinstance(raw_trace_detailed, str):
                trace_detailed = raw_trace_detailed
            if isinstance(raw_trace_events, list):
                trace_events = [event for event in raw_trace_events if isinstance(event, dict)]
        elif isinstance(result, str):
            # Backward compatibility with the earlier Core API.
            response = result

        self._latest_trace_text = trace
        self._latest_trace_detailed = trace_detailed
        self._latest_trace_events = trace_events

        self._append_message("AMADEUS", response)
        self._render_latest_trace()
        self._render_side_panel(side_panel)
        self._set_waiting_for_response(False)

    def _render_side_panel(self, side_panel: object | None) -> None:
        """Delegate right-panel payload rendering to the reusable panel widget."""
        self.right_panel.render_side_panel_payload(side_panel, chat_context_text=self._current_chat_context_text())

    def _render_latest_trace(self) -> None:
        """Render the latest trace through the right-panel widget."""
        self.right_panel.render_trace(self._latest_trace_text, self._latest_trace_detailed)

    def _update_annotation_suggestions(self) -> None:
        """Refresh the slash/annotation suggestion box from Core."""
        if self._applying_suggestion or not hasattr(self.core, "get_annotation_suggestions"):
            return

        suggestions = self.core.get_annotation_suggestions(self.message_input.toPlainText())
        self.annotation_suggestion_box.clear()
        if not suggestions:
            self.annotation_suggestion_box.hide()
            return

        for suggestion in suggestions:
            label = suggestion.get("label", "")
            detail = suggestion.get("detail", "")
            insert_text = suggestion.get("insert_text", label)
            display_text = f"{label} — {detail}" if detail else label
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, insert_text)
            self.annotation_suggestion_box.addItem(item)

        self.annotation_suggestion_box.show()

    def _apply_annotation_suggestion(self, item: QListWidgetItem) -> None:
        """Insert a selected annotation suggestion into the input box."""
        insert_text = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(insert_text, str):
            return

        self._applying_suggestion = True
        try:
            self.message_input.setPlainText(insert_text)
            self.message_input.moveCursor(QTextCursor.MoveOperation.End)
        finally:
            self._applying_suggestion = False

        # Rebuild suggestions after insertion so `[file] -> modules -> files` becomes a guided path.
        self._update_annotation_suggestions()
        self.message_input.setFocus()


    def _refresh_chat_selector(self) -> None:
        """Reload chat metadata into the top selector from Core.

        The selector display is rebuilt after create/delete/switch events because
        Storage may update ordering by recent activity. The active chat id is
        restored after the rebuild so the visible UI matches Core state.
        """
        if not hasattr(self.core, "list_chats") or not hasattr(self.core, "get_current_chat_id"):
            return

        self._refreshing_chat_selector = True
        try:
            self.chat_selector.clear()
            current_chat_id = self.core.get_current_chat_id()
            selected_index = 0
            for index, chat in enumerate(self.core.list_chats()):
                label = getattr(chat, "title", "Untitled Chat")
                chat_id = getattr(chat, "chat_id", "")
                self.chat_selector.addItem(label, chat_id)
                if chat_id == current_chat_id:
                    selected_index = index

            if self.chat_selector.count() > 0:
                self.chat_selector.setCurrentIndex(selected_index)
        finally:
            self._refreshing_chat_selector = False

    def _on_chat_selected(self, index: int) -> None:
        """Switch AMADEUS to the selected chat and reload visible history."""
        if self._refreshing_chat_selector or index < 0 or not hasattr(self.core, "switch_chat"):
            return

        chat_id = self.chat_selector.itemData(index)
        if not isinstance(chat_id, str) or not chat_id:
            return

        try:
            self.core.switch_chat(chat_id)
            self._load_existing_chat_history()
            self._reset_right_panel_for_chat_switch()
            self._refresh_sheets_panel(switch_to_tab=False)
            self._refresh_materials_panel(switch_to_tab=False)
            self._refresh_comments_panel(switch_to_tab=False)
            self.status_label.setText(f"Switched to {self.chat_selector.currentText()}")
        except Exception as error:
            self.status_label.setText(f"Could not switch chat: {error}")

    def _create_new_chat(self) -> None:
        """Create a new chat workspace with title and optional description."""
        if not hasattr(self.core, "create_chat"):
            return

        dialog = NewChatDialog(suggested_title=f"New Chat {self.chat_selector.count() + 1}", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.core.create_chat(title=dialog.chat_title(), description=dialog.chat_description())
            self._refresh_chat_selector()
            self._load_existing_chat_history()
            self._reset_right_panel_for_chat_switch()
            self._refresh_sheets_panel(switch_to_tab=False)
            self._refresh_materials_panel(switch_to_tab=False)
            self._refresh_comments_panel(switch_to_tab=False)
            self.status_label.setText("Created new chat workspace.")
        except Exception as error:
            self.status_label.setText(f"Could not create chat: {error}")

    def _delete_current_chat(self) -> None:
        """Delete the currently selected chat after a confirmation prompt."""
        if not hasattr(self.core, "delete_chat"):
            return

        chat_title = self.chat_selector.currentText() or "this chat"
        confirmation = QMessageBox.question(
            self,
            "Delete Chat",
            f"Delete '{chat_title}'? This removes its local chat history file.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        chat_id = self.chat_selector.currentData()
        try:
            self.core.delete_chat(chat_id if isinstance(chat_id, str) else None)
            self._refresh_chat_selector()
            self._load_existing_chat_history()
            self._reset_right_panel_for_chat_switch()
            self._refresh_sheets_panel(switch_to_tab=False)
            self._refresh_materials_panel(switch_to_tab=False)
            self._refresh_comments_panel(switch_to_tab=False)
            self.status_label.setText("Deleted chat.")
        except Exception as error:
            self.status_label.setText(f"Could not delete chat: {error}")


    def _refresh_sheets_panel(self, switch_to_tab: bool = False, selected_sheet_id: str | None = None) -> None:
        """Reload visible sheets into the right-side Sheets tab.

        The panel is refreshed after chat switches and sheet saves/deletes because
        chat-scoped sheets depend on the active chat id. This keeps the GUI honest:
        the sheet list always reflects what the active chat can see.
        """
        if not hasattr(self.core, "get_sheets_panel_payload"):
            return
        try:
            payload = self.core.get_sheets_panel_payload(selected_sheet_id=selected_sheet_id)
            self.right_panel.render_sheets_payload(payload, switch_to_tab=switch_to_tab)
        except Exception as error:
            self.status_label.setText(f"Could not refresh sheets: {error}")

    def _refresh_materials_panel(self, switch_to_tab: bool = False) -> None:
        """Load the current Materials panel payload.

        Materials are only a foundation in this patch, but the tab exists now so
        future chat exports can appear there without another right-panel redesign.
        """
        if not hasattr(self.core, "get_materials_panel_payload"):
            return
        try:
            payload = self.core.get_materials_panel_payload()
            self.right_panel.render_materials_payload(payload, switch_to_tab=switch_to_tab)
        except Exception as error:
            self.status_label.setText(f"Could not refresh materials: {error}")

    def _save_sheet_from_panel(self, payload: object) -> None:
        """Create or update a sheet using data emitted by the Sheets panel."""
        if not isinstance(payload, dict):
            return
        try:
            sheet_id = str(payload.get("sheet_id") or "").strip()
            title = str(payload.get("title") or "New Sheet").strip() or "New Sheet"
            description = str(payload.get("description") or "")
            content = str(payload.get("content") or "")
            scope = str(payload.get("scope") or "chat").strip().lower()
            if scope not in {"chat", "global"}:
                scope = "chat"

            if sheet_id:
                saved_sheet = self.core.update_sheet(
                    sheet_id=sheet_id,
                    title=title,
                    description=description,
                    content=content,
                    scope=scope,
                )
                self.status_label.setText(f"Saved sheet: {getattr(saved_sheet, 'title', title)}")
            else:
                saved_sheet = self.core.create_sheet(
                    title=title,
                    description=description,
                    content=content,
                    scope=scope,
                )
                self.status_label.setText(f"Created sheet: {getattr(saved_sheet, 'title', title)}")

            selected_id = getattr(saved_sheet, "sheet_id", None)
            self._refresh_sheets_panel(switch_to_tab=True, selected_sheet_id=selected_id)
        except Exception as error:
            self.status_label.setText(f"Could not save sheet: {error}")

    def _delete_sheet_from_panel(self, sheet_id: str) -> None:
        """Delete the selected sheet and refresh the Sheets tab."""
        if not sheet_id:
            return
        try:
            self.core.delete_sheet(sheet_id)
            self._refresh_sheets_panel(switch_to_tab=True)
            self.status_label.setText("Deleted sheet.")
        except Exception as error:
            self.status_label.setText(f"Could not delete sheet: {error}")


    def _save_side_ask_to_chat(self) -> None:
        """Persist the latest Side Ask Q&A into the active chat when Dato asks."""
        question = getattr(self, "_latest_side_ask_question", self.right_panel.current_side_ask_question())
        answer = getattr(self, "_latest_side_ask_answer", self.right_panel.current_side_ask_answer())
        selected = getattr(self, "_latest_side_ask_selected_text", "")
        if not question.strip() or not answer.strip():
            self.status_label.setText("No Side Ask answer to save yet.")
            return
        try:
            saved_messages = self.core.save_side_ask_to_chat(question, answer, selected)
            for saved_message in saved_messages:
                self._append_message(saved_message.speaker, saved_message.message, message_number=saved_message.message_number)
            self.status_label.setText("Saved Side Ask Q&A to chat.")
        except Exception as error:
            self.status_label.setText(f"Could not save Side Ask: {error}")

    def _create_chat_from_side_ask(self) -> None:
        """Create a new chat and insert the latest Side Ask Q&A as its first exchange."""
        question = getattr(self, "_latest_side_ask_question", self.right_panel.current_side_ask_question())
        answer = getattr(self, "_latest_side_ask_answer", self.right_panel.current_side_ask_answer())
        selected = getattr(self, "_latest_side_ask_selected_text", "")
        if not question.strip() or not answer.strip():
            self.status_label.setText("No Side Ask answer to move into a new chat yet.")
            return

        suggested_title = question.strip().replace("\n", " ")[:48] or "Side Ask Chat"
        dialog = NewChatDialog(suggested_title=suggested_title, parent=self)
        dialog.description_input.setPlainText("Created from a Side Ask Q&A.")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.core.create_chat(title=dialog.chat_title(), description=dialog.chat_description())
            self.core.save_side_ask_to_chat(question, answer, selected)
            self._refresh_chat_selector()
            self._load_existing_chat_history()
            self._reset_right_panel_for_chat_switch()
            self._refresh_sheets_panel(switch_to_tab=False)
            self._refresh_materials_panel(switch_to_tab=False)
            self._refresh_comments_panel(switch_to_tab=False)
            self.status_label.setText("Created new chat from Side Ask.")
        except Exception as error:
            self.status_label.setText(f"Could not create Side Ask chat: {error}")

    def _add_comment_from_selection(self) -> None:
        """Save a simple comment on the selected visible chat text."""
        selected_text = self._selected_chat_text()
        if not selected_text:
            self.status_label.setText("Select chat text before adding a comment.")
            return

        comment, accepted = QInputDialog.getMultiLineText(
            self,
            "Add Comment",
            "Comment for selected chat text:",
            "",
        )
        if not accepted or not comment.strip():
            return

        try:
            saved_comment = self.core.add_comment(comment.strip(), selected_text)
            self._refresh_comments_panel(switch_to_tab=True)
            self.status_label.setText(f"Saved comment: {getattr(saved_comment, 'comment_id', 'comment')}")
        except Exception as error:
            self.status_label.setText(f"Could not save comment: {error}")

    def _selected_chat_text(self) -> str:
        """Return selected chat text with Qt paragraph separators normalized."""
        cursor = self.chat_history.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n").strip()
        return selected

    def _refresh_comments_panel(self, switch_to_tab: bool = False) -> None:
        """Refresh right-panel Comments list from Core."""
        if not hasattr(self.core, "get_comments_panel_payload"):
            return
        try:
            self.right_panel.render_comments_payload(
                self.core.get_comments_panel_payload(),
                switch_to_tab=switch_to_tab,
            )
        except Exception as error:
            self.status_label.setText(f"Could not refresh comments: {error}")

    def _reset_right_panel_for_chat_switch(self) -> None:
        """Clear per-chat side-panel state when the visible conversation changes.

        This avoids an old Code Viewer file or old Process Monitor trace looking
        like it belongs to the newly selected chat.
        """
        self._latest_trace_text = "Process Monitor will show the latest message trace here."
        self._latest_trace_detailed = self._latest_trace_text
        self._latest_trace_events = []
        self.right_panel.reset_for_chat_switch(self._current_chat_context_text())

    def _set_waiting_for_response(self, waiting: bool) -> None:
        """Toggle input and chat controls while AMADEUS is generating a response.

        Chat switching is disabled during a request so the response cannot be
        saved into a different chat than the one that sent the message.
        """
        self.message_input.setDisabled(waiting)
        self.send_button.setDisabled(waiting)
        self.annotation_suggestion_box.setDisabled(waiting)
        self.chat_selector.setDisabled(waiting)
        self.new_chat_button.setDisabled(waiting)
        self.delete_chat_button.setDisabled(waiting)
        self.add_comment_button.setDisabled(waiting)
        self.status_label.setText("AMADEUS is thinking..." if waiting else "Ready")

    def _load_existing_chat_history(self) -> None:
        """Load saved messages for the active chat into the visible chat box."""
        self.chat_history.clear()
        self._visible_message_count = 0
        if not hasattr(self.core, "load_chat_history"):
            self._render_current_chat_context_in_memory_panel()
            return

        for saved_message in self.core.load_chat_history():
            message_number = getattr(saved_message, "message_number", None)
            self._append_message(saved_message.speaker, saved_message.message, message_number=message_number)

        self._render_current_chat_context_in_memory_panel()

    def _remove_worker(self, thread: QThread, worker: ChatResponseWorker) -> None:
        """Forget a completed worker so Qt and Python can clean it up."""
        if thread in self._active_threads:
            self._active_threads.remove(thread)
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt uses camelCase names.
        """Prevent closing while a background chat request is still running."""
        if self._active_threads:
            self.status_label.setText("AMADEUS is still thinking. Wait for the response before closing.")
            event.ignore()
            return

        super().closeEvent(event)

    def _append_message(self, speaker: str, message: str, message_number: int | None = None) -> None:
        """Append one speaker message to the chat history with a chat-local number."""
        if message_number is None:
            self._visible_message_count += 1
            message_number = self._visible_message_count
        else:
            # Keep the next live message number higher than any loaded message.
            self._visible_message_count = max(self._visible_message_count, int(message_number))

        clean_speaker = speaker.strip() or "Unknown"
        self.chat_history.append(f"[{message_number}] {clean_speaker}: {message}")

    def _current_chat_context_text(self) -> str:
        """Return readable current-chat metadata for the Memory panel.

        This panel text is not generated by the LLM. It comes from chat metadata
        stored in `data/chats/chats_index.json`, making the workspace context easy
        for Dato to inspect and future modules to retrieve.
        """
        if not hasattr(self.core, "get_current_chat_metadata"):
            return "Current Chat Context\nMetadata unavailable."

        try:
            metadata = self.core.get_current_chat_metadata()
        except Exception as error:
            return f"Current Chat Context\nCould not load metadata: {error}"

        title = getattr(metadata, "title", "Untitled Chat")
        description = getattr(metadata, "description", "") or "No description yet."
        summary = getattr(metadata, "summary", "") or "No callable summary yet."

        return (
            "Current Chat Context\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Callable Summary: {summary}"
        )

    def _render_current_chat_context_in_memory_panel(self) -> None:
        """Show current chat metadata in the Memory tab by default."""
        self.right_panel.render_chat_context(self._current_chat_context_text())
