"""QGraphics items used by the AMADEUS Mind Map view."""

from __future__ import annotations

import math
from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsPathItem, QStyleOptionGraphicsItem, QWidget

from mindmap.models import GraphLink, GraphNode


class GraphNodeItem(QGraphicsObject):
    """Movable visual representation of one persisted graph node."""

    TYPE_COLORS = {
        "chat": "#5b8def", "sheet": "#50be8c", "material": "#e6aa50",
        "feature": "#64d2e6", "task": "#f0d25a", "bug": "#eb5f5f",
        "decision": "#78e6b4", "memory": "#a880ff", "idea": "#7ca8d8",
    }

    def __init__(
        self,
        node: GraphNode,
        *,
        moved_callback: Callable[[str, float, float], None],
        hover_callback: Callable[[str | None], None] | None = None,
        relevance: float = 0.0,
    ) -> None:
        super().__init__()
        self.node = node
        self._moved_callback = moved_callback
        self._hover_callback = hover_callback
        self._relevance = max(0.0, min(1.0, relevance))
        self._links: set[GraphLinkItem] = set()
        self._hovered = False
        self.setPos(node.position_x, node.position_y)
        self._apply_interaction_flags()
        self.setToolTip(self._tooltip_text())
        self.setZValue(10.0)
        self.setAcceptHoverEvents(True)

    @property
    def node_id(self) -> str:
        return self.node.node_id

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt naming.
        radius = self.radius
        return QRectF(-radius, -radius, radius * 2, radius * 2)

    @property
    def radius(self) -> float:
        return 24.0 + self.node.importance * 28.0 + self._relevance * 12.0

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        rect = self.boundingRect()
        fill = QColor(self.TYPE_COLORS.get(self.node.node_type, "#94a3b8"))
        fill.setAlpha(215)
        border = QColor("#dbeafe")
        if self.isSelected():
            border = QColor("#ffffff")
        elif self._hovered:
            border = QColor("#fde68a")
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(border, 3.0 if self.isSelected() else 1.7))
        painter.setBrush(QBrush(fill))
        if self._central():
            painter.setPen(QPen(QColor("#67e8f9"), 2.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect.adjusted(-8, -8, 8, 8))
            painter.setPen(QPen(border, 3.0 if self.isSelected() else 1.7))
            painter.setBrush(QBrush(fill))
        painter.drawEllipse(rect)

        title_font = QFont(painter.font())
        title_font.setPointSize(9)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QPen(QColor("#17212b")))
        title_rect = QRectF(rect.left() + 8, rect.top() + 12, rect.width() - 16, rect.height() - 24)
        elided_title = QFontMetrics(title_font).elidedText(
            self.node.title, Qt.TextElideMode.ElideRight, int(title_rect.width())
        )
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            elided_title,
        )

        if self.node.position_locked:
            painter.setPen(QPen(QColor("#6b7280")))
            painter.drawText(
                QRectF(rect.right() - 22, rect.top() + 4, 18, 18),
                Qt.AlignmentFlag.AlignCenter,
                "L",
            )

        if self._pinned():
            painter.setPen(QPen(QColor("#fde68a")))
            painter.drawText(QRectF(-8, rect.top() - 19, 16, 16), Qt.AlignmentFlag.AlignCenter, "P")

    def add_link(self, link: "GraphLinkItem") -> None:
        self._links.add(link)

    def remove_link(self, link: "GraphLinkItem") -> None:
        self._links.discard(link)

    def update_node(self, node: GraphNode) -> None:
        self.prepareGeometryChange()
        self.node = node
        if self.pos() != QPointF(node.position_x, node.position_y):
            self.setPos(node.position_x, node.position_y)
        self._apply_interaction_flags()
        self.setToolTip(self._tooltip_text())
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
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if self.node.position_locked or self._pinned():
            return
        position = self.pos()
        self._moved_callback(self.node_id, position.x(), position.y())

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        if self._hover_callback:
            self._hover_callback(self.node_id)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        if self._hover_callback:
            self._hover_callback(None)
        super().hoverLeaveEvent(event)

    def _pinned(self) -> bool:
        return bool(self.node.metadata.get("mindmap_pinned", self.node.position_locked))

    def _central(self) -> bool:
        return bool(self.node.metadata.get("mindmap_central", False))

    def _tooltip_text(self) -> str:
        description = self.node.description or "No description"
        return f"{self.node.title}\nType: {self.node.node_type}\n{description}"


class GraphLinkItem(QGraphicsPathItem):
    """Selectable relationship line that follows its source and target nodes."""

    def __init__(self, link: GraphLink, source: GraphNodeItem, target: GraphNodeItem) -> None:
        super().__init__()
        self.link = link
        self.source = source
        self.target = target
        self.label_item = None
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
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

    def update_path(self) -> None:
        start = self.source.pos()
        end = self.target.pos()
        delta_x = end.x() - start.x()
        control_offset = max(50.0, abs(delta_x) * 0.45)
        direction = 1.0 if delta_x >= 0 else -1.0
        path = QPainterPath(start)
        path.cubicTo(
            QPointF(start.x() + control_offset * direction, start.y()),
            QPointF(end.x() - control_offset * direction, end.y()),
            end,
        )
        self.setPath(path)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = 1.2 + self.link.strength * 2.2
        color = QColor("#2563eb") if self.isSelected() else QColor("#718096")
        painter.setPen(QPen(color, width))
        painter.setBrush(QBrush(color))
        painter.drawPath(self.path())

        end = self.path().pointAtPercent(1.0)
        before_end = self.path().pointAtPercent(0.96)
        angle = math.atan2(end.y() - before_end.y(), end.x() - before_end.x())
        arrow_size = 9.0
        left = QPointF(
            end.x() - arrow_size * math.cos(angle - math.pi / 6),
            end.y() - arrow_size * math.sin(angle - math.pi / 6),
        )
        right = QPointF(
            end.x() - arrow_size * math.cos(angle + math.pi / 6),
            end.y() - arrow_size * math.sin(angle + math.pi / 6),
        )
        painter.drawPolygon(QPolygonF([end, left, right]))

        midpoint = self.path().pointAtPercent(0.5)
        label = self.link.label or self.link.link_type.replace("_", " ")
        label_rect = QRectF(midpoint.x() - 65, midpoint.y() - 12, 130, 24)
        painter.setPen(QPen(QColor("#2d3748")))
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(label_rect, 5, 5)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)

    def detach(self) -> None:
        self.source.remove_link(self)
        self.target.remove_link(self)

    def _tooltip_text(self) -> str:
        return (
            f"{self.link.link_type}\n"
            f"Strength: {self.link.strength:.2f}\n"
            f"Confidence: {self.link.confidence:.2f}"
        )
