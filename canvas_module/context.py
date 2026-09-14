"""Semantic context extraction for AMADEUS Canvas.

The visible viewport defines the *allowed supporting context*, not the question
AMADEUS should answer. New/changed or explicitly selected objects are response
targets. Arrows define directional thought flow; plain lines define peer
relationships with similar semantic weight.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Mapping

from canvas_module.models import CanvasConnector, CanvasDocumentSnapshot, CanvasTextBlock


SUPPORTED_CONTEXT_MODES = frozenset({"viewport", "selection", "branch"})


@dataclass(frozen=True, slots=True)
class CanvasChangeSet:
    """Semantic differences between the current canvas and its sent baseline."""

    has_baseline: bool
    new_object_ids: tuple[str, ...] = ()
    changed_object_ids: tuple[str, ...] = ()
    deleted_object_ids: tuple[str, ...] = ()
    new_connector_ids: tuple[str, ...] = ()
    changed_connector_ids: tuple[str, ...] = ()
    deleted_connector_ids: tuple[str, ...] = ()

    @property
    def target_object_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.new_object_ids, *self.changed_object_ids)))

    @property
    def target_connector_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.new_connector_ids, *self.changed_connector_ids)))


@dataclass(frozen=True, slots=True)
class CanvasContextPackage:
    """Structured preview of what a future Canvas request would contain."""

    workspace_id: str
    canvas_revision: int
    context_mode: str
    root_object_id: str | None
    active_root_id: str | None
    target_object_ids: tuple[str, ...]
    target_connector_ids: tuple[str, ...]
    ancestor_object_ids: tuple[str, ...]
    descendant_object_ids: tuple[str, ...]
    peer_object_ids: tuple[str, ...]
    supporting_connector_ids: tuple[str, ...]
    deleted_object_ids: tuple[str, ...]
    deleted_connector_ids: tuple[str, ...]
    excluded_visible_object_ids: tuple[str, ...]
    trimmed_object_ids: tuple[str, ...]
    objects: tuple[CanvasTextBlock, ...]
    connectors: tuple[CanvasConnector, ...]
    estimated_tokens: int
    warnings: tuple[str, ...] = ()

    @property
    def supporting_object_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (*self.ancestor_object_ids, *self.descendant_object_ids, *self.peer_object_ids)
            )
        )

    def to_prompt_dict(self) -> dict[str, object]:
        """Return a future-LLM-ready payload without GUI-specific state."""

        roles: dict[str, str] = {}
        for object_id in self.target_object_ids:
            roles[object_id] = "response_target"
        for object_id in self.ancestor_object_ids:
            roles.setdefault(object_id, "directional_ancestor")
        for object_id in self.descendant_object_ids:
            roles.setdefault(object_id, "directional_descendant")
        for object_id in self.peer_object_ids:
            roles.setdefault(object_id, "related_peer")

        return {
            "workspace_id": self.workspace_id,
            "canvas_revision": self.canvas_revision,
            "context_mode": self.context_mode,
            "root_object_id": self.root_object_id,
            "active_root_id": self.active_root_id,
            "response_targets": list(self.target_object_ids),
            "target_connectors": list(self.target_connector_ids),
            "deleted_objects_since_last_send": list(self.deleted_object_ids),
            "deleted_connectors_since_last_send": list(self.deleted_connector_ids),
            "objects": [
                {
                    **block.to_dict(),
                    "context_role": roles.get(block.object_id, "supporting_context"),
                }
                for block in self.objects
            ],
            "connectors": [connector.to_dict() for connector in self.connectors],
            "estimated_tokens": self.estimated_tokens,
            "warnings": list(self.warnings),
        }


class CanvasContextBuilder:
    """Build target-focused context by traversing semantic Canvas relations."""

    def detect_changes(self, snapshot: CanvasDocumentSnapshot) -> CanvasChangeSet:
        baseline = snapshot.context_baseline
        if baseline is None:
            return CanvasChangeSet(has_baseline=False)

        current_objects = {
            block.object_id: semantic_fingerprint_for_block(block) for block in snapshot.text_blocks
        }
        current_connectors = {
            connector.connector_id: semantic_fingerprint_for_connector(connector)
            for connector in snapshot.connectors
        }
        baseline_objects = dict(baseline.object_fingerprints)
        baseline_connectors = dict(baseline.connector_fingerprints)

        new_objects = sorted(current_objects.keys() - baseline_objects.keys())
        changed_objects = sorted(
            object_id
            for object_id in current_objects.keys() & baseline_objects.keys()
            if current_objects[object_id] != baseline_objects[object_id]
        )
        deleted_objects = sorted(baseline_objects.keys() - current_objects.keys())

        new_connectors = sorted(current_connectors.keys() - baseline_connectors.keys())
        changed_connectors = sorted(
            connector_id
            for connector_id in current_connectors.keys() & baseline_connectors.keys()
            if current_connectors[connector_id] != baseline_connectors[connector_id]
        )
        deleted_connectors = sorted(baseline_connectors.keys() - current_connectors.keys())
        return CanvasChangeSet(
            has_baseline=True,
            new_object_ids=tuple(new_objects),
            changed_object_ids=tuple(changed_objects),
            deleted_object_ids=tuple(deleted_objects),
            new_connector_ids=tuple(new_connectors),
            changed_connector_ids=tuple(changed_connectors),
            deleted_connector_ids=tuple(deleted_connectors),
        )

    def build(
        self,
        snapshot: CanvasDocumentSnapshot,
        *,
        context_mode: str = "viewport",
        visible_object_ids: Iterable[str] = (),
        selected_object_ids: Iterable[str] = (),
        selected_connector_ids: Iterable[str] = (),
        branch_root_id: str | None = None,
        ancestor_depth: int = 8,
        descendant_depth: int = 2,
        peer_depth: int = 1,
        token_budget: int = 6000,
    ) -> CanvasContextPackage:
        mode = context_mode.strip().lower()
        if mode not in SUPPORTED_CONTEXT_MODES:
            raise ValueError(f"Unsupported Canvas context mode: {mode}")
        if ancestor_depth < 0 or descendant_depth < 0 or peer_depth < 0:
            raise ValueError("Context traversal depths cannot be negative")
        if token_budget < 256:
            raise ValueError("Canvas context token budget must be at least 256")

        block_by_id = {block.object_id: block for block in snapshot.text_blocks}
        connector_by_id = {connector.connector_id: connector for connector in snapshot.connectors}
        visible_ids = _clean_known_ids(visible_object_ids, block_by_id)
        selected_ids = _clean_known_ids(selected_object_ids, block_by_id)
        selected_connector_set = _clean_known_ids(selected_connector_ids, connector_by_id)

        # The viewport is the default semantic boundary. Selection/branch targets
        # may be explicitly supplied, but supporting traversal remains bounded by
        # what Dato intentionally placed in view.
        allowed_ids = set(visible_ids)
        allowed_ids.update(selected_ids)
        if not allowed_ids and mode != "viewport":
            allowed_ids.update(block_by_id)

        changes = self.detect_changes(snapshot)
        changed_object_ids = set(changes.target_object_ids)
        changed_connector_ids = set(changes.target_connector_ids)

        target_object_ids: set[str] = set()
        target_connector_ids: set[str] = set()
        warnings: list[str] = []

        if mode == "selection":
            target_object_ids.update(selected_ids)
            target_connector_ids.update(selected_connector_set)
            if not target_object_ids and not target_connector_ids:
                warnings.append("Selection context needs at least one selected block or connector.")
        elif mode == "branch":
            active_branch_root = _first_known_id(branch_root_id, selected_ids, snapshot.root_object_id, block_by_id)
            if active_branch_root is not None:
                target_object_ids.add(active_branch_root)
                allowed_ids.add(active_branch_root)
            else:
                warnings.append("Branch context needs a selected block or a saved Canvas root.")
        else:
            target_object_ids.update(changed_object_ids & allowed_ids)
            target_connector_ids.update(
                connector_id
                for connector_id in changed_connector_ids
                if connector_id in connector_by_id
                and connector_by_id[connector_id].source_object_id in allowed_ids
                and connector_by_id[connector_id].target_object_id in allowed_ids
            )
            target_connector_ids.update(selected_connector_set)
            target_object_ids.update(selected_ids)
            if not changes.has_baseline and not selected_ids and not selected_connector_set:
                warnings.append(
                    "No sent baseline exists yet. Select the block AMADEUS should answer before the first send."
                )

        # A changed/new relationship is itself a response target. Its endpoints
        # must also be present so the relationship has meaning.
        for connector_id in tuple(target_connector_ids):
            connector = connector_by_id.get(connector_id)
            if connector is None:
                continue
            target_object_ids.update({connector.source_object_id, connector.target_object_id})
            allowed_ids.update({connector.source_object_id, connector.target_object_id})

        target_object_ids &= set(block_by_id)
        active_root_id = _first_known_id(branch_root_id, selected_ids, snapshot.root_object_id, block_by_id)

        incoming_arrows: dict[str, list[CanvasConnector]] = defaultdict(list)
        outgoing_arrows: dict[str, list[CanvasConnector]] = defaultdict(list)
        peer_lines: dict[str, list[CanvasConnector]] = defaultdict(list)
        for connector in snapshot.connectors:
            if connector.connector_type == "arrow":
                outgoing_arrows[connector.source_object_id].append(connector)
                incoming_arrows[connector.target_object_id].append(connector)
            else:
                peer_lines[connector.source_object_id].append(connector)
                peer_lines[connector.target_object_id].append(connector)

        ancestors, ancestor_connectors, ancestor_distance = _walk_directional(
            start_ids=target_object_ids,
            adjacency=incoming_arrows,
            allowed_ids=allowed_ids,
            depth=ancestor_depth,
            next_id=lambda connector, current: connector.source_object_id,
        )
        descendants, descendant_connectors, descendant_distance = _walk_directional(
            start_ids=target_object_ids,
            adjacency=outgoing_arrows,
            allowed_ids=allowed_ids,
            depth=descendant_depth,
            next_id=lambda connector, current: connector.target_object_id,
        )

        peer_starts = set(target_object_ids) | ancestors | descendants
        peers, peer_connectors, peer_distance = _walk_peers(
            start_ids=peer_starts,
            adjacency=peer_lines,
            allowed_ids=allowed_ids,
            depth=peer_depth,
        )
        peers -= target_object_ids | ancestors | descendants
        ancestors -= target_object_ids
        descendants -= target_object_ids | ancestors

        # If the marked root is visible and reachable through incoming arrows it
        # naturally appears in ancestors. We never inject an unrelated root just
        # because it exists elsewhere on the canvas.
        support_connector_ids = set(ancestor_connectors) | set(descendant_connectors) | set(peer_connectors)
        support_connector_ids.update(target_connector_ids)

        role_priority: dict[str, tuple[int, int, float, float, str]] = {}
        for object_id in target_object_ids:
            block = block_by_id[object_id]
            role_priority[object_id] = (0, 0, block.position_y, block.position_x, object_id)
        for object_id in ancestors:
            block = block_by_id[object_id]
            role_priority[object_id] = (
                1,
                ancestor_distance.get(object_id, ancestor_depth + 1),
                block.position_y,
                block.position_x,
                object_id,
            )
        for object_id in descendants:
            block = block_by_id[object_id]
            role_priority[object_id] = (
                2,
                descendant_distance.get(object_id, descendant_depth + 1),
                block.position_y,
                block.position_x,
                object_id,
            )
        for object_id in peers:
            block = block_by_id[object_id]
            role_priority[object_id] = (
                3,
                peer_distance.get(object_id, peer_depth + 1),
                block.position_y,
                block.position_x,
                object_id,
            )

        ordered_ids = sorted(role_priority, key=role_priority.__getitem__)
        included_ids: list[str] = []
        trimmed_ids: list[str] = []
        estimated_tokens = 0
        for object_id in ordered_ids:
            block_cost = estimate_block_tokens(block_by_id[object_id])
            is_target = object_id in target_object_ids
            if not is_target and included_ids and estimated_tokens + block_cost > token_budget:
                trimmed_ids.append(object_id)
                continue
            included_ids.append(object_id)
            estimated_tokens += block_cost

        included_set = set(included_ids)
        included_connector_ids: list[str] = []
        for connector_id in sorted(support_connector_ids):
            connector = connector_by_id.get(connector_id)
            if connector is None:
                continue
            if connector.source_object_id in included_set and connector.target_object_id in included_set:
                connector_cost = estimate_connector_tokens(connector)
                if connector_id not in target_connector_ids and estimated_tokens + connector_cost > token_budget:
                    continue
                included_connector_ids.append(connector_id)
                estimated_tokens += connector_cost

        if trimmed_ids:
            warnings.append(
                f"Context budget trimmed {len(trimmed_ids)} supporting block(s); response targets were preserved."
            )

        visible_set = set(visible_ids)
        excluded_visible = sorted(visible_set - included_set)
        objects = tuple(block_by_id[object_id] for object_id in included_ids)
        connectors = tuple(connector_by_id[connector_id] for connector_id in included_connector_ids)

        included_ancestors = tuple(object_id for object_id in included_ids if object_id in ancestors)
        included_descendants = tuple(object_id for object_id in included_ids if object_id in descendants)
        included_peers = tuple(object_id for object_id in included_ids if object_id in peers)
        included_targets = tuple(object_id for object_id in included_ids if object_id in target_object_ids)
        included_target_connectors = tuple(
            connector_id for connector_id in included_connector_ids if connector_id in target_connector_ids
        )

        if not included_targets and not included_target_connectors and not changes.deleted_object_ids and not changes.deleted_connector_ids:
            warnings.append("No new, edited, or explicitly selected response target was found.")

        return CanvasContextPackage(
            workspace_id=snapshot.workspace_id,
            canvas_revision=snapshot.revision,
            context_mode=mode,
            root_object_id=snapshot.root_object_id,
            active_root_id=active_root_id,
            target_object_ids=included_targets,
            target_connector_ids=included_target_connectors,
            ancestor_object_ids=included_ancestors,
            descendant_object_ids=included_descendants,
            peer_object_ids=included_peers,
            supporting_connector_ids=tuple(
                connector_id for connector_id in included_connector_ids if connector_id not in target_connector_ids
            ),
            deleted_object_ids=changes.deleted_object_ids,
            deleted_connector_ids=changes.deleted_connector_ids,
            excluded_visible_object_ids=tuple(excluded_visible),
            trimmed_object_ids=tuple(trimmed_ids),
            objects=objects,
            connectors=connectors,
            estimated_tokens=max(1, estimated_tokens) if objects or connectors else 0,
            warnings=tuple(dict.fromkeys(warnings)),
        )


def semantic_fingerprint_for_block(block: CanvasTextBlock) -> str:
    """Fingerprint meaning, deliberately excluding position and dimensions."""

    payload = {
        "object_type": block.object_type,
        "text": block.text,
        "title": block.title,
        "comment": block.comment,
        "created_by": block.created_by,
    }
    return _fingerprint(payload)


def semantic_fingerprint_for_connector(connector: CanvasConnector) -> str:
    """Fingerprint connector meaning, including direction and annotations."""

    payload = {
        "connector_type": connector.connector_type,
        "source_object_id": connector.source_object_id,
        "target_object_id": connector.target_object_id,
        "relation_type": connector.relation_type,
        "label": connector.label,
        "comment": connector.comment,
        "created_by": connector.created_by,
    }
    return _fingerprint(payload)


def estimate_block_tokens(block: CanvasTextBlock) -> int:
    semantic_text = " ".join(part for part in (block.title, block.text, block.comment) if part)
    return max(12, (len(semantic_text) + 3) // 4 + 18)


def estimate_connector_tokens(connector: CanvasConnector) -> int:
    semantic_text = " ".join(
        part for part in (connector.relation_type, connector.label, connector.comment) if part
    )
    return max(10, (len(semantic_text) + 3) // 4 + 14)


def _fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _clean_known_ids(values: Iterable[str], known: Mapping[str, object]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value).strip()
        if clean and clean in known and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return tuple(result)


def _first_known_id(
    preferred: str | None,
    selected_ids: Iterable[str],
    fallback: str | None,
    known: Mapping[str, object],
) -> str | None:
    candidates = [preferred, *selected_ids, fallback]
    for candidate in candidates:
        clean = str(candidate or "").strip()
        if clean and clean in known:
            return clean
    return None


def _walk_directional(
    *,
    start_ids: Iterable[str],
    adjacency: Mapping[str, list[CanvasConnector]],
    allowed_ids: set[str],
    depth: int,
    next_id,
) -> tuple[set[str], set[str], dict[str, int]]:
    found: set[str] = set()
    connector_ids: set[str] = set()
    distance: dict[str, int] = {}
    queue = deque((object_id, 0) for object_id in start_ids)
    visited = set(start_ids)
    while queue:
        current_id, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for connector in sorted(adjacency.get(current_id, ()), key=lambda item: item.connector_id):
            related_id = next_id(connector, current_id)
            if related_id not in allowed_ids:
                continue
            connector_ids.add(connector.connector_id)
            if related_id in visited:
                continue
            visited.add(related_id)
            found.add(related_id)
            distance[related_id] = current_depth + 1
            queue.append((related_id, current_depth + 1))
    return found, connector_ids, distance


def _walk_peers(
    *,
    start_ids: Iterable[str],
    adjacency: Mapping[str, list[CanvasConnector]],
    allowed_ids: set[str],
    depth: int,
) -> tuple[set[str], set[str], dict[str, int]]:
    found: set[str] = set()
    connector_ids: set[str] = set()
    distance: dict[str, int] = {}
    starts = set(start_ids)
    queue = deque((object_id, 0) for object_id in starts)
    visited = set(starts)
    while queue:
        current_id, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for connector in sorted(adjacency.get(current_id, ()), key=lambda item: item.connector_id):
            related_id = (
                connector.target_object_id
                if connector.source_object_id == current_id
                else connector.source_object_id
            )
            if related_id not in allowed_ids:
                continue
            connector_ids.add(connector.connector_id)
            if related_id in visited:
                continue
            visited.add(related_id)
            found.add(related_id)
            distance[related_id] = current_depth + 1
            queue.append((related_id, current_depth + 1))
    return found, connector_ids, distance
