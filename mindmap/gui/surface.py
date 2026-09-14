"""Zoom, grid painting, and pointer navigation for the Mind Map canvas."""

from __future__ import annotations

import math

from PyQt6.QtCore import QLineF, QPointF, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QGraphicsScene, QGraphicsView, QWidget

from mindmap.gui.items import GraphNodeItem


class MindMapCanvas(QGraphicsView):
    """Zoomable relevance canvas with a quiet grid and inline guidance."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setSceneRect(QRectF(-5000, -5000, 10000, 10000))
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def set_fast_drag_mode(self, enabled: bool) -> None:
        """Reduce repaint cost only while a node is actively being dragged."""
        self.setRenderHint(QPainter.RenderHint.Antialiasing, not enabled)
        mode = (
            QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate
            if enabled
            else QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate
        )
        self.setViewportUpdateMode(mode)

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt naming.
        current = self.transform().m11()
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        target = current * factor
        if 0.18 <= target <= 4.0:
            self.scale(factor, factor)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        painter.fillRect(rect, QColor("#090c10"))
        scale = max(0.01, self.transform().m11())
        grid = 48.0
        if scale < 0.45:
            grid *= 2
        left = math.floor(rect.left() / grid) * grid
        top = math.floor(rect.top() / grid) * grid
        lines: list[QLineF] = []
        x = left
        while x < rect.right():
            lines.append(QLineF(x, rect.top(), x, rect.bottom()))
            x += grid
        y = top
        while y < rect.bottom():
            lines.append(QLineF(rect.left(), y, rect.right(), y))
            y += grid
        painter.setPen(QPen(QColor(255, 255, 255, 11), 0))
        if lines:
            painter.drawLines(lines)
        painter.setPen(QPen(QColor(84, 178, 220, 24), 0))
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        del rect
        painter.save()
        painter.resetTransform()
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(188, 199, 211, 120))
        painter.drawText(16, self.viewport().height() - 18, "Wheel: zoom  •  drag empty space: pan  •  double-click node: open source")
        painter.restore()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt naming.
        item = self.itemAt(event.pos())
        if isinstance(item, GraphNodeItem):
            # The node item handles source opening. Keeping the canvas centred
            # makes the result feel deliberate even for manual nodes.
            self.centerOn(item)
        super().mouseDoubleClickEvent(event)
