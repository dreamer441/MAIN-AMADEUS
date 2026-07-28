"""Public module entry point for the AMADEUS Infinite Canvas."""

from __future__ import annotations

from pathlib import Path

from canvas_module.models import CanvasWorkspaceDescriptor


class CanvasModule:
    """Stable Core-registered facade for Canvas behavior.

    Canvas is intentionally only a workspace foundation in this phase. The
    module owns its identity and future storage boundary while PyQt rendering
    remains inside ``canvas_module.gui``. Core and other modules should call
    this facade instead of reaching into scene widgets directly.
    """

    def __init__(self, project_root: Path, workspace_id: str = "main") -> None:
        self.project_root = Path(project_root)
        self.workspace_id = workspace_id

    def get_workspace_descriptor(self) -> CanvasWorkspaceDescriptor:
        """Return the stable metadata needed to mount the Canvas GUI shell."""
        return CanvasWorkspaceDescriptor(
            workspace_id=self.workspace_id,
            title="AMADEUS Canvas",
            purpose="Spatial brainstorming, branching conversation, diagrams, and future visual collaboration.",
            status="foundation_ready",
        )
