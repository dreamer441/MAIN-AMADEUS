"""Public module entry point and domain operations for AMADEUS Canvas."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from canvas_module.context import (
    CanvasChangeSet,
    CanvasContextBuilder,
    CanvasContextPackage,
    semantic_fingerprint_for_block,
    semantic_fingerprint_for_connector,
)
from canvas_module.models import (
    DEFAULT_RELATION_TYPE,
    CanvasConnector,
    CanvasContextBaseline,
    CanvasDocumentSnapshot,
    CanvasSendOperation,
    CanvasTextBlock,
    CanvasWorkspaceDescriptor,
    CanvasWorkspaceRecord,
    CanvasWorkspaceRegistrySnapshot,
)
from canvas_module.storage import CanvasDocumentStore, CanvasWorkspaceRegistryStore


_UNSET = object()
_MINDMAP_PROJECTION_WORKSPACE_ID = "mindmap_projection"
_MINDMAP_PROJECTION_WORKSPACE_TITLE = "Mind Map"


class CanvasModule:
    """Core-owned facade for Canvas persistence and validated mutations.

    PyQt scene items are only views of these models. All meaningful edits pass
    through this facade so later context extraction, revisions, undo, and
    AMADEUS-generated changes have one stable domain boundary.
    """

    def __init__(self, project_root: Path, workspace_id: str | None = None) -> None:
        self.project_root = Path(project_root)
        self.store = CanvasDocumentStore(self.project_root)
        self.registry_store = CanvasWorkspaceRegistryStore(self.project_root, self.store)
        registry = self.registry_store.load_or_create(workspace_id)
        self.workspace_id = registry.active_workspace_id
        self.context_builder = CanvasContextBuilder()
        # Undo is session-local but isolated per workspace. Switching projects
        # never lets Ctrl+Z restore content from another Canvas workspace.
        self._undo_stacks: dict[str, list[CanvasDocumentSnapshot]] = {}
        self._undo_limit = 100
        self._listeners: dict[str, Callable[[dict[str, object]], None]] = {}
        self.store.path_for(self.workspace_id)

    @property
    def _undo_stack(self) -> list[CanvasDocumentSnapshot]:
        return self._undo_stacks.setdefault(self.workspace_id, [])

    def get_workspace_descriptor(self) -> CanvasWorkspaceDescriptor:
        record = self._workspace_record(self.workspace_id)
        return CanvasWorkspaceDescriptor(
            workspace_id=record.workspace_id,
            title=record.title,
            purpose="Spatial brainstorming, branching conversation, diagrams, and future visual collaboration.",
            status="conversation_ready",
        )

    def list_workspaces(self) -> list[CanvasWorkspaceRecord]:
        """Return the lightweight workspace registry in stable display order."""

        return list(self.registry_store.load().workspaces)

    def workspace_by_id(self, workspace_id: str) -> CanvasWorkspaceRecord | None:
        """Return one registered workspace without changing the active workspace."""

        clean_id = workspace_id.strip()
        return next(
            (workspace for workspace in self.registry_store.load().workspaces if workspace.workspace_id == clean_id),
            None,
        )

    def ensure_workspace(self, workspace_id: str, title: str) -> CanvasWorkspaceRecord:
        """Create a stable workspace ID without taking focus from the active Canvas."""

        clean_id = workspace_id.strip()
        clean_title = title.strip()
        if clean_id == _MINDMAP_PROJECTION_WORKSPACE_ID:
            clean_title = _MINDMAP_PROJECTION_WORKSPACE_TITLE
        if not clean_id:
            raise ValueError("workspace_id cannot be empty")
        if not clean_title:
            raise ValueError("Canvas workspace title cannot be empty")
        registry = self.registry_store.load()
        existing = next(
            (workspace for workspace in registry.workspaces if workspace.workspace_id == clean_id),
            None,
        )
        if existing is not None:
            if (
                clean_id == _MINDMAP_PROJECTION_WORKSPACE_ID
                and existing.title != _MINDMAP_PROJECTION_WORKSPACE_TITLE
            ):
                existing = replace(
                    existing,
                    title=_MINDMAP_PROJECTION_WORKSPACE_TITLE,
                    updated_at=self._timestamp(),
                )
                self.registry_store.save(
                    CanvasWorkspaceRegistrySnapshot(
                        active_workspace_id=registry.active_workspace_id,
                        workspaces=tuple(
                            existing if workspace.workspace_id == clean_id else workspace
                            for workspace in registry.workspaces
                        ),
                    )
                )
            return existing
        timestamp = self._timestamp()
        record = CanvasWorkspaceRecord(
            workspace_id=clean_id,
            title=clean_title,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.store.save(CanvasDocumentSnapshot.empty(clean_id))
        self.registry_store.save(
            CanvasWorkspaceRegistrySnapshot(
                active_workspace_id=registry.active_workspace_id,
                workspaces=(*registry.workspaces, record),
            )
        )
        return record

    def create_workspace(self, title: str) -> CanvasWorkspaceRecord:
        """Create and activate an empty independent Canvas workspace."""

        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Canvas workspace title cannot be empty")
        registry = self.registry_store.load()
        timestamp = self._timestamp()
        workspace_id = f"canvas_{uuid4().hex[:16]}"
        record = CanvasWorkspaceRecord(
            workspace_id=workspace_id,
            title=clean_title,
            created_at=timestamp,
            updated_at=timestamp,
        )
        blank_path = self.store.save(CanvasDocumentSnapshot.empty(workspace_id))
        updated_registry = CanvasWorkspaceRegistrySnapshot(
            active_workspace_id=workspace_id,
            workspaces=(*registry.workspaces, record),
        )
        try:
            self.registry_store.save(updated_registry)
        except Exception:
            blank_path.unlink(missing_ok=True)
            raise
        self.workspace_id = workspace_id
        return record

    def switch_workspace(self, workspace_id: str) -> CanvasWorkspaceDescriptor:
        """Activate a registered workspace and persist it as the last opened."""

        clean_id = workspace_id.strip()
        registry = self.registry_store.load()
        if clean_id not in {workspace.workspace_id for workspace in registry.workspaces}:
            raise KeyError(f"Unknown Canvas workspace: {clean_id}")
        # Validate the target document before changing the active registry.
        self.store.load(clean_id)
        if clean_id != registry.active_workspace_id:
            self.registry_store.save(
                CanvasWorkspaceRegistrySnapshot(
                    active_workspace_id=clean_id,
                    workspaces=registry.workspaces,
                )
            )
        self.workspace_id = clean_id
        return self.get_workspace_descriptor()

    def rename_workspace(self, workspace_id: str, title: str) -> CanvasWorkspaceRecord:
        """Rename a workspace without changing its stable ID or document."""

        clean_id = workspace_id.strip()
        self._reject_managed_projection_workspace(clean_id)
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Canvas workspace title cannot be empty")
        registry = self.registry_store.load()
        current = next(
            (workspace for workspace in registry.workspaces if workspace.workspace_id == clean_id),
            None,
        )
        if current is None:
            raise KeyError(f"Unknown Canvas workspace: {clean_id}")
        updated = replace(current, title=clean_title, updated_at=self._timestamp())
        workspaces = tuple(
            updated if workspace.workspace_id == clean_id else workspace
            for workspace in registry.workspaces
        )
        self.registry_store.save(
            CanvasWorkspaceRegistrySnapshot(
                active_workspace_id=registry.active_workspace_id,
                workspaces=workspaces,
            )
        )
        return updated

    def delete_workspace(self, workspace_id: str) -> CanvasWorkspaceDescriptor:
        """Archive a workspace and activate a safe remaining workspace.

        Workspace files are moved to ``data/canvas/trash`` instead of being
        permanently erased. If the deleted workspace was the only one, a new
        blank Main Canvas is created automatically.
        """

        clean_id = workspace_id.strip()
        self._reject_managed_projection_workspace(clean_id)
        registry = self.registry_store.load()
        if clean_id not in {workspace.workspace_id for workspace in registry.workspaces}:
            raise KeyError(f"Unknown Canvas workspace: {clean_id}")
        remaining = tuple(
            workspace for workspace in registry.workspaces if workspace.workspace_id != clean_id
        )
        archived_path, original_path = self.store.archive(clean_id)
        replacement_path: Path | None = None
        try:
            if not remaining:
                timestamp = self._timestamp()
                replacement_id = "main"
                replacement = CanvasWorkspaceRecord(
                    workspace_id=replacement_id,
                    title="Main Canvas",
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                remaining = (replacement,)
                replacement_path = self.store.save(CanvasDocumentSnapshot.empty(replacement_id))
            active_id = (
                registry.active_workspace_id
                if registry.active_workspace_id != clean_id
                else remaining[0].workspace_id
            )
            self.registry_store.save(
                CanvasWorkspaceRegistrySnapshot(
                    active_workspace_id=active_id,
                    workspaces=remaining,
                )
            )
        except Exception:
            if replacement_path is not None:
                replacement_path.unlink(missing_ok=True)
            self.store.restore_archive(archived_path, original_path)
            raise
        self._undo_stacks.pop(clean_id, None)
        self.workspace_id = active_id
        return self.get_workspace_descriptor()

    def _workspace_record(self, workspace_id: str) -> CanvasWorkspaceRecord:
        registry = self.registry_store.load()
        record = next(
            (workspace for workspace in registry.workspaces if workspace.workspace_id == workspace_id),
            None,
        )
        if record is None:
            raise KeyError(f"Unknown Canvas workspace: {workspace_id}")
        return record

    def get_snapshot(self) -> CanvasDocumentSnapshot:
        return self.store.load(self.workspace_id)

    def get_snapshot_for_workspace(self, workspace_id: str) -> CanvasDocumentSnapshot:
        """Return a registered workspace document without changing the active workspace."""

        self._workspace_record(workspace_id)
        return self.store.load(workspace_id)

    def replace_mindmap_projection(
        self,
        workspace_id: str,
        *,
        blocks: tuple[CanvasTextBlock, ...],
        connectors: tuple[CanvasConnector, ...],
    ) -> None:
        """Atomically reconcile only Mind Map-managed records in one workspace.

        Normal Canvas records are retained even when this method removes stale
        projection records. This does not publish Canvas source events because
        the projection is derived from the Mind Map rather than user Canvas input.
        """

        if workspace_id != _MINDMAP_PROJECTION_WORKSPACE_ID:
            raise ValueError("Mind Map projection must use the managed Mind Map workspace")
        self.ensure_workspace(_MINDMAP_PROJECTION_WORKSPACE_ID, _MINDMAP_PROJECTION_WORKSPACE_TITLE)
        self._workspace_record(workspace_id)
        snapshot = self.store.load(workspace_id)
        if any(
            block.workspace_id != workspace_id or block.metadata.get("mindmap_projection") is not True
            for block in blocks
        ) or any(
            connector.workspace_id != workspace_id or connector.metadata.get("mindmap_projection") is not True
            for connector in connectors
        ):
            raise ValueError("Mind Map projection records must be marked for their target workspace")
        normal_blocks = tuple(
            block for block in snapshot.text_blocks if block.metadata.get("mindmap_projection") is not True
        )
        normal_connectors = tuple(
            connector for connector in snapshot.connectors if connector.metadata.get("mindmap_projection") is not True
        )
        # CanvasDocumentSnapshot validates unique IDs and connector endpoints before saving.
        self.store.save(
            CanvasDocumentSnapshot(
                workspace_id=workspace_id,
                revision=snapshot.revision + 1,
                text_blocks=(*normal_blocks, *blocks),
                connectors=(*normal_connectors, *connectors),
                root_object_id=snapshot.root_object_id,
                context_baseline=snapshot.context_baseline,
                send_operations=snapshot.send_operations,
            )
        )

    def _replace_mindmap_projection(self, workspace_id, *, blocks, connectors) -> None:
        """Compatibility wrapper; integrations use the validated public method."""
        return self.replace_mindmap_projection(workspace_id, blocks=blocks, connectors=connectors)

    def list_text_blocks(self) -> list[CanvasTextBlock]:
        return list(self.get_snapshot().text_blocks)

    def list_connectors(self) -> list[CanvasConnector]:
        return list(self.get_snapshot().connectors)

    def list_send_operations(self) -> list[CanvasSendOperation]:
        return list(self.get_snapshot().send_operations)

    def can_undo(self) -> bool:
        """Return whether this running Canvas session has a reversible edit."""

        return bool(self._undo_stack)

    def subscribe(self, listener: Callable[[dict[str, object]], None]) -> Callable[[], None]:
        """Subscribe to completed Canvas mutations and return an unsubscribe callback."""

        listener_id = uuid4().hex
        self._listeners[listener_id] = listener
        subscribed = True

        def unsubscribe() -> None:
            nonlocal subscribed
            if subscribed:
                self._listeners.pop(listener_id, None)
                subscribed = False

        return unsubscribe

    def undo_last_change(self) -> CanvasDocumentSnapshot | None:
        """Restore the previous complete Canvas state for this session.

        The restored document receives a fresh monotonically increasing
        revision. That preserves stale-response protection even though the
        visible content moves backwards in history. Undo history intentionally
        resets when AMADEUS restarts; persistent cross-session history can be
        introduced later without changing this public method.
        """

        self._require_editable_workspace()
        if not self._undo_stack:
            return None
        current = self.get_snapshot()
        previous = self._undo_stack.pop()
        restored = CanvasDocumentSnapshot(
            workspace_id=self.workspace_id,
            revision=current.revision + 1,
            text_blocks=previous.text_blocks,
            connectors=previous.connectors,
            root_object_id=previous.root_object_id,
            context_baseline=previous.context_baseline,
            send_operations=previous.send_operations,
        )
        try:
            self.store.save(restored)
        except Exception:
            # Do not consume the history entry if persistence fails.
            self._undo_stack.append(previous)
            raise
        self._publish("canvas_snapshot_restored", snapshot=restored)
        return restored

    def get_change_set(self) -> CanvasChangeSet:
        return self.context_builder.detect_changes(self.get_snapshot())

    def build_context_preview(
        self,
        *,
        context_mode: str = "viewport",
        visible_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_object_ids: list[str] | tuple[str, ...] | set[str] = (),
        selected_connector_ids: list[str] | tuple[str, ...] | set[str] = (),
        branch_root_id: str | None = None,
        ancestor_depth: int = 8,
        descendant_depth: int = 2,
        peer_depth: int = 1,
        token_budget: int = 6000,
    ) -> CanvasContextPackage:
        """Build a target-focused preview without calling an LLM."""

        return self.context_builder.build(
            self.get_snapshot(),
            context_mode=context_mode,
            visible_object_ids=visible_object_ids,
            selected_object_ids=selected_object_ids,
            selected_connector_ids=selected_connector_ids,
            branch_root_id=branch_root_id,
            ancestor_depth=ancestor_depth,
            descendant_depth=descendant_depth,
            peer_depth=peer_depth,
            token_budget=token_budget,
        )

    def set_root_object(self, object_id: str | None) -> CanvasDocumentSnapshot:
        """Persist the default central/root block used by Canvas traversal."""

        self._require_editable_workspace()
        snapshot = self.get_snapshot()
        clean_id = str(object_id or "").strip() or None
        if clean_id is not None:
            block = next((item for item in snapshot.text_blocks if item.object_id == clean_id), None)
            if block is None:
                raise KeyError(f"Unknown Canvas root object: {clean_id}")
            self._reject_managed_projection(block)
        if clean_id == snapshot.root_object_id:
            return snapshot
        return self._save_document(snapshot, root_object_id=clean_id)

    def mark_current_state_sent(self) -> CanvasDocumentSnapshot:
        """Record the current semantic state as the last successful send.

        This temporary UI action lets the context system be tested before the
        real LLM workflow exists. Later it should run only after AMADEUS has
        successfully produced and stored a Canvas response.
        """

        self._require_editable_workspace()
        snapshot = self.get_snapshot()
        baseline = CanvasContextBaseline(
            document_revision=snapshot.revision,
            object_fingerprints={
                block.object_id: semantic_fingerprint_for_block(block) for block in snapshot.text_blocks
            },
            connector_fingerprints={
                connector.connector_id: semantic_fingerprint_for_connector(connector)
                for connector in snapshot.connectors
            },
            created_at=self._timestamp(),
        )
        return self._save_document(snapshot, context_baseline=baseline)

    def commit_amadeus_response(
        self,
        *,
        context_package: CanvasContextPackage,
        response_text: str,
        instruction: str = "",
        process_run_id: str = "",
        model_name: str = "",
        prompt_text: str = "",
    ) -> tuple[CanvasTextBlock, CanvasConnector | None, CanvasSendOperation]:
        """Atomically add an AMADEUS response and advance the sent baseline.

        The LLM call happens before this method. If the Canvas changed after its
        context package was built, the response is rejected rather than being
        attached to stale spatial context.
        """

        self._require_editable_workspace()
        clean_response = response_text.strip()
        if not clean_response:
            raise ValueError("AMADEUS returned an empty Canvas response")
        if context_package.workspace_id != self.workspace_id:
            raise RuntimeError(
                "Canvas workspace changed while AMADEUS was responding. Return to the original workspace and send again."
            )
        current = self.get_snapshot()
        if current.revision != context_package.canvas_revision:
            raise RuntimeError(
                "Canvas changed while AMADEUS was responding. Review the new state and send again."
            )

        valid_block_ids = {block.object_id for block in current.text_blocks}
        primary_source_id = next(
            (object_id for object_id in context_package.target_object_ids if object_id in valid_block_ids),
            None,
        )
        if primary_source_id is None:
            connector_by_id = {connector.connector_id: connector for connector in current.connectors}
            for connector_id in context_package.target_connector_ids:
                connector = connector_by_id.get(connector_id)
                if connector is not None:
                    primary_source_id = connector.target_object_id
                    break
        if primary_source_id is None:
            candidate_root = context_package.active_root_id or current.root_object_id
            if candidate_root in valid_block_ids:
                primary_source_id = candidate_root

        operation_id = f"canvas_send_{uuid4().hex}"
        timestamp = self._timestamp()
        response_width, response_height = self._response_block_size(clean_response)
        response_x, response_y = self._find_response_position(
            current,
            source_object_ids=context_package.target_object_ids or ((primary_source_id,) if primary_source_id else ()),
            response_width=response_width,
            response_height=response_height,
        )
        response_block = CanvasTextBlock(
            object_id=f"canvas_text_{uuid4().hex}",
            workspace_id=self.workspace_id,
            text=clean_response,
            position_x=response_x,
            position_y=response_y,
            width=response_width,
            height=response_height,
            created_by="amadeus",
            created_at=timestamp,
            updated_at=timestamp,
            metadata={
                "canvas_role": "amadeus_response",
                "source_operation_id": operation_id,
            },
        )
        connector: CanvasConnector | None = None
        new_connectors = current.connectors
        if primary_source_id is not None:
            connector = CanvasConnector(
                connector_id=f"canvas_connector_{uuid4().hex}",
                workspace_id=self.workspace_id,
                source_object_id=primary_source_id,
                target_object_id=response_block.object_id,
                connector_type="arrow",
                relation_type="responds_to",
                label="AMADEUS response",
                created_by="amadeus",
                created_at=timestamp,
                updated_at=timestamp,
                metadata={
                    "canvas_role": "response_link",
                    "source_operation_id": operation_id,
                },
            )
            new_connectors = (*new_connectors, connector)

        new_blocks = (*current.text_blocks, response_block)
        committed_revision = current.revision + 1
        baseline = CanvasContextBaseline(
            document_revision=committed_revision,
            object_fingerprints={
                block.object_id: semantic_fingerprint_for_block(block) for block in new_blocks
            },
            connector_fingerprints={
                item.connector_id: semantic_fingerprint_for_connector(item)
                for item in new_connectors
            },
            created_at=timestamp,
        )
        operation = CanvasSendOperation(
            operation_id=operation_id,
            workspace_id=self.workspace_id,
            instruction=instruction,
            context_mode=context_package.context_mode,
            source_canvas_revision=context_package.canvas_revision,
            committed_canvas_revision=committed_revision,
            response_object_id=response_block.object_id,
            response_connector_id=connector.connector_id if connector is not None else None,
            process_run_id=process_run_id,
            model_name=model_name,
            prompt_text=prompt_text,
            context_payload=context_package.to_prompt_dict(),
            created_at=timestamp,
        )
        snapshot = CanvasDocumentSnapshot(
            workspace_id=self.workspace_id,
            revision=committed_revision,
            text_blocks=new_blocks,
            connectors=new_connectors,
            root_object_id=current.root_object_id,
            context_baseline=baseline,
            send_operations=(*current.send_operations, operation),
        )
        self.store.save(snapshot)
        self._remember_undo(current)
        self._publish("canvas_block_saved", block=response_block)
        if connector is not None:
            self._publish("canvas_connector_saved", connector=connector)
        return response_block, connector, operation

    def create_text_block(
        self,
        *,
        text: str,
        position_x: float = 0.0,
        position_y: float = 0.0,
        width: float = 320.0,
        height: float = 180.0,
        title: str = "",
        comment: str = "",
        comment_anchor_degrees: float = 315.0,
        comment_width: float = 190.0,
        comment_height: float = 74.0,
        created_by: str = "dato",
    ) -> CanvasTextBlock:
        self._require_editable_workspace()
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Canvas text cannot be empty")
        snapshot = self.get_snapshot()
        timestamp = self._timestamp()
        block = CanvasTextBlock(
            object_id=f"canvas_text_{uuid4().hex}",
            workspace_id=self.workspace_id,
            text=clean_text,
            position_x=float(position_x),
            position_y=float(position_y),
            width=float(width),
            height=float(height),
            title=title,
            comment=comment,
            comment_anchor_degrees=float(comment_anchor_degrees),
            comment_width=float(comment_width),
            comment_height=float(comment_height),
            created_by=created_by,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._save_document(snapshot, text_blocks=(*snapshot.text_blocks, block))
        self._publish("canvas_block_saved", block=block)
        return block

    def update_text_block(
        self,
        object_id: str,
        *,
        text: str | object = _UNSET,
        position_x: float | object = _UNSET,
        position_y: float | object = _UNSET,
        width: float | object = _UNSET,
        height: float | object = _UNSET,
        title: str | object = _UNSET,
        comment: str | object = _UNSET,
        comment_anchor_degrees: float | object = _UNSET,
        comment_width: float | object = _UNSET,
        comment_height: float | object = _UNSET,
        locked: bool | object = _UNSET,
    ) -> CanvasTextBlock:
        self._require_editable_workspace()
        clean_id = object_id.strip()
        if not clean_id:
            raise ValueError("object_id cannot be empty")
        snapshot = self.get_snapshot()
        current = next((block for block in snapshot.text_blocks if block.object_id == clean_id), None)
        if current is None:
            raise KeyError(f"Unknown Canvas object: {clean_id}")
        self._reject_managed_projection(current)

        clean_text = current.text if text is _UNSET else str(text).strip()
        if not clean_text:
            raise ValueError("Canvas text cannot be empty")
        updated = replace(
            current,
            text=clean_text,
            position_x=current.position_x if position_x is _UNSET else float(position_x),
            position_y=current.position_y if position_y is _UNSET else float(position_y),
            width=current.width if width is _UNSET else float(width),
            height=current.height if height is _UNSET else float(height),
            title=current.title if title is _UNSET else str(title).strip(),
            comment=current.comment if comment is _UNSET else str(comment).strip(),
            comment_anchor_degrees=(
                current.comment_anchor_degrees
                if comment_anchor_degrees is _UNSET
                else float(comment_anchor_degrees)
            ),
            comment_width=(
                current.comment_width if comment_width is _UNSET else float(comment_width)
            ),
            comment_height=(
                current.comment_height if comment_height is _UNSET else float(comment_height)
            ),
            locked=current.locked if locked is _UNSET else bool(locked),
            revision=current.revision + 1,
            updated_at=self._timestamp(),
        )
        blocks = tuple(updated if block.object_id == clean_id else block for block in snapshot.text_blocks)
        self._save_document(snapshot, text_blocks=blocks)
        self._publish("canvas_block_saved", block=updated)
        return updated

    def create_connector(
        self,
        *,
        source_object_id: str,
        target_object_id: str,
        connector_type: str = "arrow",
        relation_type: str = DEFAULT_RELATION_TYPE,
        label: str = "",
        comment: str = "",
        created_by: str = "dato",
    ) -> CanvasConnector:
        self._require_editable_workspace()
        snapshot = self.get_snapshot()
        source_id = source_object_id.strip()
        target_id = target_object_id.strip()
        self._validate_connector_endpoints(snapshot, source_id, target_id)
        timestamp = self._timestamp()
        connector = CanvasConnector(
            connector_id=f"canvas_connector_{uuid4().hex}",
            workspace_id=self.workspace_id,
            source_object_id=source_id,
            target_object_id=target_id,
            connector_type=connector_type,
            relation_type=relation_type,
            label=label,
            comment=comment,
            created_by=created_by,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._save_document(snapshot, connectors=(*snapshot.connectors, connector))
        self._publish("canvas_connector_saved", connector=connector)
        return connector

    def update_connector(
        self,
        connector_id: str,
        *,
        connector_type: str | object = _UNSET,
        relation_type: str | object = _UNSET,
        label: str | object = _UNSET,
        comment: str | object = _UNSET,
    ) -> CanvasConnector:
        self._require_editable_workspace()
        clean_id = connector_id.strip()
        if not clean_id:
            raise ValueError("connector_id cannot be empty")
        snapshot = self.get_snapshot()
        current = next((connector for connector in snapshot.connectors if connector.connector_id == clean_id), None)
        if current is None:
            raise KeyError(f"Unknown Canvas connector: {clean_id}")
        self._reject_managed_projection(current)
        updated = replace(
            current,
            connector_type=current.connector_type if connector_type is _UNSET else str(connector_type),
            relation_type=current.relation_type if relation_type is _UNSET else str(relation_type),
            label=current.label if label is _UNSET else str(label),
            comment=current.comment if comment is _UNSET else str(comment),
            revision=current.revision + 1,
            updated_at=self._timestamp(),
        )
        connectors = tuple(
            updated if connector.connector_id == clean_id else connector for connector in snapshot.connectors
        )
        self._save_document(snapshot, connectors=connectors)
        self._publish("canvas_connector_saved", connector=updated)
        return updated

    def delete_items(
        self,
        *,
        object_ids: list[str] | tuple[str, ...] | set[str] = (),
        connector_ids: list[str] | tuple[str, ...] | set[str] = (),
    ) -> tuple[int, int]:
        """Delete selected blocks/connectors atomically and remove orphans.

        Deleting a block always deletes every connector attached to it. This
        keeps the persisted graph valid and avoids invisible orphan relations.
        """

        self._require_editable_workspace()
        clean_object_ids = {str(object_id).strip() for object_id in object_ids if str(object_id).strip()}
        clean_connector_ids = {
            str(connector_id).strip() for connector_id in connector_ids if str(connector_id).strip()
        }
        if not clean_object_ids and not clean_connector_ids:
            return (0, 0)

        snapshot = self.get_snapshot()
        managed_block_ids = {
            block.object_id
            for block in snapshot.text_blocks
            if self._is_managed_projection(block)
        }
        managed_connector_ids = {
            connector.connector_id
            for connector in snapshot.connectors
            if self._is_managed_projection(connector)
        }
        attached_connector_ids = {
            connector.connector_id
            for connector in snapshot.connectors
            if connector.source_object_id in clean_object_ids or connector.target_object_id in clean_object_ids
        }
        if clean_object_ids & managed_block_ids or (clean_connector_ids | attached_connector_ids) & managed_connector_ids:
            raise PermissionError("Mind Map projection records are read-only in Canvas")
        remaining_blocks = tuple(
            block for block in snapshot.text_blocks if block.object_id not in clean_object_ids
        )
        deleted_object_count = len(snapshot.text_blocks) - len(remaining_blocks)
        deleted_object_ids = [
            block.object_id for block in snapshot.text_blocks if block.object_id in clean_object_ids
        ]

        all_connector_ids = clean_connector_ids | attached_connector_ids
        remaining_connectors = tuple(
            connector for connector in snapshot.connectors if connector.connector_id not in all_connector_ids
        )
        deleted_connector_count = len(snapshot.connectors) - len(remaining_connectors)
        deleted_connector_ids = [
            connector.connector_id
            for connector in snapshot.connectors
            if connector.connector_id in all_connector_ids
        ]

        if deleted_object_count or deleted_connector_count:
            self._save_document(
                snapshot,
                text_blocks=remaining_blocks,
                connectors=remaining_connectors,
                root_object_id=(
                    None if snapshot.root_object_id in clean_object_ids else snapshot.root_object_id
                ),
            )
            self._publish(
                "canvas_items_deleted",
                deleted_object_ids=deleted_object_ids,
                deleted_connector_ids=deleted_connector_ids,
            )
        return deleted_object_count, deleted_connector_count

    def delete_items_in_workspace(
        self,
        workspace_id: str,
        *,
        object_ids: list[str] | tuple[str, ...] | set[str] = (),
        connector_ids: list[str] | tuple[str, ...] | set[str] = (),
    ) -> tuple[int, int]:
        """Delete source records in their owning workspace without changing the active workspace.

        Cross-module consumers use this when a Mind Map source reference points
        at a non-active Canvas workspace. The registry's active workspace is
        restored even if the deletion fails.
        """

        source_workspace_id = workspace_id.strip()
        if not source_workspace_id:
            raise ValueError("workspace_id cannot be empty")
        previous_workspace_id = self.workspace_id
        if source_workspace_id == previous_workspace_id:
            return self.delete_items(object_ids=object_ids, connector_ids=connector_ids)
        self.switch_workspace(source_workspace_id)
        try:
            return self.delete_items(object_ids=object_ids, connector_ids=connector_ids)
        finally:
            self.switch_workspace(previous_workspace_id)

    def delete_objects(self, object_ids: list[str] | tuple[str, ...] | set[str]) -> int:
        deleted_objects, _deleted_connectors = self.delete_items(object_ids=object_ids)
        return deleted_objects

    def delete_connectors(self, connector_ids: list[str] | tuple[str, ...] | set[str]) -> int:
        _deleted_objects, deleted_connectors = self.delete_items(connector_ids=connector_ids)
        return deleted_connectors

    def _save_document(
        self,
        previous: CanvasDocumentSnapshot,
        *,
        text_blocks: tuple[CanvasTextBlock, ...] | None = None,
        connectors: tuple[CanvasConnector, ...] | None = None,
        root_object_id: str | None | object = _UNSET,
        context_baseline: CanvasContextBaseline | None | object = _UNSET,
        send_operations: tuple[CanvasSendOperation, ...] | None = None,
    ) -> CanvasDocumentSnapshot:
        snapshot = CanvasDocumentSnapshot(
            workspace_id=self.workspace_id,
            revision=previous.revision + 1,
            text_blocks=previous.text_blocks if text_blocks is None else text_blocks,
            connectors=previous.connectors if connectors is None else connectors,
            root_object_id=(
                previous.root_object_id if root_object_id is _UNSET else root_object_id
            ),
            context_baseline=(
                previous.context_baseline if context_baseline is _UNSET else context_baseline
            ),
            send_operations=(
                previous.send_operations if send_operations is None else send_operations
            ),
        )
        self.store.save(snapshot)
        self._remember_undo(previous)
        return snapshot

    def is_read_only_workspace(self, workspace_id: str | None = None) -> bool:
        """Return whether a workspace is owned by a managed projection."""

        return (workspace_id or self.workspace_id).strip() == _MINDMAP_PROJECTION_WORKSPACE_ID

    def _require_editable_workspace(self) -> None:
        self._reject_managed_projection_workspace(self.workspace_id)

    @staticmethod
    def _reject_managed_projection_workspace(workspace_id: str) -> None:
        if workspace_id == _MINDMAP_PROJECTION_WORKSPACE_ID:
            raise PermissionError("Mind Map workspace is read-only in Canvas")

    def _publish(self, event_type: str, **fields: object) -> None:
        """Notify a stable listener snapshot without affecting saved Canvas state."""

        event = {"event_type": event_type, **fields}
        for listener in tuple(self._listeners.values()):
            try:
                listener(event)
            except Exception:
                # Observers are projections; their failure must not undo a saved Canvas mutation.
                continue

    def _remember_undo(self, snapshot: CanvasDocumentSnapshot) -> None:
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._undo_limit:
            del self._undo_stack[: len(self._undo_stack) - self._undo_limit]

    @staticmethod
    def _is_managed_projection(record: CanvasTextBlock | CanvasConnector) -> bool:
        """Identify records owned by the Mind Map-to-Canvas projector."""

        return record.metadata.get("mindmap_projection") is True

    @classmethod
    def _reject_managed_projection(cls, record: CanvasTextBlock | CanvasConnector) -> None:
        """Keep graph-derived Canvas records read-only through public APIs."""

        if cls._is_managed_projection(record):
            raise PermissionError("Mind Map projection records are read-only in Canvas")

    @staticmethod
    def _find_response_position(
        snapshot: CanvasDocumentSnapshot,
        *,
        source_object_ids: tuple[str, ...] | list[str],
        response_width: float = 380.0,
        response_height: float = 220.0,
    ) -> tuple[float, float]:
        """Choose predictable open space near the response targets."""

        block_by_id = {block.object_id: block for block in snapshot.text_blocks}
        sources = [block_by_id[object_id] for object_id in source_object_ids if object_id in block_by_id]
        if sources:
            base_x = max(block.position_x + block.width for block in sources) + 100.0
            base_y = min(block.position_y for block in sources)
        elif snapshot.text_blocks:
            base_x = max(block.position_x + block.width for block in snapshot.text_blocks) + 100.0
            base_y = min(block.position_y for block in snapshot.text_blocks)
        else:
            return (0.0, 0.0)

        margin = 36.0

        def overlaps(x: float, y: float) -> bool:
            left = x - margin
            right = x + response_width + margin
            top = y - margin
            bottom = y + response_height + margin
            return any(
                not (
                    right < block.position_x
                    or left > block.position_x + block.width
                    or bottom < block.position_y
                    or top > block.position_y + block.height
                )
                for block in snapshot.text_blocks
            )

        for column in range(4):
            candidate_x = base_x + column * (response_width + 100.0)
            for row in range(10):
                candidate_y = base_y + row * (response_height + 60.0)
                if not overlaps(candidate_x, candidate_y):
                    return (candidate_x, candidate_y)
        return (base_x, base_y + 10 * (response_height + 60.0))

    @staticmethod
    def _response_block_size(response_text: str) -> tuple[float, float]:
        """Choose a readable initial size while keeping manual resize available."""

        width = 420.0
        characters_per_line = 56
        visual_lines = 0
        for paragraph in response_text.splitlines() or [response_text]:
            visual_lines += max(1, (len(paragraph) + characters_per_line - 1) // characters_per_line)
        height = min(760.0, max(180.0, 78.0 + visual_lines * 23.0))
        return width, height

    @staticmethod
    def _validate_connector_endpoints(
        snapshot: CanvasDocumentSnapshot,
        source_object_id: str,
        target_object_id: str,
    ) -> None:
        if not source_object_id or not target_object_id:
            raise ValueError("Connector source and target IDs cannot be empty")
        if source_object_id == target_object_id:
            raise ValueError("Canvas connectors cannot link an object to itself")
        object_ids = {block.object_id for block in snapshot.text_blocks}
        if source_object_id not in object_ids:
            raise KeyError(f"Unknown Canvas source object: {source_object_id}")
        if target_object_id not in object_ids:
            raise KeyError(f"Unknown Canvas target object: {target_object_id}")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
