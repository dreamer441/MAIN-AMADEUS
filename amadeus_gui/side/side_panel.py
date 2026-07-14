"""Reusable PyQt widget for AMADEUS's right-side workspace panel.

`main_window.py` should coordinate the whole window, not own every side-panel
screen. This widget contains the current tabs and rendering logic while
`side_panel` provides the payload/state model underneath it.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QHeaderView, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QTextEdit, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from side_panel import SidePanelPayload, SidePanelState


class RightPanelWidget(QTabWidget):
    """Tabbed workspace panel displayed on the right side of AMADEUS.

    The widget knows how to *display* traces, code, memory, sheets, and materials.
    It does not know how to produce them. Core and modules send payloads; this
    widget renders them and keeps enough visible state for future `[panel]`
    context injection.
    """

    sheet_save_requested = pyqtSignal(object)
    sheet_delete_requested = pyqtSignal(str)
    side_ask_requested = pyqtSignal(str, str)
    side_ask_save_requested = pyqtSignal()
    side_ask_new_chat_requested = pyqtSignal()
    project_tree_requested = pyqtSignal(str)
    project_file_open_requested = pyqtSignal(str)
    project_file_ask_requested = pyqtSignal(str, str, bool, str)
    material_preview_requested = pyqtSignal(str)
    material_open_requested = pyqtSignal(str)
    material_use_requested = pyqtSignal(str)
    material_ask_requested = pyqtSignal(str, str)
    material_remove_requested = pyqtSignal(str)
    material_copy_reference_requested = pyqtSignal(str)
    comment_edit_requested = pyqtSignal(str)
    comment_delete_requested = pyqtSignal(str)
    comment_jump_requested = pyqtSignal(int)
    comment_refresh_requested = pyqtSignal()

    PROCESS_TAB_INDEX = 0
    CODE_TAB_INDEX = 1
    MEMORY_TAB_INDEX = 2
    SHEETS_TAB_INDEX = 3
    MATERIALS_TAB_INDEX = 4
    SIDE_ASK_TAB_INDEX = 5
    COMMENTS_TAB_INDEX = 6

    def __init__(self, initial_trace_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = SidePanelState(compact_trace=initial_trace_text, detailed_trace=initial_trace_text)
        self._loading_sheets_panel = False
        self._sheet_rows_by_id: dict[str, dict] = {}
        self._comment_rows_by_id: dict[str, dict] = {}

        self.addTab(self._build_process_monitor_tab(initial_trace_text), "Process Monitor")
        self.addTab(self._build_code_viewer_tab(), "Code Viewer")
        self.addTab(self._build_memory_tab(), "Memory")
        self.addTab(self._build_sheets_tab(), "Sheets")
        self.addTab(self._build_materials_tab(), "Materials")
        self.addTab(self._build_side_ask_tab(), "Side Ask")
        self.addTab(self._build_comments_tab(), "Comments")

    def _build_process_monitor_tab(self, initial_trace_text: str) -> QWidget:
        """Build the tab that displays real execution events for the latest request."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        header = QHBoxLayout()
        monitor_title = QLabel("AMADEUS Process Monitor")
        monitor_title.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.trace_mode_selector = QComboBox()
        self.trace_mode_selector.addItems(["Compact", "Detailed"])
        self.trace_mode_selector.currentTextChanged.connect(self.render_latest_trace)

        header.addWidget(monitor_title)
        header.addStretch()
        header.addWidget(self.trace_mode_selector)

        self.process_monitor = QTextEdit()
        self.process_monitor.setReadOnly(True)
        self.process_monitor.setPlaceholderText("Execution trace for the latest message will appear here.")
        self.process_monitor.setPlainText(initial_trace_text)

        monitor_note = QLabel("Shows real execution events only, not hidden thoughts.")
        monitor_note.setStyleSheet("color: #666; padding: 2px;")

        layout.addLayout(header)
        layout.addWidget(self.process_monitor)
        layout.addWidget(monitor_note)
        return tab

    def _build_code_viewer_tab(self) -> QWidget:
        """Build a read-only Code Viewer backed by Core project-tree requests."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.code_viewer_title = QLabel("No file opened")
        self.code_viewer_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.code_viewer_meta = QLabel("Use [file][module][file.py] to open exact file content here.")
        self.code_viewer_meta.setStyleSheet("color: #666; padding: 2px;")

        self.project_browser_toggle = QToolButton()
        self.project_browser_toggle.setText("Project Browser")
        self.project_browser_toggle.setCheckable(True)
        self.project_browser_toggle.setChecked(False)
        self.project_browser_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.project_browser_toggle.setArrowType(Qt.ArrowType.RightArrow)

        self.project_browser_container = QWidget()
        browser_layout = QVBoxLayout(self.project_browser_container)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        tree_controls = QHBoxLayout()
        self.code_tree_filter = QLineEdit()
        self.code_tree_filter.setPlaceholderText("Filter filenames")
        self.code_tree_filter.textChanged.connect(self._filter_code_tree)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(lambda: self.project_tree_requested.emit(""))
        self.copy_relative_path_button = QPushButton("Copy Relative Path")
        self.copy_relative_path_button.clicked.connect(self._copy_selected_relative_path)
        tree_controls.addWidget(self.code_tree_filter)
        tree_controls.addWidget(refresh_button)
        tree_controls.addWidget(self.copy_relative_path_button)

        self.code_tree_path = QLabel("Project root")
        self.code_tree_path.setStyleSheet("color: #666; padding: 2px;")
        self.code_tree = QTreeWidget()
        self.code_tree.setHeaderLabels(["Project files", "Size"])
        self.code_tree.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.code_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.code_tree.header().setStretchLastSection(False)
        self.code_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.code_tree.setColumnWidth(0, 520)
        self.code_tree.itemExpanded.connect(self._request_expanded_directory)
        self.code_tree.itemDoubleClicked.connect(self._open_tree_item)
        self.project_browser_toggle.toggled.connect(self._set_project_browser_visible)

        file_actions = QHBoxLayout()
        self.include_code_context = QCheckBox("Include code context")
        self.include_code_context.setToolTip("When enabled, Ask includes only the selected file or line range.")
        self.code_context_range = QLineEdit()
        self.code_context_range.setPlaceholderText("Lines (optional: 15 or 15-30)")
        self.ask_file_input = QLineEdit()
        self.ask_file_input.setPlaceholderText("Ask AMADEUS about selected file")
        self.ask_file_button = QPushButton("Ask AMADEUS About File")
        self.ask_file_button.clicked.connect(self._ask_about_selected_file)
        file_actions.addWidget(self.include_code_context)
        file_actions.addWidget(self.code_context_range)
        file_actions.addWidget(self.ask_file_input)
        file_actions.addWidget(self.ask_file_button)

        self.code_viewer = QTextEdit()
        self.code_viewer.setReadOnly(True)
        self.code_viewer.setPlaceholderText("Exact file content opened by [file] will appear here.")
        self.code_viewer.setFont(QFont("Consolas", 10))

        layout.addWidget(self.code_viewer_title)
        layout.addWidget(self.code_viewer_meta)
        layout.addWidget(self.project_browser_toggle)
        browser_layout.addLayout(tree_controls)
        browser_layout.addWidget(self.code_tree_path)
        browser_layout.addWidget(self.code_tree)
        self.project_browser_container.hide()
        layout.addWidget(self.project_browser_container)
        layout.addLayout(file_actions)
        layout.addWidget(self.code_viewer)
        return tab

    def _set_project_browser_visible(self, visible: bool) -> None:
        """Collapse the project browser so opened code keeps the available panel space."""
        self.project_browser_container.setVisible(visible)
        self.project_browser_toggle.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)

    def _build_memory_tab(self) -> QWidget:
        """Build the read-only Memory panel for `[memory]` annotation results."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.memory_panel_title = QLabel("AMADEUS Memory")
        self.memory_panel_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.memory_panel_meta = QLabel("Current chat context and explicit memory appear here.")
        self.memory_panel_meta.setStyleSheet("color: #666; padding: 2px;")

        self.memory_panel = QTextEdit()
        self.memory_panel.setReadOnly(True)
        self.memory_panel.setPlaceholderText("Current chat context and explicit AMADEUS memory will appear here.")

        memory_note = QLabel("Memory shown here is explicit saved context, not hidden thoughts.")
        memory_note.setStyleSheet("color: #666; padding: 2px;")

        layout.addWidget(self.memory_panel_title)
        layout.addWidget(self.memory_panel_meta)
        layout.addWidget(self.memory_panel)
        layout.addWidget(memory_note)
        return tab

    def _build_sheets_tab(self) -> QWidget:
        """Build the editable Sheets panel.

        Sheets are the first right-panel tab that can edit data. The widget emits
        save/delete requests, but storage still belongs to `sheets_module` through
        Core. This keeps the GUI from becoming the owner of project data.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QHBoxLayout()
        self.sheets_title = QLabel("AMADEUS Sheets")
        self.sheets_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.sheets_selector = QComboBox()
        self.sheets_selector.currentIndexChanged.connect(self._load_selected_sheet_into_editor)
        header.addWidget(self.sheets_title)
        header.addStretch()
        header.addWidget(QLabel("Sheet:"))
        header.addWidget(self.sheets_selector)

        self.sheets_meta = QLabel("Create a chat or global sheet, edit it here, then save.")
        self.sheets_meta.setStyleSheet("color: #666; padding: 2px;")

        self.sheet_id_label = QLabel("New sheet")
        self.sheet_id_label.setStyleSheet("color: #777; padding: 2px;")

        self.sheet_title_input = QLineEdit()
        self.sheet_title_input.setPlaceholderText("Sheet title")

        self.sheet_scope_selector = QComboBox()
        self.sheet_scope_selector.addItems(["chat", "global"])

        self.sheet_description_input = QTextEdit()
        self.sheet_description_input.setPlaceholderText("Optional sheet description")
        self.sheet_description_input.setMaximumHeight(70)

        self.sheet_content_editor = QTextEdit()
        self.sheet_content_editor.setPlaceholderText("Write sheet content here...")

        button_row = QHBoxLayout()
        self.new_sheet_button = QPushButton("New Sheet")
        self.save_sheet_button = QPushButton("Save Sheet")
        self.delete_sheet_button = QPushButton("Delete Sheet")
        self.new_sheet_button.clicked.connect(self._prepare_new_sheet)
        self.save_sheet_button.clicked.connect(self._emit_sheet_save_requested)
        self.delete_sheet_button.clicked.connect(self._emit_sheet_delete_requested)
        button_row.addWidget(self.new_sheet_button)
        button_row.addWidget(self.save_sheet_button)
        button_row.addWidget(self.delete_sheet_button)
        button_row.addStretch()

        layout.addLayout(header)
        layout.addWidget(self.sheets_meta)
        layout.addWidget(self.sheet_id_label)
        layout.addWidget(QLabel("Title:"))
        layout.addWidget(self.sheet_title_input)
        layout.addWidget(QLabel("Scope:"))
        layout.addWidget(self.sheet_scope_selector)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.sheet_description_input)
        layout.addWidget(QLabel("Content:"))
        layout.addWidget(self.sheet_content_editor)
        layout.addLayout(button_row)
        return tab

    def _build_materials_tab(self) -> QWidget:
        """Build Materials controls; material data remains Core/module-owned."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.materials_title = QLabel("AMADEUS Materials")
        self.materials_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.materials_meta = QLabel("Select a reference. Opening or selecting never adds it to chat.")
        self.materials_meta.setStyleSheet("color: #666; padding: 2px;")

        self._loading_materials_panel = False
        self._material_rows_by_id: dict[str, dict] = {}
        self.materials_selector = QComboBox()
        self.materials_selector.currentIndexChanged.connect(self._load_selected_material)
        self.materials_details = QLabel("No material selected.")
        self.materials_details.setWordWrap(True)
        actions = QHBoxLayout()
        self.material_preview_button = QPushButton("Preview")
        self.material_open_button = QPushButton("Open")
        self.material_use_button = QPushButton("Use in Next Message")
        self.material_copy_button = QPushButton("Copy Ref")
        self.material_remove_button = QPushButton("Remove")
        self.material_preview_button.clicked.connect(lambda: self._emit_material_action(self.material_preview_requested))
        self.material_open_button.clicked.connect(lambda: self._emit_material_action(self.material_open_requested))
        self.material_use_button.clicked.connect(lambda: self._emit_material_action(self.material_use_requested))
        self.material_copy_button.clicked.connect(lambda: self._emit_material_action(self.material_copy_reference_requested))
        self.material_remove_button.clicked.connect(lambda: self._emit_material_action(self.material_remove_requested))
        actions.addWidget(self.material_preview_button)
        actions.addWidget(self.material_open_button)
        actions.addWidget(self.material_use_button)
        actions.addWidget(self.material_copy_button)
        actions.addWidget(self.material_remove_button)
        ask_actions = QHBoxLayout()
        self.material_ask_input = QLineEdit()
        self.material_ask_input.setPlaceholderText("Ask AMADEUS about selected material")
        self.material_ask_button = QPushButton("Ask AMADEUS")
        self.material_ask_button.clicked.connect(self._emit_material_ask)
        self.material_refresh_button = QPushButton("Refresh")
        self.material_refresh_button.clicked.connect(lambda: self.material_open_requested.emit(""))
        ask_actions.addWidget(self.material_ask_input)
        ask_actions.addWidget(self.material_ask_button)
        ask_actions.addWidget(self.material_refresh_button)

        self.materials_viewer = QTextEdit()
        self.materials_viewer.setReadOnly(True)
        self.materials_viewer.setPlaceholderText("Materials and exported chat references will appear here.")

        layout.addWidget(self.materials_title)
        layout.addWidget(self.materials_meta)
        layout.addWidget(self.materials_selector)
        layout.addWidget(self.materials_details)
        layout.addLayout(actions)
        layout.addLayout(ask_actions)
        layout.addWidget(self.materials_viewer)
        return tab


    def _build_side_ask_tab(self) -> QWidget:
        """Build the always-available Side Ask tab.

        The tab collects a secondary question. MainWindow supplies any currently
        selected chat text and/or manually pasted context as temporary context when
        the Ask button is pressed. The answer stays here until Dato explicitly saves it to the chat or starts
        a new chat from it.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.side_ask_title = QLabel("AMADEUS Side Ask")
        self.side_ask_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.side_ask_meta = QLabel("Ask a side question. Selected chat text or the context box can be used as temporary context.")
        self.side_ask_meta.setStyleSheet("color: #666; padding: 2px;")

        self.side_ask_question = QTextEdit()
        self.side_ask_question.setPlaceholderText("Ask a small side question here...")
        self.side_ask_question.setMaximumHeight(85)

        # Manual context is separate from the question and answer. This lets Dato
        # paste a specific message snippet or code fragment into Side Ask without
        # needing to select text in the main chat first. The context is temporary
        # and is not saved unless the Side Ask Q&A is explicitly saved to chat.
        self.side_ask_context = QTextEdit()
        self.side_ask_context.setPlaceholderText("Optional context snippet. Paste selected message/code/text here, or leave empty.")
        self.side_ask_context.setMaximumHeight(95)

        self.side_ask_answer = QTextEdit()
        self.side_ask_answer.setReadOnly(True)
        self.side_ask_answer.setPlaceholderText("Side Ask answer will appear here.")

        button_row = QHBoxLayout()
        self.side_ask_button = QPushButton("Ask")
        self.side_ask_save_button = QPushButton("Save to Chat")
        self.side_ask_new_chat_button = QPushButton("New Chat")
        self.side_ask_button.clicked.connect(self._emit_side_ask_requested)
        self.side_ask_save_button.clicked.connect(self.side_ask_save_requested.emit)
        self.side_ask_new_chat_button.clicked.connect(self.side_ask_new_chat_requested.emit)
        self.side_ask_save_button.setDisabled(True)
        self.side_ask_new_chat_button.setDisabled(True)
        button_row.addWidget(self.side_ask_button)
        button_row.addWidget(self.side_ask_save_button)
        button_row.addWidget(self.side_ask_new_chat_button)
        button_row.addStretch()

        layout.addWidget(self.side_ask_title)
        layout.addWidget(self.side_ask_meta)
        layout.addWidget(QLabel("Question:"))
        layout.addWidget(self.side_ask_question)
        layout.addWidget(QLabel("Optional context box:"))
        layout.addWidget(self.side_ask_context)
        layout.addWidget(QLabel("Answer:"))
        layout.addWidget(self.side_ask_answer)
        layout.addLayout(button_row)
        return tab

    def _build_comments_tab(self) -> QWidget:
        """Build comment selection and actions for the current chat."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.comments_title = QLabel("AMADEUS Comments")
        self.comments_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.comments_meta = QLabel("Select chat text and press Add Comment to save a simple note.")
        self.comments_meta.setStyleSheet("color: #666; padding: 2px;")
        self.comments_selector = QComboBox()
        self.comments_selector.currentIndexChanged.connect(self._load_selected_comment)
        action_row = QHBoxLayout()
        self.comment_edit_button = QPushButton("Edit")
        self.comment_delete_button = QPushButton("Delete")
        self.comment_jump_button = QPushButton("Jump to Message")
        self.comment_refresh_button = QPushButton("Refresh")
        self.comment_edit_button.clicked.connect(lambda: self._emit_comment_action(self.comment_edit_requested))
        self.comment_delete_button.clicked.connect(lambda: self._emit_comment_action(self.comment_delete_requested))
        self.comment_jump_button.clicked.connect(self._emit_comment_jump_requested)
        self.comment_refresh_button.clicked.connect(self.comment_refresh_requested.emit)
        action_row.addWidget(self.comment_edit_button)
        action_row.addWidget(self.comment_delete_button)
        action_row.addWidget(self.comment_jump_button)
        action_row.addWidget(self.comment_refresh_button)
        self.comments_viewer = QTextEdit()
        self.comments_viewer.setReadOnly(True)
        self.comments_viewer.setPlaceholderText("Select a comment to view its details.")
        layout.addWidget(self.comments_title)
        layout.addWidget(self.comments_meta)
        layout.addWidget(self.comments_selector)
        layout.addLayout(action_row)
        layout.addWidget(self.comments_viewer)
        self._set_comment_action_state(None)
        return tab

    def show_waiting_trace(self) -> None:
        """Show a temporary GUI-side status while Core is still working."""
        self.state.set_trace("[Input Sent]\nWaiting for Core trace...")
        self.render_latest_trace()
        self.setCurrentIndex(self.PROCESS_TAB_INDEX)

    def render_trace(self, compact_trace: str, detailed_trace: str | None = None) -> None:
        """Render the latest Core trace in the Process Monitor tab."""
        self.state.set_trace(compact_trace, detailed_trace)
        self.render_latest_trace()

    def render_latest_trace(self) -> None:
        """Switch Compact/Detailed trace text without asking Core to run again."""
        mode = self.trace_mode_selector.currentText().lower() if hasattr(self, "trace_mode_selector") else "compact"
        if mode == "detailed":
            self.process_monitor.setPlainText(self.state.detailed_trace)
        else:
            self.process_monitor.setPlainText(self.state.compact_trace)

    def render_side_panel_payload(self, raw_payload: object, chat_context_text: str) -> None:
        """Render a side-panel payload returned by Core.

        Invalid payloads are ignored. This makes panel display optional: chat must
        still work even if a future module returns an incomplete panel payload.
        """
        payload = SidePanelPayload.from_raw(raw_payload)
        if payload is None:
            return

        self.state.set_payload(payload)
        normalized_type = payload.panel_type.lower()
        if normalized_type == "code":
            self._render_code_viewer(payload)
            self.setCurrentIndex(self.CODE_TAB_INDEX)
            return

        if normalized_type == "memory":
            self._render_memory_panel(payload, chat_context_text)
            self.setCurrentIndex(self.MEMORY_TAB_INDEX)
            return

        if normalized_type == "sheets":
            self._render_sheets_panel(payload)
            self.setCurrentIndex(self.SHEETS_TAB_INDEX)
            return

        if normalized_type == "materials":
            self._render_materials_panel(payload)
            self.setCurrentIndex(self.MATERIALS_TAB_INDEX)
            return

        if normalized_type == "comments":
            self._render_comments_panel(payload)
            self.setCurrentIndex(self.COMMENTS_TAB_INDEX)
            return

        self.setCurrentIndex(self.PROCESS_TAB_INDEX)

    def render_sheets_payload(self, raw_payload: object, switch_to_tab: bool = False) -> None:
        """Refresh the Sheets tab without always stealing focus from the current tab."""
        payload = SidePanelPayload.from_raw(raw_payload)
        if payload is None:
            return
        previous_active_tab = self.state.active_tab
        self.state.set_payload(payload)
        if not switch_to_tab:
            self.state.active_tab = previous_active_tab
        self._render_sheets_panel(payload)
        if switch_to_tab:
            self.setCurrentIndex(self.SHEETS_TAB_INDEX)

    def render_materials_payload(self, raw_payload: object, switch_to_tab: bool = False) -> None:
        """Refresh the Materials tab without always stealing focus."""
        payload = SidePanelPayload.from_raw(raw_payload)
        if payload is None:
            return
        previous_active_tab = self.state.active_tab
        self.state.set_payload(payload)
        if not switch_to_tab:
            self.state.active_tab = previous_active_tab
        self._render_materials_panel(payload)
        if switch_to_tab:
            self.setCurrentIndex(self.MATERIALS_TAB_INDEX)

    def _render_code_viewer(self, payload: SidePanelPayload) -> None:
        """Display exact file content returned by `[file]` in the Code Viewer tab."""
        metadata = payload.metadata
        lines = metadata.get("lines", "?")
        characters_read = metadata.get("characters_read", len(payload.content))
        total_characters = metadata.get("total_characters", characters_read)
        truncated = bool(metadata.get("truncated", False))

        self.code_viewer_title.setText(payload.title)
        truncation_text = " • truncated" if truncated else ""
        size_bytes = metadata.get("size_bytes")
        encoding = metadata.get("encoding")
        details = f"Lines: {lines} • Characters: {characters_read} of {total_characters}{truncation_text}"
        if size_bytes is not None:
            details += f" • {size_bytes} bytes"
        if encoding:
            details += f" • {encoding}"
        self.code_viewer_meta.setText(details)
        self.code_viewer.setPlainText(self._line_labelled_code(payload.content))
        self.code_viewer.moveCursor(QTextCursor.MoveOperation.Start)

    def _line_labelled_code(self, content: str) -> str:
        """Render Code Viewer text with stable one-based source line numbers."""
        return "\n".join(f"{number}: {line}" for number, line in enumerate(content.splitlines(), start=1))

    def render_project_tree(self, raw_tree: object) -> None:
        """Render one Core-provided directory listing and keep lazy child folders."""
        if not isinstance(raw_tree, dict):
            return
        path = str(raw_tree.get("path") or "")
        parent = self._find_tree_item(path)
        if parent is None:
            self.code_tree.clear()
            parent = self.code_tree.invisibleRootItem()
        else:
            parent.takeChildren()
        self.code_tree_path.setText("Project root" if not path else f"Project root / {path}")
        for folder in raw_tree.get("folders", []):
            if not isinstance(folder, dict):
                continue
            item = QTreeWidgetItem([str(folder.get("name", "")), ""])
            item.setData(0, Qt.ItemDataRole.UserRole, str(folder.get("relative_path", "")))
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
            item.addChild(QTreeWidgetItem(["Loading...", ""]))
            parent.addChild(item)
        for file_entry in raw_tree.get("files", []):
            if not isinstance(file_entry, dict):
                continue
            item = QTreeWidgetItem([str(file_entry.get("name", "")), f"{file_entry.get('size_bytes', 0)} B"])
            item.setData(0, Qt.ItemDataRole.UserRole, str(file_entry.get("relative_path", "")))
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "file")
            parent.addChild(item)
        if parent is self.code_tree.invisibleRootItem():
            self.code_tree.expandToDepth(0)
        self._filter_code_tree(self.code_tree_filter.text())

    def _find_tree_item(self, path: str) -> QTreeWidgetItem | None:
        """Find an already-rendered directory node by its Core-provided path."""
        def visit(parent: QTreeWidgetItem) -> QTreeWidgetItem | None:
            for index in range(parent.childCount()):
                child = parent.child(index)
                if child.data(0, Qt.ItemDataRole.UserRole) == path:
                    return child
                match = visit(child)
                if match is not None:
                    return match
            return None
        return visit(self.code_tree.invisibleRootItem())

    def _request_expanded_directory(self, item: QTreeWidgetItem) -> None:
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == "folder":
            self.project_tree_requested.emit(str(item.data(0, Qt.ItemDataRole.UserRole)))

    def _open_tree_item(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == "file":
            self.project_file_open_requested.emit(str(item.data(0, Qt.ItemDataRole.UserRole)))

    def _selected_code_file_path(self) -> str:
        item = self.code_tree.currentItem()
        if item is not None and item.data(0, Qt.ItemDataRole.UserRole + 1) == "file":
            return str(item.data(0, Qt.ItemDataRole.UserRole))
        return ""

    def _copy_selected_relative_path(self) -> None:
        path = self._selected_code_file_path()
        if path:
            QApplication.clipboard().setText(path)

    def _ask_about_selected_file(self) -> None:
        path = self._selected_code_file_path()
        question = self.ask_file_input.text().strip()
        if path and question:
            self.project_file_ask_requested.emit(
                path, question, self.include_code_context.isChecked(), self.code_context_range.text()
            )

    def _filter_code_tree(self, text: str) -> None:
        """Filter visible filenames only; tree data remains Core-owned and complete."""
        needle = text.strip().lower()
        def apply(parent: QTreeWidgetItem) -> bool:
            matched_child = False
            for index in range(parent.childCount()):
                child = parent.child(index)
                child_match = apply(child)
                is_file = child.data(0, Qt.ItemDataRole.UserRole + 1) == "file"
                own_match = not needle or not is_file or needle in child.text(0).lower()
                visible = own_match or child_match
                child.setHidden(not visible)
                matched_child = matched_child or visible
            return matched_child
        apply(self.code_tree.invisibleRootItem())

    def _render_memory_panel(self, payload: SidePanelPayload, chat_context_text: str) -> None:
        """Display explicit AMADEUS memory returned by `[memory]` in the Memory tab."""
        metadata = payload.metadata
        scope = metadata.get("scope", "all")
        global_count = metadata.get("global_count", 0)
        chat_count = metadata.get("chat_count", 0)

        self.state.set_chat_context(chat_context_text)
        self.memory_panel_title.setText(payload.title)
        self.memory_panel_meta.setText(f"Scope: {scope} • Global: {global_count} • Chat: {chat_count}")
        combined_content = chat_context_text
        if payload.content.strip():
            combined_content += "\n\n---\n\n" + payload.content
        self.memory_panel.setPlainText(combined_content)
        self.memory_panel.moveCursor(QTextCursor.MoveOperation.Start)

    def _render_sheets_panel(self, payload: SidePanelPayload) -> None:
        """Load sheet metadata/content into the editable Sheets tab."""
        metadata = payload.metadata
        sheets = metadata.get("sheets") if isinstance(metadata.get("sheets"), list) else []
        selected_sheet_id = str(metadata.get("selected_sheet_id") or "")
        self._sheet_rows_by_id = {str(row.get("sheet_id")): row for row in sheets if isinstance(row, dict) and row.get("sheet_id")}

        self._loading_sheets_panel = True
        try:
            self.sheets_title.setText(payload.title or "AMADEUS Sheets")
            self.sheets_meta.setText(f"Sheets visible here: {len(self._sheet_rows_by_id)}")
            self.sheets_selector.clear()
            self.sheets_selector.addItem("+ New Sheet", "")
            selected_index = 0
            for index, row in enumerate(self._sheet_rows_by_id.values(), start=1):
                label = f"{row.get('title', 'Untitled')} ({row.get('scope', 'chat')})"
                sheet_id = str(row.get("sheet_id", ""))
                self.sheets_selector.addItem(label, sheet_id)
                if sheet_id == selected_sheet_id:
                    selected_index = index
            self.sheets_selector.setCurrentIndex(selected_index)
        finally:
            self._loading_sheets_panel = False

        self._load_selected_sheet_into_editor(self.sheets_selector.currentIndex())

    def _render_materials_panel(self, payload: SidePanelPayload) -> None:
        """Display Core-provided material rows and optional opened content."""
        metadata = payload.metadata
        material_count = metadata.get("material_count", 0)
        status = metadata.get("status", "ready")
        rows = metadata.get("materials") if isinstance(metadata.get("materials"), list) else []
        selected_material_id = str(metadata.get("selected_material_id") or "")
        self._material_rows_by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}
        self._loading_materials_panel = True
        try:
            self.materials_selector.clear()
            self.materials_selector.addItem("Select material", "")
            selected_index = 0
            for index, row in enumerate(self._material_rows_by_id.values(), start=1):
                material_id = str(row["id"])
                self.materials_selector.addItem(f"{row.get('name', 'Untitled')} ({row.get('type', 'material')})", material_id)
                if material_id == selected_material_id:
                    selected_index = index
            self.materials_selector.setCurrentIndex(selected_index)
        finally:
            self._loading_materials_panel = False
        self.materials_title.setText(payload.title)
        self.materials_meta.setText(f"Materials: {material_count} • Status: {status}")
        self.materials_viewer.setPlainText(payload.content)
        self.materials_viewer.moveCursor(QTextCursor.MoveOperation.Start)
        self._load_selected_material(self.materials_selector.currentIndex())

    def _load_selected_material(self, index: int) -> None:
        """Show selected metadata only; selection is never callable context."""
        if self._loading_materials_panel:
            return
        material_id = self.materials_selector.itemData(index)
        row = self._material_rows_by_id.get(material_id) if isinstance(material_id, str) else None
        if row is None:
            self.materials_details.setText("No material selected.")
            return
        if row.get("type") == "chat_export":
            self.material_open_button.setText("Open")
            self.material_copy_button.setText("Copy Path")
            self.material_remove_button.setText("Delete")
            self.material_preview_button.setDisabled(True)
            self.material_ask_input.setDisabled(True)
            self.material_ask_button.setDisabled(True)
            self.materials_details.setText(f"{row['display_date']}\n{row['display_range']}")
            return
        self.material_open_button.setText("Open")
        self.material_copy_button.setText("Copy Ref")
        self.material_remove_button.setText("Remove")
        self.material_preview_button.setDisabled(False)
        self.material_ask_input.setDisabled(False)
        self.material_ask_button.setDisabled(False)
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        details = ", ".join(f"{key}: {value}" for key, value in metadata.items())
        self.materials_details.setText(f"id: {row['id']}\ntype: {row.get('type', 'material')}\n{details}")

    def material_type(self, material_id: str) -> str:
        """Return the selected row type so MainWindow can label confirmations."""
        row = self._material_rows_by_id.get(material_id)
        return str(row.get("type") or "") if row is not None else ""

    def _selected_material_id(self) -> str:
        material_id = self.materials_selector.currentData()
        return material_id if isinstance(material_id, str) else ""

    def _emit_material_action(self, signal) -> None:
        material_id = self._selected_material_id()
        if material_id:
            signal.emit(material_id)

    def _emit_material_ask(self) -> None:
        material_id = self._selected_material_id()
        question = self.material_ask_input.text().strip()
        if material_id and question:
            self.material_ask_requested.emit(material_id, question)

    def _load_selected_sheet_into_editor(self, index: int) -> None:
        """Show the selected sheet row in the editor fields."""
        if self._loading_sheets_panel:
            return
        sheet_id = self.sheets_selector.itemData(index)
        if not isinstance(sheet_id, str) or not sheet_id:
            self._prepare_new_sheet()
            return

        row = self._sheet_rows_by_id.get(sheet_id)
        if row is None:
            self._prepare_new_sheet()
            return

        self._loading_sheets_panel = True
        try:
            self.sheet_id_label.setText(f"Sheet id: {sheet_id}")
            self.sheet_title_input.setText(str(row.get("title") or ""))
            scope = str(row.get("scope") or "chat")
            self.sheet_scope_selector.setCurrentText(scope if scope in {"chat", "global"} else "chat")
            self.sheet_description_input.setPlainText(str(row.get("description") or ""))
            self.sheet_content_editor.setPlainText(str(row.get("content") or ""))
        finally:
            self._loading_sheets_panel = False

    def _prepare_new_sheet(self) -> None:
        """Clear editor fields so Save creates a new sheet."""
        if self._loading_sheets_panel:
            return
        self._loading_sheets_panel = True
        try:
            self.sheets_selector.setCurrentIndex(0)
            self.sheet_id_label.setText("New sheet")
            self.sheet_title_input.clear()
            self.sheet_scope_selector.setCurrentText("chat")
            self.sheet_description_input.clear()
            self.sheet_content_editor.clear()
        finally:
            self._loading_sheets_panel = False

    def _emit_sheet_save_requested(self) -> None:
        """Ask MainWindow/Core to save the current sheet editor fields."""
        sheet_id = self.sheets_selector.currentData()
        if not isinstance(sheet_id, str):
            sheet_id = ""
        payload = {
            "sheet_id": sheet_id,
            "title": self.sheet_title_input.text().strip() or "New Sheet",
            "scope": self.sheet_scope_selector.currentText().strip() or "chat",
            "description": self.sheet_description_input.toPlainText().strip(),
            "content": self.sheet_content_editor.toPlainText(),
        }
        self.sheet_save_requested.emit(payload)

    def _emit_sheet_delete_requested(self) -> None:
        """Ask MainWindow/Core to delete the selected sheet."""
        sheet_id = self.sheets_selector.currentData()
        if isinstance(sheet_id, str) and sheet_id:
            self.sheet_delete_requested.emit(sheet_id)


    def render_side_ask_answer(self, question: str, answer: str, selected_text: str = "") -> None:
        """Show a completed Side Ask answer and enable save/new-chat actions."""
        context_note = "Temporary context attached." if selected_text.strip() else "No temporary context attached."
        self.side_ask_meta.setText(context_note)
        self.side_ask_question.setPlainText(question)
        self.side_ask_answer.setPlainText(answer)
        self.side_ask_answer.moveCursor(QTextCursor.MoveOperation.Start)
        self.side_ask_save_button.setDisabled(False)
        self.side_ask_new_chat_button.setDisabled(False)
        self.setCurrentIndex(self.SIDE_ASK_TAB_INDEX)

    def show_side_ask_waiting(self) -> None:
        """Show a temporary waiting state for Side Ask."""
        self.side_ask_answer.setPlainText("Waiting for AMADEUS Side Ask answer...")
        self.side_ask_save_button.setDisabled(True)
        self.side_ask_new_chat_button.setDisabled(True)
        self.setCurrentIndex(self.SIDE_ASK_TAB_INDEX)

    def set_side_ask_busy(self, busy: bool) -> None:
        """Disable only Side Ask controls while the side request runs."""
        self.side_ask_button.setDisabled(busy)
        self.side_ask_question.setDisabled(busy)
        self.side_ask_context.setDisabled(busy)

    def current_side_ask_question(self) -> str:
        """Return the current Side Ask question text."""
        return self.side_ask_question.toPlainText().strip()

    def current_side_ask_answer(self) -> str:
        """Return the current Side Ask answer text."""
        return self.side_ask_answer.toPlainText().strip()

    def current_side_ask_manual_context(self) -> str:
        """Return manually pasted Side Ask context from the separate context box."""
        return self.side_ask_context.toPlainText().strip()

    def _emit_side_ask_requested(self) -> None:
        """Emit the current Side Ask question and manual context to MainWindow/Core."""
        self.side_ask_requested.emit(self.current_side_ask_question(), self.current_side_ask_manual_context())

    def render_comments_payload(self, raw_payload: object, switch_to_tab: bool = False) -> None:
        """Refresh the Comments tab from a side-panel payload."""
        payload = SidePanelPayload.from_raw(raw_payload)
        if payload is None:
            return
        previous_active_tab = self.state.active_tab
        self.state.set_payload(payload)
        if not switch_to_tab:
            self.state.active_tab = previous_active_tab
        self._render_comments_panel(payload)
        if switch_to_tab:
            self.setCurrentIndex(self.COMMENTS_TAB_INDEX)

    def _render_comments_panel(self, payload: SidePanelPayload) -> None:
        """Load Core-provided comment rows into the selector."""
        count = payload.metadata.get("comment_count", 0)
        comments = payload.metadata.get("comments") if isinstance(payload.metadata.get("comments"), list) else []
        self._comment_rows_by_id = {
            str(row.get("comment_id")): row
            for row in comments
            if isinstance(row, dict) and row.get("comment_id")
        }
        self.comments_title.setText(payload.title)
        self.comments_meta.setText(f"Comments in this chat: {count}")
        self.comments_selector.clear()
        for comment_id, row in self._comment_rows_by_id.items():
            message_number = row.get("message_number")
            label = f"Comment({message_number})" if isinstance(message_number, int) else "Comment(A)"
            self.comments_selector.addItem(label, comment_id)
        self._load_selected_comment(self.comments_selector.currentIndex())

    def _load_selected_comment(self, index: int) -> None:
        """Show readable content and target details for the selected comment."""
        comment_id = self.comments_selector.itemData(index)
        row = self._comment_rows_by_id.get(comment_id) if isinstance(comment_id, str) else None
        self._set_comment_action_state(row)
        if row is None:
            self.comments_viewer.clear()
            return
        message_number = row.get("message_number")
        target = f"Message {message_number}" if isinstance(message_number, int) else "General chat"
        comment_type = str(row.get("comment_type") or "general").capitalize()
        self.comments_viewer.setPlainText(f"{row.get('comment', '')}\n\nTarget: {target}\nType: {comment_type}")
        self.comments_viewer.moveCursor(QTextCursor.MoveOperation.Start)

    def _set_comment_action_state(self, row: dict | None) -> None:
        """Enable selected-comment actions without coupling them to chat requests."""
        has_comment = row is not None
        self.comment_edit_button.setEnabled(has_comment)
        self.comment_delete_button.setEnabled(has_comment)
        self.comment_jump_button.setEnabled(has_comment and isinstance(row.get("message_number"), int))

    def _emit_comment_action(self, signal) -> None:
        """Emit a selected comment id only when a valid row is active."""
        comment_id = self.comments_selector.currentData()
        if isinstance(comment_id, str) and comment_id in self._comment_rows_by_id:
            signal.emit(comment_id)

    def _emit_comment_jump_requested(self) -> None:
        """Emit the selected message number only for message-attached comments."""
        comment_id = self.comments_selector.currentData()
        row = self._comment_rows_by_id.get(comment_id) if isinstance(comment_id, str) else None
        message_number = row.get("message_number") if row is not None else None
        if isinstance(message_number, int):
            self.comment_jump_requested.emit(message_number)

    def render_chat_context(self, chat_context_text: str) -> None:
        """Show current chat title/description in the Memory tab by default."""
        self.state.set_chat_context(chat_context_text)
        self.memory_panel_title.setText("Current Chat Context")
        self.memory_panel_meta.setText("Chat title/description are active context for this chat.")
        self.memory_panel.setPlainText(chat_context_text)
        self.memory_panel.moveCursor(QTextCursor.MoveOperation.Start)

    def reset_for_chat_switch(self, chat_context_text: str) -> None:
        """Clear visible panel state that belongs to the previous chat."""
        self.state.reset_for_chat_switch(chat_context_text)
        self.render_latest_trace()
        self.code_viewer_title.setText("No file opened")
        self.code_viewer_meta.setText("Use [file][module][file.py] to open exact file content here.")
        self.code_viewer.clear()
        self.side_ask_answer.clear()
        self.side_ask_context.clear()
        self.side_ask_save_button.setDisabled(True)
        self.side_ask_new_chat_button.setDisabled(True)
        self._comment_rows_by_id = {}
        self.comments_selector.clear()
        self.comments_viewer.clear()
        self.render_chat_context(chat_context_text)
        self.setCurrentIndex(self.PROCESS_TAB_INDEX)

    def current_panel_context_text(self) -> str:
        """Expose visible panel context for future `[panel]` annotation use."""
        return self.state.current_context_text()
