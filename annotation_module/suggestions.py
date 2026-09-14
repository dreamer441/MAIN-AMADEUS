"""Provide failure-tolerant annotation suggestions to every conversation view."""

from __future__ import annotations

from typing import Any


class AnnotationSuggestions:
    """Provide failure-tolerant annotation suggestions to every conversation view."""

    def __init__(self, *, annotation_suggestion_service: Any) -> None:
        """Receive the public services needed by this workflow."""
        self.annotation_suggestion_service = annotation_suggestion_service

    def get_annotation_suggestions(self, current_input: str) -> list[dict[str, str]]:
        """Return GUI suggestions for slash/annotation building.

        Suggestions are read-only and quick. If something goes wrong, Core returns
        an empty list so the chat window remains usable.
        """
        try:
            return self.annotation_suggestion_service.get_suggestions(current_input)
        except Exception:
            return []

    def get_flow_annotation_suggestions(self, text: str) -> list[dict[str, str]]:
        """Return the same annotation suggestions used by dedicated chat."""
        return self.get_annotation_suggestions(text)
