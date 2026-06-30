from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation


class IdentityAnnotation:
    """Handles `[identity]` annotations through read-only identity access."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> str:
        """Return identity status, prompt views, or the full charter."""
        if not annotation.arguments:
            return context.identity_service.build_status_report()

        requested_view = annotation.arguments[0]
        snapshot = context.identity_service.load_snapshot()

        if requested_view in {"prompt", "compact"}:
            return snapshot.compact_prompt
        if requested_view in {"project", "strong"}:
            return snapshot.project_prompt
        if requested_view in {"charter", "full"}:
            return snapshot.charter_markdown

        return (
            f"Unknown identity view: {requested_view}\n\n"
            "Available views:\n"
            "* [identity]\n"
            "* [identity][prompt]\n"
            "* [identity][project]\n"
            "* [identity][charter]"
        )
