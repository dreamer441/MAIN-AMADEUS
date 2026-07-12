"""Structured payloads for the AMADEUS right-side panel.

Core and annotation handlers currently pass dictionaries to the GUI. This class
keeps that contract compatible while giving future modules one clear shape for
right-panel updates. The payload is display data only: exact file reading still
belongs to `project_file_reader`, memory still belongs to `memory_module`, and
trace creation still belongs to `amadeus_trace`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SidePanelPayload:
    """One requested update for the right-side workspace panel.

    A payload says *what should be displayed*, not *how it was produced*.
    Keeping this separate prevents the right panel from becoming a giant module
    that secretly owns file access, memory, traces, or future sheets/materials.
    """

    panel_type: str
    title: str
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw_payload: object) -> "SidePanelPayload | None":
        """Convert Core's current dictionary payload into a safe object.

        The GUI should be tolerant because older modules may still return plain
        dictionaries. Invalid payloads are ignored rather than crashing AMADEUS.
        """
        if isinstance(raw_payload, cls):
            return raw_payload
        if not isinstance(raw_payload, dict):
            return None

        panel_type = str(raw_payload.get("type") or raw_payload.get("panel_type") or "").strip()
        if not panel_type:
            return None

        title = str(raw_payload.get("title") or panel_type.title())
        content = str(raw_payload.get("content") or "")
        metadata = raw_payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        return cls(panel_type=panel_type, title=title, content=content, metadata=metadata)

    def to_dict(self) -> dict[str, Any]:
        """Return the older dictionary shape for compatibility with Core/GUI code."""
        return {
            "type": self.panel_type,
            "title": self.title,
            "content": self.content,
            "metadata": dict(self.metadata),
        }
