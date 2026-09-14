"""Interactive PyQt6 workspace for AMADEUS Canvas blocks and connectors."""

from __future__ import annotations

import math
from typing import Any, Callable

from PyQt6.QtCore import QObject, QLineF, QPointF, QRectF, QSettings, QThread, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QKeySequence,
    QPainterPathStroker,
    QPen,
    QPolygonF,
    QShortcut,
    QTextCursor,
    QTextOption,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from canvas_module import (
    CANVAS_MODEL_PROFILES,
    DEFAULT_CANVAS_MODEL_WEIGHT,
    DEFAULT_RELATION_TYPE,
    CanvasConnector,
    CanvasContextPackage,
    CanvasStorageError,
    CanvasTextBlock,
    CanvasWorkspaceDescriptor,
)


# Keep historical view imports available to callers.
from .constants import (
    _COMMENT_RESIZE_HANDLE_SIZE,
    _MIN_BLOCK_HEIGHT,
    _MIN_BLOCK_WIDTH,
    _MIN_COMMENT_HEIGHT,
    _MIN_COMMENT_WIDTH,
    _RELATION_TYPES,
    _RESIZE_HANDLE_SIZE,
)
from .dialogs import (
    ConnectorEditorDialog,
    CanvasContextPreviewDialog,
    CanvasTextEditor,
    CanvasTextEditorDialog,
)
from .items import (
    CanvasTitleTabItem,
    CanvasCommentBubbleItem,
    CanvasTextBlockItem,
    CanvasConnectorItem,
)
from .surface import CanvasSurface


class CanvasResponseWorker(QObject):
    """Run Canvas generation outside the GUI thread and stream safe events."""

    finished = pyqtSignal(object)
    process_event = pyqtSignal(object)

    def __init__(self, core: Any, request: dict[str, object]) -> None:
        super().__init__()
        self.core = core
        self.request = dict(request)

    def run(self) -> None:
        try:
            result = self.core.handle_canvas_message(
                **self.request,
                event_listener=self.process_event.emit,
            )
        except Exception as exc:
            result = {
                "response": f"AMADEUS could not complete that Canvas request: {exc}",
                "canvas_response_block": None,
                "canvas_response_connector": None,
                "trace_events": [],
            }
        self.finished.emit(result)


