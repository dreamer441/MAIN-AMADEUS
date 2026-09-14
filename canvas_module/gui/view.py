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


_RELATION_TYPES = (
    "related_to",
    "expands",
    "responds_to",
    "supports",
    "contradicts",
    "depends_on",
    "alternative_to",
    "derived_from",
    "example_of",
)

_MIN_BLOCK_WIDTH = 160.0
_MIN_BLOCK_HEIGHT = 100.0
_RESIZE_HANDLE_SIZE = 16.0
_MIN_COMMENT_WIDTH = 100.0
_MIN_COMMENT_HEIGHT = 48.0
_COMMENT_RESIZE_HANDLE_SIZE = 12.0


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


class ConnectorEditorDialog(QDialog):
    """Small editor for the semantic metadata carried by a connector."""

    def __init__(self, connector: CanvasConnector, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Canvas Connector")
        self.resize(440, 330)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_combo = QComboBox()
        self.type_combo.addItem("Directional arrow", "arrow")
        self.type_combo.addItem("Plain relationship line", "line")
        type_index = self.type_combo.findData(connector.connector_type)
        self.type_combo.setCurrentIndex(max(0, type_index))

        self.relation_combo = QComboBox()
        self.relation_combo.setEditable(True)
        for relation_type in _RELATION_TYPES:
            self.relation_combo.addItem(relation_type.replace("_", " "), relation_type)
        relation_index = self.relation_combo.findData(connector.relation_type)
        if relation_index >= 0:
            self.relation_combo.setCurrentIndex(relation_index)
        else:
            self.relation_combo.setEditText(connector.relation_type.replace("_", " "))

        self.label_edit = QLineEdit(connector.label)
        self.label_edit.setPlaceholderText("Optional visible label")
        self.comment_edit = QTextEdit(connector.comment)
        self.comment_edit.setPlaceholderText("Optional explanation of why this relationship exists")

        form.addRow("Connector type", self.type_combo)
        form.addRow("Relation type", self.relation_combo)
        form.addRow("Visible label", self.label_edit)
        form.addRow("Comment", self.comment_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        relation_text = self.relation_combo.currentText().strip().lower().replace(" ", "_")
        return {
            "connector_type": str(self.type_combo.currentData()),
            "relation_type": relation_text or DEFAULT_RELATION_TYPE,
            "label": self.label_edit.text().strip(),
            "comment": self.comment_edit.toPlainText().strip(),
        }


class CanvasContextPreviewDialog(QDialog):
    """Human-readable inspection of the exact structured Canvas context."""

    def __init__(self, package: CanvasContextPackage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Canvas Context Preview")
        self.resize(760, 680)

        layout = QVBoxLayout(self)
        summary = QLabel(
            f"Mode: {package.context_mode.title()}  •  "
            f"Targets: {len(package.target_object_ids)} block(s), "
            f"{len(package.target_connector_ids)} connector(s)  •  "
            f"Estimated size: {package.estimated_tokens} tokens"
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("font-weight: 600; color: #dce7f2;")
        layout.addWidget(summary)

        explanation = QLabel(
            "AMADEUS will answer the response targets. Directional ancestors, descendants, and line-connected "
            "peers are supporting context only. The visible viewport limits what supporting information is eligible."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #8fa0b2;")
        layout.addWidget(explanation)

        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        preview.setPlainText(self._format_package(package))
        layout.addWidget(preview, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _format_package(package: CanvasContextPackage) -> str:
        blocks = {block.object_id: block for block in package.objects}

        def lines_for(title: str, object_ids: tuple[str, ...]) -> list[str]:
            result = [title]
            if not object_ids:
                result.append("  (none)")
            for object_id in object_ids:
                block = blocks.get(object_id)
                if block is None:
                    text = object_id
                else:
                    parts = [block.title, block.text, block.comment]
                    text = " | ".join(part.replace("\n", " ") for part in parts if part)
                if len(text) > 150:
                    text = text[:147] + "..."
                root_marker = " [ROOT]" if object_id == package.root_object_id else ""
                result.append(f"  • {text}{root_marker}\n    ID: {object_id}")
            return result

        sections: list[str] = []
        sections.extend(lines_for("RESPONSE TARGETS", package.target_object_ids))
        sections.append("")
        sections.extend(lines_for("DIRECTIONAL ANCESTORS (arrow history)", package.ancestor_object_ids))
        sections.append("")
        sections.extend(lines_for("DIRECTIONAL DESCENDANTS (arrow follow-ups)", package.descendant_object_ids))
        sections.append("")
        sections.extend(lines_for("RELATED PEERS (plain lines)", package.peer_object_ids))
        sections.append("")

        sections.append("TARGET CONNECTORS")
        target_connector_set = set(package.target_connector_ids)
        target_connectors = [
            connector for connector in package.connectors if connector.connector_id in target_connector_set
        ]
        if not target_connectors:
            sections.append("  (none)")
        for connector in target_connectors:
            sections.append(
                f"  • {connector.connector_type}: {connector.source_object_id} -> {connector.target_object_id} "
                f"[{connector.relation_type}] {connector.label}".rstrip()
            )

        sections.append("")
        sections.append("CHANGES REMOVED SINCE LAST SENT BASELINE")
        if not package.deleted_object_ids and not package.deleted_connector_ids:
            sections.append("  (none)")
        for object_id in package.deleted_object_ids:
            sections.append(f"  • Deleted block: {object_id}")
        for connector_id in package.deleted_connector_ids:
            sections.append(f"  • Deleted connector: {connector_id}")

        sections.append("")
        sections.append("VISIBLE BUT EXCLUDED AS UNRELATED")
        if not package.excluded_visible_object_ids:
            sections.append("  (none)")
        for object_id in package.excluded_visible_object_ids:
            sections.append(f"  • {object_id}")

        sections.append("")
        sections.append("TRIMMED BY CONTEXT BUDGET")
        if not package.trimmed_object_ids:
            sections.append("  (none)")
        for object_id in package.trimmed_object_ids:
            sections.append(f"  • {object_id}")

        if package.warnings:
            sections.append("")
            sections.append("WARNINGS")
            sections.extend(f"  • {warning}" for warning in package.warnings)
        return "\n".join(sections)


class CanvasTextEditor(QTextEdit):
    """Text editor where Enter submits and Shift+Enter inserts a line break."""

    submit_requested = pyqtSignal()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            modifiers = event.modifiers()
            if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
                self.submit_requested.emit()
                event.accept()
                return
        super().keyPressEvent(event)


class CanvasTextEditorDialog(QDialog):
    """Focused create/edit dialog with fast Enter-to-commit behavior."""

    def __init__(
        self,
        *,
        title: str,
        label: str,
        initial_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 300)

        layout = QVBoxLayout(self)
        prompt = QLabel(label)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        self.editor = CanvasTextEditor()
        self.editor.setPlainText(initial_text)
        self.editor.setPlaceholderText("Type the Canvas content…")
        self.editor.submit_requested.connect(self._accept_non_empty)
        layout.addWidget(self.editor, stretch=1)

        hint = QLabel("Enter creates/saves the block  •  Shift+Enter adds a new line")
        hint.setStyleSheet("color: #7f8a99;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_non_empty)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.editor.setFocus()
        self.editor.moveCursor(QTextCursor.MoveOperation.End)

    def _accept_non_empty(self) -> None:
        if self.editor.toPlainText().strip():
            self.accept()

    def text(self) -> str:
        return self.editor.toPlainText().strip()


class CanvasTitleTabItem(QGraphicsObject):
    """Attached title tab rendered above a Canvas block."""

    def __init__(self, parent_block: "CanvasTextBlockItem") -> None:
        super().__init__(parent_block)
        self.parent_block = parent_block
        self._title = ""
        self._width = 160.0
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(6.0)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(0.0, 0.0, self._width, 34.0)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: ANN001
        del option, widget
        if not self._title:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#202b38"))
        painter.setPen(QPen(QColor("#52687d"), 1.2))
        painter.drawRoundedRect(self.boundingRect(), 8.0, 8.0)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor("#e8f0f7"))
        painter.drawText(
            self.boundingRect().adjusted(10.0, 3.0, -10.0, -3.0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._title,
        )

    def apply(self, title: str, block_width: float) -> None:
        clean_title = title.strip()
        new_width = min(max(120.0, block_width * 0.72), max(120.0, block_width - 28.0))
        if new_width != self._width:
            self.prepareGeometryChange()
            self._width = new_width
        self._title = clean_title
        self.setVisible(bool(clean_title))
        self.setPos(14.0, -30.0)
        self.setToolTip(clean_title)
        self.update()


class CanvasCommentBubbleItem(QGraphicsObject):
    """Selectable, draggable, resizable oval comment attached to a block."""

    def __init__(
        self,
        parent_block: "CanvasTextBlockItem",
        *,
        moved_callback: Callable[[str, float], None],
        resized_callback: Callable[[str, float, float], None],
        edit_callback: Callable[[str], None],
    ) -> None:
        super().__init__(parent_block)
        self.parent_block = parent_block
        self.object_id = parent_block.object_id
        self._moved_callback = moved_callback
        self._resized_callback = resized_callback
        self._edit_callback = edit_callback
        self._comment = ""
        self._angle_degrees = 315.0
        self._width = 190.0
        self._height = 74.0
        self._dragging = False
        self._resizing = False
        self._resize_press_position = QPointF()
        self._resize_start_size = QPointF(self._width, self._height)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(8.0)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(-self._width / 2.0, -self._height / 2.0, self._width, self._height)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: ANN001
        del option, widget
        if not self._comment:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#2b2536"))
        border = QColor("#c69ae8") if self.isSelected() else QColor("#9874ba")
        painter.setPen(QPen(border, 2.2 if self.isSelected() else 1.5))
        painter.drawEllipse(self.boundingRect())
        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        text_option.setAlignment(Qt.AlignmentFlag.AlignCenter)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#f0e8f7"))
        painter.drawText(
            self.boundingRect().adjusted(12.0, 8.0, -12.0, -8.0),
            self._comment,
            text_option,
        )
        if self.isSelected():
            handle = self._resize_handle_rect()
            painter.setBrush(QColor("#c69ae8"))
            painter.setPen(QPen(QColor("#f4e7ff"), 1.0))
            painter.drawRoundedRect(handle, 2.0, 2.0)

    def apply(
        self,
        comment: str,
        angle_degrees: float,
        width: float,
        height: float,
    ) -> None:
        clean_comment = comment.strip()
        new_width = max(_MIN_COMMENT_WIDTH, float(width))
        new_height = max(_MIN_COMMENT_HEIGHT, float(height))
        if new_width != self._width or new_height != self._height:
            self.prepareGeometryChange()
            self._width = new_width
            self._height = new_height
        self._comment = clean_comment
        self._angle_degrees = float(angle_degrees) % 360.0
        self.setVisible(bool(self._comment))
        self._reposition()
        self.setToolTip(
            f"{self._comment}\nClick once to show the resize handle. Drag the oval around the block edge. "
            "Double-click to edit."
            if self._comment
            else ""
        )
        self.update()

    def update_parent_geometry(self) -> None:
        self._reposition()

    def _resize_handle_rect(self) -> QRectF:
        rect = self.boundingRect()
        size = _COMMENT_RESIZE_HANDLE_SIZE
        return QRectF(rect.right() - size, rect.bottom() - size, size, size)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        scene = self.scene()
        if scene is not None and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            scene.clearSelection()
        self.parent_block.setSelected(True)
        self.setSelected(True)
        if self._resize_handle_rect().contains(event.pos()):
            self._resizing = True
            self._resize_press_position = event.pos()
            self._resize_start_size = QPointF(self._width, self._height)
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._resizing:
            delta = event.pos() - self._resize_press_position
            new_width = max(_MIN_COMMENT_WIDTH, self._resize_start_size.x() + 2.0 * delta.x())
            new_height = max(_MIN_COMMENT_HEIGHT, self._resize_start_size.y() + 2.0 * delta.y())
            if new_width != self._width or new_height != self._height:
                self.prepareGeometryChange()
                self._width = new_width
                self._height = new_height
                self.update()
            event.accept()
            return
        if self._dragging:
            point = self.parent_block.mapFromScene(event.scenePos())
            center = QPointF(
                self.parent_block._display_width / 2.0,
                self.parent_block._display_height / 2.0,
            )
            self._angle_degrees = (
                math.degrees(math.atan2(point.y() - center.y(), point.x() - center.x())) % 360.0
            )
            self._reposition()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._resizing:
            self._resizing = False
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self._resized_callback(self.object_id, self._width, self._height)
            event.accept()
            return
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self._moved_callback(self.object_id, self._angle_degrees)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self.parent_block.block.locked:
            event.accept()
            return
        self._edit_callback(self.object_id)
        event.accept()

    def hoverMoveEvent(self, event) -> None:  # noqa: N802
        if self._resize_handle_rect().contains(event.pos()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        if not self._resizing and not self._dragging:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverLeaveEvent(event)

    def _reposition(self) -> None:
        width = self.parent_block._display_width
        height = self.parent_block._display_height
        center = QPointF(width / 2.0, height / 2.0)
        radians = math.radians(self._angle_degrees)
        dx = math.cos(radians)
        dy = math.sin(radians)
        half_width = max(1.0, width / 2.0)
        half_height = max(1.0, height / 2.0)
        x_scale = half_width / abs(dx) if abs(dx) > 0.001 else float("inf")
        y_scale = half_height / abs(dy) if abs(dy) > 0.001 else float("inf")
        scale = min(x_scale, y_scale)
        self.setPos(center.x() + dx * scale, center.y() + dy * scale)


class CanvasTextBlockItem(QGraphicsObject):
    """Movable visual projection of one persistent ``CanvasTextBlock``."""

    def __init__(
        self,
        block: CanvasTextBlock,
        *,
        is_root: bool = False,
        moved_callback: Callable[[str, float, float], None],
        resized_callback: Callable[[str, float, float], None],
        geometry_changed_callback: Callable[[str], None],
        edit_callback: Callable[[str], None],
        edit_title_callback: Callable[[str], None],
        edit_comment_callback: Callable[[str], None],
        comment_moved_callback: Callable[[str, float], None],
        comment_resized_callback: Callable[[str, float, float], None],
        quick_arrow_callback: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.block = block
        self.object_id = block.object_id
        self._moved_callback = moved_callback
        self._resized_callback = resized_callback
        self._geometry_changed_callback = geometry_changed_callback
        self._edit_callback = edit_callback
        self._edit_title_callback = edit_title_callback
        self._edit_comment_callback = edit_comment_callback
        self._comment_moved_callback = comment_moved_callback
        self._quick_arrow_callback = quick_arrow_callback
        self._is_root = is_root
        self._press_position = QPointF(block.position_x, block.position_y)
        self._display_width = block.width
        self._display_height = block.height
        self._resizing = False
        self._resize_press_scene_position = QPointF()
        self._resize_start_size = QPointF(block.width, block.height)
        self.setPos(block.position_x, block.position_y)
        self.setZValue(block.z_index)
        self._apply_interaction_flags()
        self.title_tab = CanvasTitleTabItem(self)
        self.comment_bubble = CanvasCommentBubbleItem(
            self,
            moved_callback=self._comment_moved_callback,
            resized_callback=comment_resized_callback,
            edit_callback=self._edit_comment_callback,
        )
        self.comment_bubble.setEnabled(not block.locked)
        self._sync_attachments()
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.ArrowCursor if block.locked else Qt.CursorShape.OpenHandCursor)
        self._update_tooltip()

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt naming convention.
        return QRectF(0.0, 0.0, self._display_width, self._display_height)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: ANN001
        del option, widget
        selected = self.isSelected()
        base_color = QColor("#18202b") if self.block.created_by == "dato" else QColor("#14262b")
        if selected:
            border_color = QColor("#6fbfe8")
        elif self._is_root:
            border_color = QColor("#d6a94d")
        else:
            border_color = QColor("#354454")
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(base_color)
        painter.setPen(QPen(border_color, 2.4 if selected or self._is_root else 1.2))
        painter.drawRoundedRect(self.boundingRect(), 12.0, 12.0)

        author = "DATO" if self.block.created_by == "dato" else "AMADEUS"
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.setPen(QColor("#7f91a6"))
        painter.drawText(QRectF(14.0, 10.0, self._display_width - 28.0, 18.0), author)

        if self._is_root:
            badge_rect = QRectF(self._display_width - 70.0, 8.0, 54.0, 22.0)
            painter.setBrush(QColor("#4b3a18"))
            painter.setPen(QPen(QColor("#d6a94d"), 1.0))
            painter.drawRoundedRect(badge_rect, 5.0, 5.0)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#f1d48c"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "ROOT")

        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        text_option.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        painter.setFont(QFont("Segoe UI", 11))
        painter.setPen(QColor("#e7edf4"))
        painter.drawText(
            QRectF(14.0, 34.0, self._display_width - 28.0, self._display_height - 48.0),
            self.block.text,
            text_option,
        )

        if selected and not self.block.locked:
            handle = self._resize_handle_rect()
            painter.setBrush(QColor("#6fbfe8"))
            painter.setPen(QPen(QColor("#d7f1ff"), 1.0))
            painter.drawRoundedRect(handle, 3.0, 3.0)

    def apply_model(self, block: CanvasTextBlock) -> None:
        """Refresh the item after the domain facade accepts an edit."""
        if block.width != self._display_width or block.height != self._display_height:
            self.prepareGeometryChange()
        self.block = block
        self._display_width = block.width
        self._display_height = block.height
        self.setZValue(block.z_index)
        self._apply_interaction_flags()
        self.comment_bubble.setEnabled(not block.locked)
        self.setCursor(Qt.CursorShape.ArrowCursor if block.locked else Qt.CursorShape.OpenHandCursor)
        if self.pos() != QPointF(block.position_x, block.position_y):
            self.setPos(block.position_x, block.position_y)
        self._sync_attachments()
        self.update()
        self._geometry_changed_callback(self.object_id)

    def _sync_attachments(self) -> None:
        self.title_tab.apply(self.block.title, self._display_width)
        self.comment_bubble.apply(
            self.block.comment,
            self.block.comment_anchor_degrees,
            self.block.comment_width,
            self.block.comment_height,
        )

    def set_root_state(self, is_root: bool) -> None:
        if self._is_root == is_root:
            return
        self._is_root = is_root
        self._update_tooltip()
        self.update()

    def _update_tooltip(self) -> None:
        details = [
            "Double-click to edit. Ctrl-click selects multiple blocks.",
            "Select once, then drag the bottom-right handle to resize.",
            "Right-click this block, then right-click another block to create an arrow.",
            "Use the Title and Comment toolbar buttons for optional attached annotations.",
        ]
        if self._is_root:
            details.insert(0, "Canvas root: directional ancestry is traced toward this block.")
        self.setToolTip("\n".join(details))

    def _apply_interaction_flags(self) -> None:
        flags = (
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        if not self.block.locked:
            flags |= QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        self.setFlags(flags)

    def itemChange(self, change, value):  # noqa: N802, ANN001
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._geometry_changed_callback(self.object_id)
        return result

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self.block.locked
            and self._resize_handle_rect().contains(event.pos())
        ):
            self._resizing = True
            self._resize_press_scene_position = event.scenePos()
            self._resize_start_size = QPointF(self._display_width, self._display_height)
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            event.accept()
            return
        self._press_position = self.pos()
        if not self.block.locked:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._resizing:
            self._resizing = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self._resized_callback(self.object_id, self._display_width, self._display_height)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self.setCursor(Qt.CursorShape.ArrowCursor if self.block.locked else Qt.CursorShape.OpenHandCursor)
        if not self.block.locked and self.pos() != self._press_position:
            position = self.pos()
            self._moved_callback(self.object_id, position.x(), position.y())

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self.block.locked:
            event.accept()
            return
        self._edit_callback(self.object_id)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._resizing:
            delta = event.scenePos() - self._resize_press_scene_position
            width = max(_MIN_BLOCK_WIDTH, self._resize_start_size.x() + delta.x())
            height = max(_MIN_BLOCK_HEIGHT, self._resize_start_size.y() + delta.y())
            if width != self._display_width or height != self._display_height:
                self.prepareGeometryChange()
                self._display_width = width
                self._display_height = height
                self._sync_attachments()
                self.update()
                self._geometry_changed_callback(self.object_id)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def hoverMoveEvent(self, event) -> None:  # noqa: N802
        if not self.block.locked and self.isSelected() and self._resize_handle_rect().contains(event.pos()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor if self.block.locked else Qt.CursorShape.OpenHandCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        if not self._resizing:
            self.setCursor(Qt.CursorShape.ArrowCursor if self.block.locked else Qt.CursorShape.OpenHandCursor)
        super().hoverLeaveEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if self.block.locked:
            event.accept()
            return
        self._quick_arrow_callback(self.object_id)
        event.accept()

    def _resize_handle_rect(self) -> QRectF:
        inset = 4.0
        return QRectF(
            self._display_width - _RESIZE_HANDLE_SIZE - inset,
            self._display_height - _RESIZE_HANDLE_SIZE - inset,
            _RESIZE_HANDLE_SIZE,
            _RESIZE_HANDLE_SIZE,
        )


class CanvasConnectorItem(QGraphicsObject):
    """Selectable visual projection of a semantic Canvas connector."""

    def __init__(
        self,
        connector: CanvasConnector,
        *,
        source_item: CanvasTextBlockItem,
        target_item: CanvasTextBlockItem,
        edit_callback: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.connector = connector
        self.connector_id = connector.connector_id
        self.source_item = source_item
        self.target_item = target_item
        self._edit_callback = edit_callback
        self._path = QPainterPath()
        self._arrow_head = QPolygonF()
        self._label_rect = QRectF()
        self._bounds = QRectF()
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(-20.0)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_geometry()
        self._update_tooltip()

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._bounds

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(14.0)
        selectable_shape = stroker.createStroke(self._path)
        if not self._arrow_head.isEmpty():
            arrow_path = QPainterPath()
            arrow_path.addPolygon(self._arrow_head)
            selectable_shape = selectable_shape.united(arrow_path)
        if not self._label_rect.isEmpty():
            label_path = QPainterPath()
            label_path.addRoundedRect(self._label_rect, 5.0, 5.0)
            selectable_shape = selectable_shape.united(label_path)
        return selectable_shape

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: ANN001
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = self.isSelected()
        line_color = QColor("#6fbfe8") if selected else QColor("#657487")
        painter.setPen(QPen(line_color, 3.0 if selected else 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)

        if self.connector.connector_type == "arrow" and not self._arrow_head.isEmpty():
            painter.setPen(QPen(line_color, 1.0))
            painter.setBrush(line_color)
            painter.drawPolygon(self._arrow_head)

        label_text = self._visible_label()
        if label_text and not self._label_rect.isEmpty():
            painter.setPen(QPen(QColor("#34475a"), 1.0))
            painter.setBrush(QColor("#111820"))
            painter.drawRoundedRect(self._label_rect, 5.0, 5.0)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            painter.setPen(QColor("#cbd8e6"))
            painter.drawText(self._label_rect, Qt.AlignmentFlag.AlignCenter, label_text)

    def apply_model(self, connector: CanvasConnector) -> None:
        self.connector = connector
        self.update_geometry()
        self._update_tooltip()
        self.update()

    def update_geometry(self) -> None:
        self.prepareGeometryChange()
        source_rect = self.source_item.sceneBoundingRect()
        target_rect = self.target_item.sceneBoundingRect()
        source_center = source_rect.center()
        target_center = target_rect.center()
        source_point = self._boundary_anchor(source_rect, target_center)
        target_point = self._boundary_anchor(target_rect, source_center)

        self._path = QPainterPath(source_point)
        self._path.lineTo(target_point)
        self._arrow_head = self._build_arrow_head(source_point, target_point)

        label_text = self._visible_label()
        if label_text:
            midpoint = QPointF(
                (source_point.x() + target_point.x()) / 2.0,
                (source_point.y() + target_point.y()) / 2.0,
            )
            label_width = min(260.0, max(64.0, len(label_text) * 7.2 + 20.0))
            self._label_rect = QRectF(
                midpoint.x() - label_width / 2.0,
                midpoint.y() - 15.0,
                label_width,
                30.0,
            )
        else:
            self._label_rect = QRectF()

        bounds = self._path.boundingRect().adjusted(-12.0, -12.0, 12.0, 12.0)
        if not self._arrow_head.isEmpty():
            bounds = bounds.united(self._arrow_head.boundingRect().adjusted(-4.0, -4.0, 4.0, 4.0))
        if not self._label_rect.isEmpty():
            bounds = bounds.united(self._label_rect.adjusted(-3.0, -3.0, 3.0, 3.0))
        self._bounds = bounds
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self.connector.metadata.get("mindmap_projection") is True:
            event.accept()
            return
        self._edit_callback(self.connector_id)
        event.accept()

    def _visible_label(self) -> str:
        if self.connector.label:
            return self.connector.label
        if self.connector.relation_type != DEFAULT_RELATION_TYPE:
            return self.connector.relation_type.replace("_", " ")
        return ""

    def _update_tooltip(self) -> None:
        relation = self.connector.relation_type.replace("_", " ")
        details = [f"{self.connector.connector_type.title()}: {relation}"]
        if self.connector.label:
            details.append(f"Label: {self.connector.label}")
        if self.connector.comment:
            details.append(f"Comment: {self.connector.comment}")
        details.append("Double-click to edit.")
        self.setToolTip("\n".join(details))

    @staticmethod
    def _boundary_anchor(rect: QRectF, toward: QPointF) -> QPointF:
        center = rect.center()
        dx = toward.x() - center.x()
        dy = toward.y() - center.y()
        if abs(dx) < 0.001 and abs(dy) < 0.001:
            return center
        half_width = max(1.0, rect.width() / 2.0)
        half_height = max(1.0, rect.height() / 2.0)
        x_scale = half_width / abs(dx) if abs(dx) > 0.001 else float("inf")
        y_scale = half_height / abs(dy) if abs(dy) > 0.001 else float("inf")
        scale = min(x_scale, y_scale)
        return QPointF(center.x() + dx * scale, center.y() + dy * scale)

    def _build_arrow_head(self, source_point: QPointF, target_point: QPointF) -> QPolygonF:
        if self.connector.connector_type != "arrow":
            return QPolygonF()
        dx = target_point.x() - source_point.x()
        dy = target_point.y() - source_point.y()
        length = math.hypot(dx, dy)
        if length < 1.0:
            return QPolygonF()
        unit_x = dx / length
        unit_y = dy / length
        perpendicular_x = -unit_y
        perpendicular_y = unit_x
        arrow_length = 16.0
        arrow_width = 7.0
        base = QPointF(
            target_point.x() - unit_x * arrow_length,
            target_point.y() - unit_y * arrow_length,
        )
        return QPolygonF(
            [
                target_point,
                QPointF(base.x() + perpendicular_x * arrow_width, base.y() + perpendicular_y * arrow_width),
                QPointF(base.x() - perpendicular_x * arrow_width, base.y() - perpendicular_y * arrow_width),
            ]
        )


class CanvasSurface(QGraphicsView):
    """Infinite-style surface with zoom, empty-space pan, and shortcuts."""

    def __init__(
        self,
        scene: QGraphicsScene,
        *,
        create_callback: Callable[[QPointF], None],
        delete_callback: Callable[[], None],
        cancel_callback: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(scene, parent)
        self._create_callback = create_callback
        self._delete_callback = delete_callback
        self._cancel_callback = cancel_callback
        self.setObjectName("canvasSurface")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setSceneRect(QRectF(-25000, -25000, 50000, 50000))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event) -> None:  # noqa: N802
        current_scale = self.transform().m11()
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        target_scale = current_scale * factor
        if 0.08 <= target_scale <= 6.0:
            self.scale(factor, factor)

    def visible_scene_rect(self) -> QRectF:
        """Return the current viewport bounds in scene coordinates."""

        return self.mapToScene(self.viewport().rect()).boundingRect()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self.itemAt(event.position().toPoint()) is None:
            self._create_callback(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace} and self.scene().selectedItems():
            self._delete_callback()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_callback()
            event.accept()
            return
        super().keyPressEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        painter.fillRect(rect, QColor("#0b0e13"))
        scale = max(0.01, self.transform().m11())
        grid_size = 48.0
        if scale < 0.35:
            grid_size *= 4
        elif scale < 0.7:
            grid_size *= 2

        left = math.floor(rect.left() / grid_size) * grid_size
        top = math.floor(rect.top() / grid_size) * grid_size
        lines: list[QLineF] = []
        x = left
        while x < rect.right():
            lines.append(QLineF(x, rect.top(), x, rect.bottom()))
            x += grid_size
        y = top
        while y < rect.bottom():
            lines.append(QLineF(rect.left(), y, rect.right(), y))
            y += grid_size

        painter.setPen(QPen(QColor(255, 255, 255, 12), 0))
        if lines:
            painter.drawLines(lines)
        painter.setPen(QPen(QColor(91, 176, 214, 34), 0))
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        del rect
        painter.save()
        painter.resetTransform()
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(200, 208, 218, 145))
        painter.drawText(
            18,
            self.viewport().height() - 20,
            "Viewport limits context  •  Right-click two blocks: quick arrow  •  Ctrl+Z: undo  •  Select + drag corner: resize",
        )
        painter.restore()


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
