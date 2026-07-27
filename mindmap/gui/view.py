"""Interactive PyQt6 surface for the AMADEUS Mind Map module."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QEventLoop, QObject, QRectF, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mindmap.gui.items import GraphLinkItem, GraphNodeItem
from mindmap.gui.physics import GraphPhysics
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
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setSceneRect(QRectF(-5000, -5000, 10000, 10000))

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt naming.
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt naming.
        item = self.itemAt(event.pos())
        if isinstance(item, GraphNodeItem):
            self.centerOn(item)
        super().mouseDoubleClickEvent(event)


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

    MAX_LIVE_SIMULATION_NODES = 120
    MAX_AUTO_LAYOUT_NODES = 80
    PHYSICS_INTERVAL_MS = 33
    PHYSICS_SETTLE_DISTANCE = 0.15
    PHYSICS_SETTLE_TICKS = 4
    PHYSICS_MAX_TICKS = 240

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
        self._nodes_by_id: dict[str, GraphNode] = {}
        self.physics: GraphPhysics | None = None
        self._layout_signature: tuple[object, ...] | None = None
        self._physics_ticks = 0
        self._settled_physics_ticks = 0
        self._physics_timer = QTimer(self)
        self._physics_timer.setInterval(self.PHYSICS_INTERVAL_MS)
        self._physics_timer.timeout.connect(self._advance_physics)
        self._refreshing = False
        self._busy = False
        self._refresh_pending = False
        self._after_refresh: list[Callable[[], None]] = []
        self._active_threads: list[QThread] = []
        self._active_workers: list[MindMapWorker] = []
        self._unsubscribe_graph_notifications: Callable[[], None] | None = None

        self._build_ui()
        self.scene.selectionChanged.connect(self._show_selection)
        self.graph_changed.connect(lambda _event: self.refresh_graph())
        self.worker_succeeded.connect(self._dispatch_worker_success)
        self.worker_failed.connect(self._handle_worker_failure)
        self.worker_finished.connect(self._finish_worker)
        self.destroyed.connect(self._unsubscribe_graph_changes)
        subscribe = getattr(self.core, "subscribe_mind_map", None)
        if callable(subscribe):
            unsubscribe = subscribe(self.graph_changed.emit)
            if callable(unsubscribe):
                self._unsubscribe_graph_notifications = unsubscribe
        if refresh_on_init:
            self.refresh_graph()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        title = QLabel("AMADEUS Mind Map")
        title.setObjectName("MindMapTitle")
        subtitle = QLabel(
            "This space shows AMADEUS chats, memories, features, tasks, bugs, sheets, materials, and links."
        )
        subtitle.setObjectName("MindMapSubtitle")
        subtitle.setWordWrap(True)

        panels = QHBoxLayout()
        panels.setSpacing(12)
        left_panel = self._create_panel("Mind Map")
        left_panel.layout().addWidget(self._build_left_panel())
        center_panel = self._create_panel("Graph Space")
        center_panel.layout().addWidget(self.canvas, 1)
        right_panel = self._create_panel("Context / Node Details")
        right_panel.layout().addWidget(self._build_properties_panel())
        panels.addWidget(left_panel, 1)
        panels.addWidget(center_panel, 3)
        panels.addWidget(right_panel, 2)

        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("MindMapStatus")
        self._busy_widgets = (*self.action_buttons.values(), self.search_input, self.search_button)
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addLayout(panels, 1)
        root.addWidget(self.status_label)
        self._apply_styles()

    def _create_panel(self, title: str) -> QFrame:
        """Create one legacy-compatible framed workspace panel."""
        panel = QFrame()
        panel.setObjectName("MindMapPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        header = QLabel(title)
        header.setObjectName("PanelHeader")
        layout.addWidget(header)
        return panel

    def _apply_styles(self) -> None:
        """Apply the legacy Mind Map palette without changing application-wide styling."""
        self.setStyleSheet(
            """
            QWidget { background-color: #050505; color: #f2f2f2; }
            QLabel#MindMapTitle { font-family: Segoe UI; font-size: 26px; font-weight: 800; color: #ffffff; }
            QLabel#MindMapSubtitle { font-family: Segoe UI; font-size: 13px; color: #aaaaaa; }
            QLabel#MindMapStatus { font-family: Segoe UI; font-size: 12px; color: #bbbbbb; padding: 4px 2px; }
            QFrame#MindMapPanel { background-color: #0b0b0b; border: 1px solid #333333; border-radius: 12px; padding: 10px; }
            QLabel#PanelHeader { font-family: Segoe UI; font-size: 14px; font-weight: 700; color: #f2f2f2; }
            QListWidget, QTextEdit, QLineEdit, QTabWidget::pane { background-color: #111111; color: #ffffff; border: 1px solid #444444; border-radius: 10px; padding: 8px; font-family: Segoe UI; font-size: 13px; }
            QTabBar::tab { background-color: #171717; color: #dddddd; border: 1px solid #333333; border-bottom: none; padding: 7px 12px; border-top-left-radius: 8px; border-top-right-radius: 8px; font-family: Segoe UI; }
            QTabBar::tab:selected { background-color: #242424; color: #ffffff; }
            QPushButton { background-color: #171717; color: #f2f2f2; border: 1px solid #444444; border-radius: 7px; padding: 7px 10px; font-family: Segoe UI; font-size: 13px; }
            QPushButton:hover { background-color: #242424; border-color: #666666; }
            QPushButton:disabled { color: #777777; border-color: #292929; }
            QGraphicsView { background-color: #111111; border: 1px solid #444444; border-radius: 10px; }
            """
        )

    def _build_left_panel(self) -> QWidget:
        """Build navigation and actions without exposing graph storage to widgets."""
        tabs = QTabWidget()
        self.left_tabs = tabs
        nodes_tab = QWidget()
        nodes_layout = QVBoxLayout(nodes_tab)
        nodes_layout.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search graph...")
        self.search_input.returnPressed.connect(self._search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._search)
        search_row = QHBoxLayout()
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_button)
        self.node_list = QListWidget()
        self.node_list.currentItemChanged.connect(self._select_list_node)
        nodes_layout.addLayout(search_row)
        nodes_layout.addWidget(self.node_list)
        tabs.addTab(nodes_tab, "Nodes")

        actions_tab = QWidget()
        actions_layout = QVBoxLayout(actions_tab)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions = (
            ("Edit Selected", self._edit_selected), ("Pin Node", self._toggle_pin),
            ("Set as Central", self._toggle_central), ("Recenter Linked", self._recenter_linked),
            ("Focus Selected", self._focus_selected),
            ("New Node", self._create_node), ("Delete Selected", self._delete_selected),
            ("Link Selected", self._link_selected_node), ("Unlink Selected", self._unlink_selected_node),
            ("Force Layout", self._auto_layout), ("Fit Graph", self._fit_graph), ("Refresh", self.refresh_graph),
            ("Export JSON", self._export_graph), ("Import JSON", self._import_graph),
        )
        self.action_buttons: dict[str, QPushButton] = {}
        for index, (label, callback) in enumerate(actions):
            if index == 0:
                actions_layout.addWidget(QLabel("Selected Node"))
            if index == 5:
                actions_layout.addSpacing(10)
                actions_layout.addWidget(QLabel("Graph Editing"))
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions_layout.addWidget(button)
            self.action_buttons[label] = button
        actions_layout.addStretch()
        tabs.addTab(actions_tab, "Actions")
        return tabs

    def _build_properties_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        self.right_tabs = tabs
        self.context_summary = QTextEdit()
        self.context_summary.setReadOnly(True)
        self.context_summary.setPlaceholderText("Hover or select a node to preview its stored graph context.")
        self.selection_summary = QTextEdit()
        self.selection_summary.setReadOnly(True)
        self.selection_summary.setPlaceholderText(
            "Select a node or relationship to inspect its persisted properties."
        )
        tabs.addTab(self.context_summary, "Context")
        tabs.addTab(self.selection_summary, "Node Details")
        layout.addWidget(tabs)
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
            self._stop_physics_motion()
            self._nodes_by_id = {node.node_id: node for node in snapshot.nodes}
            new_node_ids = set(self._nodes_by_id)
            new_links_by_id = {link.link_id: link for link in snapshot.links}
            layout_signature = self._physics_signature(snapshot)
            topology_changed = layout_signature != self._layout_signature
            projected_physics = GraphPhysics(snapshot)

            # Links must leave before their endpoint items can be removed.
            for link_id, item in tuple(self.link_items.items()):
                link = new_links_by_id.get(link_id)
                if link is None or (
                    link.source_node_id != item.link.source_node_id
                    or link.target_node_id != item.link.target_node_id
                ):
                    item.detach()
                    self.scene.removeItem(item)
                    del self.link_items[link_id]
            for node_id, item in tuple(self.node_items.items()):
                if node_id not in new_node_ids:
                    self.scene.removeItem(item)
                    del self.node_items[node_id]
            for node in snapshot.nodes:
                item = self.node_items.get(node.node_id)
                if item is None:
                    item = GraphNodeItem(
                        node,
                        moved_callback=self._persist_node_position,
                        hover_callback=self._show_hover_context,
                        relevance=projected_physics.nodes[node.node_id].relevance,
                    )
                    self.scene.addItem(item)
                    self.node_items[node.node_id] = item
                else:
                    item.update_node(node, projected_physics.nodes[node.node_id].relevance)

            for link in snapshot.links:
                item = self.link_items.get(link.link_id)
                if item is None:
                    source = self.node_items.get(link.source_node_id)
                    target = self.node_items.get(link.target_node_id)
                    if source is None or target is None:
                        continue
                    item = GraphLinkItem(link, source, target)
                    self.scene.addItem(item)
                    self.link_items[link.link_id] = item
                else:
                    item.update_link(link)

            self.physics = projected_physics
            self._layout_signature = layout_signature

            for node_id in selected_node_ids:
                if node_id in self.node_items:
                    self.node_items[node_id].setSelected(True)
            for link_id in selected_link_ids:
                if link_id in self.link_items:
                    self.link_items[link_id].setSelected(True)

            self.status_label.setText(
                f"{len(snapshot.nodes)} nodes · {len(snapshot.links)} links · SQLite saved"
            )
            self._populate_node_list(snapshot.nodes)
            if snapshot.nodes and not selected_node_ids and not selected_link_ids:
                self._fit_graph()
            if topology_changed:
                self._start_physics_motion()
        except Exception as error:
            self._show_error("Mind Map refresh failed", error)
        finally:
            self._refreshing = False
        callbacks, self._after_refresh = self._after_refresh, []
        for callback in callbacks:
            callback()

    @staticmethod
    def _physics_signature(snapshot: GraphSnapshot) -> tuple[object, ...]:
        """Return fields that require a fresh visual force projection."""
        return (
            tuple(
                sorted(
                    (
                        node.node_id,
                        node.importance,
                        node.confidence,
                        node.position_locked,
                        bool(node.metadata.get("mindmap_pinned", False)),
                        bool(node.metadata.get("mindmap_central", False)),
                    )
                    for node in snapshot.nodes
                )
            ),
            tuple(
                sorted(
                    (link.link_id, link.source_node_id, link.target_node_id, link.strength)
                    for link in snapshot.links
                )
            ),
        )

    def _start_physics_motion(self) -> None:
        """Start bounded visual-only motion for graphs safe to simulate in the GUI."""
        if self.physics is None or len(self.physics.nodes) < 2:
            return
        if len(self.physics.nodes) > self.MAX_LIVE_SIMULATION_NODES:
            self.status_label.setText(
                f"{len(self.physics.nodes)} nodes · live motion paused above {self.MAX_LIVE_SIMULATION_NODES} nodes"
            )
            return
        self._physics_ticks = 0
        self._settled_physics_ticks = 0
        self._physics_timer.start()

    def _advance_physics(self) -> None:
        """Apply one inexpensive visual physics tick and stop after stability."""
        if self.physics is None:
            self._stop_physics_motion()
            return
        movement = self.physics.step()
        for node_id, (x, y) in self.physics.positions().items():
            item = self.node_items.get(node_id)
            if item is not None:
                item.setPos(x, y)
        self._physics_ticks += 1
        self._settled_physics_ticks = (
            self._settled_physics_ticks + 1 if movement < self.PHYSICS_SETTLE_DISTANCE else 0
        )
        if self._settled_physics_ticks >= self.PHYSICS_SETTLE_TICKS or self._physics_ticks >= self.PHYSICS_MAX_TICKS:
            self._stop_physics_motion()

    def _stop_physics_motion(self) -> None:
        """Stop repaint work as soon as the projection has settled or is replaced."""
        if self._physics_timer.isActive():
            self._physics_timer.stop()
        if self.physics is not None:
            self.physics.settle()

    def _populate_node_list(self, nodes: tuple[GraphNode, ...]) -> None:
        selected_ids = {item.node_id for item in self.scene.selectedItems() if isinstance(item, GraphNodeItem)}
        self.node_list.blockSignals(True)
        self.node_list.clear()
        grouped: dict[str, list[GraphNode]] = {}
        for node in nodes:
            grouped.setdefault(node.node_type or "custom", []).append(node)
        for node_type in sorted(grouped):
            header = QListWidgetItem(node_type.replace("_", " ").upper())
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self.node_list.addItem(header)
            for node in sorted(grouped[node_type], key=lambda value: (value.title.lower(), value.node_id)):
                item = QListWidgetItem(f"  {node.title}")
                item.setData(Qt.ItemDataRole.UserRole, node.node_id)
                self.node_list.addItem(item)
                if node.node_id in selected_ids:
                    self.node_list.setCurrentItem(item)
        self.node_list.blockSignals(False)

    def _select_list_node(self, item: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if item is None:
            return
        node_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(node_id, str):
            self._select_node(node_id)

    def _show_hover_context(self, node_id: str | None) -> None:
        node = self._nodes_by_id.get(node_id or "")
        if node is None:
            self.context_summary.setPlainText("Select a node to view its stored graph context.")
            return
        self.context_summary.setPlainText(
            f"Preview: {node.title}\n\nType: {node.node_type}\n\n{node.description or node.content or 'No stored context.'}"
        )

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
        self.canvas.setEnabled(not busy)
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
        self._stop_physics_motion()
        self._unsubscribe_graph_changes()
        self.shutdown_workers()
        super().closeEvent(event)

    def _unsubscribe_graph_changes(self, _destroyed: object | None = None) -> None:
        if self._unsubscribe_graph_notifications is not None:
            self._unsubscribe_graph_notifications()
            self._unsubscribe_graph_notifications = None

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

    def _link_selected_node(self) -> None:
        nodes = [item for item in self.scene.selectedItems() if isinstance(item, GraphNodeItem)]
        if len(nodes) == 2:
            self._connect_selected()
            return
        if len(nodes) != 1:
            QMessageBox.information(self, "Select a node", "Select one source node, then choose a target.")
            return
        source = nodes[0]
        targets = {f"{node.title} [{node.node_id[:8]}]": node for node in self._nodes_by_id.values() if node.node_id != source.node_id}
        label, accepted = QInputDialog.getItem(self, "Link selected node", "Target:", list(targets), 0, False)
        if not accepted or not label:
            return
        dialog = LinkDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._run_core(
            lambda: self.core.create_mind_map_link(
                source_node_id=source.node_id, target_node_id=targets[label].node_id, **dialog.values()
            ),
            lambda _link: self._refresh_then(lambda: self._select_node(source.node_id)),
            "Creating link",
        )

    def _unlink_selected_node(self) -> None:
        nodes = [item for item in self.scene.selectedItems() if isinstance(item, GraphNodeItem)]
        if len(nodes) != 1:
            QMessageBox.information(self, "Select a node", "Select one node to choose one of its links.")
            return
        node_id = nodes[0].node_id
        links = [link for link in self.link_items.values() if link.link.source_node_id == node_id or link.link.target_node_id == node_id]
        if not links:
            QMessageBox.information(self, "No links", "The selected node has no links.")
            return
        choices = {f"{link.link.link_type}: {link.link_id[:8]}": link for link in links}
        label, accepted = QInputDialog.getItem(self, "Unlink selected node", "Link:", list(choices), 0, False)
        if accepted and label:
            self._run_core(
                lambda: self.core.delete_mind_map_link(choices[label].link_id),
                lambda _result: self._refresh_then(lambda: self._select_node(node_id)),
                "Deleting link",
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
        node = self._nodes_by_id.get(node_id)
        if self._refreshing or node is None or node.position_locked or node.metadata.get("mindmap_pinned", False):
            return
        if not self._busy:
            self._run_core(
                lambda: self.core.move_mind_map_node(node_id, x, y),
                lambda _result: None,
                "Saving position",
                error_title="Position save failed",
            )

    def _auto_layout(self) -> None:
        if self.physics is None or not self.physics.nodes:
            return
        if len(self.physics.nodes) > self.MAX_AUTO_LAYOUT_NODES:
            self.status_label.setText(
                f"Force layout is limited to {self.MAX_AUTO_LAYOUT_NODES} nodes; this graph has {len(self.physics.nodes)}."
            )
            return
        self._stop_physics_motion()
        self.physics.step(80)
        positions = {
            node_id: (x, y)
            for node_id, (x, y) in self.physics.positions().items()
            if not self.physics.nodes[node_id].pinned
        }
        if not positions:
            self.status_label.setText("All node positions are pinned.")
            return

        self._run_core(
            lambda: self.core.move_mind_map_nodes(positions),
            lambda _result: self._refresh_then(self._fit_graph),
            "Saving auto layout",
        )

    def _toggle_pin(self) -> None:
        node = self._single_selected_node()
        if node is None:
            return
        metadata = dict(node.metadata)
        metadata["mindmap_pinned"] = not bool(metadata.get("mindmap_pinned", node.position_locked))
        self._run_core(
            lambda: self.core.update_mind_map_node(node.node_id, metadata=metadata),
            lambda _result: self._refresh_then(lambda: self._select_node(node.node_id)),
            "Saving pin state",
        )

    def _toggle_central(self) -> None:
        node = self._single_selected_node()
        if node is None:
            return
        metadata = dict(node.metadata)
        metadata["mindmap_central"] = not bool(metadata.get("mindmap_central", False))
        self._run_core(
            lambda: self.core.update_mind_map_node(node.node_id, metadata=metadata),
            lambda _result: self._refresh_then(lambda: self._select_node(node.node_id)),
            "Saving central state",
        )

    def _recenter_linked(self) -> None:
        node = self._single_selected_node()
        if node is None:
            return
        neighbor_ids = []
        for link in self.link_items.values():
            if link.link.source_node_id == node.node_id:
                neighbor_ids.append(link.link.target_node_id)
            elif link.link.target_node_id == node.node_id:
                neighbor_ids.append(link.link.source_node_id)
        neighbor_ids = list(dict.fromkeys(neighbor_ids))
        if not neighbor_ids:
            self.status_label.setText("Selected node has no direct links.")
            return
        positions: dict[str, tuple[float, float]] = {}
        for index, neighbor_id in enumerate(neighbor_ids):
            neighbor = self._nodes_by_id[neighbor_id]
            if neighbor.position_locked or neighbor.metadata.get("mindmap_pinned", False):
                continue
            angle = math.tau * index / len(neighbor_ids)
            positions[neighbor_id] = (node.position_x + math.cos(angle) * 150, node.position_y + math.sin(angle) * 150)
        self._run_core(
            lambda: self.core.move_mind_map_nodes(positions),
            lambda _result: self._refresh_then(lambda: self._select_node(node.node_id)),
            "Recentering linked nodes",
        )

    def _focus_selected(self) -> None:
        node = self._single_selected_node()
        if node is not None:
            self._select_node(node.node_id)

    def _single_selected_node(self) -> GraphNode | None:
        nodes = [item.node for item in self.scene.selectedItems() if isinstance(item, GraphNodeItem)]
        if len(nodes) != 1:
            QMessageBox.information(self, "Select one node", "Select exactly one node first.")
            return None
        return nodes[0]

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
            self.context_summary.setPlainText(
                f"Selected: {node.title}\n\nType: {node.node_type}\n\n"
                f"{node.description or node.content or 'No stored context.'}"
            )
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
