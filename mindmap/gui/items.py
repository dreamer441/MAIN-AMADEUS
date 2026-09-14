"""Living QGraphics items for the AMADEUS Mind Map.

The older AMADEUS graph succeeded because nodes felt like a relevance space,
not form fields placed on a canvas.  These items restore that visual language
while retaining the current service-owned graph architecture.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
)
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from mindmap.models import GraphLink, GraphNode


class GraphNodeItem(QGraphicsObject):
    """Movable visual representation of one persisted graph node."""

    TYPE_COLORS = {
        "chat": "#5b8def",
        "sheet": "#50be8c",
        "comment": "#ec8fb8",
        "material": "#e6aa50",
        "export": "#a880ff",
        "feature": "#64d2e6",
        "task": "#f0d25a",
        "bug": "#eb5f5f",
        "decision": "#78e6b4",
        "memory": "#a880ff",
        "idea": "#7ca8d8",
        "reference": "#b8a47b",
        "container": "#6b7d99",
        "custom": "#8d99ae",
    }

    def __init__(
        self,
        node: GraphNode,
        *,
        moved_callback: Callable[[str, float, float], None],
        drag_started_callback: Callable[[str], None] | None = None,
        dragged_callback: Callable[[str, float, float], None] | None = None,
        hover_callback: Callable[[str | None], None] | None = None,
        double_click_callback: Callable[[str], None] | None = None,
        relevance: float = 0.0,
        visual_radius: float | None = None,
        opacity: float = 1.0,
        layer_score: float = 0.5,
    ) -> None:
        super().__init__()
        self.node = node
        self._moved_callback = moved_callback
        self._drag_started_callback = drag_started_callback
        self._dragged_callback = dragged_callback
        self._user_dragging = False
        self._press_scene_pos: QPointF | None = None
        self._drag_threshold = 6.0
        self._hover_callback = hover_callback
        self._double_click_callback = double_click_callback
        self._relevance = max(0.0, min(1.0, relevance))
        self._visual_radius = visual_radius
        self._base_opacity = max(0.18, min(1.0, opacity))
        self._layer_score = max(0.0, min(1.0, layer_score))
        self._focus_level = "normal"
        self._links: set[GraphLinkItem] = set()
        self._hovered = False
        self.setPos(node.position_x, node.position_y)
        self._apply_interaction_flags()
        self.setToolTip(self._tooltip_text())
        self.setZValue(10.0 + self._layer_score * 20.0)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

    @property
    def node_id(self) -> str:
        return self.node.node_id

    @property
    def radius(self) -> float:
        if self._visual_radius is not None:
            return max(14.0, self._visual_radius)
        return 17.0 + self.node.importance * 16.0 + self._relevance * 9.0

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt naming.
        radius = self.radius
        if self._is_canvas_backed():
            rectangle = self._canvas_rectangle()
            return QRectF(
                rectangle.left() - 10,
                rectangle.top() - 13,
                rectangle.width() + 20,
                rectangle.height() + 48,
            )
        label_width = max(104.0, radius * 4.6)
        return QRectF(-label_width / 2, -radius - 13, label_width, radius * 2 + 48)

    def shape(self) -> QPainterPath:  # noqa: N802 - Qt naming.
        path = QPainterPath()
        if self._is_canvas_backed():
            rectangle = self._canvas_rectangle()
            path.addRoundedRect(rectangle, 9, 9)
            return path
        radius = self.radius
        path.addEllipse(QRectF(-radius, -radius, radius * 2, radius * 2))
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = self.radius
        orb = QRectF(-radius, -radius, radius * 2, radius * 2)
        is_canvas = self._is_canvas_backed()
        node_shape = self._canvas_rectangle() if is_canvas else orb

        opacity = self._base_opacity
        if self._focus_level == "dimmed":
            opacity *= 0.22
        elif self._focus_level == "neighbor":
            opacity = max(opacity, 0.82)
        elif self._focus_level == "selected":
            opacity = 1.0

        fill = QColor(self.TYPE_COLORS.get(self.node.node_type, "#94a3b8"))
        fill.setAlphaF(opacity)
        border = QColor(225, 231, 239, int(150 + 90 * opacity))
        border_width = 1.15

        if self._pinned():
            border = QColor("#f5dc78")
        if self._central():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(70, 220, 255, int(110 + 100 * opacity)), 2.1))
            if is_canvas:
                painter.drawRoundedRect(node_shape.adjusted(-10, -10, 10, 10), 12, 12)
            else:
                painter.drawEllipse(orb.adjusted(-10, -10, 10, 10))
        if self._hovered:
            painter.setBrush(QBrush(QColor(255, 255, 255, 28)))
            painter.setPen(Qt.PenStyle.NoPen)
            if is_canvas:
                painter.drawRoundedRect(node_shape.adjusted(-7, -7, 7, 7), 11, 11)
            else:
                painter.drawEllipse(orb.adjusted(-7, -7, 7, 7))
        if self.isSelected() or self._focus_level == "selected":
            painter.setBrush(QBrush(QColor(255, 255, 255, 36)))
            painter.setPen(Qt.PenStyle.NoPen)
            if is_canvas:
                painter.drawRoundedRect(node_shape.adjusted(-9, -9, 9, 9), 12, 12)
            else:
                painter.drawEllipse(orb.adjusted(-9, -9, 9, 9))
            border = QColor("#ffffff")
            border_width = 2.7

        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, border_width))
        if is_canvas:
            painter.drawRoundedRect(node_shape, 9, 9)
        else:
            painter.drawEllipse(orb)

        # A restrained inner glow gives important nodes depth without turning
        # them into large filled buttons.
        inner = QColor(255, 255, 255, int(12 + 35 * self._layer_score))
        painter.setBrush(QBrush(inner))
        painter.setPen(Qt.PenStyle.NoPen)
        if is_canvas:
            painter.drawRoundedRect(
                node_shape.adjusted(
                    node_shape.width() * 0.35,
                    node_shape.height() * 0.35,
                    -node_shape.width() * 0.35,
                    -node_shape.height() * 0.35,
                ),
                4,
                4,
            )
        else:
            painter.drawEllipse(orb.adjusted(radius * 0.35, radius * 0.35, -radius * 0.35, -radius * 0.35))

        if self._pinned():
            painter.setBrush(QBrush(QColor("#f5dc78")))
            painter.drawEllipse(QPointF(0, node_shape.top() - 8), 3.2, 3.2)

        type_font = QFont("Segoe UI", 7)
        type_font.setBold(True)
        painter.setFont(type_font)
        painter.setPen(QColor(235, 240, 247, int(120 + 120 * opacity)))
        painter.drawText(
            QRectF(node_shape.left(), -7, node_shape.width(), 14),
            Qt.AlignmentFlag.AlignCenter,
            self.node.node_type.upper()[:12],
        )

        title_font = QFont("Segoe UI", 9)
        title_font.setBold(self.isSelected() or self.node.importance >= 0.75)
        painter.setFont(title_font)
        metrics = QFontMetrics(title_font)
        max_width = max(98, int(node_shape.width() - 6))
        title = metrics.elidedText(self.node.title, Qt.TextElideMode.ElideRight, max_width)
        title_color = QColor(239, 243, 248, int(115 + 140 * opacity))
        painter.setPen(title_color)
        painter.drawText(
            QRectF(-max_width / 2, node_shape.bottom() + 6, max_width, 20),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            title,
        )

    def _is_canvas_backed(self) -> bool:
        """Return whether this node is projected from a Canvas text block."""
        reference = self.node.source_reference
        return reference is not None and reference.source_type == "canvas_block"

    def _canvas_rectangle(self) -> QRectF:
        """Return the compact rounded rectangle used by Canvas-backed nodes."""
        return QRectF(-42, -20, 84, 40)

    def connection_point_toward(self, target: QPointF) -> QPointF:
        """Return the visible edge point nearest a link's other endpoint."""

        center = self.pos()
        dx = target.x() - center.x()
        dy = target.y() - center.y()
        distance = math.hypot(dx, dy)
        if distance == 0:
            return center
        if not self._is_canvas_backed():
            scale = (self.radius + 3.0) / distance
            return QPointF(center.x() + dx * scale, center.y() + dy * scale)

        rectangle = self._canvas_rectangle()
        scale = min(
            (rectangle.width() / 2) / abs(dx) if dx else float("inf"),
            (rectangle.height() / 2) / abs(dy) if dy else float("inf"),
        )
        return QPointF(center.x() + dx * scale, center.y() + dy * scale)

    def add_link(self, link: "GraphLinkItem") -> None:
        self._links.add(link)

    def remove_link(self, link: "GraphLinkItem") -> None:
        self._links.discard(link)

    def update_node(
        self,
        node: GraphNode,
        relevance: float | None = None,
        *,
        visual_radius: float | None = None,
        opacity: float | None = None,
        layer_score: float | None = None,
    ) -> None:
        """Refresh persisted and visual projection fields in-place."""
        self.prepareGeometryChange()
        self.node = node
        if relevance is not None:
            self._relevance = max(0.0, min(1.0, relevance))
        if visual_radius is not None:
            self._visual_radius = visual_radius
        if opacity is not None:
            self._base_opacity = max(0.18, min(1.0, opacity))
        if layer_score is not None:
            self._layer_score = max(0.0, min(1.0, layer_score))
            self.setZValue(10.0 + self._layer_score * 20.0)
        if self.pos() != QPointF(node.position_x, node.position_y):
            self.setPos(node.position_x, node.position_y)
        self._apply_interaction_flags()
        self.setToolTip(self._tooltip_text())
        self.update()

    def set_visual_position(self, x: float, y: float) -> None:
        """Move for visual simulation without invoking persistence callbacks."""
        self.setPos(x, y)

    def set_focus_level(self, level: str) -> None:
        if level not in {"normal", "selected", "neighbor", "dimmed"}:
            level = "normal"
        if self._focus_level != level:
            self._focus_level = level
            self.update()

    def _apply_interaction_flags(self) -> None:
        flags = (
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        if not self.node.position_locked and not self._pinned():
            flags |= QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        self.setFlags(flags)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: object) -> object:  # noqa: N802
        if change is QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for link in tuple(self._links):
                link.update_path()
            if self._user_dragging and self._dragged_callback is not None:
                position = self.pos()
                self._dragged_callback(self.node_id, position.x(), position.y())
        return super().itemChange(change, value)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # A normal selection click must not wake graph physics. The old behavior
        # treated every press as a drag, which made the whole canvas visibly
        # reflow even when Dato only wanted to inspect a node.
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_scene_pos = event.scenePos()
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        movable = not self.node.position_locked and not self._pinned()
        if movable and self._press_scene_pos is not None:
            delta = event.scenePos() - self._press_scene_pos
            if not self._user_dragging and math.hypot(delta.x(), delta.y()) >= self._drag_threshold:
                self._user_dragging = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                if self._drag_started_callback is not None:
                    self._drag_started_callback(self.node_id)
        # Ignore tiny pointer jitter so the built-in movable-item behavior does
        # not shift a node before the drag threshold is crossed.
        if movable and not self._user_dragging:
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self.unsetCursor()
        super().mouseReleaseEvent(event)
        was_dragging = self._user_dragging
        self._user_dragging = False
        self._press_scene_pos = None
        if self.node.position_locked or self._pinned() or not was_dragging:
            return
        position = self.pos()
        if self._dragged_callback is not None:
            self._dragged_callback(self.node_id, position.x(), position.y())
        self._moved_callback(self.node_id, position.x(), position.y())

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self._double_click_callback is not None:
            self._double_click_callback(self.node_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()
        if self._hover_callback:
            self._hover_callback(self.node_id)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.unsetCursor()
        self.update()
        if self._hover_callback:
            self._hover_callback(None)
        super().hoverLeaveEvent(event)

    def _pinned(self) -> bool:
        return bool(self.node.metadata.get("mindmap_pinned", self.node.position_locked))

    def _central(self) -> bool:
        return bool(self.node.metadata.get("mindmap_central", False))

    def _tooltip_text(self) -> str:
        description = self.node.description or self.node.content or "No stored context"
        if len(description) > 420:
            description = description[:417].rstrip() + "..."
        return (
            f"{self.node.title}\n"
            f"Type: {self.node.node_type}\n"
            f"Importance: {self.node.importance:.2f} | Confidence: {self.node.confidence:.2f}\n\n"
            f"{description}"
        )


class GraphLinkItem(QGraphicsPathItem):
    """Clean selectable relationship line with one midpoint interaction point.

    The graph stays visually quiet: relationship details live in the Context
    panel after the midpoint point (or line) is clicked.
    """

    TYPE_COLORS = {
        "supports": "#64d8a4",
        "contradicts": "#ef7474",
        "depends_on": "#e6b85c",
        "part_of": "#72a7ef",
        "contains": "#72a7ef",
        "derived_from": "#a78bfa",
        "references": "#9aa5b1",
        "solves": "#61d4c4",
    }

    def __init__(self, link: GraphLink, source: GraphNodeItem, target: GraphNodeItem) -> None:
        super().__init__()
        self.link = link
        self.source = source
        self.target = target
        self._focus_level = "normal"
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.setZValue(1.0)
        source.add_link(self)
        target.add_link(self)
        self.update_path()
        self.setToolTip(self._tooltip_text())

    @property
    def link_id(self) -> str:
        return self.link.link_id

    def update_link(self, link: GraphLink) -> None:
        self.link = link
        self.setToolTip(self._tooltip_text())
        self.update_path()
        self.update()

    def set_focus_level(self, level: str) -> None:
        if level not in {"normal", "connected", "dimmed"}:
            level = "normal"
        if self._focus_level != level:
            self._focus_level = level
            self.update()

    def update_path(self) -> None:
        start_center = self.source.pos()
        end_center = self.target.pos()
        start = self.source.connection_point_toward(end_center)
        end = self.target.connection_point_toward(start_center)
        path = QPainterPath(start)
        path.lineTo(end)
        self.setPath(path)

    def shape(self) -> QPainterPath:  # noqa: N802 - Qt naming.
        """Make the thin line and midpoint point comfortable to click."""
        stroker = QPainterPathStroker()
        stroker.setWidth(14.0)
        shape = stroker.createStroke(self.path())
        midpoint = self.path().pointAtPercent(0.5)
        shape.addEllipse(QRectF(midpoint.x() - 8, midpoint.y() - 8, 16, 16))
        return shape

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.TYPE_COLORS.get(self.link.link_type, "#77828f"))
        alpha = int(50 + self.link.confidence * 78 + self.link.permanence * 38)
        width = 0.7 + self.link.strength * 1.5
        if self.link.is_temporary:
            alpha = int(alpha * 0.60)
        if self._focus_level == "dimmed":
            alpha = max(12, int(alpha * 0.16))
            width *= 0.72
        elif self._focus_level == "connected":
            alpha = max(alpha, 180)
            width += 0.7
        if self.isSelected():
            color = QColor("#edf5ff")
            alpha = 245
            width += 1.0
        color.setAlpha(max(12, min(245, alpha)))

        pen = QPen(color, width)
        if self.link.is_temporary:
            pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

        # The midpoint is the only persistent relationship control. Selecting it
        # opens full link details in the Context panel instead of cluttering map.
        midpoint = self.path().pointAtPercent(0.5)
        point_radius = 4.8 if self.isSelected() else (4.0 if self._focus_level == "connected" else 3.2)
        painter.setPen(QPen(QColor(225, 235, 245, min(245, alpha + 40)), 0.9))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(midpoint, point_radius, point_radius)
        if self.isSelected():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(235, 245, 255, 180), 1.0))
            painter.drawEllipse(midpoint, point_radius + 3.2, point_radius + 3.2)

    def detach(self) -> None:
        self.source.remove_link(self)
        self.target.remove_link(self)

    def _tooltip_text(self) -> str:
        evidence = self.link.evidence.strip()
        if len(evidence) > 300:
            evidence = evidence[:297].rstrip() + "..."
        injection = self.link.metadata.get("inject_into_chat", True)
        return (
            f"{self.link.link_type}\n"
            f"Strength: {self.link.strength:.2f} | Confidence: {self.link.confidence:.2f}\n"
            f"Chat injection: {'on' if injection is not False else 'off'}"
            + (f"\n\nEvidence: {evidence}" if evidence else "")
        )
