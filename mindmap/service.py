"""Business logic for the AMADEUS Mind Map / Relevance Graph."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from amadeus_trace import BrainRole, ProcessEventEmitter, ProcessEventStatus, ProcessEventType
from mindmap.models import (
    DEFAULT_GRAPH_ID,
    GraphLink,
    GraphNeighborhood,
    GraphNode,
    GraphSnapshot,
    SourceReference,
)
from mindmap.repository import SQLiteMindMapRepository


GraphListener = Callable[[dict[str, Any]], None]
ProcessListener = Callable[[dict[str, object]], None]
_UNSET = object()


class MindMapService:
    """Own validated graph operations independently from storage and GUI code."""

    def __init__(
        self,
        repository: SQLiteMindMapRepository,
        graph_id: str = DEFAULT_GRAPH_ID,
    ) -> None:
        self.repository = repository
        self.graph_id = self._clean_required(graph_id, "graph_id")
        self._listeners: list[GraphListener] = []

    def subscribe(self, listener: GraphListener) -> Callable[[], None]:
        """Subscribe to completed graph changes.

        Listeners are fault-isolated because GUI refresh failures must not corrupt a
        successfully committed graph operation.
        """
        if not callable(listener):
            raise ValueError("listener must be callable")
        self._listeners.append(listener)

        def unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return unsubscribe

    def get_snapshot(self) -> GraphSnapshot:
        return GraphSnapshot(
            graph_id=self.graph_id,
            nodes=tuple(self.repository.list_nodes(self.graph_id)),
            links=tuple(self.repository.list_links(self.graph_id)),
        )

    def list_nodes(self) -> list[GraphNode]:
        return self.repository.list_nodes(self.graph_id)

    def list_links(self) -> list[GraphLink]:
        return self.repository.list_links(self.graph_id)

    def get_node(self, node_id: str) -> GraphNode | None:
        node = self.repository.get_node(node_id)
        return node if node is not None and node.graph_id == self.graph_id else None

    def get_link(self, link_id: str) -> GraphLink | None:
        link = self.repository.get_link(link_id)
        return link if link is not None and link.graph_id == self.graph_id else None

    def create_node(
        self,
        *,
        title: str,
        node_type: str = "idea",
        description: str = "",
        content: str = "",
        importance: float = 0.5,
        confidence: float = 1.0,
        status: str = "active",
        position_x: float = 0.0,
        position_y: float = 0.0,
        position_locked: bool = False,
        source_reference: SourceReference | None = None,
        metadata: Mapping[str, Any] | None = None,
        event_listener: ProcessListener | None = None,
    ) -> GraphNode:
        with self._operation(
            event_listener,
            title="Create Mind Map Node",
            summary="Validate and persist one graph node.",
        ) as emitter:
            now = self._now()
            node = GraphNode(
                node_id=uuid4().hex,
                graph_id=self.graph_id,
                node_type=self._clean_type(node_type, "idea"),
                title=self._clean_required(title, "title"),
                description=description.strip(),
                content=content.strip(),
                importance=self._unit_interval(importance, "importance"),
                confidence=self._unit_interval(confidence, "confidence"),
                status=self._clean_type(status, "active"),
                position_x=float(position_x),
                position_y=float(position_y),
                position_locked=bool(position_locked),
                source_reference=source_reference,
                metadata=dict(metadata or {}),
                created_at=now,
                updated_at=now,
            )
            self.repository.create_node(node)
            emitter.emit(
                source_module="mindmap",
                brain_role=BrainRole.SYSTEM,
                event_type=ProcessEventType.RESULT,
                status=ProcessEventStatus.COMPLETED,
                title="Node Saved",
                summary="Graph node was created and saved.",
                metadata={"node_id": node.node_id, "node_type": node.node_type},
            )
        self._publish("node_created", "node", node.node_id, node.to_dict())
        return node

    def update_node(
        self,
        node_id: str,
        *,
        title: str | object = _UNSET,
        node_type: str | object = _UNSET,
        description: str | object = _UNSET,
        content: str | object = _UNSET,
        importance: float | object = _UNSET,
        confidence: float | object = _UNSET,
        status: str | object = _UNSET,
        position_x: float | object = _UNSET,
        position_y: float | object = _UNSET,
        position_locked: bool | object = _UNSET,
        source_reference: SourceReference | None | object = _UNSET,
        metadata: Mapping[str, Any] | object = _UNSET,
        event_listener: ProcessListener | None = None,
    ) -> GraphNode:
        existing = self._require_node(node_id)
        with self._operation(
            event_listener,
            title="Update Mind Map Node",
            summary="Validate and persist graph node changes.",
        ) as emitter:
            updated = replace(
                existing,
                title=existing.title if title is _UNSET else self._clean_required(str(title), "title"),
                node_type=existing.node_type if node_type is _UNSET else self._clean_type(str(node_type), "idea"),
                description=existing.description if description is _UNSET else str(description).strip(),
                content=existing.content if content is _UNSET else str(content).strip(),
                importance=existing.importance if importance is _UNSET else self._unit_interval(importance, "importance"),
                confidence=existing.confidence if confidence is _UNSET else self._unit_interval(confidence, "confidence"),
                status=existing.status if status is _UNSET else self._clean_type(str(status), "active"),
                position_x=existing.position_x if position_x is _UNSET else float(position_x),
                position_y=existing.position_y if position_y is _UNSET else float(position_y),
                position_locked=existing.position_locked if position_locked is _UNSET else bool(position_locked),
                source_reference=existing.source_reference if source_reference is _UNSET else source_reference,
                metadata=existing.metadata if metadata is _UNSET else dict(metadata),
                updated_at=self._now(),
            )
            self.repository.update_node(updated)
            emitter.emit(
                source_module="mindmap",
                brain_role=BrainRole.SYSTEM,
                event_type=ProcessEventType.RESULT,
                status=ProcessEventStatus.COMPLETED,
                title="Node Updated",
                summary="Graph node changes were saved.",
                metadata={"node_id": updated.node_id},
            )
        self._publish("node_updated", "node", updated.node_id, updated.to_dict())
        return updated

    def move_node(
        self,
        node_id: str,
        position_x: float,
        position_y: float,
        *,
        event_listener: ProcessListener | None = None,
    ) -> GraphNode:
        existing = self._require_node(node_id)
        if existing.position_locked or existing.metadata.get("mindmap_pinned", False):
            return existing
        return self.update_node(
            node_id,
            position_x=position_x,
            position_y=position_y,
            event_listener=event_listener,
        )

    def move_nodes(self, positions: Mapping[str, tuple[float, float]]) -> None:
        """Persist a validated layout projection atomically for this graph."""
        clean_positions = {
            self._clean_required(node_id, "node_id"):
            (self._finite_number(position[0], "position_x"), self._finite_number(position[1], "position_y"))
            for node_id, position in positions.items()
        }
        for node_id in clean_positions:
            existing = self._require_node(node_id)
            if existing.position_locked or existing.metadata.get("mindmap_pinned", False):
                raise ValueError("Pinned mind map nodes cannot be moved")
        self.repository.update_node_positions(self.graph_id, clean_positions)
        self._publish("nodes_moved", "graph", self.graph_id)

    def delete_node(self, node_id: str, *, event_listener: ProcessListener | None = None) -> None:
        existing = self._require_node(node_id)
        with self._operation(
            event_listener,
            title="Delete Mind Map Node",
            summary="Delete one graph node and its connected links.",
        ) as emitter:
            self.repository.delete_node(existing.node_id)
            emitter.emit(
                source_module="mindmap",
                brain_role=BrainRole.SYSTEM,
                event_type=ProcessEventType.RESULT,
                status=ProcessEventStatus.COMPLETED,
                title="Node Deleted",
                summary="Graph node and connected links were deleted.",
                metadata={"node_id": existing.node_id},
            )
        self._publish("node_deleted", "node", existing.node_id, existing.to_dict())

    def create_link(
        self,
        *,
        source_node_id: str,
        target_node_id: str,
        link_type: str = "related_to",
        label: str = "",
        strength: float = 0.5,
        confidence: float = 1.0,
        permanence: float = 0.5,
        evidence: str = "",
        is_temporary: bool = False,
        expires_at: str = "",
        decay_rate: float = 0.0,
        source_reference: SourceReference | None = None,
        metadata: Mapping[str, Any] | None = None,
        event_listener: ProcessListener | None = None,
    ) -> GraphLink:
        source = self._require_node(source_node_id)
        target = self._require_node(target_node_id)
        if source.node_id == target.node_id:
            raise ValueError("A mind map link must connect two different nodes")
        if source.graph_id != self.graph_id or target.graph_id != self.graph_id:
            raise ValueError("Both linked nodes must belong to the active graph")

        with self._operation(
            event_listener,
            title="Create Mind Map Link",
            summary="Validate and persist one first-class graph relationship.",
        ) as emitter:
            now = self._now()
            link = GraphLink(
                link_id=uuid4().hex,
                graph_id=self.graph_id,
                source_node_id=source.node_id,
                target_node_id=target.node_id,
                link_type=self._clean_type(link_type, "related_to"),
                label=label.strip(),
                strength=self._unit_interval(strength, "strength"),
                confidence=self._unit_interval(confidence, "confidence"),
                permanence=self._unit_interval(permanence, "permanence"),
                evidence=evidence.strip(),
                is_temporary=bool(is_temporary),
                expires_at=expires_at.strip(),
                decay_rate=self._non_negative(decay_rate, "decay_rate"),
                source_reference=source_reference,
                metadata=dict(metadata or {}),
                created_at=now,
                updated_at=now,
            )
            self.repository.create_link(link)
            emitter.emit(
                source_module="mindmap",
                brain_role=BrainRole.SYSTEM,
                event_type=ProcessEventType.RESULT,
                status=ProcessEventStatus.COMPLETED,
                title="Link Saved",
                summary="Graph relationship was created and saved.",
                metadata={"link_id": link.link_id, "link_type": link.link_type},
            )
        self._publish("link_created", "link", link.link_id, link.to_dict())
        return link

    def update_link(
        self,
        link_id: str,
        *,
        link_type: str | object = _UNSET,
        label: str | object = _UNSET,
        strength: float | object = _UNSET,
        confidence: float | object = _UNSET,
        permanence: float | object = _UNSET,
        evidence: str | object = _UNSET,
        is_temporary: bool | object = _UNSET,
        expires_at: str | object = _UNSET,
        decay_rate: float | object = _UNSET,
        source_reference: SourceReference | None | object = _UNSET,
        metadata: Mapping[str, Any] | object = _UNSET,
        event_listener: ProcessListener | None = None,
    ) -> GraphLink:
        existing = self._require_link(link_id)
        with self._operation(
            event_listener,
            title="Update Mind Map Link",
            summary="Validate and persist graph relationship changes.",
        ) as emitter:
            updated = replace(
                existing,
                link_type=existing.link_type if link_type is _UNSET else self._clean_type(str(link_type), "related_to"),
                label=existing.label if label is _UNSET else str(label).strip(),
                strength=existing.strength if strength is _UNSET else self._unit_interval(strength, "strength"),
                confidence=existing.confidence if confidence is _UNSET else self._unit_interval(confidence, "confidence"),
                permanence=existing.permanence if permanence is _UNSET else self._unit_interval(permanence, "permanence"),
                evidence=existing.evidence if evidence is _UNSET else str(evidence).strip(),
                is_temporary=existing.is_temporary if is_temporary is _UNSET else bool(is_temporary),
                expires_at=existing.expires_at if expires_at is _UNSET else str(expires_at).strip(),
                decay_rate=existing.decay_rate if decay_rate is _UNSET else self._non_negative(decay_rate, "decay_rate"),
                source_reference=existing.source_reference if source_reference is _UNSET else source_reference,
                metadata=existing.metadata if metadata is _UNSET else dict(metadata),
                updated_at=self._now(),
            )
            self.repository.update_link(updated)
            emitter.emit(
                source_module="mindmap",
                brain_role=BrainRole.SYSTEM,
                event_type=ProcessEventType.RESULT,
                status=ProcessEventStatus.COMPLETED,
                title="Link Updated",
                summary="Graph relationship changes were saved.",
                metadata={"link_id": updated.link_id},
            )
        self._publish("link_updated", "link", updated.link_id, updated.to_dict())
        return updated

    def delete_link(self, link_id: str, *, event_listener: ProcessListener | None = None) -> None:
        existing = self._require_link(link_id)
        with self._operation(
            event_listener,
            title="Delete Mind Map Link",
            summary="Delete one graph relationship.",
        ) as emitter:
            self.repository.delete_link(existing.link_id)
            emitter.emit(
                source_module="mindmap",
                brain_role=BrainRole.SYSTEM,
                event_type=ProcessEventType.RESULT,
                status=ProcessEventStatus.COMPLETED,
                title="Link Deleted",
                summary="Graph relationship was deleted.",
                metadata={"link_id": existing.link_id},
            )
        self._publish("link_deleted", "link", existing.link_id, existing.to_dict())

    def search_nodes(self, query: str, limit: int = 50) -> list[GraphNode]:
        clean_query = query.strip()
        if not clean_query:
            return self.list_nodes()
        if limit < 1:
            raise ValueError("limit must be positive")
        return self.repository.search_nodes(self.graph_id, clean_query, limit=limit)

    def get_neighborhood(self, root_node_id: str, depth: int = 1) -> GraphNeighborhood:
        """Retrieve a bounded graph neighborhood without loading unrelated objects."""
        if depth < 0 or depth > 5:
            raise ValueError("depth must be between 0 and 5")
        root = self._require_node(root_node_id)
        visited = {root.node_id}
        frontier: deque[tuple[str, int]] = deque([(root.node_id, 0)])
        collected_links: dict[str, GraphLink] = {}

        while frontier:
            current_id, current_depth = frontier.popleft()
            if current_depth >= depth:
                continue
            for link in self.repository.list_links_for_nodes(self.graph_id, [current_id]):
                collected_links[link.link_id] = link
                neighbor_id = (
                    link.target_node_id if link.source_node_id == current_id else link.source_node_id
                )
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    frontier.append((neighbor_id, current_depth + 1))

        nodes = tuple(
            node
            for node_id in visited
            if (node := self.repository.get_node(node_id)) is not None
        )
        return GraphNeighborhood(
            root_node_id=root.node_id,
            depth=depth,
            nodes=tuple(sorted(nodes, key=lambda node: (node.title.lower(), node.node_id))),
            links=tuple(sorted(collected_links.values(), key=lambda link: link.link_id)),
        )

    def upsert_source_node(
        self,
        *,
        source_type: str,
        source_id: str,
        title: str,
        node_type: str,
        description: str = "",
        content: str = "",
        source_locator: str = "",
        importance: float = 0.5,
        confidence: float = 1.0,
        metadata: Mapping[str, Any] | None = None,
        event_listener: ProcessListener | None = None,
    ) -> GraphNode:
        """Create or refresh a node for an external AMADEUS object.

        This is the stable integration seam for Chat Registry, Sheets, Materials,
        Memory, and the future Creation Module. Callers provide plain metadata;
        they never write directly to graph storage.
        """
        reference = SourceReference(source_type, source_id, source_locator)
        existing = self.repository.find_node_by_source(
            self.graph_id, reference.source_type, reference.source_id
        )
        if existing is None:
            return self.create_node(
                title=title,
                node_type=node_type,
                description=description,
                content=content,
                importance=importance,
                confidence=confidence,
                source_reference=reference,
                metadata=metadata,
                event_listener=event_listener,
            )
        return self.update_node(
            existing.node_id,
            title=title,
            node_type=node_type,
            description=description,
            content=content,
            importance=importance,
            confidence=confidence,
            source_reference=reference,
            metadata={
                **(metadata if metadata is not None else existing.metadata),
                **{key: value for key, value in existing.metadata.items() if key.startswith("mindmap_")},
            },
            event_listener=event_listener,
        )

    def export_to_json(self, destination: Path | str) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.get_snapshot().to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def import_from_json(self, source: Path | str, *, replace_graph: bool = False) -> GraphSnapshot:
        """Import an AMADEUS graph export through normal validation paths."""
        raw = json.loads(Path(source).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Mind map import must contain a JSON object")
        raw_nodes = raw.get("nodes", [])
        raw_links = raw.get("links", [])
        if not isinstance(raw_nodes, list) or not isinstance(raw_links, list):
            raise ValueError("Mind map import nodes and links must be lists")

        imported_id_map: dict[str, str] = {}
        nodes: list[GraphNode] = []
        for raw_node in raw_nodes:
            if not isinstance(raw_node, dict):
                raise ValueError("Mind map import nodes must contain JSON objects")
            old_id = self._clean_required(
                self._raw_string(raw_node, "node_id"), "imported node_id"
            )
            if old_id in imported_id_map:
                raise ValueError(f"Mind map import contains duplicate node_id: {old_id}")
            now = self._now()
            node = GraphNode(
                node_id=uuid4().hex,
                graph_id=self.graph_id,
                title=self._clean_required(self._raw_string(raw_node, "title"), "title"),
                node_type=self._clean_type(self._raw_string(raw_node, "node_type", "custom"), "custom"),
                description=self._raw_string(raw_node, "description"),
                content=self._raw_string(raw_node, "content"),
                importance=self._unit_interval(raw_node.get("importance", 0.5), "importance"),
                confidence=self._unit_interval(raw_node.get("confidence", 1.0), "confidence"),
                status=self._clean_type(self._raw_string(raw_node, "status", "active"), "active"),
                position_x=self._finite_number(raw_node.get("position_x", 0.0), "position_x"),
                position_y=self._finite_number(raw_node.get("position_y", 0.0), "position_y"),
                position_locked=bool(raw_node.get("position_locked", False)),
                source_reference=self._source_from_import_raw(raw_node.get("source_reference")),
                metadata=self._raw_metadata(raw_node),
                created_at=now,
                updated_at=now,
            )
            imported_id_map[old_id] = node.node_id
            nodes.append(node)

        links: list[GraphLink] = []
        for raw_link in raw_links:
            if not isinstance(raw_link, dict):
                raise ValueError("Mind map import links must contain JSON objects")
            source_node_id = imported_id_map.get(str(raw_link.get("source_node_id", "")))
            target_node_id = imported_id_map.get(str(raw_link.get("target_node_id", "")))
            if not source_node_id or not target_node_id:
                raise ValueError("Mind map import link endpoints must reference imported nodes")
            if source_node_id == target_node_id:
                raise ValueError("A mind map link must connect two different nodes")
            now = self._now()
            links.append(GraphLink(
                link_id=uuid4().hex,
                graph_id=self.graph_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                link_type=self._clean_type(self._raw_string(raw_link, "link_type", "related_to"), "related_to"),
                label=self._raw_string(raw_link, "label"),
                strength=self._unit_interval(raw_link.get("strength", 0.5), "strength"),
                confidence=self._unit_interval(raw_link.get("confidence", 1.0), "confidence"),
                permanence=self._unit_interval(raw_link.get("permanence", 0.5), "permanence"),
                evidence=self._raw_string(raw_link, "evidence"),
                is_temporary=bool(raw_link.get("is_temporary", False)),
                expires_at=self._raw_string(raw_link, "expires_at"),
                decay_rate=self._non_negative(raw_link.get("decay_rate", 0.0), "decay_rate"),
                source_reference=self._source_from_import_raw(raw_link.get("source_reference")),
                metadata=self._raw_metadata(raw_link),
                created_at=now,
                updated_at=now,
            ))

        self.repository.import_graph(self.graph_id, nodes, links, replace_graph=replace_graph)
        snapshot = self.get_snapshot()
        self._publish("graph_imported", "graph", self.graph_id)
        return snapshot

    @contextmanager
    def _operation(
        self,
        listener: ProcessListener | None,
        *,
        title: str,
        summary: str,
    ) -> Iterator[ProcessEventEmitter]:
        emitter = ProcessEventEmitter()
        if listener is not None:
            emitter.subscribe(lambda event: listener(event.to_dict()))
        emitter.start_run(source_module="mindmap", title=title, summary=summary)
        try:
            yield emitter
        except Exception:
            emitter.fail_run(
                title=f"{title} Failed",
                summary="The graph operation could not be completed.",
            )
            raise
        else:
            emitter.complete_run(title=f"{title} Complete", summary=summary)

    def _publish(self, event_type: str, entity_type: str, entity_id: str, payload: dict[str, Any] | None = None) -> None:
        event = {
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "graph_id": self.graph_id,
            "created_at": self._now(),
        }
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:
                continue

    def _raw_string(self, raw: Mapping[str, Any], field_name: str, default: str = "") -> str:
        value = raw.get(field_name, default)
        if not isinstance(value, str):
            raise ValueError(f"Mind map import {field_name} must be a string")
        return value.strip()

    def _raw_metadata(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        value = raw.get("metadata", {})
        if not isinstance(value, dict):
            raise ValueError("Mind map import metadata must be a JSON object")
        return value

    def _finite_number(self, value: object, field_name: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{field_name} must be a number") from error
        if number == float("inf") or number == float("-inf") or number != number:
            raise ValueError(f"{field_name} must be finite")
        return number

    def _require_node(self, node_id: str) -> GraphNode:
        node = self.get_node(self._clean_required(node_id, "node_id"))
        if node is None:
            raise KeyError(f"Unknown mind map node in graph '{self.graph_id}': {node_id}")
        return node

    def _require_link(self, link_id: str) -> GraphLink:
        link = self.get_link(self._clean_required(link_id, "link_id"))
        if link is None:
            raise KeyError(f"Unknown mind map link in graph '{self.graph_id}': {link_id}")
        return link

    def _source_from_raw(self, value: object) -> SourceReference | None:
        if not isinstance(value, dict):
            return None
        source_type = value.get("source_type")
        source_id = value.get("source_id")
        if not isinstance(source_type, str) or not isinstance(source_id, str):
            return None
        if not source_type.strip() or not source_id.strip():
            return None
        locator = value.get("source_locator") if isinstance(value.get("source_locator"), str) else ""
        return SourceReference(source_type, source_id, locator)

    def _source_from_import_raw(self, value: object) -> SourceReference | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("Mind map import source_reference must be a JSON object or null")
        source_type = self._raw_string(value, "source_type")
        source_id = self._raw_string(value, "source_id")
        locator = self._raw_string(value, "source_locator")
        return SourceReference(source_type, source_id, locator)

    def _clean_required(self, value: str, field_name: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError(f"{field_name} cannot be empty")
        return clean

    def _clean_type(self, value: str, fallback: str) -> str:
        clean = value.strip().lower().replace(" ", "_")
        return clean or fallback

    def _unit_interval(self, value: object, field_name: str) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{field_name} must be a number") from error
        if not 0.0 <= numeric <= 1.0:
            raise ValueError(f"{field_name} must be between 0.0 and 1.0")
        return numeric

    def _non_negative(self, value: object, field_name: str) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{field_name} must be a number") from error
        if numeric < 0.0:
            raise ValueError(f"{field_name} cannot be negative")
        return numeric

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
