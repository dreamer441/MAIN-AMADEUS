"""Canvas scene surface with viewport navigation and interaction callbacks."""

from __future__ import annotations

import math
from typing import Callable
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QGraphicsScene, QGraphicsView, QWidget


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
