from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation
from project_file_reader import ModuleDocumentation, ProjectModuleNotFoundError


class FileAnnotation:
    """Handles `[file]` annotations through read-only project documentation access."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> str:
        """Return module options or read one requested module's documentation."""
        if not annotation.arguments:
            return self._available_modules_response(context)

        requested_module = annotation.arguments[0]
        try:
            documentation = context.file_reader.read_module_documentation(requested_module)
        except ProjectModuleNotFoundError as error:
            return self._module_not_found_response(error)

        return self._module_documentation_response(documentation)

    def _available_modules_response(self, context: AnnotationContext) -> str:
        """Show safe module options for the user to choose from."""
        modules = context.file_reader.list_module_names()
        if not modules:
            return "No readable AMADEUS module folders were found."

        module_lines = "\n".join(f"* [file][{module_name}]" for module_name in modules)
        return (
            "Available project modules:\n\n"
            f"{module_lines}\n\n"
            "Use one of these to ask AMADEUS to read a specific module."
        )

    def _module_documentation_response(self, documentation: ModuleDocumentation) -> str:
        """Format one module's approved documentation for display."""
        python_files = self._format_python_files(documentation.python_files)
        return (
            f"Module: {documentation.module_name}\n\n"
            "Description:\n\n"
            f"{documentation.readme}\n\n"
            "Current features:\n\n"
            f"{documentation.features}\n\n"
            "Future updates:\n\n"
            f"{documentation.future_updates}\n\n"
            "Important code files:\n"
            f"{python_files}"
        )

    def _module_not_found_response(self, error: ProjectModuleNotFoundError) -> str:
        """Return a helpful read-only error for unknown module names."""
        if error.suggestions:
            suggestions = "\n".join(f"* [file][{module_name}]" for module_name in error.suggestions)
            return (
                f"Module not found: {error.requested_name}\n\n"
                "Closest available modules:\n"
                f"{suggestions}"
            )

        return f"Module not found: {error.requested_name}\n\nNo close module matches were found."

    def _format_python_files(self, python_files: list[str]) -> str:
        """Format top-level Python files without reading their contents."""
        if not python_files:
            return "No top-level Python files found."

        return "\n".join(f"* {file_name}" for file_name in python_files)