class CanvasView(QWidget):
    """Persistent main-window page for typed Canvas brainstorming."""

    def __init__(self, core: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.module_name = "Canvas"
        self.core = core
        self.canvas_module = self._load_module(core)
        self.descriptor = self._load_descriptor(core)
        self._items_by_id: dict[str, CanvasTextBlockItem] = {}
        self._connectors_by_id: dict[str, CanvasConnectorItem] = {}
        self._root_object_id: str | None = None
        self._connection_mode: str | None = None
        self._pending_source_id: str | None = None
        self._right_click_source_id: str | None = None
        self._handling_connection_selection = False
        self._active_threads: list[QThread] = []
        self._active_workers: list[CanvasResponseWorker] = []
        self._refreshing_workspace_combo = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.title_label = QLabel("AMADEUS Canvas")
        self.title_label.setObjectName("canvasTitle")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold;")

        purpose = QLabel(self.descriptor.purpose)
        purpose.setObjectName("canvasPurpose")
        purpose.setWordWrap(True)
        purpose.setStyleSheet("color: #7f8a99;")

        workspace_toolbar = QHBoxLayout()
        workspace_label = QLabel("Workspace")
        workspace_label.setStyleSheet("color: #8fa0b2; font-weight: 600;")
        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumWidth(260)
        self.workspace_combo.currentIndexChanged.connect(self._workspace_selection_changed)
        self.new_workspace_button = QPushButton("New")
        self.new_workspace_button.clicked.connect(self._create_workspace)
        self.rename_workspace_button = QPushButton("Rename")
        self.rename_workspace_button.clicked.connect(self._rename_workspace)
        self.delete_workspace_button = QPushButton("Delete")
        self.delete_workspace_button.clicked.connect(self._delete_workspace)
        workspace_help = QLabel("Each workspace keeps separate blocks, links, roots, send history, and context baseline.")
        workspace_help.setStyleSheet("color: #738397;")
        workspace_help.setWordWrap(True)
        workspace_toolbar.addWidget(workspace_label)
        workspace_toolbar.addWidget(self.workspace_combo)
        workspace_toolbar.addWidget(self.new_workspace_button)
        workspace_toolbar.addWidget(self.rename_workspace_button)
        workspace_toolbar.addWidget(self.delete_workspace_button)
        workspace_toolbar.addStretch()
        workspace_toolbar.addWidget(workspace_help)

        toolbar = QHBoxLayout()
        self.add_text_button = QPushButton("Add Text")
        self.add_text_button.clicked.connect(self._add_text_at_center)
        self.add_line_button = QPushButton("Add Line")
        self.add_line_button.clicked.connect(lambda: self._start_connection_mode("line"))
        self.add_arrow_button = QPushButton("Add Arrow")
        self.add_arrow_button.clicked.connect(lambda: self._start_connection_mode("arrow"))
        self.cancel_link_button = QPushButton("Cancel Link")
        self.cancel_link_button.setEnabled(False)
        self.cancel_link_button.clicked.connect(self._cancel_connection_mode)
        self.edit_button = QPushButton("Edit")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self._edit_selected)
        self.title_button = QPushButton("Title")
        self.title_button.setEnabled(False)
        self.title_button.setToolTip("Add, edit, or remove the selected block's attached title tab")
        self.title_button.clicked.connect(self._edit_selected_title)
        self.comment_button = QPushButton("Comment")
        self.comment_button.setEnabled(False)
        self.comment_button.setToolTip("Add, edit, or remove the selected block's draggable oval comment")
        self.comment_button.clicked.connect(self._edit_selected_comment)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._delete_selected)
        self.undo_button = QPushButton("Undo")
        self.undo_button.setEnabled(False)
        self.undo_button.setToolTip("Undo the most recent Canvas change (Ctrl+Z)")
        self.undo_button.clicked.connect(self._undo_last_change)
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.clicked.connect(self._reset_view)
        self.object_count_label = QLabel("0 blocks • 0 connectors")
        self.object_count_label.setStyleSheet("color: #7f8a99;")
        toolbar.addWidget(self.add_text_button)
        toolbar.addWidget(self.add_line_button)
        toolbar.addWidget(self.add_arrow_button)
        toolbar.addWidget(self.cancel_link_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.title_button)
        toolbar.addWidget(self.comment_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.undo_button)
        toolbar.addWidget(self.reset_view_button)
        toolbar.addStretch()
        toolbar.addWidget(self.object_count_label)

        context_toolbar = QHBoxLayout()
        context_label = QLabel("Context")
        context_label.setStyleSheet("color: #8fa0b2; font-weight: 600;")
        self.context_mode_combo = QComboBox()
        self.context_mode_combo.addItem("Viewport changes", "viewport")
        self.context_mode_combo.addItem("Selected targets", "selection")
        self.context_mode_combo.addItem("Selected branch", "branch")
        self.preview_context_button = QPushButton("Preview Context")
        self.preview_context_button.clicked.connect(self._preview_context)
        self.set_root_button = QPushButton("Set Selected as Root")
        self.set_root_button.setEnabled(False)
        self.set_root_button.clicked.connect(self._set_selected_as_root)
        self.clear_root_button = QPushButton("Clear Root")
        self.clear_root_button.setEnabled(False)
        self.clear_root_button.clicked.connect(self._clear_root)
        model_label = QLabel("Model")
        model_label.setStyleSheet("color: #8fa0b2; font-weight: 600;")
        self.model_weight_combo = QComboBox()
        self.model_weight_combo.setToolTip(
            "Light = qwen3:4b, Normal = qwen3:14b, Heavy = qwen3:32b"
        )
        for weight, model_name in CANVAS_MODEL_PROFILES.items():
            self.model_weight_combo.addItem(
                f"{weight.title()} — {model_name}",
                weight,
            )
        settings = QSettings("Dato", "AMADEUS")
        saved_weight = str(settings.value("canvas/model_weight", DEFAULT_CANVAS_MODEL_WEIGHT))
        model_index = self.model_weight_combo.findData(saved_weight)
        self.model_weight_combo.setCurrentIndex(
            model_index if model_index >= 0 else self.model_weight_combo.findData(DEFAULT_CANVAS_MODEL_WEIGHT)
        )
        self.model_weight_combo.currentIndexChanged.connect(self._model_weight_changed)
        self.instruction_input = QLineEdit()
        self.instruction_input.setPlaceholderText(
            "Optional instruction: continue, critique, compare…"
        )
        self.instruction_input.setMinimumWidth(280)
        self.instruction_input.returnPressed.connect(self._send_to_amadeus)
        self.send_button = QPushButton("Send Changes to AMADEUS")
        self.send_button.clicked.connect(self._send_to_amadeus)
        context_help = QLabel(
            "Viewport = supporting boundary; new/edited or selected items = answer targets."
        )
        context_help.setStyleSheet("color: #738397;")
        context_toolbar.addWidget(context_label)
        context_toolbar.addWidget(self.context_mode_combo)
        context_toolbar.addWidget(self.preview_context_button)
        context_toolbar.addWidget(self.set_root_button)
        context_toolbar.addWidget(self.clear_root_button)
        context_toolbar.addStretch()
        context_toolbar.addWidget(model_label)
        context_toolbar.addWidget(self.model_weight_combo)
        context_toolbar.addWidget(self.instruction_input)
        context_toolbar.addWidget(self.send_button)
        context_toolbar.addWidget(context_help)

        self.status_label = QLabel(
            "Select a block to move or resize it. Right-click two blocks to create a quick directional arrow."
        )
        self.status_label.setObjectName("canvasStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #9aa7b8; padding-bottom: 4px;")

        self.scene = QGraphicsScene(self)
        self.scene.selectionChanged.connect(self._selection_changed)
        self.surface = CanvasSurface(
            self.scene,
            create_callback=self._create_text_block,
            delete_callback=self._delete_selected,
            cancel_callback=self._cancel_connection_mode,
            parent=self,
        )
        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.undo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.undo_shortcut.activated.connect(self._undo_last_change)

        layout.addWidget(self.title_label)
        layout.addWidget(purpose)
        layout.addLayout(workspace_toolbar)
        layout.addLayout(toolbar)
        layout.addLayout(context_toolbar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.surface, stretch=1)

        if self.canvas_module is None:
            self._set_storage_enabled(False)
            self.status_label.setText("Canvas storage facade is unavailable in this application shell.")
        else:
            self._refresh_workspace_controls()
            self._load_persisted_content()

    @staticmethod
    def _load_module(core: Any) -> Any | None:
        """Bind only the explicitly registered Core Canvas route."""
        return getattr(core, "canvas", None)

    @staticmethod
    def _load_descriptor(core: Any) -> CanvasWorkspaceDescriptor:
        try:
            descriptor = core.get_canvas_workspace_descriptor()
            if isinstance(descriptor, CanvasWorkspaceDescriptor):
                return descriptor
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
        return CanvasWorkspaceDescriptor(
            workspace_id="main",
            title="AMADEUS Canvas",
            purpose="Spatial brainstorming, branching conversation, diagrams, and future visual collaboration.",
            status="foundation_unavailable",
        )

    def _refresh_workspace_controls(self) -> None:
        if self.canvas_module is None:
            return
        try:
            workspaces = self.canvas_module.list_workspaces()
        except CanvasStorageError as exc:
            self._show_error("Could not load Canvas workspaces", exc)
            return
        self._refreshing_workspace_combo = True
        try:
            self.workspace_combo.clear()
            for workspace in workspaces:
                self.workspace_combo.addItem(workspace.title, workspace.workspace_id)
            active_index = self.workspace_combo.findData(self.canvas_module.workspace_id)
            if active_index >= 0:
                self.workspace_combo.setCurrentIndex(active_index)
        finally:
            self._refreshing_workspace_combo = False
        has_workspace = self.workspace_combo.count() > 0
        read_only = self._active_workspace_is_read_only()
        self.rename_workspace_button.setEnabled(has_workspace and not self._active_threads and not read_only)
        self.delete_workspace_button.setEnabled(has_workspace and not self._active_threads and not read_only)
        self.new_workspace_button.setEnabled(not self._active_threads)
        if read_only:
            self.add_text_button.setEnabled(False)
            self.add_line_button.setEnabled(False)
            self.add_arrow_button.setEnabled(False)
            self.undo_button.setEnabled(False)
            self.preview_context_button.setEnabled(False)
            self.set_root_button.setEnabled(False)
            self.clear_root_button.setEnabled(False)
            self.send_button.setEnabled(False)
            self.instruction_input.setEnabled(False)

    def _workspace_selection_changed(self, _index: int) -> None:
        if self._refreshing_workspace_combo or self.canvas_module is None or self._active_threads:
            return
        workspace_id = str(self.workspace_combo.currentData() or "").strip()
        if not workspace_id or workspace_id == self.canvas_module.workspace_id:
            return
        try:
            descriptor = self.canvas_module.switch_workspace(workspace_id)
            snapshot = self.canvas_module.get_snapshot()
        except (CanvasStorageError, KeyError, ValueError) as exc:
            self._show_error("Could not switch Canvas workspace", exc)
            self._refresh_workspace_controls()
            return
        self.descriptor = descriptor
        self.instruction_input.clear()
        self._render_snapshot(snapshot)
        self._reset_view()
        self.status_label.setText(
            f"Opened '{descriptor.title}' with {len(snapshot.text_blocks)} blocks and "
            f"{len(snapshot.connectors)} connectors."
        )

    def _create_workspace(self) -> None:
        if self.canvas_module is None or self._active_threads:
            return
        title, accepted = QInputDialog.getText(
            self,
            "New Canvas Workspace",
            "Workspace title:",
        )
        if not accepted or not title.strip():
            return
        try:
            record = self.canvas_module.create_workspace(title)
            snapshot = self.canvas_module.get_snapshot()
        except (CanvasStorageError, ValueError) as exc:
            self._show_error("Could not create Canvas workspace", exc)
            return
        self._refresh_workspace_controls()
        self._render_snapshot(snapshot)
        self._reset_view()
        self.instruction_input.clear()
        self.status_label.setText(f"Created empty Canvas workspace '{record.title}'.")

    def _rename_workspace(self) -> None:
        if self.canvas_module is None or self._active_threads:
            return
        workspace_id = self.canvas_module.workspace_id
        current_title = self.workspace_combo.currentText().strip()
        title, accepted = QInputDialog.getText(
            self,
            "Rename Canvas Workspace",
            "Workspace title:",
            text=current_title,
        )
        if not accepted or not title.strip() or title.strip() == current_title:
            return
        try:
            updated = self.canvas_module.rename_workspace(workspace_id, title)
        except (CanvasStorageError, KeyError, ValueError) as exc:
            self._show_error("Could not rename Canvas workspace", exc)
            return
        self._refresh_workspace_controls()
        self.status_label.setText(f"Canvas workspace renamed to '{updated.title}'.")

    def _delete_workspace(self) -> None:
        if self.canvas_module is None or self._active_threads:
            return
        workspace_id = self.canvas_module.workspace_id
        title = self.workspace_combo.currentText().strip() or workspace_id
        answer = QMessageBox.question(
            self,
            "Delete Canvas Workspace",
            f"Archive '{title}' and remove it from the workspace list?\n\n"
            "Its JSON file will be kept in data/canvas/trash for recovery.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            descriptor = self.canvas_module.delete_workspace(workspace_id)
            snapshot = self.canvas_module.get_snapshot()
        except (CanvasStorageError, KeyError, ValueError) as exc:
            self._show_error("Could not delete Canvas workspace", exc)
            return
        self.descriptor = descriptor
        self._refresh_workspace_controls()
        self._render_snapshot(snapshot)
        self._reset_view()
        self.instruction_input.clear()
        self.status_label.setText(
            f"Workspace archived. Now using '{descriptor.title}'."
        )

    def _load_persisted_content(self) -> None:
        assert self.canvas_module is not None
        try:
            snapshot = self.canvas_module.get_snapshot()
        except CanvasStorageError as exc:
            self._set_storage_enabled(False)
            self.status_label.setText(f"Canvas data could not be loaded safely: {exc}")
            return
        self._render_snapshot(snapshot)
        self.status_label.setText(
            f"Loaded {len(snapshot.text_blocks)} blocks and {len(snapshot.connectors)} connectors. "
            f"Workspace revision: {snapshot.revision}. "
            f"Sent baseline: {snapshot.context_baseline.document_revision if snapshot.context_baseline else 'not set'}."
        )

    def _render_snapshot(self, snapshot) -> None:  # noqa: ANN001
        """Replace scene projections with one already-validated domain snapshot."""

        self._handling_connection_selection = True
        try:
            self._connection_mode = None
            self._pending_source_id = None
            self._right_click_source_id = None
            self.cancel_link_button.setEnabled(False)
            self.surface.viewport().unsetCursor()
            self.scene.clear()
            self._items_by_id.clear()
            self._connectors_by_id.clear()
            self._root_object_id = snapshot.root_object_id
            for block in snapshot.text_blocks:
                self._add_block_item(block)
            for connector in snapshot.connectors:
                self._add_connector_item(connector)
        finally:
            self._handling_connection_selection = False
        self._update_object_count()
        self._selection_changed()

    def _add_text_at_center(self) -> None:
        center = self.surface.mapToScene(self.surface.viewport().rect().center())
        self._create_text_block(center)

    def _create_text_block(self, scene_position: QPointF) -> None:
        if self.canvas_module is None:
            return
        dialog = CanvasTextEditorDialog(
            title="New Canvas Text",
            label="Write an idea or note:",
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        text = dialog.text()
        if not text:
            return
        try:
            block = self.canvas_module.create_text_block(
                text=text,
                position_x=scene_position.x() - 160.0,
                position_y=scene_position.y() - 90.0,
            )
        except (CanvasStorageError, ValueError) as exc:
            self._show_error("Could not create Canvas block", exc)
            return
        item = self._add_block_item(block)
        self.scene.clearSelection()
        item.setSelected(True)
        self.surface.centerOn(item)
        self._update_object_count()
        self.status_label.setText("Text block created and saved.")

    def _add_block_item(self, block: CanvasTextBlock) -> CanvasTextBlockItem:
        item = CanvasTextBlockItem(
            block,
            is_root=block.object_id == self._root_object_id,
            moved_callback=self._persist_movement,
            resized_callback=self._persist_resize,
            geometry_changed_callback=self._update_attached_connectors,
            edit_callback=self._edit_block,
            edit_title_callback=self._edit_title,
            edit_comment_callback=self._edit_comment,
            comment_moved_callback=self._persist_comment_anchor,
            comment_resized_callback=self._persist_comment_resize,
            quick_arrow_callback=self._handle_quick_arrow_click,
        )
        self._items_by_id[block.object_id] = item
        self.scene.addItem(item)
        return item

    def _add_connector_item(self, connector: CanvasConnector) -> CanvasConnectorItem:
        source_item = self._items_by_id[connector.source_object_id]
        target_item = self._items_by_id[connector.target_object_id]
        item = CanvasConnectorItem(
            connector,
            source_item=source_item,
            target_item=target_item,
            edit_callback=self._edit_connector,
        )
        self._connectors_by_id[connector.connector_id] = item
        self.scene.addItem(item)
        return item

    def _persist_movement(self, object_id: str, x: float, y: float) -> None:
        if self.canvas_module is None:
            return
        item = self._items_by_id.get(object_id)
        if item is None:
            return
        previous = item.block
        try:
            updated = self.canvas_module.update_text_block(object_id, position_x=x, position_y=y)
        except (CanvasStorageError, KeyError, ValueError) as exc:
            item.setPos(previous.position_x, previous.position_y)
            self._show_error("Could not save Canvas position", exc)
            return
        item.apply_model(updated)
        self._refresh_undo_state()
        self.status_label.setText("Block position saved; semantic connectors were unchanged.")

    def _persist_resize(self, object_id: str, width: float, height: float) -> None:
        if self.canvas_module is None:
            return
        item = self._items_by_id.get(object_id)
        if item is None:
            return
        previous = item.block
        try:
            updated = self.canvas_module.update_text_block(
                object_id,
                width=max(_MIN_BLOCK_WIDTH, width),
                height=max(_MIN_BLOCK_HEIGHT, height),
            )
        except (CanvasStorageError, KeyError, ValueError) as exc:
            item.apply_model(previous)
            self._show_error("Could not save Canvas block size", exc)
            return
        item.apply_model(updated)
        self._refresh_undo_state()
        self.status_label.setText("Block size saved. Resizing changes layout, not semantic context.")

    def _persist_comment_anchor(self, object_id: str, angle_degrees: float) -> None:
        if self.canvas_module is None:
            return
        item = self._items_by_id.get(object_id)
        if item is None:
            return
        previous = item.block
        try:
            updated = self.canvas_module.update_text_block(
                object_id,
                comment_anchor_degrees=angle_degrees,
            )
        except (CanvasStorageError, KeyError, ValueError) as exc:
            item.apply_model(previous)
            self._show_error("Could not save Canvas comment position", exc)
            return
        item.apply_model(updated)
        self._refresh_undo_state()
        self.status_label.setText("Comment position saved around the block perimeter.")

    def _persist_comment_resize(self, object_id: str, width: float, height: float) -> None:
        if self.canvas_module is None:
            return
        item = self._items_by_id.get(object_id)
        if item is None:
            return
        previous = item.block
        try:
            updated = self.canvas_module.update_text_block(
                object_id,
                comment_width=width,
                comment_height=height,
            )
        except (CanvasStorageError, KeyError, ValueError) as exc:
            item.apply_model(previous)
            self._show_error("Could not save Canvas comment size", exc)
            return
        item.apply_model(updated)
        self._refresh_undo_state()
        self.status_label.setText("Comment oval size saved.")

    def _update_attached_connectors(self, object_id: str) -> None:
        for connector_item in self._connectors_by_id.values():
            connector = connector_item.connector
            if object_id in {connector.source_object_id, connector.target_object_id}:
                connector_item.update_geometry()

    def _visible_object_ids(self) -> list[str]:
        viewport_rect = self.surface.visible_scene_rect()
        return [
            object_id
            for object_id, item in self._items_by_id.items()
            if item.sceneBoundingRect().intersects(viewport_rect)
        ]

    def _preview_context(self) -> None:
        if self.canvas_module is None:
            return
        mode = str(self.context_mode_combo.currentData())
        selected_blocks = self._selected_block_items()
        selected_connectors = self._selected_connector_items()
        branch_root_id = selected_blocks[0].object_id if selected_blocks else self._root_object_id
        try:
            package = self.canvas_module.build_context_preview(
                context_mode=mode,
                visible_object_ids=self._visible_object_ids(),
                selected_object_ids=[item.object_id for item in selected_blocks],
                selected_connector_ids=[item.connector_id for item in selected_connectors],
                branch_root_id=branch_root_id,
            )
        except (CanvasStorageError, ValueError) as exc:
            self._show_error("Could not build Canvas context", exc)
            return
        CanvasContextPreviewDialog(package, self).exec()
        if package.warnings:
            self.status_label.setText(package.warnings[0])
        else:
            self.status_label.setText(
                f"Context preview: {len(package.target_object_ids)} target block(s), "
                f"{len(package.supporting_object_ids)} supporting block(s), "
                f"about {package.estimated_tokens} tokens."
            )

    def _canvas_request_arguments(self) -> dict[str, object]:
        mode = str(self.context_mode_combo.currentData())
        selected_blocks = self._selected_block_items()
        selected_connectors = self._selected_connector_items()
        branch_root_id = selected_blocks[0].object_id if selected_blocks else self._root_object_id
        return {
            "instruction": self.instruction_input.text().strip(),
            "context_mode": mode,
            "visible_object_ids": self._visible_object_ids(),
            "selected_object_ids": [item.object_id for item in selected_blocks],
            "selected_connector_ids": [item.connector_id for item in selected_connectors],
            "branch_root_id": branch_root_id,
            "model_weight": str(self.model_weight_combo.currentData()),
        }

    def _model_weight_changed(self) -> None:
        weight = str(self.model_weight_combo.currentData() or DEFAULT_CANVAS_MODEL_WEIGHT)
        QSettings("Dato", "AMADEUS").setValue("canvas/model_weight", weight)
        model_name = CANVAS_MODEL_PROFILES.get(weight, CANVAS_MODEL_PROFILES[DEFAULT_CANVAS_MODEL_WEIGHT])
        self.status_label.setText(f"Canvas model set to {weight.title()} ({model_name}).")

    def _send_to_amadeus(self) -> None:
        if self.canvas_module is None or self._active_threads:
            return
        request = self._canvas_request_arguments()
        self._set_waiting(True)
        weight = str(self.model_weight_combo.currentData() or DEFAULT_CANVAS_MODEL_WEIGHT)
        model_name = CANVAS_MODEL_PROFILES.get(
            weight, CANVAS_MODEL_PROFILES[DEFAULT_CANVAS_MODEL_WEIGHT]
        )
        self.status_label.setText(
            f"AMADEUS is preparing Canvas context for {model_name}… Heavy models may take longer to load."
        )
        thread = QThread(self)
        worker = CanvasResponseWorker(self.core, request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.process_event.connect(self._handle_process_event)
        worker.finished.connect(self._handle_canvas_response)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._remove_worker(thread, worker))
        self._active_threads.append(thread)
        self._active_workers.append(worker)
        thread.start()

    def _handle_process_event(self, event: object) -> None:
        if not isinstance(event, dict):
            return
        title = event.get("title") if isinstance(event.get("title"), str) else "Canvas request"
        summary = event.get("summary") if isinstance(event.get("summary"), str) else ""
        self.status_label.setText(f"{title}: {summary}".strip())

    def _handle_canvas_response(self, result: object) -> None:
        response_block: CanvasTextBlock | None = None
        response_connector: CanvasConnector | None = None
        response_text = "AMADEUS returned an unreadable Canvas response."
        if isinstance(result, dict):
            if isinstance(result.get("response"), str):
                response_text = str(result["response"])
            raw_block = result.get("canvas_response_block")
            raw_connector = result.get("canvas_response_connector")
            try:
                if isinstance(raw_block, dict):
                    response_block = CanvasTextBlock.from_dict(raw_block)
                if isinstance(raw_connector, dict):
                    response_connector = CanvasConnector.from_dict(raw_connector)
            except (TypeError, ValueError):
                response_block = None
                response_connector = None

        if response_block is None:
            self.status_label.setText(response_text)
            self._set_waiting(False)
            QMessageBox.warning(self, "Canvas request failed", response_text)
            return

        block_item = self._items_by_id.get(response_block.object_id)
        if block_item is None:
            block_item = self._add_block_item(response_block)
        else:
            block_item.apply_model(response_block)
        if response_connector is not None and response_connector.connector_id not in self._connectors_by_id:
            self._add_connector_item(response_connector)
        self.scene.clearSelection()
        block_item.setSelected(True)
        self.surface.centerOn(block_item)
        self.instruction_input.clear()
        self._update_object_count()
        self.status_label.setText(
            "AMADEUS response was added to the Canvas. The successful send baseline was updated."
        )
        self._set_waiting(False)

    def _set_waiting(self, waiting: bool) -> None:
        self.surface.setDisabled(waiting)
        self.workspace_combo.setDisabled(waiting or self.canvas_module is None)
        self.new_workspace_button.setDisabled(waiting or self.canvas_module is None)
        self.rename_workspace_button.setDisabled(waiting or self.canvas_module is None)
        self.delete_workspace_button.setDisabled(waiting or self.canvas_module is None)
        self.add_text_button.setDisabled(waiting or self.canvas_module is None)
        self.add_line_button.setDisabled(waiting or self.canvas_module is None)
        self.add_arrow_button.setDisabled(waiting or self.canvas_module is None)
        self.context_mode_combo.setDisabled(waiting or self.canvas_module is None)
        self.preview_context_button.setDisabled(waiting or self.canvas_module is None)
        self.model_weight_combo.setDisabled(waiting or self.canvas_module is None)
        self.instruction_input.setDisabled(waiting or self.canvas_module is None)
        self.send_button.setDisabled(waiting or self.canvas_module is None)
        self.reset_view_button.setDisabled(waiting)
        self.undo_button.setDisabled(waiting or self.canvas_module is None or not self.canvas_module.can_undo())
        self.cancel_link_button.setDisabled(
            waiting or (self._connection_mode is None and self._right_click_source_id is None)
        )
        if waiting:
            self.edit_button.setDisabled(True)
            self.title_button.setDisabled(True)
            self.comment_button.setDisabled(True)
            self.delete_button.setDisabled(True)
            self.set_root_button.setDisabled(True)
            self.clear_root_button.setDisabled(True)
        else:
            self._selection_changed()
            self._refresh_undo_state()
            self._refresh_workspace_controls()

    def _remove_worker(self, thread: QThread, worker: CanvasResponseWorker) -> None:
        if thread in self._active_threads:
            self._active_threads.remove(thread)
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    def has_active_workers(self) -> bool:
        return bool(self._active_threads)

    def _set_selected_as_root(self) -> None:
        if self.canvas_module is None:
            return
        selected = self._selected_block_items()
        if len(selected) != 1:
            return
        object_id = selected[0].object_id
        try:
            self.canvas_module.set_root_object(object_id)
        except (CanvasStorageError, KeyError, ValueError) as exc:
            self._show_error("Could not set Canvas root", exc)
            return
        self._apply_root_state(object_id)
        self._refresh_undo_state()
        self.status_label.setText(
            "Canvas root saved. Incoming arrows will reconstruct directional history toward this block."
        )

    def _clear_root(self) -> None:
        if self.canvas_module is None or self._root_object_id is None:
            return
        try:
            self.canvas_module.set_root_object(None)
        except (CanvasStorageError, ValueError) as exc:
            self._show_error("Could not clear Canvas root", exc)
            return
        self._apply_root_state(None)
        self._refresh_undo_state()
        self.status_label.setText("Canvas root cleared.")

    def _apply_root_state(self, root_object_id: str | None) -> None:
        self._root_object_id = root_object_id
        for object_id, item in self._items_by_id.items():
            item.set_root_state(object_id == root_object_id)
        self.clear_root_button.setEnabled(
            root_object_id is not None
            and self.canvas_module is not None
            and not self._active_workspace_is_read_only()
        )

    def _start_connection_mode(self, connector_type: str) -> None:
        if self.canvas_module is None:
            return
        if len(self._items_by_id) < 2:
            self.status_label.setText("Create at least two text blocks before adding a connector.")
            return
        self._connection_mode = connector_type
        self._pending_source_id = None
        self._right_click_source_id = None
        self.cancel_link_button.setEnabled(True)
        self.surface.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.scene.clearSelection()
        noun = "arrow" if connector_type == "arrow" else "line"
        self.status_label.setText(f"Creating a {noun}: click the source block, then click the target block. Esc cancels.")

    def _cancel_connection_mode(self) -> None:
        if self._connection_mode is None and self._right_click_source_id is None:
            return
        self._connection_mode = None
        self._pending_source_id = None
        self._right_click_source_id = None
        self.cancel_link_button.setEnabled(False)
        self.surface.viewport().unsetCursor()
        self.status_label.setText("Connector creation cancelled.")

    def _handle_connection_selection(self) -> None:
        if self._connection_mode is None or self._handling_connection_selection:
            return
        selected_blocks = self._selected_block_items()
        if len(selected_blocks) != 1:
            return
        selected_id = selected_blocks[0].object_id
        if self._pending_source_id is None:
            self._pending_source_id = selected_id
            self.status_label.setText("Source selected. Click a different block to create the target connection.")
            return
        if selected_id == self._pending_source_id:
            self.status_label.setText("A block cannot connect to itself. Click a different target block.")
            return

        self._create_connection(
            source_object_id=self._pending_source_id,
            target_object_id=selected_id,
            connector_type=self._connection_mode,
        )

    def _handle_quick_arrow_click(self, object_id: str) -> None:
        """Create a directional arrow using two consecutive right-clicks."""

        if self.canvas_module is None or object_id not in self._items_by_id:
            return
        if self._active_threads:
            return
        if self._connection_mode is not None:
            self._connection_mode = None
            self._pending_source_id = None
            self.surface.viewport().unsetCursor()

        if self._right_click_source_id is None:
            self._right_click_source_id = object_id
            self.cancel_link_button.setEnabled(True)
            self._handling_connection_selection = True
            try:
                self.scene.clearSelection()
                self._items_by_id[object_id].setSelected(True)
            finally:
                self._handling_connection_selection = False
            self.status_label.setText(
                "Quick arrow source selected. Right-click a different block to create source → target."
            )
            return

        source_id = self._right_click_source_id
        if source_id == object_id:
            self._right_click_source_id = None
            self.cancel_link_button.setEnabled(False)
            self.status_label.setText("Quick arrow cancelled because the same block was right-clicked twice.")
            return

        self._create_connection(
            source_object_id=source_id,
            target_object_id=object_id,
            connector_type="arrow",
        )

    def _create_connection(
        self,
        *,
        source_object_id: str,
        target_object_id: str,
        connector_type: str,
    ) -> None:
        assert self.canvas_module is not None
        try:
            connector = self.canvas_module.create_connector(
                source_object_id=source_object_id,
                target_object_id=target_object_id,
                connector_type=connector_type,
            )
        except (CanvasStorageError, KeyError, ValueError) as exc:
            self._show_error("Could not create Canvas connector", exc)
            self._cancel_connection_mode()
            return

        self._handling_connection_selection = True
        try:
            connector_item = self._add_connector_item(connector)
            self._connection_mode = None
            self._pending_source_id = None
            self._right_click_source_id = None
            self.cancel_link_button.setEnabled(False)
            self.surface.viewport().unsetCursor()
            self.scene.clearSelection()
            connector_item.setSelected(True)
        finally:
            self._handling_connection_selection = False
        self._update_object_count()
        self.status_label.setText(
            "Connector created and saved. Double-click it to add a relation, label, or comment."
        )

    def _edit_selected_title(self) -> None:
        selected = self._selected_block_items()
        if len(selected) == 1:
            self._edit_title(selected[0].object_id)

    def _edit_selected_comment(self) -> None:
        selected = self._selected_block_items()
        if len(selected) == 1:
            self._edit_comment(selected[0].object_id)

    def _edit_selected(self) -> None:
        selected = self._selected_canvas_items()
        if len(selected) != 1:
            return
        item = selected[0]
        if isinstance(item, CanvasTextBlockItem):
            self._edit_block(item.object_id)
        elif isinstance(item, CanvasConnectorItem):
            self._edit_connector(item.connector_id)

    def _edit_block(self, object_id: str) -> None:
        if self.canvas_module is None:
            return
        item = self._items_by_id.get(object_id)
        if item is None:
            return
        dialog = CanvasTextEditorDialog(
            title="Edit Canvas Text",
            label="Update the idea or note:",
            initial_text=item.block.text,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        text = dialog.text()
        if not text or text == item.block.text:
            return
        try:
            updated = self.canvas_module.update_text_block(object_id, text=text)
        except (CanvasStorageError, KeyError, ValueError) as exc:
            self._show_error("Could not edit Canvas block", exc)
            return
        item.apply_model(updated)
        self._refresh_undo_state()
        self.status_label.setText("Text block edited and saved.")

    def _edit_title(self, object_id: str) -> None:
        if self.canvas_module is None:
            return
        item = self._items_by_id.get(object_id)
        if item is None:
            return
        title, accepted = QInputDialog.getText(
            self,
            "Canvas Block Title",
            "Optional title (leave empty to remove):",
            QLineEdit.EchoMode.Normal,
            item.block.title,
        )
        if not accepted or title.strip() == item.block.title:
            return
        try:
            updated = self.canvas_module.update_text_block(object_id, title=title)
        except (CanvasStorageError, KeyError, ValueError) as exc:
            self._show_error("Could not save Canvas title", exc)
            return
        item.apply_model(updated)
        self._refresh_undo_state()
        self.status_label.setText("Block title updated and attached above the box.")

    def _edit_comment(self, object_id: str) -> None:
        if self.canvas_module is None:
            return
        item = self._items_by_id.get(object_id)
        if item is None:
            return
        comment, accepted = QInputDialog.getMultiLineText(
            self,
            "Canvas Block Comment",
            "Optional comment (leave empty to remove):",
            item.block.comment,
        )
        if not accepted or comment.strip() == item.block.comment:
            return
        try:
            updated = self.canvas_module.update_text_block(object_id, comment=comment)
        except (CanvasStorageError, KeyError, ValueError) as exc:
            self._show_error("Could not save Canvas comment", exc)
            return
        item.apply_model(updated)
        self._refresh_undo_state()
        self.status_label.setText(
            "Block comment updated. Drag the oval around the box edge to reposition it."
        )

    def _edit_connector(self, connector_id: str) -> None:
        if self.canvas_module is None:
            return
        item = self._connectors_by_id.get(connector_id)
        if item is None:
            return
        dialog = ConnectorEditorDialog(item.connector, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        current = item.connector
        if (
            values["connector_type"] == current.connector_type
            and values["relation_type"] == current.relation_type
            and values["label"] == current.label
            and values["comment"] == current.comment
        ):
            return
        try:
            updated = self.canvas_module.update_connector(connector_id, **values)
        except (CanvasStorageError, KeyError, ValueError) as exc:
            self._show_error("Could not edit Canvas connector", exc)
            return
        item.apply_model(updated)
        self._refresh_undo_state()
        self.status_label.setText("Connector metadata edited and saved.")

    def _delete_selected(self) -> None:
        if self.canvas_module is None:
            return
        selected_blocks = self._selected_block_items()
        selected_connectors = self._selected_connector_items()
        if not selected_blocks and not selected_connectors:
            return

        object_ids = {item.object_id for item in selected_blocks}
        connector_ids = {item.connector_id for item in selected_connectors}
        attached_connector_ids = {
            connector_id
            for connector_id, item in self._connectors_by_id.items()
            if item.connector.source_object_id in object_ids or item.connector.target_object_id in object_ids
        }
        total_connector_ids = connector_ids | attached_connector_ids
        message = (
            f"Delete {len(object_ids)} selected block(s) and {len(total_connector_ids)} connector(s)? "
            "Attached connectors are removed automatically. Ctrl+Z can restore this change."
        )
        answer = QMessageBox.question(
            self,
            "Delete Canvas Items",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted_blocks, deleted_connectors = self.canvas_module.delete_items(
                object_ids=object_ids,
                connector_ids=connector_ids,
            )
        except CanvasStorageError as exc:
            self._show_error("Could not delete Canvas items", exc)
            return

        for connector_id in total_connector_ids:
            connector_item = self._connectors_by_id.pop(connector_id, None)
            if connector_item is not None:
                self.scene.removeItem(connector_item)
        for object_id in object_ids:
            block_item = self._items_by_id.pop(object_id, None)
            if block_item is not None:
                self.scene.removeItem(block_item)
        if self._root_object_id in object_ids:
            self._apply_root_state(None)
        self._update_object_count()
        self.status_label.setText(
            f"Deleted and saved {deleted_blocks} block(s) and {deleted_connectors} connector(s)."
        )

    def _undo_last_change(self) -> None:
        if self.canvas_module is None or self._active_threads:
            return
        center = self.surface.mapToScene(self.surface.viewport().rect().center())
        try:
            snapshot = self.canvas_module.undo_last_change()
        except CanvasStorageError as exc:
            self._show_error("Could not undo Canvas change", exc)
            return
        if snapshot is None:
            self.status_label.setText("There is no Canvas change to undo in this session.")
            self._refresh_undo_state()
            return
        self._render_snapshot(snapshot)
        self.surface.centerOn(center)
        self.status_label.setText(
            "Last Canvas change undone. Undo history is available for the current AMADEUS session."
        )

    def _refresh_undo_state(self) -> None:
        enabled = (
            self.canvas_module is not None
            and not self._active_threads
            and self.canvas_module.can_undo()
            and not self._active_workspace_is_read_only()
        )
        self.undo_button.setEnabled(enabled)

    def _selection_changed(self) -> None:
        if self._connection_mode is not None:
            self._handle_connection_selection()
        selected_items = self._selected_canvas_items()
        selected_count = len(selected_items)
        selected_block_count = len(self._selected_block_items())
        managed_selected = any(self._is_managed_projection_item(item) for item in selected_items)
        editable_selection = (
            not managed_selected
            and self.canvas_module is not None
            and not self._active_workspace_is_read_only()
        )
        self.edit_button.setEnabled(selected_count == 1 and editable_selection)
        self.title_button.setEnabled(selected_block_count == 1 and editable_selection)
        self.comment_button.setEnabled(selected_block_count == 1 and editable_selection)
        self.delete_button.setEnabled(selected_count > 0 and editable_selection)
        self.set_root_button.setEnabled(selected_block_count == 1 and editable_selection)
        self.clear_root_button.setEnabled(
            self._root_object_id is not None and editable_selection
        )
        if managed_selected or self._active_workspace_is_read_only():
            self.status_label.setText("Mind Map projection records are read-only in Canvas.")

    def _active_workspace_is_read_only(self) -> bool:
        return self.canvas_module is not None and self.canvas_module.is_read_only_workspace()

    def _selected_block_items(self) -> list[CanvasTextBlockItem]:
        return [item for item in self.scene.selectedItems() if isinstance(item, CanvasTextBlockItem)]

    def _selected_connector_items(self) -> list[CanvasConnectorItem]:
        return [item for item in self.scene.selectedItems() if isinstance(item, CanvasConnectorItem)]

    def _selected_canvas_items(self) -> list[CanvasTextBlockItem | CanvasConnectorItem]:
        return [
            item
            for item in self.scene.selectedItems()
            if isinstance(item, (CanvasTextBlockItem, CanvasConnectorItem))
        ]

    @staticmethod
    def _is_managed_projection_item(item: CanvasTextBlockItem | CanvasConnectorItem) -> bool:
        record = item.block if isinstance(item, CanvasTextBlockItem) else item.connector
        return record.metadata.get("mindmap_projection") is True

    def _reset_view(self) -> None:
        self.surface.resetTransform()
        if self._items_by_id:
            self.surface.fitInView(
                self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
            if self.surface.transform().m11() > 1.0:
                self.surface.resetTransform()
                self.surface.centerOn(self.scene.itemsBoundingRect().center())
        else:
            self.surface.centerOn(0.0, 0.0)

    def _update_object_count(self) -> None:
        blocks = len(self._items_by_id)
        connectors = len(self._connectors_by_id)
        self.object_count_label.setText(f"{blocks} blocks • {connectors} connectors")
        self._refresh_undo_state()

    def _set_storage_enabled(self, enabled: bool) -> None:
        self.workspace_combo.setEnabled(enabled)
        self.new_workspace_button.setEnabled(enabled)
        editable = enabled and not self._active_workspace_is_read_only()
        self.rename_workspace_button.setEnabled(editable and self.workspace_combo.count() > 0)
        self.delete_workspace_button.setEnabled(editable and self.workspace_combo.count() > 0)
        self.add_text_button.setEnabled(editable)
        self.add_line_button.setEnabled(editable)
        self.add_arrow_button.setEnabled(editable)
        self._right_click_source_id = None
        self.cancel_link_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.title_button.setEnabled(False)
        self.comment_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.undo_button.setEnabled(editable and self.canvas_module is not None and self.canvas_module.can_undo())
        self.context_mode_combo.setEnabled(editable)
        self.preview_context_button.setEnabled(editable)
        self.model_weight_combo.setEnabled(editable)
        self.set_root_button.setEnabled(False)
        self.clear_root_button.setEnabled(editable and self._root_object_id is not None)
        self.instruction_input.setEnabled(editable)
        self.send_button.setEnabled(editable)

    def _show_error(self, title: str, error: Exception) -> None:
        self.status_label.setText(str(error))
        QMessageBox.warning(self, title, str(error))
