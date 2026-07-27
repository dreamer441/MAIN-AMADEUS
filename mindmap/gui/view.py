"""Interactive PyQt6 surface for the AMADEUS Mind Map module."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QEventLoop, QObject, QRectF, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mindmap.gui.items import GraphLinkItem, GraphNodeItem
from mindmap.models import GraphLink, GraphNode, GraphSnapshot


NODE_TYPES = (
    "idea",
    "task",
    "decision",
    "feature",
    "bug",
    "reference",
    "container",
    "chat",
    "sheet",
    "material",
    "memory",
    "custom",
)

LINK_TYPES = (
    "related_to",
    "contains",
    "part_of",
    "depends_on",
    "supports",
    "contradicts",
    "derived_from",
    "references",
    "caused_by",
    "solves",
)


class MindMapCanvas(QGraphicsView):
    """Zoomable canvas that keeps graph rendering independent from storage."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setSceneRect(QRectF(-5000, -5000, 10000, 10000))

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt naming.
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class MindMapWorker(QObject):
    """Run one Core graph operation without blocking Qt's GUI event loop."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self.operation = operation

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.finished.emit(self.operation())
        except Exception as error:
            self.failed.emit(str(error))


class NodeDialog(QDialog):
    """Collect the minimum meaningful node properties for V1."""

    def __init__(self, parent: QWidget | None = None, node: GraphNode | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Node" if node else "Create Node")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_input = QLineEdit(node.title if node else "")
        self.type_input = QComboBox()
        self.type_input.setEditable(True)
        self.type_input.addItems(NODE_TYPES)
        self.type_input.setCurrentText(node.node_type if node else "idea")
        self.description_input = QTextEdit(node.description if node else "")
        self.description_input.setMaximumHeight(100)
        self.content_input = QTextEdit(node.content if node else "")
        self.content_input.setMaximumHeight(120)
        self.importance_input = self._unit_spin(node.importance if node else 0.5)
        self.confidence_input = self._unit_spin(node.confidence if node else 1.0)
        self.locked_input = QCheckBox()
        self.locked_input.setChecked(node.position_locked if node else False)

        form.addRow("Title:", self.title_input)
        form.addRow("Type:", self.type_input)
        form.addRow("Description:", self.description_input)
        form.addRow("Content:", self.content_input)
        form.addRow("Importance:", self.importance_input)
        form.addRow("Confidence:", self.confidence_input)
        form.addRow("Lock position:", self.locked_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Any]:
        return {
            "title": self.title_input.text().strip(),
            "node_type": self.type_input.currentText().strip(),
            "description": self.description_input.toPlainText().strip(),
            "content": self.content_input.toPlainText().strip(),
            "importance": self.importance_input.value(),
            "confidence": self.confidence_input.value(),
            "position_locked": self.locked_input.isChecked(),
        }

    def _unit_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 1.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.05)
        spin.setValue(value)
        return spin


class LinkDialog(QDialog):
    """Collect first-class relationship properties."""

    def __init__(self, parent: QWidget | None = None, link: GraphLink | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Link" if link else "Create Link")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_input = QComboBox()
        self.type_input.setEditable(True)
        self.type_input.addItems(LINK_TYPES)
        self.type_input.setCurrentText(link.link_type if link else "related_to")
        self.label_input = QLineEdit(link.label if link else "")
        self.strength_input = self._unit_spin(link.strength if link else 0.5)
        self.confidence_input = self._unit_spin(link.confidence if link else 1.0)
        self.permanence_input = self._unit_spin(link.permanence if link else 0.5)
        self.evidence_input = QTextEdit(link.evidence if link else "")
        self.evidence_input.setMaximumHeight(100)
        self.temporary_input = QCheckBox()
        self.temporary_input.setChecked(link.is_temporary if link else False)

        form.addRow("Relationship:", self.type_input)
        form.addRow("Visible label:", self.label_input)
        form.addRow("Strength:", self.strength_input)
        form.addRow("Confidence:", self.confidence_input)
        form.addRow("Permanence:", self.permanence_input)
        form.addRow("Evidence:", self.evidence_input)
        form.addRow("Temporary:", self.temporary_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Any]:
        return {
            "link_type": self.type_input.currentText().strip(),
            "label": self.label_input.text().strip(),
            "strength": self.strength_input.value(),
            "confidence": self.confidence_input.value(),
            "permanence": self.permanence_input.value(),
            "evidence": self.evidence_input.toPlainText().strip(),
            "is_temporary": self.temporary_input.isChecked(),
        }

    def _unit_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 1.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.05)
        spin.setValue(value)
        return spin


class MindMapView(QWidget):
    """Main Mind Map page; all mutations route through AMADEUS Core."""

    graph_changed = pyqtSignal(object)
    worker_succeeded = pyqtSignal(object, object)
    worker_failed = pyqtSignal(str, str)
    worker_finished = pyqtSignal(object, object)

    def __init__(self, core: object, parent: QWidget | None = None, *, refresh_on_init: bool = True) -> None:
        super().__init__(parent)
        self.core = core
        self.scene = QGraphicsScene(self)
        self.canvas = MindMapCanvas(self.scene, self)
        self.node_items: dict[str, GraphNodeItem] = {}
        self.link_items: dict[str, GraphLinkItem] = {}
        self._refreshing = False
        self._busy = False
        self._refresh_pending = False
        self._after_refresh: list[Callable[[], None]] = []
        self._active_threads: list[QThread] = []
        self._active_workers: list[MindMapWorker] = []

        self._build_ui()
        self.scene.selectionChanged.connect(self._show_selection)
        self.graph_changed.connect(lambda _event: self.refresh_graph())
        self.worker_succeeded.connect(self._dispatch_worker_success)
        self.worker_failed.connect(self._handle_worker_failure)
        self.worker_finished.connect(self._finish_worker)
        subscribe = getattr(self.core, "subscribe_mind_map", None)
        if callable(subscribe):
            subscribe(self.graph_changed.emit)
        if refresh_on_init:
            self.refresh_graph()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title_row = QHBoxLayout()
        title = QLabel("Mind Map / Relevance Graph")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #667085;")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.status_label)

        toolbar = QHBoxLayout()
        new_node = QPushButton("New Node")
        new_node.clicked.connect(self._create_node)
        connect_nodes = QPushButton("Connect Selected")
        connect_nodes.clicked.connect(self._connect_selected)
        edit_selected = QPushButton("Edit Selected")
        edit_selected.clicked.connect(self._edit_selected)
        delete_selected = QPushButton("Delete Selected")
        delete_selected.clicked.connect(self._delete_selected)
        auto_layout = QPushButton("Auto Layout")
        auto_layout.clicked.connect(self._auto_layout)
        fit_button = QPushButton("Fit Graph")
        fit_button.clicked.connect(self._fit_graph)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_graph)
        export_button = QPushButton("Export JSON")
        export_button.clicked.connect(self._export_graph)
        import_button = QPushButton("Import JSON")
        import_button.clicked.connect(self._import_graph)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search title, type, description, content...")
        self.search_input.returnPressed.connect(self._search)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self._search)

        self._busy_widgets = (
            new_node,
            connect_nodes,
            edit_selected,
            delete_selected,
            auto_layout,
            fit_button,
            refresh_button,
            export_button,
            import_button,
            self.search_input,
            search_button,
        )
        for widget in self._busy_widgets:
            toolbar.addWidget(widget)
        toolbar.addStretch()
        toolbar.addWidget(self.search_input)
        toolbar.addWidget(search_button)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.canvas)
        splitter.addWidget(self._build_properties_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 280])

        root.addLayout(title_row)
        root.addLayout(toolbar)
        root.addWidget(splitter)

    def _build_properties_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        heading = QLabel("Selected Object")
        heading.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.selection_summary = QTextEdit()
        self.selection_summary.setReadOnly(True)
        self.selection_summary.setPlaceholderText(
            "Select a node or relationship to inspect its persisted properties."
        )
        layout.addWidget(heading)
        layout.addWidget(self.selection_summary)
        return panel

    def refresh_graph(self) -> None:
        if self._refreshing or self._busy:
            self._refresh_pending = True
            return
        self._refreshing = True
        self._run_core(self.core.get_mind_map_snapshot, self._render_snapshot, "Refreshing graph")

    def _render_snapshot(self, snapshot: object) -> None:
        selected_node_ids = {
            item.node_id for item in self.scene.selectedItems() if isinstance(item, GraphNodeItem)
        }
        selected_link_ids = {
            item.link_id for item in self.scene.selectedItems() if isinstance(item, GraphLinkItem)
        }
        try:
            if not isinstance(snapshot, GraphSnapshot):
                raise ValueError("Core returned an invalid mind map snapshot")
            for item in self.link_items.values():
                item.detach()
            self.scene.clear()
            self.node_items.clear()
            self.link_items.clear()

            for node in snapshot.nodes:
                item = GraphNodeItem(node, moved_callback=self._persist_node_position)
                self.scene.addItem(item)
                self.node_items[node.node_id] = item

            for link in snapshot.links:
                source = self.node_items.get(link.source_node_id)
                target = self.node_items.get(link.target_node_id)
                if source is None or target is None:
                    continue
                item = GraphLinkItem(link, source, target)
                self.scene.addItem(item)
                self.link_items[link.link_id] = item

            for node_id in selected_node_ids:
                if node_id in self.node_items:
                    self.node_items[node_id].setSelected(True)
            for link_id in selected_link_ids:
                if link_id in self.link_items:
                    self.link_items[link_id].setSelected(True)

            self.status_label.setText(
                f"{len(snapshot.nodes)} nodes · {len(snapshot.links)} links · SQLite saved"
            )
            if snapshot.nodes and not selected_node_ids and not selected_link_ids:
                self._fit_graph()
        except Exception as error:
            self._show_error("Mind Map refresh failed", error)
        finally:
            self._refreshing = False
        callbacks, self._after_refresh = self._after_refresh, []
        for callback in callbacks:
            callback()

    def _run_core(
        self,
        operation: Callable[[], object],
        on_success: Callable[[object], None],
        busy_text: str,
        *,
        error_title: str | None = None,
    ) -> None:
        """Use the established worker lifecycle; slots update Qt widgets on the GUI thread."""
        if self._busy:
            self._refresh_pending = True
            return
        self._set_busy(True, busy_text)
        thread = QThread(self)
        worker = MindMapWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda result: self.worker_succeeded.emit(on_success, result))
        # Quit directly from the worker thread so shutdown does not depend on a
        # GUI event-loop turn (important while windows are being closed).
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(lambda message: self.worker_failed.emit(error_title or busy_text, message))
        worker.failed.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self.worker_finished.emit(thread, worker))
        self._active_threads.append(thread)
        self._active_workers.append(worker)
        thread.start()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        for widget in self._busy_widgets:
            widget.setEnabled(not busy)
        if busy:
            self.status_label.setText(message)

    def _dispatch_worker_success(self, callback: Callable[[object], None], result: object) -> None:
        callback(result)

    def _finish_worker(self, thread: QThread, worker: MindMapWorker) -> None:
        if thread in self._active_threads:
            self._active_threads.remove(thread)
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        self._set_busy(False)
        if self._refresh_pending:
            self._refresh_pending = False
            self.refresh_graph()

    def has_active_workers(self) -> bool:
        """Report whether this view still owns graph-operation threads."""
        return bool(self._active_threads)

    def shutdown_workers(self) -> None:
        """Join owned workers before their view can be destroyed.

        A graph operation cannot safely outlive its Qt view because its completion
        signals target that view. A nested Qt loop, rather than ``QThread.wait()``,
        lets the worker retain the Python interpreter while it completes.
        """
        for thread in tuple(self._active_threads):
            if thread.isRunning():
                loop = QEventLoop(self)
                thread.finished.connect(loop.quit)
                loop.exec()
        self._active_threads.clear()
        self._active_workers.clear()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt uses camelCase names.
        self.shutdown_workers()
        super().closeEvent(event)

    def _handle_worker_failure(self, title: str, message: str) -> None:
        self._refreshing = False
        self._show_error(title, RuntimeError(message))

    def _refresh_then(self, callback: Callable[[], None]) -> None:
        self._after_refresh.append(callback)
        self.refresh_graph()

    def _create_node(self) -> None:
        dialog = NodeDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["title"]:
            QMessageBox.warning(self, "Missing title", "A mind map node needs a title.")
            return
        center = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        self._run_core(
            lambda: self.core.create_mind_map_node(**values, position_x=center.x(), position_y=center.y()),
            lambda node: self._refresh_then(lambda: self._select_node(node.node_id)),
            "Creating node",
        )

    def _connect_selected(self) -> None:
        nodes = [item for item in self.scene.selectedItems() if isinstance(item, GraphNodeItem)]
        if len(nodes) != 2:
            QMessageBox.information(
                self,
                "Select two nodes",
                "Select exactly two nodes, then choose Connect Selected.",
            )
            return
        nodes.sort(key=lambda item: item.node.title.lower())
        source_options = {
            f"{item.node.title} [{item.node_id[:8]}]": item for item in nodes
        }
        source_label, accepted = QInputDialog.getItem(
            self,
            "Choose relationship direction",
            "Source node:",
            list(source_options),
            0,
            False,
        )
        if not accepted:
            return
        source = source_options[source_label]
        target = nodes[1] if source is nodes[0] else nodes[0]
        dialog = LinkDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._run_core(
            lambda: self.core.create_mind_map_link(
                source_node_id=source.node_id, target_node_id=target.node_id, **values
            ),
            lambda link: self._refresh_then(lambda: self._select_link(link.link_id)),
            "Creating link",
        )

    def _edit_selected(self) -> None:
        selected = self.scene.selectedItems()
        if len(selected) != 1:
            QMessageBox.information(self, "Select one object", "Select exactly one node or link to edit.")
            return
        item = selected[0]
        if isinstance(item, GraphNodeItem):
            dialog = NodeDialog(self, item.node)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                values = dialog.values()
                self._run_core(
                    lambda: self.core.update_mind_map_node(item.node_id, **values),
                    lambda _result: self._refresh_then(lambda: self._select_node(item.node_id)),
                    "Updating node",
                )
        elif isinstance(item, GraphLinkItem):
            dialog = LinkDialog(self, item.link)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                values = dialog.values()
                self._run_core(
                    lambda: self.core.update_mind_map_link(item.link_id, **values),
                    lambda _result: self._refresh_then(lambda: self._select_link(item.link_id)),
                    "Updating link",
                )

    def _delete_selected(self) -> None:
        selected = self.scene.selectedItems()
        if not selected:
            return
        if QMessageBox.question(
            self,
            "Delete graph objects",
            "Delete the selected graph objects? Deleting a node also deletes its connected links.",
        ) != QMessageBox.StandardButton.Yes:
            return
        link_ids = [item.link_id for item in selected if isinstance(item, GraphLinkItem)]
        node_ids = [item.node_id for item in selected if isinstance(item, GraphNodeItem)]

        def delete_selected() -> None:
            for link_id in link_ids:
                self.core.delete_mind_map_link(link_id)
            for node_id in node_ids:
                self.core.delete_mind_map_node(node_id)

        self._run_core(delete_selected, lambda _result: self.refresh_graph(), "Deleting graph objects")

    def _persist_node_position(self, node_id: str, x: float, y: float) -> None:
        if self._refreshing:
            return
        if not self._busy:
            self._run_core(
                lambda: self.core.move_mind_map_node(node_id, x, y),
                lambda _result: None,
                "Saving position",
                error_title="Position save failed",
            )

    def _auto_layout(self) -> None:
        nodes = list(self.node_items.values())
        if not nodes:
            return
        unlocked = [item for item in nodes if not item.node.position_locked]
        if not unlocked:
            self.status_label.setText("All node positions are locked.")
            return
        radius = max(220.0, len(unlocked) * 42.0)
        positions = []
        for index, item in enumerate(unlocked):
            angle = 2 * math.pi * index / max(1, len(unlocked))
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            positions.append((item.node_id, x, y))

        def save_layout() -> None:
            for node_id, x, y in positions:
                self.core.move_mind_map_node(node_id, x, y)

        self._run_core(save_layout, lambda _result: self._refresh_then(self._fit_graph), "Saving auto layout")

    def _search(self) -> None:
        query = self.search_input.text().strip()
        self._run_core(lambda: self.core.search_mind_map_nodes(query), self._show_search_results, "Searching graph")

    def _show_search_results(self, matches: object) -> None:
        if not isinstance(matches, list):
            self._show_error("Mind Map search failed", ValueError("Core returned invalid search results"))
            return
        self.scene.clearSelection()
        visible_items = [self.node_items[node.node_id] for node in matches if node.node_id in self.node_items]
        for item in visible_items:
            item.setSelected(True)
        if visible_items:
            bounds = visible_items[0].sceneBoundingRect()
            for item in visible_items[1:]:
                bounds = bounds.united(item.sceneBoundingRect())
            self.canvas.fitInView(bounds.adjusted(-80, -80, 80, 80), Qt.AspectRatioMode.KeepAspectRatio)
            self.status_label.setText(f"{len(visible_items)} search matches")
        else:
            self.status_label.setText("No matching nodes")

    def _fit_graph(self) -> None:
        bounds = self.scene.itemsBoundingRect()
        if not bounds.isNull():
            self.canvas.fitInView(bounds.adjusted(-80, -80, 80, 80), Qt.AspectRatioMode.KeepAspectRatio)

    def _export_graph(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Mind Map",
            "amadeus_mind_map.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        self._run_core(
            lambda: self.core.export_mind_map(path),
            lambda saved_path: self.status_label.setText(f"Exported: {saved_path}"),
            "Exporting graph",
        )

    def _import_graph(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Import Mind Map",
            "",
            "JSON Files (*.json)",
        )
        if not path:
            return
        replace_graph = QMessageBox.question(
            self,
            "Import mode",
            "Replace the current graph before importing? Choose No to merge as new objects.",
        ) == QMessageBox.StandardButton.Yes
        self._run_core(
            lambda: self.core.import_mind_map(path, replace_graph=replace_graph),
            lambda _result: self._refresh_then(self._fit_graph),
            "Importing graph",
        )

    def _show_selection(self) -> None:
        selected = self.scene.selectedItems()
        if len(selected) != 1:
            self.selection_summary.setPlainText(
                f"{len(selected)} objects selected." if selected else "No graph object selected."
            )
            return
        item = selected[0]
        if isinstance(item, GraphNodeItem):
            node = item.node
            source = (
                f"{node.source_reference.source_type}:{node.source_reference.source_id}"
                if node.source_reference else "manual"
            )
            self.selection_summary.setPlainText(
                f"NODE\n\nTitle: {node.title}\nType: {node.node_type}\nStatus: {node.status}\n"
                f"Importance: {node.importance:.2f}\nConfidence: {node.confidence:.2f}\n"
                f"Position: ({node.position_x:.1f}, {node.position_y:.1f})\n"
                f"Locked: {node.position_locked}\nSource: {source}\n\n"
                f"Description:\n{node.description or '—'}\n\nContent:\n{node.content or '—'}"
            )
        elif isinstance(item, GraphLinkItem):
            link = item.link
            self.selection_summary.setPlainText(
                f"LINK\n\nType: {link.link_type}\nLabel: {link.label or '—'}\n"
                f"Strength: {link.strength:.2f}\nConfidence: {link.confidence:.2f}\n"
                f"Permanence: {link.permanence:.2f}\nTemporary: {link.is_temporary}\n"
                f"Usage count: {link.usage_count}\nReward: {link.reward_score:.2f}\n"
                f"Punishment: {link.punishment_score:.2f}\n\nEvidence:\n{link.evidence or '—'}"
            )

    def _select_node(self, node_id: str) -> None:
        self.scene.clearSelection()
        item = self.node_items.get(node_id)
        if item is not None:
            item.setSelected(True)
            self.canvas.centerOn(item)

    def _select_link(self, link_id: str) -> None:
        self.scene.clearSelection()
        item = self.link_items.get(link_id)
        if item is not None:
            item.setSelected(True)
            self.canvas.centerOn(item)

    def _show_error(self, title: str, error: Exception) -> None:
        QMessageBox.critical(self, title, str(error))
        self.status_label.setText(str(error))
