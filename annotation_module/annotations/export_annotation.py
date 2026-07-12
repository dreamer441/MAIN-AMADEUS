"""`[export]` annotation handler for chat exports.

Export commands are deterministic workspace actions. They create/open exported
chat references and display them in the Materials panel. When Dato adds prompt
text after an export annotation, Core routes the selected export segment into
normal chat as callable context.

The handler supports a clearer structured path now:
- `[export][open][Chat Title][4-6]` opens a selected range in Materials.
- `[export][use][Chat Title][4-6] prompt` injects that selected range.

The older shorthand `[export][Chat Title][4-6]` still works for speed, but the
structured form is easier to teach through suggestions.
"""

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation
from annotation_module.annotation_result import AnnotationResult


class ExportAnnotation:
    """Handles direct `[export]` commands that do not need an LLM answer."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> AnnotationResult | str:
        """Export/list/open chat exports in the Materials panel.

        Direct forms open the Materials panel and keep the main chat clean. If
        annotation content exists after the brackets, Core handles the request as
        callable export context instead of using this direct handler.
        """
        target, parse_problem = context.export_service.parse_annotation_target(annotation.arguments)
        if parse_problem is not None or target is None:
            return self._help(parse_problem)

        if target.mode == "help":
            return self._help()

        if target.mode == "list":
            return AnnotationResult(
                response="Opened exported chats in the Materials panel.",
                side_panel=context.export_service.build_materials_panel_payload(),
            )

        selection, problem = context.export_service.resolve_selection(target.title_or_id, target.range_token)
        if problem is not None or selection is None:
            return self._help(problem)

        if target.mode == "current" and target.range_token is None:
            # `[export]` and `[export][current]` also refresh the current chat export.
            response = (
                f"Exported/opened current chat `{selection.record.chat_title}` in Materials.\n"
                f"Formats saved: TXT, MD, JSON. Messages exported: {selection.record.message_count}."
            )
        elif target.range_token:
            response = (
                f"Opened export `{selection.record.chat_title}` message range `{selection.range_label}` in Materials.\n"
                "This is a real exported chat segment, not metadata. Add text after the annotation to ask about this exact segment."
            )
        else:
            response = (
                f"Exported/opened chat `{selection.record.chat_title}` in Materials.\n"
                "Use `[export][open][chat title][4-6]` to open a specific message range, or "
                "`[export][use][chat title][4-6] your question` to inject it into AMADEUS context."
            )

        return AnnotationResult(
            response=response,
            side_panel=context.export_service.build_materials_panel_payload(selection),
        )

    def _help(self, problem: str | None = None) -> str:
        """Return concise export usage help."""
        prefix = f"Export problem: {problem}\n\n" if problem else ""
        return (
            prefix
            + "Use export annotations like this:\n"
            "* `[export]` - export/open the current chat in Materials\n"
            "* `[export][list]` - show exported chats in Materials\n"
            "* `[export][open][Chat Title]` - export/open a named chat\n"
            "* `[export][open][Chat Title][4-6]` - open selected real messages\n"
            "* `[export][use][Chat Title][4-6] your prompt` - answer using only that selected exported segment\n\n"
            "Shorthand still works: `[export][Chat Title][4-6] your prompt`."
        )
