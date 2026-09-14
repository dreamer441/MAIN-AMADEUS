"""Safe local persistence for AMADEUS Canvas workspaces and their registry."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Mapping

from canvas_module.models import (
    CANVAS_SCHEMA_VERSION,
    CANVAS_WORKSPACE_REGISTRY_SCHEMA_VERSION,
    DEFAULT_WORKSPACE_ID,
    CanvasConnector,
    CanvasContextBaseline,
    CanvasDocumentSnapshot,
    CanvasSendOperation,
    CanvasTextBlock,
    CanvasWorkspaceRecord,
    CanvasWorkspaceRegistrySnapshot,
)


_WORKSPACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_MIN_SUPPORTED_SCHEMA_VERSION = 1


class CanvasStorageError(RuntimeError):
    """Raised when Canvas data cannot be loaded or saved safely."""


def _validate_workspace_id(workspace_id: str) -> str:
    clean_id = workspace_id.strip()
    if not clean_id or not _WORKSPACE_ID_PATTERN.fullmatch(clean_id):
        raise ValueError("workspace_id may contain only letters, numbers, underscores, and hyphens")
    return clean_id


def _atomic_write_json(path: Path, payload: Mapping[str, object], *, error_message: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
        return path
    except OSError as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise CanvasStorageError(error_message) from exc


class CanvasDocumentStore:
    """Persist one JSON document per Canvas workspace using atomic replacement.

    Current documents live under ``data/canvas/workspaces``. Older Canvas
    builds stored ``data/canvas/<workspace>.json``; those files remain readable
    and are moved into the new location only after a successful save or registry
    migration, so existing brainstorming is never silently discarded.
    """

    def __init__(self, project_root: Path) -> None:
        self.root = Path(project_root) / "data" / "canvas"
        self.workspaces_root = self.root / "workspaces"
        self.trash_root = self.root / "trash"

    def path_for(self, workspace_id: str) -> Path:
        clean_id = _validate_workspace_id(workspace_id)
        return self.workspaces_root / f"{clean_id}.json"

    def legacy_path_for(self, workspace_id: str) -> Path:
        clean_id = _validate_workspace_id(workspace_id)
        return self.root / f"{clean_id}.json"

    def existing_path_for(self, workspace_id: str) -> Path | None:
        current = self.path_for(workspace_id)
        if current.exists():
            return current
        legacy = self.legacy_path_for(workspace_id)
        return legacy if legacy.exists() else None

    def load(self, workspace_id: str) -> CanvasDocumentSnapshot:
        path = self.existing_path_for(workspace_id)
        if path is None:
            return CanvasDocumentSnapshot.empty(workspace_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CanvasStorageError(f"Could not load Canvas workspace '{workspace_id}'") from exc
        if not isinstance(payload, Mapping):
            raise CanvasStorageError("Canvas workspace root must be a JSON object")
        try:
            schema_version = int(payload.get("schema_version", 1))
            if not _MIN_SUPPORTED_SCHEMA_VERSION <= schema_version <= CANVAS_SCHEMA_VERSION:
                raise ValueError(f"Unsupported Canvas schema version: {schema_version}")

            stored_workspace_id = str(payload.get("workspace_id", ""))
            if stored_workspace_id != workspace_id:
                raise ValueError("Canvas workspace identity does not match its file")

            raw_objects = payload.get("objects", [])
            if not isinstance(raw_objects, list):
                raise ValueError("Canvas objects must be stored as a list")
            text_blocks = tuple(
                CanvasTextBlock.from_dict(item) for item in raw_objects if isinstance(item, Mapping)
            )
            if len(text_blocks) != len(raw_objects):
                raise ValueError("Canvas objects contain invalid entries")

            raw_connectors = payload.get("connectors", []) if schema_version >= 2 else []
            if not isinstance(raw_connectors, list):
                raise ValueError("Canvas connectors must be stored as a list")
            connectors = tuple(
                CanvasConnector.from_dict(item)
                for item in raw_connectors
                if isinstance(item, Mapping)
            )
            if len(connectors) != len(raw_connectors):
                raise ValueError("Canvas connectors contain invalid entries")

            root_object_id = None
            context_baseline = None
            if schema_version >= 3:
                raw_root_value = payload.get("root_object_id")
                if raw_root_value is not None:
                    raw_root = str(raw_root_value).strip()
                    root_object_id = raw_root or None
                raw_baseline = payload.get("context_baseline")
                if raw_baseline is not None:
                    if not isinstance(raw_baseline, Mapping):
                        raise ValueError("Canvas context baseline must be a JSON object or null")
                    context_baseline = CanvasContextBaseline.from_dict(raw_baseline)

            raw_operations = payload.get("send_operations", []) if schema_version >= 4 else []
            if not isinstance(raw_operations, list):
                raise ValueError("Canvas send operations must be stored as a list")
            send_operations = tuple(
                CanvasSendOperation.from_dict(item)
                for item in raw_operations
                if isinstance(item, Mapping)
            )
            if len(send_operations) != len(raw_operations):
                raise ValueError("Canvas send operations contain invalid entries")

            return CanvasDocumentSnapshot(
                workspace_id=stored_workspace_id,
                revision=int(payload.get("revision", 0)),
                text_blocks=text_blocks,
                connectors=connectors,
                root_object_id=root_object_id,
                context_baseline=context_baseline,
                send_operations=send_operations,
                schema_version=CANVAS_SCHEMA_VERSION,
            )
        except (TypeError, ValueError) as exc:
            raise CanvasStorageError(f"Canvas workspace '{workspace_id}' has invalid data") from exc

    def save(self, snapshot: CanvasDocumentSnapshot) -> Path:
        path = self.path_for(snapshot.workspace_id)
        saved_path = _atomic_write_json(
            path,
            snapshot.to_dict(),
            error_message=f"Could not save Canvas workspace '{snapshot.workspace_id}'",
        )
        legacy = self.legacy_path_for(snapshot.workspace_id)
        if legacy != path:
            legacy.unlink(missing_ok=True)
        return saved_path

    def archive(self, workspace_id: str) -> tuple[Path | None, Path | None]:
        """Move one workspace document into recoverable trash.

        Returns ``(archived_path, original_path)``. Empty workspaces may not
        have a document yet, in which case both values are ``None``.
        """

        original = self.existing_path_for(workspace_id)
        if original is None:
            return None, None
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.trash_root.mkdir(parents=True, exist_ok=True)
        archived = self.trash_root / f"{_validate_workspace_id(workspace_id)}_{timestamp}.json"
        try:
            os.replace(original, archived)
        except OSError as exc:
            raise CanvasStorageError(f"Could not archive Canvas workspace '{workspace_id}'") from exc
        return archived, original

    @staticmethod
    def restore_archive(archived_path: Path | None, original_path: Path | None) -> None:
        if archived_path is None or original_path is None or not archived_path.exists():
            return
        original_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(archived_path, original_path)


class CanvasWorkspaceRegistryStore:
    """Persist the lightweight list of Canvas workspaces and active selection."""

    def __init__(self, project_root: Path, document_store: CanvasDocumentStore | None = None) -> None:
        self.root = Path(project_root) / "data" / "canvas"
        self.path = self.root / "registry.json"
        self.document_store = document_store or CanvasDocumentStore(project_root)

    def load_or_create(self, preferred_workspace_id: str | None = None) -> CanvasWorkspaceRegistrySnapshot:
        preferred = (
            _validate_workspace_id(preferred_workspace_id)
            if preferred_workspace_id is not None
            else None
        )
        if self.path.exists():
            registry = self.load()
            self._migrate_registered_legacy_documents(registry)
            if preferred is not None and preferred not in {
                workspace.workspace_id for workspace in registry.workspaces
            }:
                timestamp = self._timestamp()
                registry = CanvasWorkspaceRegistrySnapshot(
                    active_workspace_id=preferred,
                    workspaces=(
                        *registry.workspaces,
                        CanvasWorkspaceRecord(
                            workspace_id=preferred,
                            title=self.default_title(preferred),
                            created_at=timestamp,
                            updated_at=timestamp,
                        ),
                    ),
                )
                self.save(registry)
            elif preferred is not None and preferred != registry.active_workspace_id:
                registry = CanvasWorkspaceRegistrySnapshot(
                    active_workspace_id=preferred,
                    workspaces=registry.workspaces,
                )
                self.save(registry)
            return registry

        workspace_ids = self._discover_and_migrate_documents()
        if preferred is not None and preferred not in workspace_ids:
            workspace_ids.append(preferred)
        if not workspace_ids:
            workspace_ids = [preferred or DEFAULT_WORKSPACE_ID]
        ordered_ids = list(dict.fromkeys(workspace_ids))
        timestamp = self._timestamp()
        workspaces = tuple(
            CanvasWorkspaceRecord(
                workspace_id=workspace_id,
                title=self.default_title(workspace_id),
                created_at=timestamp,
                updated_at=timestamp,
            )
            for workspace_id in ordered_ids
        )
        active = preferred if preferred in ordered_ids else ordered_ids[0]
        registry = CanvasWorkspaceRegistrySnapshot(
            active_workspace_id=active,
            workspaces=workspaces,
        )
        self.save(registry)
        return registry

    def load(self) -> CanvasWorkspaceRegistrySnapshot:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CanvasStorageError("Could not load the Canvas workspace registry") from exc
        if not isinstance(payload, Mapping):
            raise CanvasStorageError("Canvas workspace registry root must be a JSON object")
        try:
            return CanvasWorkspaceRegistrySnapshot.from_dict(payload)
        except (TypeError, ValueError) as exc:
            raise CanvasStorageError("Canvas workspace registry has invalid data") from exc

    def save(self, registry: CanvasWorkspaceRegistrySnapshot) -> Path:
        return _atomic_write_json(
            self.path,
            registry.to_dict(),
            error_message="Could not save the Canvas workspace registry",
        )

    def _discover_and_migrate_documents(self) -> list[str]:
        self.document_store.workspaces_root.mkdir(parents=True, exist_ok=True)
        discovered: list[str] = []
        for path in sorted(self.document_store.workspaces_root.glob("*.json")):
            try:
                discovered.append(_validate_workspace_id(path.stem))
            except ValueError:
                continue

        for legacy in sorted(self.root.glob("*.json")):
            if legacy == self.path:
                continue
            try:
                workspace_id = _validate_workspace_id(legacy.stem)
            except ValueError:
                continue
            target = self.document_store.path_for(workspace_id)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.replace(legacy, target)
                except OSError as exc:
                    raise CanvasStorageError(
                        f"Could not migrate legacy Canvas workspace '{workspace_id}'"
                    ) from exc
            discovered.append(workspace_id)
        return list(dict.fromkeys(discovered))

    def _migrate_registered_legacy_documents(
        self, registry: CanvasWorkspaceRegistrySnapshot
    ) -> None:
        for workspace in registry.workspaces:
            current = self.document_store.path_for(workspace.workspace_id)
            legacy = self.document_store.legacy_path_for(workspace.workspace_id)
            if current.exists() or not legacy.exists():
                continue
            current.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(legacy, current)
            except OSError as exc:
                raise CanvasStorageError(
                    f"Could not migrate legacy Canvas workspace '{workspace.workspace_id}'"
                ) from exc

    @staticmethod
    def default_title(workspace_id: str) -> str:
        if workspace_id == DEFAULT_WORKSPACE_ID:
            return "Main Canvas"
        readable = workspace_id.replace("_", " ").replace("-", " ").strip()
        return readable.title() or "Canvas Workspace"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
