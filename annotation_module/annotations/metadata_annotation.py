"""Read-only `[metadata]` access to verified module documentation."""

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import AnnotationParser, ParsedAnnotation
from annotation_module.annotation_result import AnnotationResult
from project_file_reader import ModuleMetadataDocument, ProjectModuleNotFoundError


class MetadataAnnotation:
    """Render fixed module metadata documents in the Memory side panel."""

    _DOCUMENT_KINDS = {"features", "future", "both"}

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> str | AnnotationResult:
        """Accept only all-module or one verified-module metadata commands."""
        arguments = [AnnotationParser().normalize_token(argument) for argument in annotation.arguments]
        kind = arguments[-1] if arguments else ""
        if kind not in self._DOCUMENT_KINDS:
            return self._usage()
        if arguments == ["all", kind]:
            return self._read(context, module_name="", document_kind=kind)
        if len(arguments) == 3 and arguments[0] == "module" and arguments[2] == kind:
            return self._read(context, module_name=annotation.arguments[1], document_kind=kind)
        return self._usage()

    def _read(self, context: AnnotationContext, module_name: str, document_kind: str) -> str | AnnotationResult:
        """Read fixed metadata files and preserve their literal contents in one payload."""
        try:
            result = context.file_reader.read_module_metadata(
                module_name,
                document_kind,
                format_payload=self._format_content,
            )
        except ProjectModuleNotFoundError as error:
            return self._module_not_found_response(error)

        content = self._format_content(result.documents, result.missing, result.truncated)
        return AnnotationResult(
            response=f"Opened {len(result.documents)} module metadata document(s) in the Memory panel.",
            side_panel={
                "type": "memory",
                "title": "Module Metadata",
                "content": content,
                "metadata": {
                    "include_chat_context": False,
                    "document_count": len(result.documents),
                    "missing_paths": list(result.missing),
                    "truncated": result.truncated,
                },
            },
        )

    @staticmethod
    def _format_content(
        documents: tuple[ModuleMetadataDocument, ...], missing: tuple[str, ...], truncated: bool
    ) -> str:
        """Format the exact Memory payload used by the reader's aggregate bound."""
        sections = [
            f"=== {document.module_name}/{document.file_name} ===\n{document.content}"
            for document in documents
        ]
        if missing:
            sections.append("Missing metadata files:\n" + "\n".join(f"- {path}" for path in missing))
        if truncated:
            sections.append("Metadata output was truncated for safety.")
        if not sections:
            sections.append("No metadata documents were available for the selected modules.")
        return "\n\n".join(sections)

    def _module_not_found_response(self, error: ProjectModuleNotFoundError) -> str:
        """Provide only the reader's verified closest module names."""
        if error.suggestions:
            suggestions = "\n".join(f"* [metadata][module][{name}]" for name in error.suggestions)
            return f"Module not found: `{error.requested_name}`\n\nClosest available modules:\n{suggestions}"
        return f"Module not found: `{error.requested_name}`\n\nNo close module matches were found."

    def _usage(self) -> str:
        """Return the complete fixed grammar without exposing file paths."""
        return (
            "Module metadata usage:\n\n"
            "* `[metadata][all][features|future|both]`\n"
            "* `[metadata][module][verified_module][features|future|both]`"
        )
