"""Graphics items that render and manipulate Canvas blocks and connectors."""

from __future__ import annotations

import math
from typing import Callable
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
    QTextOption,
)
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject
from canvas_module import DEFAULT_RELATION_TYPE, CanvasConnector, CanvasTextBlock

from .constants import (
    _COMMENT_RESIZE_HANDLE_SIZE,
    _MIN_BLOCK_HEIGHT,
    _MIN_BLOCK_WIDTH,
    _MIN_COMMENT_HEIGHT,
    _MIN_COMMENT_WIDTH,
    _RESIZE_HANDLE_SIZE,
)


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
