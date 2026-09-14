"""`[sheet]` annotation handler for AMADEUS Sheets.

The sheet annotation has two roles:
1. open/list sheets in the right panel without polluting chat;
2. select a sheet as callable context when Core routes `[sheet][... ] prompt`.

The LLM does not invent sheet content. Sheet content comes from `sheets_module`
and is injected only when Dato explicitly asks through `[sheet]`.
"""

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation
from annotation_module.annotation_result import AnnotationResult


def resolve_sheet_annotation_target(sheet_service, annotation: ParsedAnnotation, chat_id: str):
    """Interpret bracket syntax here and send plain scope/locator values to Sheets."""
    arguments = annotation.arguments
    normalized = annotation.normalized_arguments
    if not arguments:
        return sheet_service.resolve_target(chat_id)
    first = normalized[0] if normalized else ""
    if first == "list":
        scope = normalized[1] if len(normalized) > 1 else "all"
        if scope not in {"all", "chat", "global"}:
            return None, f"Unknown sheet list scope: `{arguments[1]}`", "all"
        return sheet_service.resolve_target(chat_id, scope=scope)
    if first in {"chat", "global"}:
        reference = arguments[1] if len(arguments) > 1 else None
        return sheet_service.resolve_target(chat_id, scope=first, reference=reference)
    return sheet_service.resolve_target(chat_id, reference=arguments[0])


class SheetAnnotation:
    """Handles read/list/open commands for `[sheet]`."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> AnnotationResult | str:
        """Open sheet lists or one selected sheet in the right-side Sheets panel.

        If the annotation contains extra prompt text, Core handles it before this
        direct handler so the selected sheet can be injected into normal chat.
        """
        chat_id = context.current_chat_id_provider()
        sheet, problem, scope = resolve_sheet_annotation_target(context.sheet_service, annotation, chat_id)
        if problem is not None:
            return self._sheet_help(problem)

        if sheet is None:
            return AnnotationResult(
                response=f"Opened {scope} sheets in the right panel.",
                side_panel=context.sheet_service.build_panel_payload(
                    chat_id=chat_id,
                    scope=scope,
                    title="AMADEUS Sheets" if scope == "all" else f"AMADEUS {scope.title()} Sheets",
                ),
            )

        return AnnotationResult(
            response=(
                f"Opened sheet `{sheet.title}` in the right panel.\n"
                "Use extra text after the annotation to ask AMADEUS about this sheet, for example:\n"
                f"[sheet][{sheet.scope}][{sheet.title}] summarize the next steps"
            ),
            side_panel=context.sheet_service.build_panel_payload(
                chat_id=chat_id,
                scope=sheet.scope,
                selected_sheet_id=sheet.sheet_id,
                title=f"Sheet: {sheet.title}",
            ),
        )

    def _sheet_help(self, problem: str | None = None) -> str:
        """Return concise usage help for incomplete/unknown sheet commands."""
        prefix = f"{problem}\n\n" if problem else ""
        return (
            f"{prefix}Sheet annotation commands:\n\n"
            "* `[sheet]` - open all visible sheets in the right panel\n"
            "* `[sheet][chat]` - open current-chat sheets\n"
            "* `[sheet][global]` - open global sheets\n"
            "* `[sheet][chat][Sheet Title]` - open one chat sheet\n"
            "* `[sheet][global][Sheet Title] your question` - inject that sheet as callable context\n\n"
            "* `[sheet][create] request` - prepare a new sheet for approval\n\n"
            "Create requests are approved in the dialog; existing sheets can be edited in the right-side Sheets panel."
        )
