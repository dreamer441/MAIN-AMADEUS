"""Foundation service for the future AMADEUS Materials panel.

Materials are larger readable references such as exported chats, PDFs, text notes,
images, or imported documents. V1 only creates the panel placeholder and stable
payload shape. Chat export and real material indexing should build on this module
instead of adding more logic into the GUI.
"""

from __future__ import annotations

from pathlib import Path


class MaterialsService:
    """Builds the first right-panel payload for materials/export references."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.materials_directory = self.project_root / "data" / "materials"
        self.materials_directory.mkdir(parents=True, exist_ok=True)

    def build_panel_payload(self) -> dict:
        """Return the placeholder Materials panel payload.

        This is intentionally not a fake material list. It tells Dato what the
        panel is for and leaves real export/material records for the next patches.
        """
        return {
            "type": "materials",
            "title": "AMADEUS Materials",
            "content": (
                "Materials panel foundation is ready.\n\n"
                "Future items shown here:\n"
                "- exported chats (.txt visible, .md/.json usable for context)\n"
                "- uploaded text/Markdown files\n"
                "- PDFs\n"
                "- images/screenshots after image support exists\n\n"
                "Next planned export annotation shape:\n"
                "[export][chat name][4-6]"
            ),
            "metadata": {
                "material_count": 0,
                "directory": str(self.materials_directory),
                "status": "foundation_only",
            },
        }
