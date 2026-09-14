"""Expose managed materials and explicitly requested conversation context."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class MaterialsWorkspace:
    """Expose managed materials and explicitly requested conversation context."""

    def __init__(self, *, materials_service: Any, handle_user_message: Any) -> None:
        """Receive the public services needed by this workflow."""
        self.materials_service = materials_service
        self.handle_user_message = handle_user_message

    def get_materials_panel_payload(self) -> dict[str, Any]:
        """Return material rows without opening or injecting a selected reference."""
        return self.materials_service.build_panel_payload()

    def list_materials(self) -> list[dict[str, Any]]:
        """Return material metadata for non-GUI callers through Materials only."""
        return self.materials_service.list_materials()

    def preview_material(self, material_id: str) -> dict[str, Any]:
        """Preview one explicitly selected Materials record through its module API."""
        return self.materials_service.preview_material(material_id)

    def open_material(self, material_id: str) -> dict[str, Any]:
        """Open one explicitly selected Materials record without injecting it."""
        return self.materials_service.open_material(material_id)

    def get_material_reference(self, material_id: str) -> str:
        """Return a selected stable material reference for GUI clipboard actions."""
        return self.materials_service.material_reference(material_id)

    def get_material_copy_text(self, material_id: str) -> str:
        """Return the selected material's Core-owned clipboard text."""
        return self.materials_service.material_copy_text(material_id)

    def remove_material(self, material_id: str) -> None:
        """Remove one explicitly selected Materials record where supported."""
        self.materials_service.remove_material(material_id)

    def handle_material_message(
        self,
        material_id: str,
        message: str,
        event_listener: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        """Use one selected material as callable context for this one chat request."""
        return self.handle_user_message(
            message,
            callable_context=self.materials_service.build_callable_context(material_id),
            event_listener=event_listener,
        )
