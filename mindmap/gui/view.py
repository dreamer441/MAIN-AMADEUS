"""Interactive PyQt6 surface for the AMADEUS Mind Map module."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QEventLoop, QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mindmap.gui.dialogs import LINK_TYPES, NODE_TYPES, ChatImportDialog, LinkDialog, NodeDialog
from mindmap.gui.surface import MindMapCanvas
from mindmap.gui.items import GraphLinkItem, GraphNodeItem
from mindmap.gui.physics import GraphPhysics
from mindmap.models import GraphLink, GraphNode, GraphSnapshot


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
    source_open_requested = pyqtSignal(str, str, str)

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
        self._dragging_node_ids: set[str] = set()
        self._pending_node_positions: dict[str, tuple[float, float]] = {}
        self._saving_node_position = False
        self._shutting_down = False
        self._after_refresh: list[Callable[[], None]] = []
        self._resume_physics_after_refresh = False
        self._active_threads: list[QThread] = []
        self._active_workers: list[MindMapWorker] = []
        self._unsubscribe_graph_notifications: Callable[[], None] | None = None

        self._build_ui()
        self.scene.selectionChanged.connect(self._show_selection)
        self._delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self)
        self._delete_shortcut.activated.connect(self._delete_selected)
        self._focus_shortcut = QShortcut(QKeySequence("F"), self)
        self._focus_shortcut.activated.connect(self._focus_selected)
        self._fit_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        self._fit_shortcut.activated.connect(self._fit_graph)
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
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        heading_row = QHBoxLayout()
        heading_column = QVBoxLayout()
        heading_column.setSpacing(2)
        title = QLabel("AMADEUS Mind Map")
        title.setObjectName("MindMapTitle")
        subtitle = QLabel("A living relevance space for chats, ideas, decisions, tasks, materials, memories, and evidence.")
        subtitle.setObjectName("MindMapSubtitle")
        subtitle.setWordWrap(True)
        heading_column.addWidget(title)
        heading_column.addWidget(subtitle)
        heading_row.addLayout(heading_column, 1)

        self.quick_new_button = QPushButton("+ Node")
        self.quick_new_button.setObjectName("PrimaryMindMapButton")
        self.quick_new_button.clicked.connect(self._create_node)
        self.quick_edit_button = QPushButton("Edit Node")
        self.quick_edit_button.clicked.connect(self._edit_selected)
        self.quick_edit_button.setEnabled(False)
        self.quick_import_chat_button = QPushButton("Import Chats")
        self.quick_import_chat_button.clicked.connect(self._import_chats)
        self.quick_fit_button = QPushButton("Fit")
        self.quick_fit_button.clicked.connect(self._fit_graph)
        heading_row.addWidget(self.quick_import_chat_button)
        heading_row.addWidget(self.quick_new_button)
        heading_row.addWidget(self.quick_edit_button)
        heading_row.addWidget(self.quick_fit_button)

        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setChildrenCollapsible(True)
        self.workspace_splitter.setHandleWidth(7)

        left_panel = self._create_panel("Explore")
        left_panel.layout().addWidget(self._build_left_panel())

        center_panel = self._create_panel("Graph")
        graph_toolbar = QHBoxLayout()
        graph_toolbar.setSpacing(6)
        self.graph_hint = QLabel("Select a node to reveal its local neighborhood")
        self.graph_hint.setObjectName("GraphHint")
        graph_toolbar.addWidget(self.graph_hint, 1)
        layout_button = QPushButton("Settle")
        layout_button.clicked.connect(self._auto_layout)
        graph_toolbar.addWidget(layout_button)
        center_panel.layout().addLayout(graph_toolbar)
        center_panel.layout().addWidget(self.canvas, 1)

        right_panel = self._create_panel("Context")
        right_panel.layout().addWidget(self._build_properties_panel())

        self.workspace_splitter.addWidget(left_panel)
        self.workspace_splitter.addWidget(center_panel)
        self.workspace_splitter.addWidget(right_panel)
        self.workspace_splitter.setStretchFactor(0, 0)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setStretchFactor(2, 0)
        self.workspace_splitter.setSizes([250, 760, 340])

        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("MindMapStatus")
        self.selection_label = QLabel("No selection")
        self.selection_label.setObjectName("MindMapSelectionStatus")
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.selection_label)

        self._busy_widgets = (
            *self.action_buttons.values(),
            self.search_input,
            self.search_button,
            self.quick_new_button,
            self.quick_import_chat_button,
            self.quick_fit_button,
            layout_button,
        )
        root.addLayout(heading_row)
        root.addWidget(self.workspace_splitter, 1)
        root.addLayout(status_row)
        self._apply_styles()

    def _create_panel(self, title: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("MindMapPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        header = QLabel(title)
        header.setObjectName("PanelHeader")
        layout.addWidget(header)
        return panel

    def _apply_styles(self) -> None:
        """Keep the graph visually distinct without changing the whole application."""
        self.setStyleSheet(
            """
            QWidget { background-color: #07090c; color: #edf2f7; font-family: Segoe UI; }
            QLabel#MindMapTitle { font-size: 25px; font-weight: 800; color: #ffffff; }
            QLabel#MindMapSubtitle { font-size: 12px; color: #8f9baa; }
            QLabel#MindMapStatus { font-size: 11px; color: #91a0b0; padding: 3px 2px; }
            QLabel#MindMapSelectionStatus { font-size: 11px; color: #b7c4d2; padding: 3px 2px; }
            QLabel#GraphHint { font-size: 11px; color: #718095; }
            QFrame#MindMapPanel { background-color: #0d1117; border: 1px solid #202833; border-radius: 12px; }
            QLabel#PanelHeader { font-size: 12px; font-weight: 700; color: #cbd5df; padding: 0 2px 2px 2px; }
            QListWidget, QTextEdit, QLineEdit { background-color: #090d12; color: #edf2f7; border: 1px solid #26313d; border-radius: 8px; padding: 7px; font-size: 12px; selection-background-color: #254d78; }
            QListWidget::item { padding: 4px 5px; border-radius: 5px; }
            QListWidget::item:hover { background-color: #151c25; }
            QListWidget::item:selected { background-color: #1d3853; color: #ffffff; }
            QTabWidget::pane { background-color: #090d12; border: 1px solid #26313d; border-radius: 8px; top: -1px; }
            QTabBar::tab { background-color: #111720; color: #9eabba; border: 1px solid #26313d; border-bottom: none; padding: 7px 10px; }
            QTabBar::tab:selected { background-color: #18212c; color: #ffffff; }
            QPushButton { background-color: #121820; color: #e7edf4; border: 1px solid #2b3744; border-radius: 7px; padding: 7px 10px; font-size: 12px; }
            QPushButton:hover { background-color: #1a2430; border-color: #43566a; }
            QPushButton:pressed { background-color: #203044; }
            QPushButton:disabled { color: #596675; border-color: #1c242d; }
            QPushButton#PrimaryMindMapButton { background-color: #245f8f; border-color: #3779aa; font-weight: 700; }
            QPushButton#PrimaryMindMapButton:hover { background-color: #2f73aa; }
            QGraphicsView { background-color: #090c10; border: 1px solid #222c37; border-radius: 9px; }
            QSplitter::handle { background-color: #111820; border-radius: 3px; }
            QSplitter::handle:hover { background-color: #233244; }
            """
        )

    def _build_left_panel(self) -> QWidget:
        tabs = QTabWidget()
        self.left_tabs = tabs

        nodes_tab = QWidget()
        nodes_layout = QVBoxLayout(nodes_tab)
        nodes_layout.setContentsMargins(6, 8, 6, 6)
        nodes_layout.setSpacing(7)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search title, content, type...")
        self.search_input.returnPressed.connect(self._search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._search)
        search_row = QHBoxLayout()
        search_row.setSpacing(5)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_button)
        self.node_list = QListWidget()
        self.node_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.node_list.currentItemChanged.connect(self._select_list_node)
        self.node_list.itemDoubleClicked.connect(lambda _item: self._open_selected_source())
        nodes_layout.addLayout(search_row)
        nodes_layout.addWidget(self.node_list, 1)
        tabs.addTab(nodes_tab, "Nodes")

        actions_tab = QWidget()
        actions_layout = QVBoxLayout(actions_tab)
        actions_layout.setContentsMargins(6, 8, 6, 6)
        actions_layout.setSpacing(7)
        actions = (
            ("Open Source", self._open_selected_source),
            ("Edit Selected", self._edit_selected),
            ("Copy Node ID", self._copy_selected_node_id),
            ("Pin Node", self._toggle_pin),
            ("Set as Central", self._toggle_central),
            ("Recenter Linked", self._recenter_linked),
            ("Focus Selected", self._focus_selected),
            ("New Node", self._create_node),
            ("Import Chats", self._import_chats),
            ("Delete Selected", self._delete_selected),
            ("Link Selected", self._link_selected_node),
            ("Unlink Selected", self._unlink_selected_node),
            ("Force Layout", self._auto_layout),
            ("Fit Graph", self._fit_graph),
            ("Refresh", self.refresh_graph),
            ("Export JSON", self._export_graph),
            ("Import JSON", self._import_graph),
        )
        self.action_buttons: dict[str, QPushButton] = {}
        for index, (label, callback) in enumerate(actions):
            if index == 0:
                heading = QLabel("Selected object")
                heading.setObjectName("GraphHint")
                actions_layout.addWidget(heading)
            if index == 7:
                actions_layout.addSpacing(7)
                heading = QLabel("Graph editing")
                heading.setObjectName("GraphHint")
                actions_layout.addWidget(heading)
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
        self.context_summary.setPlaceholderText("Hover or select a node to preview its meaning.")
        self.selection_summary = QTextEdit()
        self.selection_summary.setReadOnly(True)
        self.selection_summary.setPlaceholderText("Select a node or relationship to inspect persisted properties.")
        self.connections_summary = QTextEdit()
        self.connections_summary.setReadOnly(True)
        self.connections_summary.setPlaceholderText("Connected nodes and relationship evidence will appear here.")
        tabs.addTab(self.context_summary, "Context")
        tabs.addTab(self.selection_summary, "Details")
        tabs.addTab(self.connections_summary, "Connections")
        layout.addWidget(tabs)
        return panel

    def refresh_graph(self) -> None:
        if self._shutting_down:
            return
        if self._refreshing or self._busy or self._dragging_node_ids or self._pending_node_positions:
            self._refresh_pending = True
            return
        self._refreshing = True
        self._run_core(
            self.core.get_mind_map_snapshot, self._render_snapshot, "Refreshing graph",
            keep_canvas_interactive=bool(self.node_items),
        )

    def _render_snapshot(self, snapshot: object) -> None:
        # A read started before a gesture may contain its old persisted position.
        if self._dragging_node_ids or self._pending_node_positions or self._saving_node_position:
            self._refreshing = False
            self._refresh_pending = True
            return
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
            projected_positions = projected_physics.positions()

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
                    visual_radius, opacity, layer_score = projected_physics.visual_metrics(node.node_id)
                    item = GraphNodeItem(
                        node,
                        moved_callback=self._persist_node_position,
                        drag_started_callback=self._begin_node_drag,
                        dragged_callback=self._update_node_drag,
                        hover_callback=self._show_hover_context,
                        double_click_callback=self._open_node_source,
                        relevance=projected_physics.nodes[node.node_id].relevance,
                        visual_radius=visual_radius,
                        opacity=opacity,
                        layer_score=layer_score,
                    )
                    projected_position = projected_positions[node.node_id]
                    item.set_visual_position(*projected_position)
                    self.scene.addItem(item)
                    self.node_items[node.node_id] = item
                else:
                    visual_radius, opacity, layer_score = projected_physics.visual_metrics(node.node_id)
                    item.update_node(
                        node,
                        projected_physics.nodes[node.node_id].relevance,
                        visual_radius=visual_radius,
                        opacity=opacity,
                        layer_score=layer_score,
                    )
                    item.set_visual_position(*projected_positions[node.node_id])

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
                f"{len(snapshot.nodes)} nodes · {len(snapshot.links)} links · graph storage synchronized"
            )
            self._populate_node_list(snapshot.nodes)
            if snapshot.nodes and not selected_node_ids and not selected_link_ids:
                self._fit_graph()
            resume_physics = topology_changed or self._resume_physics_after_refresh
            self._resume_physics_after_refresh = False
            if resume_physics:
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
        if self._dragging_node_ids or self._pending_node_positions or self._saving_node_position:
            return
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
        if self.physics is None or self._dragging_node_ids:
            self._stop_physics_motion()
            return
        movement = self.physics.step()
        for node_id, (x, y) in self.physics.positions().items():
            item = self.node_items.get(node_id)
            if item is not None:
                radius, opacity, layer_score = self.physics.visual_metrics(node_id)
                item.update_node(
                    item.node,
                    self.physics.nodes[node_id].relevance,
                    visual_radius=radius,
                    opacity=opacity,
                    layer_score=layer_score,
                )
                item.set_visual_position(x, y)
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
            selected = [item.node for item in self.scene.selectedItems() if isinstance(item, GraphNodeItem)]
            if selected:
                self.context_summary.setPlainText(self._node_context_text(selected[0]))
            else:
                self.context_summary.setPlainText("Select a node to view its stored graph context.")
            return
        self.context_summary.setPlainText(self._node_context_text(node, preview=True))

    def _node_context_text(self, node: GraphNode, *, preview: bool = False) -> str:
        metadata = dict(node.metadata)
        tags = metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [value.strip() for value in tags.split(",") if value.strip()]
        source = "Manual Mind Map object"
        if node.source_reference is not None:
            source = f"{node.source_reference.source_type}:{node.source_reference.source_id}"
            if node.source_reference.source_locator:
                source += f" · {node.source_reference.source_locator}"
        body = node.description or node.content or "No stored context."
        if preview and len(body) > 1300:
            body = body[:1297].rstrip() + "..."
        lines = [
            f"{node.title}",
            f"{node.node_type.replace('_', ' ').title()} · importance {node.importance:.2f} · confidence {node.confidence:.2f}",
            "",
            body,
        ]
        if node.description and node.content and node.content != node.description:
            content = node.content
            if preview and len(content) > 900:
                content = content[:897].rstrip() + "..."
            lines.extend(("", "Stored content", content))
        lines.extend(("", f"Source: {source}"))
        if tags:
            lines.append(f"Tags: {', '.join(str(tag) for tag in tags)}")
        return "\n".join(lines)

    def _connection_text(self, node_id: str) -> str:
        records: list[str] = []
        for item in self.link_items.values():
            link = item.link
            if link.source_node_id == node_id:
                other_id = link.target_node_id
                direction = "→"
            elif link.target_node_id == node_id:
                other_id = link.source_node_id
                direction = "←"
            else:
                continue
            other = self._nodes_by_id.get(other_id)
            other_title = other.title if other else other_id
            relation = link.label or link.link_type.replace("_", " ")
            detail = (
                f"{direction} {other_title}\n"
                f"   {relation} · strength {link.strength:.2f} · confidence {link.confidence:.2f}"
            )
            if link.evidence:
                evidence = link.evidence if len(link.evidence) <= 420 else link.evidence[:417].rstrip() + "..."
                detail += f"\n   Evidence: {evidence}"
            records.append(detail)
        if not records:
            return "This node has no direct graph relationships yet."
        return f"{len(records)} direct relationship(s)\n\n" + "\n\n".join(records)

    def _apply_focus_highlight(self, node_id: str | None) -> None:
        if not node_id or node_id not in self.node_items:
            for item in self.node_items.values():
                item.set_focus_level("normal")
            for item in self.link_items.values():
                item.set_focus_level("normal")
            return
        neighbors = self.physics.get_direct_neighbors(node_id) if self.physics else set()
        for candidate_id, item in self.node_items.items():
            if candidate_id == node_id:
                item.set_focus_level("selected")
            elif candidate_id in neighbors:
                item.set_focus_level("neighbor")
            else:
                item.set_focus_level("dimmed")
        for item in self.link_items.values():
            link = item.link
            connected = link.source_node_id == node_id or link.target_node_id == node_id
            item.set_focus_level("connected" if connected else "dimmed")

    def _open_node_source(self, node_id: str) -> None:
        node = self._nodes_by_id.get(node_id)
        if node is None:
            return
        if node.source_reference is None:
            self._select_node(node_id)
            self._edit_selected()
            return
        self.source_open_requested.emit(
            node.source_reference.source_type,
            node.source_reference.source_id,
            node.source_reference.source_locator,
        )
        self.status_label.setText(f"Opening source for {node.title}...")

    def _open_selected_source(self) -> None:
        node = self._single_selected_node()
        if node is not None:
            self._open_node_source(node.node_id)

    def _copy_selected_node_id(self) -> None:
        node = self._single_selected_node()
        if node is None:
            return
        QApplication.clipboard().setText(node.node_id)
        self.status_label.setText(f"Copied node ID: {node.node_id}")

    def _import_chats(self) -> None:
        list_chats = getattr(self.core, "list_chats", None)
        upsert = getattr(self.core, "upsert_mind_map_source_node", None)
        if not callable(list_chats) or not callable(upsert):
            QMessageBox.information(self, "Chat import unavailable", "Current Core does not expose Chat Registry import methods.")
            return
        try:
            chats = list(list_chats())
        except Exception as error:
            self._show_error("Could not load chats", error)
            return
        if not chats:
            QMessageBox.information(self, "No chats", "There are no dedicated AMADEUS chats to import.")
            return
        dialog = ChatImportDialog(chats, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_chats()
        if not selected:
            return

        def import_selected() -> list[str]:
            imported_ids: list[str] = []
            for chat in selected:
                chat_id = str(getattr(chat, "chat_id", "")).strip()
                if not chat_id:
                    continue
                priority = str(getattr(chat, "priority", "Normal"))
                priority_score = {"critical": 1.0, "important": 0.82, "normal": 0.55, "low": 0.32, "ignore": 0.10}.get(priority.lower(), 0.55)
                metadata = {
                    "chat_priority": priority,
                    "chat_purpose": str(getattr(chat, "purpose", "General")),
                    "chat_scope": str(getattr(chat, "scope", "Local")),
                    "tags": ["chat", str(getattr(chat, "purpose", "General")).lower().replace(" ", "_")],
                    "source_registry": "chat_registry",
                }
                node = upsert(
                    source_type="chat",
                    source_id=chat_id,
                    title=str(getattr(chat, "title", "Untitled Chat")),
                    description=str(getattr(chat, "description", "")),
                    node_type="chat",
                    importance=priority_score,
                    confidence=1.0,
                    metadata=metadata,
                )
                imported_ids.append(node.node_id)
            return imported_ids

        self._run_core(
            import_selected,
            self._show_chat_import_result,
            f"Importing {len(selected)} chat(s)",
            error_title="Chat import failed",
        )

    def _show_chat_import_result(self, imported: object) -> None:
        node_ids = list(imported) if isinstance(imported, list) else []
        self.status_label.setText(f"Imported or updated {len(node_ids)} chat node(s).")
        self._after_refresh.append(lambda: self._select_node(node_ids[-1]) if node_ids else None)
        self.refresh_graph()

    def _run_core(
        self,
        operation: Callable[[], object],
        on_success: Callable[[object], None],
        busy_text: str,
        *,
        error_title: str | None = None,
        keep_canvas_interactive: bool = False,
    ) -> None:
        """Use the established worker lifecycle; slots update Qt widgets on the GUI thread."""
        if self._busy:
            self._refresh_pending = True
            return
        self._set_busy(True, busy_text, keep_canvas_interactive=keep_canvas_interactive)
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

    def _set_busy(
        self, busy: bool, message: str = "", *, keep_canvas_interactive: bool = False,
    ) -> None:
        self._busy = busy
        self.canvas.setEnabled(not busy or keep_canvas_interactive or bool(self._dragging_node_ids))
        for widget in self._busy_widgets:
            widget.setEnabled(not busy)
        self.quick_edit_button.setEnabled(False)
        if busy:
            self.status_label.setText(message)
        else:
            self._update_action_buttons()

    def _dispatch_worker_success(self, callback: Callable[[object], None], result: object) -> None:
        callback(result)

    def _finish_worker(self, thread: QThread, worker: MindMapWorker) -> None:
        if thread in self._active_threads:
            self._active_threads.remove(thread)
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        self._saving_node_position = False
        self._set_busy(False)
        self._drain_position_saves()
        if self._busy:
            return
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
        self._shutting_down = True
        # A finishing position save may launch another queued move. Keep the
        # GUI event loop alive until all completion slots and queued saves drain.
        while self._active_threads or self._busy:
            loop = QEventLoop(self)
            QTimer.singleShot(10, loop.quit)
            loop.exec()

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
        selected_chat_node_id = next(
            (
                item.node_id
                for item in self.scene.selectedItems()
                if isinstance(item, GraphNodeItem)
                and item.node.source_reference is not None
                and item.node.source_reference.source_type == "chat"
            ),
            None,
        )
        create_workspace_node = getattr(self.core, "create_mind_map_workspace_node", None)
        operation = create_workspace_node if callable(create_workspace_node) else self.core.create_mind_map_node
        self._run_core(
            lambda: operation(
                **values,
                linked_chat_node_id=selected_chat_node_id,
                position_x=center.x(),
                position_y=center.y(),
            ),
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
                values.pop("create_workspace_object", None)
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
        source_backed_nodes = [
            item.node
            for item in selected
            if isinstance(item, GraphNodeItem) and item.node.source_reference is not None
        ]
        source_warning = ""
        if source_backed_nodes:
            source_types = ", ".join(sorted({node.source_reference.source_type for node in source_backed_nodes}))
            source_warning = (
                "\n\nThis selection includes real AMADEUS workspace objects "
                f"({source_types}). Their corresponding chat/sheet/comment/memory records will also be deleted."
            )
        if QMessageBox.question(
            self,
            "Delete graph objects",
            "Delete the selected graph objects? Deleting a node also deletes its connected links."
            + source_warning,
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

    def _begin_node_drag(self, node_id: str) -> None:
        """Pause graph-wide work while the pointer directly controls a node."""
        node = self._nodes_by_id.get(node_id)
        if node is None or node.position_locked or node.metadata.get("mindmap_pinned", False):
            return
        self._dragging_node_ids.add(node_id)
        self._stop_physics_motion()
        self._resume_physics_after_refresh = False
        self.canvas.set_fast_drag_mode(True)
        if self.physics is not None and node_id in self.physics.nodes:
            self.physics.start_drag(node_id)

    def _update_node_drag(self, node_id: str, x: float, y: float) -> None:
        """Keep the physics anchor current without simulating other nodes."""
        if self.physics is not None and node_id in self.physics.nodes:
            self.physics.drag_to(node_id, x, y)

    def _persist_node_position(self, node_id: str, x: float, y: float) -> None:
        """Queue the latest release position, including releases during a save."""
        self._dragging_node_ids.discard(node_id)
        self.canvas.set_fast_drag_mode(bool(self._dragging_node_ids))
        if self.physics is not None and node_id in self.physics.nodes:
            self.physics.drag_to(node_id, x, y)
            self.physics.stop_drag(node_id)
        node = self._nodes_by_id.get(node_id)
        if node is not None and not node.position_locked and not node.metadata.get("mindmap_pinned", False):
            self._pending_node_positions[node_id] = (x, y)
        self._drain_position_saves()
        if not self._busy and self._refresh_pending:
            self._refresh_pending = False
            self.refresh_graph()

    def _drain_position_saves(self) -> None:
        """Serialize coalesced moves through Core before reading another snapshot."""
        if self._busy:
            return
        while self._pending_node_positions:
            node_id = next(iter(self._pending_node_positions))
            x, y = self._pending_node_positions.pop(node_id)
            node = self._nodes_by_id.get(node_id)
            if node is None or node.position_locked or node.metadata.get("mindmap_pinned", False):
                continue
            self._saving_node_position = True
            # Refresh even when Core does not publish a change, or a save fails.
            self._refresh_pending = True
            self._run_core(
                lambda: self.core.move_mind_map_node(node_id, x, y),
                lambda _result: None,
                "Saving position",
                error_title="Position save failed",
                keep_canvas_interactive=True,
            )
            return

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
        center_item = self.node_items.get(node.node_id)
        center_x = center_item.pos().x() if center_item is not None else node.position_x
        center_y = center_item.pos().y() if center_item is not None else node.position_y
        for index, neighbor_id in enumerate(neighbor_ids):
            neighbor = self._nodes_by_id[neighbor_id]
            if neighbor.position_locked or neighbor.metadata.get("mindmap_pinned", False):
                continue
            angle = math.tau * index / len(neighbor_ids)
            positions[neighbor_id] = (center_x + math.cos(angle) * 165, center_y + math.sin(angle) * 165)
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

    def _update_action_buttons(self) -> None:
        if not hasattr(self, "action_buttons") or self._busy:
            return
        selected = self.scene.selectedItems()
        selected_nodes = [item for item in selected if isinstance(item, GraphNodeItem)]
        one_node = len(selected_nodes) == 1 and len(selected) == 1
        one_object = len(selected) == 1
        has_selection = bool(selected)
        node = selected_nodes[0].node if one_node else None
        has_source = bool(node and node.source_reference)
        has_links = bool(
            node
            and any(
                item.link.source_node_id == node.node_id or item.link.target_node_id == node.node_id
                for item in self.link_items.values()
            )
        )
        states = {
            "Open Source": has_source,
            "Edit Selected": one_object,
            "Copy Node ID": one_node,
            "Pin Node": one_node,
            "Set as Central": one_node,
            "Recenter Linked": one_node and has_links,
            "Focus Selected": one_node,
            "Delete Selected": has_selection,
            "Link Selected": len(selected_nodes) in {1, 2} and len(self.node_items) > 1,
            "Unlink Selected": one_node and has_links,
        }
        for label, enabled in states.items():
            button = self.action_buttons.get(label)
            if button is not None:
                button.setEnabled(enabled)
        self.quick_edit_button.setEnabled(one_node)

    def _show_selection(self) -> None:
        selected = self.scene.selectedItems()
        if len(selected) != 1:
            self.selection_summary.setPlainText(
                f"{len(selected)} objects selected." if selected else "No graph object selected."
            )
            self.connections_summary.setPlainText(
                "Select one node to inspect its direct graph neighborhood."
            )
            self.selection_label.setText(
                f"{len(selected)} selected" if selected else "No selection"
            )
            self._apply_focus_highlight(None)
            self._update_action_buttons()
            return
        item = selected[0]
        if isinstance(item, GraphNodeItem):
            node = item.node
            self.context_summary.setPlainText(self._node_context_text(node))
            source = (
                f"{node.source_reference.source_type}:{node.source_reference.source_id}"
                if node.source_reference else "manual"
            )
            metadata_lines = [f"{key}: {value}" for key, value in sorted(dict(node.metadata).items())]
            self.selection_summary.setPlainText(
                f"NODE\n\nTitle: {node.title}\nType: {node.node_type}\nStatus: {node.status}\n"
                f"Importance: {node.importance:.2f}\nConfidence: {node.confidence:.2f}\n"
                f"Position: ({item.pos().x():.1f}, {item.pos().y():.1f})\n"
                f"Locked: {node.position_locked}\nPinned: {bool(node.metadata.get('mindmap_pinned', False))}\n"
                f"Central: {bool(node.metadata.get('mindmap_central', False))}\nSource: {source}\n\n"
                f"Metadata:\n{chr(10).join(metadata_lines) if metadata_lines else '—'}"
            )
            self.connections_summary.setPlainText(self._connection_text(node.node_id))
            self.selection_label.setText(f"{node.node_type.title()}: {node.title}")
            self.graph_hint.setText("Connected nodes stay bright; unrelated nodes fade into the background")
            self._apply_focus_highlight(node.node_id)
        elif isinstance(item, GraphLinkItem):
            link = item.link
            source = self._nodes_by_id.get(link.source_node_id)
            target = self._nodes_by_id.get(link.target_node_id)
            self.context_summary.setPlainText(
                f"{source.title if source else link.source_node_id}\n"
                f"  — {link.label or link.link_type.replace('_', ' ')} →\n"
                f"{target.title if target else link.target_node_id}\n\n"
                f"{link.evidence or 'No relationship evidence has been stored yet.'}"
            )
            self.selection_summary.setPlainText(
                f"LINK\n\nType: {link.link_type}\nLabel: {link.label or '—'}\n"
                f"Strength: {link.strength:.2f}\nConfidence: {link.confidence:.2f}\n"
                f"Permanence: {link.permanence:.2f}\nTemporary: {link.is_temporary}\n"
                f"Usage count: {link.usage_count}\nReward: {link.reward_score:.2f}\n"
                f"Punishment: {link.punishment_score:.2f}\n\nEvidence:\n{link.evidence or '—'}"
            )
            self.connections_summary.setPlainText(
                f"Source: {source.title if source else link.source_node_id}\n"
                f"Target: {target.title if target else link.target_node_id}\n\n"
                "Select either endpoint to inspect its complete local neighborhood."
            )
            self.selection_label.setText(f"Link: {link.link_type.replace('_', ' ')}")
            for node_item in self.node_items.values():
                if node_item.node_id in {link.source_node_id, link.target_node_id}:
                    node_item.set_focus_level("neighbor")
                else:
                    node_item.set_focus_level("dimmed")
            for link_item in self.link_items.values():
                link_item.set_focus_level("connected" if link_item.link_id == link.link_id else "dimmed")
        self._update_action_buttons()

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
