"""Public module entry point for the AMADEUS Mind Map / Relevance Graph."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mindmap.models import GraphLink, GraphNeighborhood, GraphNode, GraphSnapshot, SourceReference
from mindmap.repository import SQLiteMindMapRepository
from mindmap.service import GraphListener, MindMapService


class MindMapModule:
    """Stable facade registered with AMADEUS Core.

    Other modules should call this facade or Core wrappers. They must never write
    directly to the SQLite repository or manipulate PyQt scene items.
    """

    def __init__(self, project_root: Path, graph_id: str = "main") -> None:
        self.repository = SQLiteMindMapRepository(project_root)
        self.service = MindMapService(self.repository, graph_id=graph_id)

    def subscribe(self, listener: GraphListener) -> Callable[[], None]:
        return self.service.subscribe(listener)

    def get_snapshot(self) -> GraphSnapshot:
        return self.service.get_snapshot()

    def list_nodes(self) -> list[GraphNode]:
        return self.service.list_nodes()

    def list_recent_nodes(self, limit: int) -> list[GraphNode]:
        """Return a bounded newest-first node window for external consumers."""
        return self.service.list_recent_nodes(limit)

    def list_links(self) -> list[GraphLink]:
        return self.service.list_links()

    def get_node(self, node_id: str) -> GraphNode | None:
        return self.service.get_node(node_id)

    def get_link(self, link_id: str) -> GraphLink | None:
        return self.service.get_link(link_id)

    def create_node(self, **fields: Any) -> GraphNode:
        return self.service.create_node(**fields)

    def update_node(self, node_id: str, **changes: Any) -> GraphNode:
        return self.service.update_node(node_id, **changes)

    def move_node(self, node_id: str, position_x: float, position_y: float, **fields: Any) -> GraphNode:
        return self.service.move_node(node_id, position_x, position_y, **fields)

    def move_nodes(self, positions: dict[str, tuple[float, float]]) -> None:
        self.service.move_nodes(positions)

    def delete_node(self, node_id: str, **fields: Any) -> None:
        self.service.delete_node(node_id, **fields)

    def create_link(self, **fields: Any) -> GraphLink:
        return self.service.create_link(**fields)

    def update_link(self, link_id: str, **changes: Any) -> GraphLink:
        return self.service.update_link(link_id, **changes)

    def delete_link(self, link_id: str, **fields: Any) -> None:
        self.service.delete_link(link_id, **fields)

    def search_nodes(self, query: str, limit: int = 50) -> list[GraphNode]:
        return self.service.search_nodes(query, limit=limit)

    def get_neighborhood(self, root_node_id: str, depth: int = 1) -> GraphNeighborhood:
        return self.service.get_neighborhood(root_node_id, depth=depth)

    def upsert_source_node(self, **fields: Any) -> GraphNode:
        return self.service.upsert_source_node(**fields)

    def export_to_json(self, destination: Path | str) -> Path:
        return self.service.export_to_json(destination)

    def import_from_json(self, source: Path | str, *, replace_graph: bool = False) -> GraphSnapshot:
        return self.service.import_from_json(source, replace_graph=replace_graph)
