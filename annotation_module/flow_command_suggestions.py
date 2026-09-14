"""Flow-only staged workspace command suggestions."""

from annotation_module.annotation_suggestions import AnnotationSuggestion


class FlowCommandSuggestionProvider:
    """Offer Flow creation commands without exposing them to dedicated Chat."""

    def get_suggestions(self, text: str) -> list[AnnotationSuggestion]:
        """Return the next command step for an exact Flow command prefix."""
        stripped = text.strip()
        if stripped == "/":
            return [AnnotationSuggestion("/create", "/create", "Create a Sheet, Comment, or Memory")]
        if stripped == "/create":
            return [
                AnnotationSuggestion("/create-chat", "/create-chat ", "Create a dedicated Chat"),
                AnnotationSuggestion("/create-sheet", "/create-sheet ", "Create a Sheet immediately"),
                AnnotationSuggestion("/create-comment", "/create-comment ", "Create a Comment immediately"),
                AnnotationSuggestion("/create-memory", "/create-memory ", "Create a Memory immediately"),
            ]
        return []
