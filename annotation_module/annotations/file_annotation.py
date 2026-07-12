"""Read-only `[file]` annotation handler.

The file annotation is the exact file-access path for AMADEUS. Normal user chat
can summarize project modules, but exact file/folder inspection should come here
so it is deterministic and does not depend on LLM guessing.

Current behavior:
- `[file]` lists available modules.
- `[file][amadeus_core]` lists direct folders/files in that module.
- `[file][annotation_module][annotations]` lists a subfolder.
- `[file][amadeus_core][core.py]` opens exact file content in the right-side Code Viewer.
"""

from annotation_module.annotation_context import AnnotationContext
from annotation_module.annotation_parser import ParsedAnnotation
from annotation_module.annotation_result import AnnotationResult
from project_file_reader import (
    ModuleDirectoryListing,
    ModuleFileContent,
    ProjectDirectoryNotFoundError,
    ProjectFileNotFoundError,
    ProjectModuleNotFoundError,
    UnsafeProjectFileError,
)


class FileAnnotation:
    """Handles `[file]` annotations through read-only project file access."""

    def handle(self, annotation: ParsedAnnotation, context: AnnotationContext) -> str | AnnotationResult:
        """Return module/folder listings or open exact file content in Code Viewer.

        The handler receives already-parsed bracket parts. It does not ask the LLM
        to interpret a path. This is why `[file][module][file.py]` is more reliable
        than a normal sentence like “open this file.”
        """
        if not annotation.arguments:
            return self._available_modules_response(context)

        requested_module = annotation.arguments[0]
        relative_path = self._join_path_parts(annotation.arguments[1:])

        try:
            # No path after the module means “show me what is inside this module.”
            if not relative_path:
                listing = context.file_reader.list_module_directory(requested_module)
                return self._directory_listing_response(listing)

            # If the bracket path points to a folder, show its direct contents so
            # Dato can keep stepping deeper through suggestions.
            if context.file_reader.path_is_directory(requested_module, relative_path):
                listing = context.file_reader.list_module_directory(requested_module, relative_path)
                return self._directory_listing_response(listing)

            # Otherwise the path must be a safe readable text file. The content is
            # sent to the GUI side panel, not dumped into main chat history.
            file_content = context.file_reader.read_module_file(requested_module, relative_path)
            return self._code_viewer_response(file_content)

        except ProjectModuleNotFoundError as error:
            return self._module_not_found_response(error)
        except ProjectDirectoryNotFoundError as error:
            return self._directory_not_found_response(requested_module, error)
        except ProjectFileNotFoundError as error:
            return self._file_not_found_response(requested_module, error)
        except UnsafeProjectFileError as error:
            return f"I cannot read that path safely: {error}"

    def _available_modules_response(self, context: AnnotationContext) -> str:
        """Show safe module options for the user to choose from."""
        modules = context.file_reader.list_module_names()
        if not modules:
            return "No readable AMADEUS module folders were found."

        module_lines = "\n".join(f"* [file][{module_name}]" for module_name in modules)
        return (
            "Available AMADEUS modules:\n\n"
            f"{module_lines}\n\n"
            "Select a module to list its folders/files, for example:\n"
            "[file][amadeus_core]"
        )

    def _directory_listing_response(self, listing: ModuleDirectoryListing) -> str:
        """Format direct folders and files from a verified module path."""
        location = listing.module_name if not listing.requested_path else f"{listing.module_name}/{listing.requested_path}"
        lines = [
            f"Module path: `{location}`",
            "",
            f"Exact direct folders found: {listing.folder_count}",
        ]

        if listing.folders:
            for index, folder in enumerate(listing.folders, start=1):
                lines.append(f"{index}. `{folder.relative_path}/`")
        else:
            lines.append("No direct folders found.")

        lines.extend(["", f"Exact direct files found: {listing.file_count}"])
        if listing.files:
            for index, file_entry in enumerate(listing.files, start=1):
                lines.append(f"{index}. `{file_entry.relative_path}`")
        else:
            lines.append("No direct files found.")

        lines.extend(
            [
                "",
                "This list is based on the real local filesystem result. I did not include guessed folders/files.",
            ]
        )
        return "\n".join(lines)

    def _code_viewer_response(self, content: ModuleFileContent) -> AnnotationResult:
        """Send exact file content to the Code Viewer instead of polluting chat."""
        title = f"{content.module_name}/{content.relative_path}"
        truncated_note = " Output was truncated for safety." if content.truncated else ""
        response = (
            f"Opened `{title}` in Code Viewer.\n"
            f"Lines: {content.total_lines}\n"
            f"Characters: {len(content.content)} of {content.total_characters}.{truncated_note}\n\n"
            "The full visible file text is in the right panel, not in main chat."
        )
        return AnnotationResult(
            response=response,
            side_panel={
                "type": "code",
                "title": title,
                "content": content.content,
                "metadata": {
                    "module": content.module_name,
                    "relative_path": content.relative_path,
                    "lines": content.total_lines,
                    "characters_read": len(content.content),
                    "total_characters": content.total_characters,
                    "truncated": content.truncated,
                },
            },
        )

    def _module_not_found_response(self, error: ProjectModuleNotFoundError) -> str:
        """Return a helpful read-only error for unknown module names."""
        if error.suggestions:
            suggestions = "\n".join(f"* [file][{module_name}]" for module_name in error.suggestions)
            return (
                f"Module not found: `{error.requested_name}`\n\n"
                "Closest available modules:\n"
                f"{suggestions}"
            )
        return f"Module not found: `{error.requested_name}`\n\nNo close module matches were found."

    def _directory_not_found_response(self, requested_module: str, error: ProjectDirectoryNotFoundError) -> str:
        """Return exact available folders when a requested folder does not exist."""
        available = "\n".join(f"* `{path}/`" for path in error.available_paths) or "No folders found."
        return (
            f"Folder not found in `{requested_module}`: `{error.requested_directory}`\n\n"
            "I will not guess the folder name. Exact folders I can verify are:\n"
            f"{available}"
        )

    def _file_not_found_response(self, requested_module: str, error: ProjectFileNotFoundError) -> str:
        """Return exact available files when a requested file does not exist."""
        available = "\n".join(f"* `{file_name}`" for file_name in error.available_files) or "No files found."
        return (
            f"File not found in `{requested_module}`: `{error.requested_file}`\n\n"
            "I will not guess the file name. Exact files I can verify are:\n"
            f"{available}"
        )

    def _join_path_parts(self, path_parts: list[str]) -> str:
        """Convert bracket path parts into one relative module path.

        `[file][annotation_module][annotations][file_annotation.py]` becomes
        `annotations/file_annotation.py`. Dots stay intact because the parser now
        preserves raw annotation arguments.
        """
        clean_parts = [part.strip().strip("`").strip("/") for part in path_parts if part.strip()]
        return "/".join(clean_parts)
