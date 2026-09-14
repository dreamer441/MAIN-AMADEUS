"""Living force-layout projection for the AMADEUS Mind Map.

The persistent graph belongs to :mod:`mindmap.service`; this module only owns
transient visual motion.  It deliberately adapts the useful behaviour of the
older AMADEUS Mind Map (importance depth, central-node gravity, typed-link
springs, pinned nodes, and relevance prominence) to the current immutable
``GraphSnapshot`` domain model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from hashlib import sha256

from mindmap.models import GraphLink, GraphSnapshot


LINK_TYPE_MULTIPLIERS = {
    "part_of": 1.45,
    "contains": 1.40,
    "depends_on": 1.30,
    "derived_from": 1.20,
    "supports": 1.15,
    "references": 1.05,
    "related_to": 1.00,
    "solves": 1.00,
    "caused_by": 0.90,
    "contradicts": 0.65,
}


@dataclass(slots=True)
class PhysicsNode:
    """Transient visual state for one immutable graph node."""

    node_id: str
    x: float
    y: float
    importance: float
    confidence: float
    relevance: float
    weight: float
    usage_count: int
    reference_count: int
    reward_score: float
    punishment_score: float
    last_used_score: float
    pinned: bool
    central: bool
    vx: float = 0.0
    vy: float = 0.0
    z: float = 0.0
    vz: float = 0.0
    target_z: float = 0.0
    dragged: bool = False

    @property
    def radius(self) -> float:
        """Return a restrained but meaningful visual radius."""
        base = 15.0 + math.sqrt(max(0.2, self.weight)) * 4.0
        importance = max(0.0, min(1.0, self.importance)) * 13.0
        relevance = max(0.0, min(1.0, self.relevance)) * 8.0
        return min(48.0, base + importance + relevance)

    @property
    def prominence(self) -> float:
        """Normalized depth/prominence used by the graphics layer."""
        return max(0.0, min(1.0, 0.45 + self.z / 420.0))


class GraphPhysics:
    """Deterministic force graph adapted from the earlier AMADEUS Mind Map.

    The simulation never persists by itself.  The GUI may save coordinates only
    through Core after an explicit drag or layout operation.
    """

    REPULSION = 6200.0
    SPRING_STRENGTH = 0.020
    CENTER_GRAVITY = 0.0045
    CENTRAL_GRAVITY = 0.075
    DAMPING = 0.84
    Z_DAMPING = 0.82
    MAX_VELOCITY = 28.0

    def __init__(self, snapshot: GraphSnapshot) -> None:
        self.links: tuple[GraphLink, ...] = tuple(snapshot.links)
        connection_strength: dict[str, float] = {node.node_id: 0.0 for node in snapshot.nodes}
        reference_count: dict[str, int] = {node.node_id: 0 for node in snapshot.nodes}
        link_rewards: dict[str, float] = {node.node_id: 0.0 for node in snapshot.nodes}
        link_punishments: dict[str, float] = {node.node_id: 0.0 for node in snapshot.nodes}

        for link in self.links:
            effective = max(0.05, link.strength) * self._link_multiplier(link.link_type)
            for node_id in (link.source_node_id, link.target_node_id):
                connection_strength[node_id] = connection_strength.get(node_id, 0.0) + effective
                reference_count[node_id] = reference_count.get(node_id, 0) + 1
                link_rewards[node_id] = link_rewards.get(node_id, 0.0) + link.reward_score
                link_punishments[node_id] = link_punishments.get(node_id, 0.0) + link.punishment_score

        self.nodes: dict[str, PhysicsNode] = {}
        for index, node in enumerate(snapshot.nodes):
            metadata = dict(node.metadata)
            pinned = node.position_locked or bool(metadata.get("mindmap_pinned", False))
            x, y = node.position_x, node.position_y
            # Newly created unlocked nodes often all start at (0, 0). Give only
            # those nodes a deterministic spiral seed; locked/pinned coordinates
            # remain exact because they are user-owned layout decisions.
            if not pinned and x == 0.0 and y == 0.0 and len(snapshot.nodes) > 1:
                x, y = self._seed_position(index, node.node_id)

            usage_count = self._int_metadata(metadata, "usage_count")
            refs = max(reference_count.get(node.node_id, 0), self._int_metadata(metadata, "reference_count"))
            reward = link_rewards.get(node.node_id, 0.0) + self._float_metadata(metadata, "reward_score")
            punishment = link_punishments.get(node.node_id, 0.0) + self._float_metadata(metadata, "punishment_score")
            last_used = self._float_metadata(metadata, "last_used_score")
            weight = max(0.2, self._float_metadata(metadata, "weight", 1.0))
            relevance = min(
                1.0,
                node.confidence * 0.38
                + min(1.0, connection_strength.get(node.node_id, 0.0) / 4.5) * 0.34
                + min(1.0, refs / 8.0) * 0.18
                + min(1.0, last_used) * 0.10,
            )
            physics_node = PhysicsNode(
                node_id=node.node_id,
                x=x,
                y=y,
                importance=node.importance,
                confidence=node.confidence,
                relevance=relevance,
                weight=weight,
                usage_count=usage_count,
                reference_count=refs,
                reward_score=reward,
                punishment_score=punishment,
                last_used_score=last_used,
                pinned=pinned,
                central=bool(metadata.get("mindmap_central", False)),
            )
            physics_node.target_z = self._target_z(physics_node)
            physics_node.z = physics_node.target_z * 0.45
            self.nodes[node.node_id] = physics_node

    def step(self, steps: int = 1) -> float:
        """Advance fixed timesteps and return the largest node displacement."""
        largest_displacement = 0.0
        for _ in range(max(0, steps)):
            forces = {node_id: [0.0, 0.0] for node_id in self.nodes}
            node_list = list(self.nodes.values())
            self._apply_repulsion(node_list, forces)
            self._apply_springs(forces)
            self._apply_central_gravity(forces)
            self._apply_center_gravity(forces)

            for node in node_list:
                node.target_z = self._target_z(node)
                node.vz = (node.vz + (node.target_z - node.z) * 0.035) * self.Z_DAMPING
                node.z += max(-26.0, min(26.0, node.vz))

                if node.pinned or node.dragged:
                    node.vx = node.vy = 0.0
                    continue
                fx, fy = forces[node.node_id]
                mass = max(0.6, node.weight)
                node.vx = (node.vx + fx / mass) * self.DAMPING
                node.vy = (node.vy + fy / mass) * self.DAMPING
                speed = math.hypot(node.vx, node.vy)
                if speed > self.MAX_VELOCITY:
                    scale = self.MAX_VELOCITY / speed
                    node.vx *= scale
                    node.vy *= scale
                node.x += node.vx
                node.y += node.vy
                largest_displacement = max(largest_displacement, math.hypot(node.vx, node.vy))
        return largest_displacement

    def settle(self) -> None:
        """Discard transient velocity when the view stops visual motion."""
        for node in self.nodes.values():
            node.vx = node.vy = node.vz = 0.0

    def positions(self) -> dict[str, tuple[float, float]]:
        """Return coordinates that the GUI may explicitly persist through Core."""
        return {node_id: (node.x, node.y) for node_id, node in self.nodes.items()}

    def start_drag(self, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        if node is None or node.pinned:
            return False
        node.dragged = True
        node.vx = node.vy = 0.0
        return True

    def drag_to(self, node_id: str, x: float, y: float) -> bool:
        node = self.nodes.get(node_id)
        if node is None or node.pinned:
            return False
        node.dragged = True
        node.x, node.y = float(x), float(y)
        node.vx = node.vy = 0.0
        return True

    def stop_drag(self, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        if node is None:
            return False
        node.dragged = False
        node.vx = node.vy = 0.0
        return True

    def get_direct_neighbors(self, node_id: str) -> set[str]:
        neighbors: set[str] = set()
        for link in self.links:
            if link.source_node_id == node_id and link.target_node_id in self.nodes:
                neighbors.add(link.target_node_id)
            elif link.target_node_id == node_id and link.source_node_id in self.nodes:
                neighbors.add(link.source_node_id)
        return neighbors

    def visual_metrics(self, node_id: str) -> tuple[float, float, float]:
        """Return radius, opacity, and layer score for one node."""
        node = self.nodes[node_id]
        layer = node.prominence
        radius = node.radius * (0.82 + layer * 0.38)
        opacity = max(0.38, min(1.0, 0.52 + layer * 0.48))
        return radius, opacity, layer

    def _apply_repulsion(self, nodes: list[PhysicsNode], forces: dict[str, list[float]]) -> None:
        for index, first in enumerate(nodes):
            for second in nodes[index + 1 :]:
                dx, dy = second.x - first.x, second.y - first.y
                if dx == 0.0 and dy == 0.0:
                    dx, dy = self._fallback_direction(first.node_id, second.node_id)
                distance_sq = max(49.0, dx * dx + dy * dy)
                distance = math.sqrt(distance_sq)
                minimum = first.radius + second.radius + 18.0
                force = self.REPULSION / distance_sq
                if distance < minimum:
                    force *= 1.0 + (minimum - distance) / max(1.0, minimum)
                fx, fy = dx / distance * force, dy / distance * force
                forces[first.node_id][0] -= fx
                forces[first.node_id][1] -= fy
                forces[second.node_id][0] += fx
                forces[second.node_id][1] += fy

    def _apply_springs(self, forces: dict[str, list[float]]) -> None:
        for link in self.links:
            first = self.nodes.get(link.source_node_id)
            second = self.nodes.get(link.target_node_id)
            if first is None or second is None:
                continue
            dx, dy = second.x - first.x, second.y - first.y
            if dx == 0.0 and dy == 0.0:
                dx, dy = self._fallback_direction(first.node_id, second.node_id)
            distance = max(1.0, math.hypot(dx, dy))
            multiplier = self._link_multiplier(link.link_type)
            effective_strength = max(0.08, min(2.5, link.strength * multiplier))
            desired = 180.0 / math.sqrt(effective_strength)
            if first.central or second.central:
                desired = max(112.0, 158.0 / math.sqrt(effective_strength))
            displacement = distance - desired
            force = displacement * self.SPRING_STRENGTH * effective_strength
            fx, fy = dx / distance * force, dy / distance * force
            forces[first.node_id][0] += fx
            forces[first.node_id][1] += fy
            forces[second.node_id][0] -= fx
            forces[second.node_id][1] -= fy

    def _apply_central_gravity(self, forces: dict[str, list[float]]) -> None:
        central_ids = [node.node_id for node in self.nodes.values() if node.central]
        if not central_ids:
            return
        for central_id in central_ids:
            central = self.nodes[central_id]
            for neighbor_id in self.get_direct_neighbors(central_id):
                neighbor = self.nodes[neighbor_id]
                if neighbor.pinned or neighbor.dragged:
                    continue
                dx, dy = central.x - neighbor.x, central.y - neighbor.y
                distance = max(1.0, math.hypot(dx, dy))
                desired = central.radius + neighbor.radius + 105.0
                force = max(-20.0, min(20.0, (distance - desired) * self.CENTRAL_GRAVITY))
                forces[neighbor_id][0] += dx / distance * force
                forces[neighbor_id][1] += dy / distance * force

    def _apply_center_gravity(self, forces: dict[str, list[float]]) -> None:
        if not self.nodes:
            return
        center_x = sum(node.x for node in self.nodes.values()) / len(self.nodes)
        center_y = sum(node.y for node in self.nodes.values()) / len(self.nodes)
        for node in self.nodes.values():
            if node.pinned or node.dragged:
                continue
            multiplier = 0.18 if node.central else 1.0
            forces[node.node_id][0] += (center_x - node.x) * self.CENTER_GRAVITY * multiplier
            forces[node.node_id][1] += (center_y - node.y) * self.CENTER_GRAVITY * multiplier

    @staticmethod
    def _target_z(node: PhysicsNode) -> float:
        return (
            node.importance * 145.0
            + node.confidence * 55.0
            + node.relevance * 125.0
            + min(node.usage_count, 20) * 2.5
            + min(node.reference_count, 20) * 4.0
            + node.reward_score * 18.0
            - node.punishment_score * 24.0
            + node.last_used_score * 50.0
            + (70.0 if node.central else 0.0)
        )

    @staticmethod
    def _link_multiplier(link_type: str) -> float:
        return LINK_TYPE_MULTIPLIERS.get(str(link_type or "related_to").lower(), 1.0)

    @staticmethod
    def _seed_position(index: int, node_id: str) -> tuple[float, float]:
        digest = sha256(node_id.encode("utf-8")).digest()
        phase = int.from_bytes(digest[:4], "big") / 2**32 * math.tau
        angle = index * 2.399963229728653 + phase * 0.18
        radius = 52.0 + 27.0 * math.sqrt(index + 1)
        return math.cos(angle) * radius, math.sin(angle) * radius

    @staticmethod
    def _fallback_direction(first_id: str, second_id: str) -> tuple[float, float]:
        digest = sha256(f"{first_id}\0{second_id}".encode("utf-8")).digest()
        angle = int.from_bytes(digest[:8], "big") / 2**64 * math.tau
        return math.cos(angle), math.sin(angle)

    @staticmethod
    def _float_metadata(metadata: dict, key: str, default: float = 0.0) -> float:
        try:
            return float(metadata.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _int_metadata(metadata: dict, key: str, default: int = 0) -> int:
        try:
            return int(metadata.get(key, default))
        except (TypeError, ValueError):
            return default
