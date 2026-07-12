"""Registry for AMADEUS annotation handlers.

The registry keeps annotation names and handler objects separate from Core. Core
only needs to parse the annotation and ask the registry to handle it.
"""

from typing import Protocol

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation
from annotation_module.annotation_result import AnnotationResult


AnnotationHandlerResult = str | AnnotationResult


class AnnotationHandler(Protocol):
    """Small interface every annotation handler must provide."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> AnnotationHandlerResult:
        """Handle a parsed annotation and return chat text or a richer result."""


class AnnotationRegistry:
    """Stores annotation handlers by normalized annotation name."""

    def __init__(self) -> None:
        # Keys are normalized names such as "file" or "identity".
        self._handlers: dict[str, AnnotationHandler] = {}

    def register(self, name: str, handler: AnnotationHandler) -> None:
        """Register one annotation handler."""
        clean_name = name.strip().lower()
        if not clean_name:
            raise ValueError("Annotation name cannot be empty.")

        self._handlers[clean_name] = handler

    def available_annotation_names(self) -> list[str]:
        """Return registered annotation names for GUI slash suggestions."""
        return sorted(self._handlers)

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> AnnotationHandlerResult:
        """Route a parsed annotation to its registered handler."""
        handler = self._handlers.get(annotation.annotation_name)
        if handler is None:
            # Unknown annotations return a readable message instead of raising.
            # This keeps user experiments safe while the annotation system grows.
            available = ", ".join(sorted(self._handlers)) or "none"
            return (
                f"Unknown annotation: [{annotation.annotation_name}]\n\n"
                f"Available annotations: {available}"
            )

        return handler.handle(annotation, context)
