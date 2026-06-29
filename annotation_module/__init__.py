"""AMADEUS annotation module package."""

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import AnnotationParser, ParsedAnnotation
from annotation_module.annotation_registry import AnnotationHandler, AnnotationRegistry

__all__ = [
    "AnnotationContext",
    "AnnotationHandler",
    "AnnotationParser",
    "AnnotationRegistry",
    "ParsedAnnotation",
]
