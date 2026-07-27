"""Deterministic in-memory force layout for Mind Map snapshots.

This module deliberately has no Qt, Core, or storage dependency. It projects
persisted graph data into visual coordinates; callers decide when a resulting
layout is persisted through Core.
"""

from __future__ import annotations

import math
from hashlib import sha256
from dataclasses import dataclass

from mindmap.models import GraphSnapshot


@dataclass(slots=True)
class PhysicsNode:
    """One visual node whose transient velocity never leaves the GUI."""

    node_id: str
    x: float
    y: float
    importance: float
    relevance: float
    pinned: bool
    central: bool
    vx: float = 0.0
    vy: float = 0.0
    dragged: bool = False

    @property
    def radius(self) -> float:
        return 24.0 + self.importance * 28.0 + self.relevance * 12.0


class GraphPhysics:
    """Small fixed-step force layout with deterministic snapshot construction."""

    def __init__(self, snapshot: GraphSnapshot) -> None:
        connection_strength: dict[str, float] = {node.node_id: 0.0 for node in snapshot.nodes}
        self.links = tuple(snapshot.links)
        for link in self.links:
            connection_strength[link.source_node_id] = connection_strength.get(link.source_node_id, 0.0) + link.strength
            connection_strength[link.target_node_id] = connection_strength.get(link.target_node_id, 0.0) + link.strength
        self.nodes = {
            node.node_id: PhysicsNode(
                node_id=node.node_id,
                x=node.position_x,
                y=node.position_y,
                importance=node.importance,
                relevance=min(1.0, node.confidence * 0.6 + connection_strength[node.node_id] * 0.2),
                pinned=node.position_locked or bool(node.metadata.get("mindmap_pinned", False)),
                central=bool(node.metadata.get("mindmap_central", False)),
            )
            for node in snapshot.nodes
        }

    def step(self, steps: int = 1) -> float:
        """Advance fixed timesteps and return the largest node displacement."""
        largest_displacement = 0.0
        for _ in range(max(0, steps)):
            forces = {node_id: [0.0, 0.0] for node_id in self.nodes}
            node_list = list(self.nodes.values())
            for index, first in enumerate(node_list):
                for second in node_list[index + 1 :]:
                    dx, dy = second.x - first.x, second.y - first.y
                    if dx == 0.0 and dy == 0.0:
                        dx, dy = self._fallback_direction(first.node_id, second.node_id)
                    distance_sq = max(64.0, dx * dx + dy * dy)
                    distance = math.sqrt(distance_sq)
                    force = 4800.0 / distance_sq
                    fx, fy = dx / distance * force, dy / distance * force
                    forces[first.node_id][0] -= fx
                    forces[first.node_id][1] -= fy
                    forces[second.node_id][0] += fx
                    forces[second.node_id][1] += fy
            for link in self.links:
                first, second = self.nodes.get(link.source_node_id), self.nodes.get(link.target_node_id)
                if first is None or second is None:
                    continue
                dx, dy = second.x - first.x, second.y - first.y
                if dx == 0.0 and dy == 0.0:
                    dx, dy = self._fallback_direction(first.node_id, second.node_id)
                distance = max(1.0, math.hypot(dx, dy))
                desired = 150.0 - link.strength * 45.0
                if first.central or second.central:
                    desired = 120.0
                force = (distance - desired) * 0.025 * max(0.2, link.strength)
                fx, fy = dx / distance * force, dy / distance * force
                forces[first.node_id][0] += fx
                forces[first.node_id][1] += fy
                forces[second.node_id][0] -= fx
                forces[second.node_id][1] -= fy
            for node in node_list:
                if node.pinned or node.dragged:
                    node.vx = node.vy = 0.0
                    continue
                fx, fy = forces[node.node_id]
                node.vx = max(-24.0, min(24.0, (node.vx + fx) * 0.82))
                node.vy = max(-24.0, min(24.0, (node.vy + fy) * 0.82))
                node.x += node.vx
                node.y += node.vy
                largest_displacement = max(largest_displacement, math.hypot(node.vx, node.vy))
        return largest_displacement

    def settle(self) -> None:
        """Discard transient velocity when the view stops visual motion."""
        for node in self.nodes.values():
            node.vx = node.vy = 0.0

    def positions(self) -> dict[str, tuple[float, float]]:
        """Return only coordinates that a view may later choose to persist."""
        return {node_id: (node.x, node.y) for node_id, node in self.nodes.items()}

    @staticmethod
    def _fallback_direction(first_id: str, second_id: str) -> tuple[float, float]:
        """Return a stable unit vector when coordinates cannot define one."""
        digest = sha256(f"{first_id}\0{second_id}".encode("utf-8")).digest()
        angle = int.from_bytes(digest[:8], "big") / 2**64 * math.tau
        return math.cos(angle), math.sin(angle)
