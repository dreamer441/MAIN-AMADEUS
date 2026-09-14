"""Result object returned by annotation handlers.

Most annotations still return simple chat text. Some annotations, especially
`[file]`, also need to update a GUI side panel without dumping large content into
main chat. This object keeps that payload explicit and avoids mixing code content
with normal conversation history.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnnotationResult:
    """User-visible annotation response plus optional GUI side-panel data."""

    response: str
    side_panel: dict[str, Any] | None = None


def unpack_annotation_output(annotation_output: object) -> tuple[str, dict | None]:
    """Normalize handler output without running or storing a conversation."""
    if isinstance(annotation_output, AnnotationResult):
        return annotation_output.response, annotation_output.side_panel
    if isinstance(annotation_output, str):
        return annotation_output, None
    return "AMADEUS annotation error: handler returned an unreadable result.", None
