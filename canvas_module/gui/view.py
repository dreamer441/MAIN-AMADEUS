"""Visible PyQt6 foundation for the AMADEUS Infinite Canvas."""

from __future__ import annotations

import math
from typing import Any

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QGraphicsScene, QGraphicsView, QLabel, QVBoxLayout, QWidget

from canvas_module.models import CanvasWorkspaceDescriptor


class CanvasSurface(QGraphicsView):
    """Empty infinite-style surface prepared for future structured objects.

    This phase deliberately implements navigation only. Text blocks, selection,
    connectors, persistence, and viewport context will be layered onto this
    surface in later phases instead of being simulated by placeholder buttons.
    """

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setObjectName("canvasSurface")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setSceneRect(QRectF(-25000, -25000, 50000, 50000))
        self.setFrameShape(QFrame.Shape.NoFrame)

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt naming convention.
        """Zoom around the cursor while keeping useful navigation limits."""
        current_scale = self.transform().m11()
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        target_scale = current_scale * factor
        if 0.08 <= target_scale <= 6.0:
            self.scale(factor, factor)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        """Draw a quiet adaptive grid without creating persistent scene items."""
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
        """Show honest navigation guidance without claiming object tools exist."""
        del rect
        painter.save()
        painter.resetTransform()
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(200, 208, 218, 145))
        painter.drawText(
            18,
            self.viewport().height() - 20,
            "Wheel: zoom  •  drag empty space: pan  •  structured Canvas objects are the next phase",
        )
        painter.restore()


class CanvasView(QWidget):
    """Mount the Canvas module as a persistent main-window page."""

    def __init__(self, core: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.module_name = "Canvas"
        self.descriptor = self._load_descriptor(core)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(self.descriptor.title)
        title.setObjectName("canvasTitle")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")

        purpose = QLabel(self.descriptor.purpose)
        purpose.setObjectName("canvasPurpose")
        purpose.setWordWrap(True)
        purpose.setStyleSheet("color: #7f8a99;")

        self.status_label = QLabel(
            "Canvas foundation ready. Next: typed blocks, selection, connectors, persistence, and viewport context."
        )
        self.status_label.setObjectName("canvasStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #9aa7b8; padding-bottom: 4px;")

        self.scene = QGraphicsScene(self)
        self.surface = CanvasSurface(self.scene, self)

        layout.addWidget(title)
        layout.addWidget(purpose)
        layout.addWidget(self.status_label)
        layout.addWidget(self.surface, stretch=1)

    @staticmethod
    def _load_descriptor(core: Any) -> CanvasWorkspaceDescriptor:
        """Ask Core for module metadata and degrade safely in test shells."""
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
