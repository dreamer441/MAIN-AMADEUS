"""`[mindmap]` annotation registration for explicit graph retrieval.

Prompt-bearing requests are routed by ``CallableContextRouter`` so the graph
remains a one-request source for Chat rather than deterministic chat output.
"""

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation


class MindMapAnnotation:
    """Provides a safe direct response when a Mind Map block has no chat prompt."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> str:
        """Describe the explicit Mind Map retrieval syntax."""
        return (
            "Mind Map retrieval is available for a chat request.\n\n"
            "* `[mindmap] your question` - use up to 10 available recent nodes\n"
            "* `[mindmap][search text] your question` - search up to 10 matching nodes\n\n"
            "Mind Map nodes are used only for this request."
        )
