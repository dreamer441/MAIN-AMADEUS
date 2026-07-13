"""Managed local references and exported-chat records for the Materials panel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from export_module import ChatExportService


class MaterialsService:
    """Lists, opens, and prepares explicit one-request material references.

    The service owns files under ``data/materials`` and composes ExportService's
    public API for exported chats. It never makes a material active by selection.
    """

    def __init__(self, project_root: Path, export_service: ChatExportService) -> None:
        self.project_root = project_root.resolve()
        self.export_service = export_service
        self.materials_directory = self.project_root / "data" / "materials"
        self.materials_directory.mkdir(parents=True, exist_ok=True)

    def list_materials(self) -> list[dict[str, Any]]:
        """Return managed files and export records as safe, display-ready rows."""
        rows: list[dict[str, Any]] = []
        for path in sorted(self.materials_directory.rglob("*")):
            if path.is_file() and self._is_within(path, self.materials_directory):
                relative_path = path.relative_to(self.materials_directory).as_posix()
                rows.append({
                    "id": f"material:{relative_path}",
                    "name": path.name,
                    "type": "managed_file",
                    "metadata": {"relative_path": relative_path, "size_bytes": path.stat().st_size},
                    "removable": True,
                })
        for record in self.export_service.list_exports():
            rows.append({
                "id": f"export:{record.export_id}",
                "name": record.chat_title,
                "type": "chat_export",
                "metadata": {
                    "export_id": record.export_id,
                    "chat_id": record.chat_id,
                    "exported_at": record.exported_at,
                    "message_count": record.message_count,
                    "txt_path": record.txt_path,
                    "md_path": record.md_path,
                    "json_path": record.json_path,
                },
                "removable": True,
            })
        return rows

    def build_panel_payload(self, selected_material_id: str | None = None) -> dict[str, Any]:
        """Build the Materials list payload without loading any material content."""
        materials = self.list_materials()
        return {
            "type": "materials",
            "title": "AMADEUS Materials",
            "content": "Select a material to preview or open it. Selection alone never adds it to a message.",
            "metadata": {
                "material_count": len(materials),
                "status": "ready",
                "materials": materials,
                "selected_material_id": selected_material_id or "",
            },
        }

    def preview_material(self, material_id: str) -> dict[str, Any]:
        """Return a bounded visual preview; this action never creates chat context."""
        return self._build_content_payload(material_id, preview=True)

    def open_material(self, material_id: str) -> dict[str, Any]:
        """Return full readable material content; this action never creates chat context."""
        return self._build_content_payload(material_id, preview=False)

    def build_callable_context(self, material_id: str) -> str:
        """Return one explicitly selected material as labelled, request-only context."""
        item = self._find_material(material_id)
        if item is None:
            raise ValueError("Unknown material reference.")
        if item["type"] == "chat_export":
            selection, problem = self.export_service.resolve_selection(
                item["metadata"]["export_id"], export_missing_chat=False
            )
            if problem is not None or selection is None:
                raise ValueError(problem or "Could not load export context.")
            return self.export_service.build_prompt_context(selection)

        path = self._managed_path(item)
        content = self._read_text(path)
        return (
            "VERIFIED MANAGED MATERIAL\n"
            "This is an explicitly selected local Materials reference for this request only.\n"
            "It is not always-active memory. Answer from it when the user refers to this material.\n\n"
            f"Material: {item['name']}\nReference: {item['id']}\n\n--- MATERIAL CONTENT ---\n\n{content}"
        )

    def remove_material(self, material_id: str) -> None:
        """Deliberately remove one managed file or known export record."""
        item = self._find_material(material_id)
        if item is None:
            raise ValueError("Unknown material reference.")
        if item["type"] == "chat_export":
            self.export_service.remove_export(item["metadata"]["export_id"])
            return
        self._managed_path(item).unlink()

    def material_reference(self, material_id: str) -> str:
        """Return the stable identifier suitable for copying into a note or message."""
        if self._find_material(material_id) is None:
            raise ValueError("Unknown material reference.")
        return material_id

    def _build_content_payload(self, material_id: str, preview: bool) -> dict[str, Any]:
        item = self._find_material(material_id)
        if item is None:
            raise ValueError("Unknown material reference.")
        if item["type"] == "chat_export":
            selection, problem = self.export_service.resolve_selection(
                item["metadata"]["export_id"], export_missing_chat=False
            )
            if problem is not None or selection is None:
                raise ValueError(problem or "Could not open export.")
            payload = self.export_service.build_materials_panel_payload(selection)
            payload["metadata"].update({"materials": self.list_materials(), "selected_material_id": material_id, "preview": preview})
            if preview and len(payload["content"]) > 4000:
                payload["content"] = payload["content"][:4000] + "\n\n[Preview truncated. Open to view all content.]"
            return payload

        content = self._read_text(self._managed_path(item))
        if preview and len(content) > 4000:
            content = content[:4000] + "\n\n[Preview truncated. Open to view all content.]"
        return {
            "type": "materials",
            "title": f"Material: {item['name']}",
            "content": content,
            "metadata": {"material_count": len(self.list_materials()), "status": "material_open", "materials": self.list_materials(), "selected_material_id": material_id, "preview": preview, **item["metadata"]},
        }

    def _find_material(self, material_id: str) -> dict[str, Any] | None:
        return next((item for item in self.list_materials() if item["id"] == material_id), None)

    def _managed_path(self, item: dict[str, Any]) -> Path:
        relative_path = str(item["metadata"].get("relative_path") or "")
        path = (self.materials_directory / relative_path).resolve()
        if not relative_path or not self._is_within(path, self.materials_directory) or not path.is_file():
            raise ValueError("Managed material path is not available.")
        return path

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("This managed material is not UTF-8 text and cannot be opened yet.") from error

    @staticmethod
    def _is_within(path: Path, directory: Path) -> bool:
        try:
            path.resolve().relative_to(directory.resolve())
            return True
        except ValueError:
            return False
