"""Domain models for the AMADEUS Mind Map / Relevance Graph.

The models are framework-independent and intentionally contain no PyQt or SQLite
logic. This lets the GUI, Creation Module, Inner Brain, and future importers use
one stable graph vocabulary without depending on each other's implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


DEFAULT_GRAPH_ID = "main"


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Trace one graph object back to the AMADEUS object that produced it.

    ``source_type`` may later be ``chat``, ``message``, ``sheet``, ``material``,
    ``memory``, or another registered source. ``source_locator`` is optional
    human-readable detail such as a message number or file section.
    """

    source_type: str
    source_id: str
    source_locator: str = ""

    def __post_init__(self) -> None:
        if not self.source_type.strip():
            raise ValueError("source_type cannot be empty")
        if not self.source_id.strip():
            raise ValueError("source_id cannot be empty")
        object.__setattr__(self, "source_type", self.source_type.strip().lower())
        object.__setattr__(self, "source_id", self.source_id.strip())
        object.__setattr__(self, "source_locator", self.source_locator.strip())

    def to_dict(self) -> dict[str, str]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "source_locator": self.source_locator,
        }


@dataclass(frozen=True, slots=True)
class GraphNode:
    """One meaningful object in the AMADEUS graph."""

    node_id: str
    graph_id: str
    node_type: str
    title: str
    description: str = ""
    content: str = ""
    importance: float = 0.5
    confidence: float = 1.0
    status: str = "active"
    position_x: float = 0.0
    position_y: float = 0.0
    position_locked: bool = False
    source_reference: SourceReference | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "graph_id": self.graph_id,
            "node_type": self.node_type,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "importance": self.importance,
            "confidence": self.confidence,
            "status": self.status,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "position_locked": self.position_locked,
            "source_reference": self.source_reference.to_dict() if self.source_reference else None,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class GraphLink:
    """A first-class relationship between two graph nodes.

    Advanced relevance fields are stored now even though V1 does not yet apply
    reward propagation or time decay. Keeping them in the domain prevents a
    destructive schema redesign when those systems become real.
    """

    link_id: str
    graph_id: str
    source_node_id: str
    target_node_id: str
    link_type: str
    label: str = ""
    strength: float = 0.5
    confidence: float = 1.0
    permanence: float = 0.5
    usage_count: int = 0
    reward_score: float = 0.0
    punishment_score: float = 0.0
    evidence: str = ""
    is_temporary: bool = False
    expires_at: str = ""
    decay_rate: float = 0.0
    source_reference: SourceReference | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "graph_id": self.graph_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "link_type": self.link_type,
            "label": self.label,
            "strength": self.strength,
            "confidence": self.confidence,
            "permanence": self.permanence,
            "usage_count": self.usage_count,
            "reward_score": self.reward_score,
            "punishment_score": self.punishment_score,
            "evidence": self.evidence,
            "is_temporary": self.is_temporary,
            "expires_at": self.expires_at,
            "decay_rate": self.decay_rate,
            "source_reference": self.source_reference.to_dict() if self.source_reference else None,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class GraphSnapshot:
    """A consistent read of one graph used by the GUI and exporters."""

    graph_id: str
    nodes: tuple[GraphNode, ...]
    links: tuple[GraphLink, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "links": [link.to_dict() for link in self.links],
        }


@dataclass(frozen=True, slots=True)
class GraphNeighborhood:
    """Bounded local retrieval result around one root node."""

    root_node_id: str
    depth: int
    nodes: tuple[GraphNode, ...]
    links: tuple[GraphLink, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_node_id": self.root_node_id,
            "depth": self.depth,
            "nodes": [node.to_dict() for node in self.nodes],
            "links": [link.to_dict() for link in self.links],
        }
