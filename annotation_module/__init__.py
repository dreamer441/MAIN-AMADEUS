"""AMADEUS annotation module package."""

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import AnnotationParser, ParsedAnnotation
from annotation_module.annotation_registry import AnnotationHandler, AnnotationRegistry
from annotation_module.annotation_result import AnnotationResult
from annotation_module.annotation_suggestions import AnnotationSuggestion, AnnotationSuggestionService

__all__ = [
    "AnnotationContext",
    "AnnotationHandler",
    "AnnotationParser",
    "AnnotationRegistry",
    "AnnotationResult",
    "AnnotationSuggestion",
    "AnnotationSuggestionService",
    "ParsedAnnotation",
]
