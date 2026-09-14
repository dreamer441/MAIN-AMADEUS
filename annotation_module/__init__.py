"""AMADEUS annotation module package."""

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import AnnotationBlock, AnnotationParser, ParsedAnnotation, ParsedAnnotationMessage
from annotation_module.annotation_registry import AnnotationHandler, AnnotationRegistry
from annotation_module.annotation_result import AnnotationResult
from annotation_module.annotation_suggestions import AnnotationSuggestion, AnnotationSuggestionService
from annotation_module.flow_command_suggestions import FlowCommandSuggestionProvider
from annotation_module.creation_commands import CreationAnnotationRequest, parse_creation_annotation

__all__ = [
    "AnnotationContext",
    "CallableContextRouter",
    "AnnotationHandler",
    "AnnotationBlock",
    "AnnotationParser",
    "AnnotationRegistry",
    "AnnotationResult",
    "AnnotationSuggestion",
    "AnnotationSuggestionService",
    "FlowCommandSuggestionProvider",
    "CreationAnnotationRequest",
    "parse_creation_annotation",
    "ParsedAnnotation",
    "ParsedAnnotationMessage",
]


def __getattr__(name: str):
    """Resolve the legacy conversation export without a package import cycle."""
    if name == "CallableContextRouter":
        from chat_workspace.selected_context import SelectedContextConversation
        return SelectedContextConversation
    raise AttributeError(name)
