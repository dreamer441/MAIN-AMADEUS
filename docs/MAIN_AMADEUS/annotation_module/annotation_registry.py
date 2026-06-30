from typing import Protocol

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation


class AnnotationHandler(Protocol):
    """Small interface every annotation handler must provide."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> str:
        """Handle a parsed annotation and return text for AMADEUS to display."""


class AnnotationRegistry:
    """Stores annotation handlers by normalized annotation name."""

    def __init__(self) -> None:
        self._handlers: dict[str, AnnotationHandler] = {}

    def register(self, name: str, handler: AnnotationHandler) -> None:
        """Register one annotation handler."""
        clean_name = name.strip().lower()
        if not clean_name:
            raise ValueError("Annotation name cannot be empty.")

        self._handlers[clean_name] = handler

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> str:
        """Route a parsed annotation to its registered handler."""
        handler = self._handlers.get(annotation.annotation_name)
        if handler is None:
            available = ", ".join(sorted(self._handlers)) or "none"
            return (
                f"Unknown annotation: [{annotation.annotation_name}]\n\n"
                f"Available annotations: {available}"
            )

        return handler.handle(annotation, context)
