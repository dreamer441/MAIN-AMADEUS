"""Framework-independent domain models for the AMADEUS Infinite Canvas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


CANVAS_SCHEMA_VERSION = 6
CANVAS_WORKSPACE_REGISTRY_SCHEMA_VERSION = 1
DEFAULT_WORKSPACE_ID = "main"
SUPPORTED_CONNECTOR_TYPES = frozenset({"line", "arrow"})
DEFAULT_RELATION_TYPE = "related_to"


@dataclass(frozen=True, slots=True)
class CanvasWorkspaceDescriptor:
    """Describe one Canvas workspace without exposing GUI internals."""

    workspace_id: str
    title: str
    purpose: str
    status: str
    schema_version: int = CANVAS_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class CanvasWorkspaceRecord:
    """One lightweight Canvas workspace entry stored in the registry."""

    workspace_id: str
    title: str
    created_at: str = ""
    updated_at: str = ""
    status: str = "active"

    def __post_init__(self) -> None:
        clean_id = self.workspace_id.strip()
        clean_title = self.title.strip()
        clean_status = self.status.strip().lower() or "active"
        if not clean_id:
            raise ValueError("workspace_id cannot be empty")
        if not clean_title:
            raise ValueError("Canvas workspace title cannot be empty")
        object.__setattr__(self, "workspace_id", clean_id)
        object.__setattr__(self, "title", clean_title)
        object.__setattr__(self, "status", clean_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CanvasWorkspaceRecord":
        return cls(
            workspace_id=str(payload.get("workspace_id", "")),
            title=str(payload.get("title", "")),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            status=str(payload.get("status", "active")),
        )


@dataclass(frozen=True, slots=True)
class CanvasWorkspaceRegistrySnapshot:
    """Versioned list of Canvas workspaces and the last active workspace."""

    active_workspace_id: str
    workspaces: tuple[CanvasWorkspaceRecord, ...]
    schema_version: int = CANVAS_WORKSPACE_REGISTRY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        clean_active = self.active_workspace_id.strip()
        if self.schema_version != CANVAS_WORKSPACE_REGISTRY_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported Canvas workspace registry schema version: {self.schema_version}"
            )
        workspace_ids = [workspace.workspace_id for workspace in self.workspaces]
        if not workspace_ids:
            raise ValueError("Canvas workspace registry must contain at least one workspace")
        if len(workspace_ids) != len(set(workspace_ids)):
            raise ValueError("Canvas workspace IDs must be unique")
        if clean_active not in set(workspace_ids):
            raise ValueError("Active Canvas workspace must exist in the registry")
        object.__setattr__(self, "active_workspace_id", clean_active)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active_workspace_id": self.active_workspace_id,
            "workspaces": [workspace.to_dict() for workspace in self.workspaces],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CanvasWorkspaceRegistrySnapshot":
        raw_workspaces = payload.get("workspaces", [])
        if not isinstance(raw_workspaces, list):
            raise ValueError("Canvas workspace registry entries must be stored as a list")
        workspaces = tuple(
            CanvasWorkspaceRecord.from_dict(item)
            for item in raw_workspaces
            if isinstance(item, Mapping)
        )
        if len(workspaces) != len(raw_workspaces):
            raise ValueError("Canvas workspace registry contains invalid entries")
        return cls(
            active_workspace_id=str(payload.get("active_workspace_id", "")),
            workspaces=workspaces,
            schema_version=int(
                payload.get("schema_version", CANVAS_WORKSPACE_REGISTRY_SCHEMA_VERSION)
            ),
        )


@dataclass(frozen=True, slots=True)
class CanvasTextBlock:
    """One typed, movable Canvas object.

    The GUI renders this model but does not own its persistence. Stable object
    IDs and revisions let later context extraction and delta tracking refer to
    the same idea even after Dato moves or edits it.
    """

    object_id: str
    workspace_id: str
    text: str
    position_x: float
    position_y: float
    width: float = 320.0
    height: float = 180.0
    title: str = ""
    comment: str = ""
    comment_anchor_degrees: float = 315.0
    comment_width: float = 190.0
    comment_height: float = 74.0
    created_by: str = "dato"
    revision: int = 1
    z_index: float = 0.0
    locked: bool = False
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        clean_id = self.object_id.strip()
        clean_workspace = self.workspace_id.strip()
        clean_text = self.text.strip()
        clean_author = self.created_by.strip().lower()
        if not clean_id:
            raise ValueError("object_id cannot be empty")
        if not clean_workspace:
            raise ValueError("workspace_id cannot be empty")
        if not clean_text:
            raise ValueError("text cannot be empty")
        if self.width < 120 or self.height < 80:
            raise ValueError("Canvas text blocks must remain large enough to use")
        if self.comment_width < 100 or self.comment_height < 48:
            raise ValueError("Canvas comment bubbles must remain large enough to use")
        if self.revision < 1:
            raise ValueError("revision must be at least 1")
        object.__setattr__(self, "object_id", clean_id)
        object.__setattr__(self, "workspace_id", clean_workspace)
        object.__setattr__(self, "text", clean_text)
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "comment", self.comment.strip())
        object.__setattr__(self, "comment_anchor_degrees", float(self.comment_anchor_degrees) % 360.0)
        object.__setattr__(self, "comment_width", float(self.comment_width))
        object.__setattr__(self, "comment_height", float(self.comment_height))
        object.__setattr__(self, "created_by", clean_author or "dato")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def object_type(self) -> str:
        return "text"

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_id": self.object_id,
            "workspace_id": self.workspace_id,
            "text": self.text,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "width": self.width,
            "height": self.height,
            "title": self.title,
            "comment": self.comment,
            "comment_anchor_degrees": self.comment_anchor_degrees,
            "comment_width": self.comment_width,
            "comment_height": self.comment_height,
            "created_by": self.created_by,
            "revision": self.revision,
            "z_index": self.z_index,
            "locked": self.locked,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CanvasTextBlock":
        if str(payload.get("object_type", "text")).strip().lower() != "text":
            raise ValueError("Unsupported Canvas object type")
        return cls(
            object_id=str(payload.get("object_id", "")),
            workspace_id=str(payload.get("workspace_id", "")),
            text=str(payload.get("text", "")),
            position_x=float(payload.get("position_x", 0.0)),
            position_y=float(payload.get("position_y", 0.0)),
            width=float(payload.get("width", 320.0)),
            height=float(payload.get("height", 180.0)),
            title=str(payload.get("title", "")),
            comment=str(payload.get("comment", "")),
            comment_anchor_degrees=float(payload.get("comment_anchor_degrees", 315.0)),
            comment_width=float(payload.get("comment_width", 190.0)),
            comment_height=float(payload.get("comment_height", 74.0)),
            created_by=str(payload.get("created_by", "dato")),
            revision=int(payload.get("revision", 1)),
            z_index=float(payload.get("z_index", 0.0)),
            locked=bool(payload.get("locked", False)),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {},
        )


@dataclass(frozen=True, slots=True)
class CanvasConnector:
    """A persisted semantic relationship between two Canvas objects.

    Connectors reference stable object IDs rather than fixed pixel endpoints.
    The GUI derives visual geometry from the current block positions, so moving
    a block never mutates or weakens the semantic relationship itself.
    """

    connector_id: str
    workspace_id: str
    source_object_id: str
    target_object_id: str
    connector_type: str = "arrow"
    relation_type: str = DEFAULT_RELATION_TYPE
    label: str = ""
    comment: str = ""
    created_by: str = "dato"
    revision: int = 1
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        clean_id = self.connector_id.strip()
        clean_workspace = self.workspace_id.strip()
        clean_source = self.source_object_id.strip()
        clean_target = self.target_object_id.strip()
        clean_type = self.connector_type.strip().lower()
        clean_relation = self.relation_type.strip().lower().replace(" ", "_")
        clean_author = self.created_by.strip().lower()
        if not clean_id:
            raise ValueError("connector_id cannot be empty")
        if not clean_workspace:
            raise ValueError("workspace_id cannot be empty")
        if not clean_source or not clean_target:
            raise ValueError("Connector source and target IDs cannot be empty")
        if clean_source == clean_target:
            raise ValueError("Canvas connectors cannot link an object to itself")
        if clean_type not in SUPPORTED_CONNECTOR_TYPES:
            raise ValueError(f"Unsupported Canvas connector type: {clean_type}")
        if not clean_relation:
            clean_relation = DEFAULT_RELATION_TYPE
        if self.revision < 1:
            raise ValueError("revision must be at least 1")
        object.__setattr__(self, "connector_id", clean_id)
        object.__setattr__(self, "workspace_id", clean_workspace)
        object.__setattr__(self, "source_object_id", clean_source)
        object.__setattr__(self, "target_object_id", clean_target)
        object.__setattr__(self, "connector_type", clean_type)
        object.__setattr__(self, "relation_type", clean_relation)
        object.__setattr__(self, "label", self.label.strip())
        object.__setattr__(self, "comment", self.comment.strip())
        object.__setattr__(self, "created_by", clean_author or "dato")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "workspace_id": self.workspace_id,
            "source_object_id": self.source_object_id,
            "target_object_id": self.target_object_id,
            "connector_type": self.connector_type,
            "relation_type": self.relation_type,
            "label": self.label,
            "comment": self.comment,
            "created_by": self.created_by,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CanvasConnector":
        return cls(
            connector_id=str(payload.get("connector_id", "")),
            workspace_id=str(payload.get("workspace_id", "")),
            source_object_id=str(payload.get("source_object_id", "")),
            target_object_id=str(payload.get("target_object_id", "")),
            connector_type=str(payload.get("connector_type", "arrow")),
            relation_type=str(payload.get("relation_type", DEFAULT_RELATION_TYPE)),
            label=str(payload.get("label", "")),
            comment=str(payload.get("comment", "")),
            created_by=str(payload.get("created_by", "dato")),
            revision=int(payload.get("revision", 1)),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {},
        )


@dataclass(frozen=True, slots=True)
class CanvasContextBaseline:
    """Semantic state recorded after the last successful Canvas send.

    The baseline stores meaning fingerprints instead of raw object revisions.
    Moving or resizing a block therefore does not make AMADEUS answer it again,
    while text and relationship edits still appear as meaningful changes.
    """

    document_revision: int
    object_fingerprints: Mapping[str, str]
    connector_fingerprints: Mapping[str, str]
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.document_revision < 0:
            raise ValueError("Baseline document revision cannot be negative")
        object.__setattr__(self, "object_fingerprints", dict(self.object_fingerprints))
        object.__setattr__(self, "connector_fingerprints", dict(self.connector_fingerprints))

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_revision": self.document_revision,
            "object_fingerprints": dict(self.object_fingerprints),
            "connector_fingerprints": dict(self.connector_fingerprints),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CanvasContextBaseline":
        raw_objects = payload.get("object_fingerprints", {})
        raw_connectors = payload.get("connector_fingerprints", {})
        if not isinstance(raw_objects, Mapping) or not isinstance(raw_connectors, Mapping):
            raise ValueError("Canvas context fingerprints must be JSON objects")
        return cls(
            document_revision=int(payload.get("document_revision", 0)),
            object_fingerprints={str(key): str(value) for key, value in raw_objects.items()},
            connector_fingerprints={str(key): str(value) for key, value in raw_connectors.items()},
            created_at=str(payload.get("created_at", "")),
        )


@dataclass(frozen=True, slots=True)
class CanvasSendOperation:
    """One auditable Canvas-to-AMADEUS request and committed response.

    The record keeps the optional one-off instruction and the exact structured
    context payload used for generation. It is Canvas history metadata, not a
    visible Canvas object unless Dato explicitly creates a block from it later.
    """

    operation_id: str
    workspace_id: str
    instruction: str
    context_mode: str
    source_canvas_revision: int
    committed_canvas_revision: int
    response_object_id: str
    response_connector_id: str | None = None
    process_run_id: str = ""
    model_name: str = ""
    prompt_text: str = ""
    context_payload: Mapping[str, Any] | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        clean_id = self.operation_id.strip()
        clean_workspace = self.workspace_id.strip()
        clean_response_id = self.response_object_id.strip()
        clean_connector_id = (self.response_connector_id or "").strip() or None
        if not clean_id:
            raise ValueError("operation_id cannot be empty")
        if not clean_workspace:
            raise ValueError("workspace_id cannot be empty")
        if not clean_response_id:
            raise ValueError("response_object_id cannot be empty")
        if self.source_canvas_revision < 0 or self.committed_canvas_revision < 1:
            raise ValueError("Canvas send revisions are invalid")
        if self.committed_canvas_revision <= self.source_canvas_revision:
            raise ValueError("Committed Canvas revision must follow the source revision")
        if not isinstance(self.context_payload, (Mapping, type(None))):
            raise ValueError("context_payload must be a mapping when provided")
        object.__setattr__(self, "operation_id", clean_id)
        object.__setattr__(self, "workspace_id", clean_workspace)
        object.__setattr__(self, "instruction", self.instruction.strip())
        object.__setattr__(self, "context_mode", self.context_mode.strip().lower())
        object.__setattr__(self, "response_object_id", clean_response_id)
        object.__setattr__(self, "response_connector_id", clean_connector_id)
        object.__setattr__(self, "process_run_id", self.process_run_id.strip())
        object.__setattr__(self, "model_name", self.model_name.strip())
        object.__setattr__(self, "prompt_text", self.prompt_text.strip())
        object.__setattr__(self, "context_payload", dict(self.context_payload or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "workspace_id": self.workspace_id,
            "instruction": self.instruction,
            "context_mode": self.context_mode,
            "source_canvas_revision": self.source_canvas_revision,
            "committed_canvas_revision": self.committed_canvas_revision,
            "response_object_id": self.response_object_id,
            "response_connector_id": self.response_connector_id,
            "process_run_id": self.process_run_id,
            "model_name": self.model_name,
            "prompt_text": self.prompt_text,
            "context_payload": dict(self.context_payload or {}),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CanvasSendOperation":
        raw_context = payload.get("context_payload", {})
        if not isinstance(raw_context, Mapping):
            raise ValueError("Canvas send context payload must be a JSON object")
        return cls(
            operation_id=str(payload.get("operation_id", "")),
            workspace_id=str(payload.get("workspace_id", "")),
            instruction=str(payload.get("instruction", "")),
            context_mode=str(payload.get("context_mode", "viewport")),
            source_canvas_revision=int(payload.get("source_canvas_revision", 0)),
            committed_canvas_revision=int(payload.get("committed_canvas_revision", 0)),
            response_object_id=str(payload.get("response_object_id", "")),
            response_connector_id=(
                str(payload.get("response_connector_id")).strip()
                if payload.get("response_connector_id") is not None
                else None
            ),
            process_run_id=str(payload.get("process_run_id", "")),
            model_name=str(payload.get("model_name", "")),
            prompt_text=str(payload.get("prompt_text", "")),
            context_payload=raw_context,
            created_at=str(payload.get("created_at", "")),
        )


@dataclass(frozen=True, slots=True)
class CanvasDocumentSnapshot:
    """A complete, versioned read of one Canvas workspace."""

    workspace_id: str
    revision: int
    text_blocks: tuple[CanvasTextBlock, ...]
    connectors: tuple[CanvasConnector, ...] = ()
    root_object_id: str | None = None
    context_baseline: CanvasContextBaseline | None = None
    send_operations: tuple[CanvasSendOperation, ...] = ()
    schema_version: int = CANVAS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        clean_workspace = self.workspace_id.strip()
        if not clean_workspace:
            raise ValueError("workspace_id cannot be empty")
        if self.revision < 0:
            raise ValueError("revision cannot be negative")
        if self.schema_version != CANVAS_SCHEMA_VERSION:
            raise ValueError(f"Unsupported Canvas schema version: {self.schema_version}")

        object_ids = [block.object_id for block in self.text_blocks]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("Canvas object IDs must be unique")
        if any(block.workspace_id != clean_workspace for block in self.text_blocks):
            raise ValueError("Canvas objects must belong to the same workspace as their document")

        connector_ids = [connector.connector_id for connector in self.connectors]
        if len(connector_ids) != len(set(connector_ids)):
            raise ValueError("Canvas connector IDs must be unique")
        if any(connector.workspace_id != clean_workspace for connector in self.connectors):
            raise ValueError("Canvas connectors must belong to the same workspace as their document")
        valid_object_ids = set(object_ids)
        for connector in self.connectors:
            if connector.source_object_id not in valid_object_ids:
                raise ValueError(f"Connector source does not exist: {connector.source_object_id}")
            if connector.target_object_id not in valid_object_ids:
                raise ValueError(f"Connector target does not exist: {connector.target_object_id}")

        operation_ids = [operation.operation_id for operation in self.send_operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("Canvas send-operation IDs must be unique")
        if any(operation.workspace_id != clean_workspace for operation in self.send_operations):
            raise ValueError("Canvas send operations must belong to the document workspace")
        clean_root = self.root_object_id.strip() if isinstance(self.root_object_id, str) else None
        clean_root = clean_root or None
        if clean_root is not None and clean_root not in valid_object_ids:
            raise ValueError(f"Canvas root does not exist: {clean_root}")

        object.__setattr__(self, "workspace_id", clean_workspace)
        object.__setattr__(self, "root_object_id", clean_root)

    @classmethod
    def empty(cls, workspace_id: str = DEFAULT_WORKSPACE_ID) -> "CanvasDocumentSnapshot":
        return cls(
            workspace_id=workspace_id,
            revision=0,
            text_blocks=(),
            connectors=(),
            root_object_id=None,
            context_baseline=None,
            send_operations=(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workspace_id": self.workspace_id,
            "revision": self.revision,
            "objects": [block.to_dict() for block in self.text_blocks],
            "connectors": [connector.to_dict() for connector in self.connectors],
            "root_object_id": self.root_object_id,
            "context_baseline": (
                self.context_baseline.to_dict() if self.context_baseline is not None else None
            ),
            "send_operations": [operation.to_dict() for operation in self.send_operations],
        }
