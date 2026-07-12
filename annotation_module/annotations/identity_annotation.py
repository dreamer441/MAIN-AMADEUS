"""Read-only `[identity]` annotation handler.

This gives Dato a simple way to inspect AMADEUS's active identity charter and
prompt forms without digging through source files.
"""

import re

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation


class IdentityAnnotation:
    """Handles `[identity]` annotations through read-only identity access."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> str:
        """Return identity status, prompt views, or the full charter."""
        if not annotation.arguments:
            return context.identity_service.build_status_report()

        # Annotation arguments are now preserved raw so file paths can keep dots.
        # Identity only needs a simple normalized view name, so it normalizes locally.
        requested_view = self._normalize_view_name(annotation.arguments[0])
        snapshot = context.identity_service.load_snapshot()

        # These aliases keep the annotation usable even if Dato types a natural variant.
        if requested_view in {"prompt", "compact"}:
            return snapshot.compact_prompt
        if requested_view in {"project", "strong"}:
            return snapshot.project_prompt
        if requested_view in {"charter", "full"}:
            return snapshot.charter_markdown

        return (
            f"Unknown identity view: {annotation.arguments[0]}\n\n"
            "Available views:\n"
            "* [identity]\n"
            "* [identity][prompt]\n"
            "* [identity][project]\n"
            "* [identity][charter]"
        )

    def _normalize_view_name(self, view_name: str) -> str:
        """Normalize a view name without changing how file annotation paths work."""
        normalized = view_name.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")
