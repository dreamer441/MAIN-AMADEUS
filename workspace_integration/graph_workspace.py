"""Coordinate graph operations with their public source synchronization boundary."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


class GraphWorkspace:
    """Coordinate graph operations with their public source synchronization boundary."""

    def __init__(self, *, mind_map_module: Any, mind_map_workspace_sync: Any) -> None:
        """Receive the public services needed by this workflow."""
        self.mind_map_module = mind_map_module
        self.mind_map_workspace_sync = mind_map_workspace_sync

    def subscribe_mind_map(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        """Subscribe a GUI or adapter to completed graph changes through Core."""
        if not callable(listener):
            raise ValueError("listener must be callable")

        def publish_safe_event(event: dict[str, Any]) -> None:
            listener({
                key: event[key]
                for key in ("event_type", "entity_type", "entity_id", "graph_id", "created_at")
                if key in event
            })

        return self.mind_map_module.subscribe(publish_safe_event)

    def get_mind_map_snapshot(self) -> Any:
        """Return the active graph snapshot for a Core-mediated view refresh."""
        return self.mind_map_module.get_snapshot()

    def create_mind_map_node(self, **fields: Any) -> Any:
        """Create one validated graph-only node through the Mind Map module."""
        node = self.mind_map_module.create_node(**fields)
        self.mind_map_workspace_sync.reconcile_canvas_projection()
        return node

    def create_mind_map_workspace_node(self, **fields: Any) -> Any:
        """Create a node and, for supported types, its real AMADEUS object."""
        return self.mind_map_workspace_sync.create_workspace_node(**fields)

    def update_mind_map_node(self, node_id: str, **changes: Any) -> Any:
        """Update one graph node and mirror content edits to its source object."""
        existing = self.mind_map_module.get_node(node_id)
        if existing is None:
            raise ValueError(f"Unknown mind map node: {node_id}")
        self.mind_map_workspace_sync.update_workspace_source_from_node(existing, changes)
        node = self.mind_map_module.update_node(node_id, **changes)
        self.mind_map_workspace_sync.reconcile_canvas_projection()
        return node

    def move_mind_map_node(self, node_id: str, position_x: float, position_y: float, **fields: Any) -> Any:
        """Persist a graph node position without exposing graph storage to the GUI."""
        node = self.mind_map_module.move_node(node_id, position_x, position_y, **fields)
        self.mind_map_workspace_sync.reconcile_canvas_projection()
        return node

    def move_mind_map_nodes(self, positions: dict[str, tuple[float, float]]) -> None:
        """Persist a complete layout projection in one graph transaction."""
        self.mind_map_module.move_nodes(positions)
        self.mind_map_workspace_sync.reconcile_canvas_projection()

    def delete_mind_map_node(self, node_id: str, delete_source: bool = True, **fields: Any) -> None:
        """Delete one graph node and, by default, its real workspace object.

        ``delete_source=False`` remains available for future archival/relinking
        interfaces, but the normal Mind Map delete action mirrors Dato's stated
        expectation that a source-backed node owns the corresponding object.
        """
        existing = self.mind_map_module.get_node(node_id)
        if existing is None:
            raise ValueError(f"Unknown mind map node: {node_id}")
        if delete_source:
            self.mind_map_workspace_sync.delete_workspace_source_for_node(existing)
        if self.mind_map_module.get_node(node_id) is not None:
            self.mind_map_module.delete_node(node_id, **fields)
        self.mind_map_workspace_sync.reconcile_canvas_projection()

    def create_mind_map_link(self, **fields: Any) -> Any:
        """Create a relationship and materialize workspace-typed chat neighbors."""
        link = self.mind_map_module.create_link(**fields)
        self.mind_map_workspace_sync.materialize_linked_node(link)
        result = self.mind_map_module.get_link(link.link_id) or link
        self.mind_map_workspace_sync.reconcile_canvas_projection()
        return result

    def update_mind_map_link(self, link_id: str, **changes: Any) -> Any:
        """Update one graph relationship through the Mind Map module."""
        link = self.mind_map_module.update_link(link_id, **changes)
        self.mind_map_workspace_sync.reconcile_canvas_projection()
        return link

    def delete_mind_map_link(self, link_id: str, **fields: Any) -> None:
        """Delete one graph relationship and its Canvas source when applicable."""
        existing = self.mind_map_module.get_link(link_id)
        if existing is None:
            raise ValueError(f"Unknown mind map link: {link_id}")
        self.mind_map_workspace_sync.delete_workspace_source_for_link(existing)
        if self.mind_map_module.get_link(link_id) is not None:
            self.mind_map_module.delete_link(link_id, **fields)
        self.mind_map_workspace_sync.reconcile_canvas_projection()

    def search_mind_map_nodes(self, query: str, limit: int = 50) -> list[Any]:
        """Search graph nodes through the module's validated retrieval API."""
        return self.mind_map_module.search_nodes(query, limit=limit)

    def get_mind_map_neighborhood(self, root_node_id: str, depth: int = 1) -> Any:
        """Return a bounded graph neighborhood through the Mind Map module."""
        return self.mind_map_module.get_neighborhood(root_node_id, depth=depth)

    def build_mind_map_context(
        self, query: str = "", *, limit: int = 8, depth: int = 1, max_nodes: int = 28
    ) -> Any:
        """Return bounded node-and-link context without exposing graph storage."""
        return self.mind_map_module.build_context_package(
            query, limit=limit, depth=depth, max_nodes=max_nodes
        )

    def upsert_mind_map_source_node(self, **fields: Any) -> Any:
        """Create or refresh a graph node for a future AMADEUS source adapter."""
        node = self.mind_map_module.upsert_source_node(**fields)
        self.mind_map_workspace_sync.reconcile_canvas_projection()
        return node

    def export_mind_map(self, destination: Path | str) -> Path:
        """Export the active graph as portable JSON through the Mind Map module."""
        return self.mind_map_module.export_to_json(destination)

    def import_mind_map(self, source: Path | str, *, replace_graph: bool = False) -> Any:
        """Import portable graph JSON through the Mind Map module."""
        snapshot = self.mind_map_module.import_from_json(source, replace_graph=replace_graph)
        self.mind_map_workspace_sync.reconcile_canvas_projection()
        return snapshot
