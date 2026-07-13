"""Read-only project file reader for AMADEUS.

This module is the trustworthy filesystem boundary for AMADEUS. It uses Python's
`pathlib` to inspect the real local project folder and returns exact results that
Core, annotations, or GUI panels can display directly.

Important boundary:
- This module may read safe local project text files.
- This module may list folders and files inside documented AMADEUS modules.
- This module must never edit files.
- This module must never invent missing files.
- If a file/folder cannot be verified from disk, the caller should say so.
"""

from dataclasses import dataclass
from pathlib import Path

from project_file_reader.module_indexer import ModuleIndexer, REQUIRED_MODULE_DOCS


# Keep read access intentionally conservative. AMADEUS can inspect her own source
# and documentation text, but she should not read arbitrary binaries or private
# user data before a real permissions system exists.
READABLE_FILE_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
}

MAX_FILE_SIZE_BYTES = 2_000_000
DEFAULT_MAX_CHARACTERS = 120_000
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


class ProjectModuleNotFoundError(ValueError):
    """Raised when a requested AMADEUS module folder cannot be found."""

    def __init__(self, requested_name: str, suggestions: list[str]) -> None:
        super().__init__(requested_name)
        self.requested_name = requested_name
        self.suggestions = suggestions


class ProjectFileNotFoundError(ValueError):
    """Raised when a requested file is not present inside a verified module folder."""

    def __init__(self, requested_file: str, available_files: list[str]) -> None:
        super().__init__(requested_file)
        self.requested_file = requested_file
        self.available_files = available_files


class ProjectDirectoryNotFoundError(ValueError):
    """Raised when a requested folder is not present inside a verified module folder."""

    def __init__(self, requested_directory: str, available_paths: list[str]) -> None:
        super().__init__(requested_directory)
        self.requested_directory = requested_directory
        self.available_paths = available_paths


class UnsafeProjectFileError(ValueError):
    """Raised when a file request tries to leave the module or read an unsafe file type."""


@dataclass(frozen=True)
class ModuleFileEntry:
    """One exact file entry discovered from the local filesystem."""

    name: str
    relative_path: str
    size_bytes: int
    extension: str


@dataclass(frozen=True)
class ModuleDirectoryEntry:
    """One exact folder entry discovered inside a module."""

    name: str
    relative_path: str


@dataclass(frozen=True)
class ModuleFileListing:
    """Exact file listing for one module folder.

    This older listing object is kept because existing code uses it. New UI flows
    should prefer `ModuleDirectoryListing` because it includes folders too.
    """

    module_name: str
    files: list[ModuleFileEntry]
    recursive: bool = False

    @property
    def file_count(self) -> int:
        """Return the number of real files found on disk."""
        return len(self.files)


@dataclass(frozen=True)
class ModuleDirectoryListing:
    """Exact direct folder and file listing for a module path."""

    module_name: str
    requested_path: str
    folders: list[ModuleDirectoryEntry]
    files: list[ModuleFileEntry]

    @property
    def folder_count(self) -> int:
        """Return the number of direct folders found on disk."""
        return len(self.folders)

    @property
    def file_count(self) -> int:
        """Return the number of direct files found on disk."""
        return len(self.files)


@dataclass(frozen=True)
class ModuleFileContent:
    """Text content read from one verified project file."""

    module_name: str
    file_name: str
    relative_path: str
    content: str
    truncated: bool
    total_characters: int
    total_lines: int


@dataclass(frozen=True)
class ProjectFileContent:
    """Verified project-root file content and metadata for GUI/Core consumers."""

    relative_path: str
    file_name: str
    size_bytes: int
    extension: str
    encoding: str
    content: str
    truncated: bool
    total_characters: int
    total_lines: int


@dataclass(frozen=True)
class ProjectDirectoryListing:
    """Direct safe tree entries below a project-root-relative directory."""

    requested_path: str
    folders: list[ModuleDirectoryEntry]
    files: list[ModuleFileEntry]


@dataclass(frozen=True)
class ModuleFileLine:
    """One exact line read from a verified project file."""

    module_name: str
    file_name: str
    relative_path: str
    line_number: int
    line_text: str
    total_lines: int


@dataclass(frozen=True)
class ModuleFileLineCount:
    """Exact line count for one verified project file."""

    module_name: str
    file_name: str
    relative_path: str
    total_lines: int


@dataclass(frozen=True)
class ModuleDocumentation:
    """Read-only documentation snapshot for one AMADEUS module folder."""

    module_name: str
    readme: str
    features: str
    future_updates: str
    python_files: list[str]
    exact_files: ModuleFileListing


class ProjectFileReader:
    """Reads approved AMADEUS project files without editing or unsafe scanning."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.indexer = ModuleIndexer(self.project_root)

    def normalize_module_name(self, name: str) -> str:
        """Normalize a user-provided module name."""
        return self.indexer.normalize_module_name(name)

    def list_module_names(self) -> list[str]:
        """List available top-level module folders."""
        return self.indexer.list_module_names()

    def list_project_directory(self, requested_path: str = "") -> ProjectDirectoryListing:
        """List direct safe entries anywhere below the project root.

        This is the public tree/navigation boundary for both the Code Viewer and
        future callers. It returns metadata only and never reads file content.
        """
        directory_path = self._resolve_safe_project_directory(requested_path)
        folders: list[ModuleDirectoryEntry] = []
        files: list[ModuleFileEntry] = []
        for child in directory_path.iterdir():
            if self._is_ignored_path(child):
                continue
            if child.is_dir():
                folders.append(ModuleDirectoryEntry(child.name, child.relative_to(self.project_root).as_posix()))
            elif child.is_file():
                files.append(self._file_entry(self.project_root, child))
        folders.sort(key=lambda entry: entry.relative_path.lower())
        files.sort(key=lambda entry: entry.relative_path.lower())
        return ProjectDirectoryListing(
            requested_path=directory_path.relative_to(self.project_root).as_posix() if directory_path != self.project_root else "",
            folders=folders,
            files=files,
        )

    def read_project_file(
        self, requested_path: str, max_characters: int = DEFAULT_MAX_CHARACTERS
    ) -> ProjectFileContent:
        """Read one safe project-root-relative text file with verified metadata."""
        target_path = self._resolve_safe_project_file(requested_path)
        size_bytes = target_path.stat().st_size
        if size_bytes > MAX_FILE_SIZE_BYTES:
            raise UnsafeProjectFileError(
                f"File is too large for safe inspection ({size_bytes} bytes; limit {MAX_FILE_SIZE_BYTES} bytes)."
            )
        raw = target_path.read_bytes()
        if self._is_binary_content(raw):
            raise UnsafeProjectFileError("Binary files cannot be opened in the text Code Viewer.")
        text, encoding = self._decode_text(raw)
        truncated = len(text) > max_characters
        return ProjectFileContent(
            relative_path=target_path.relative_to(self.project_root).as_posix(),
            file_name=target_path.name,
            size_bytes=size_bytes,
            extension=target_path.suffix.lower(),
            encoding=encoding,
            content=text[:max_characters],
            truncated=truncated,
            total_characters=len(text),
            total_lines=len(text.splitlines()),
        )

    def build_project_overview(self) -> str:
        """Build compact read-only context for normal summary/explanation chat.

        This is intentionally an overview, not exact file opening. Exact file
        access belongs to `[file]` so normal prompts do not accidentally trigger
        brittle command parsing or giant code dumps.
        """
        sections = [
            "Read-only AMADEUS project module overview.",
            "This context is for summaries/explanations only. Exact file opening must use [file].",
        ]
        for module_name in self.list_module_names():
            documentation = self.read_module_documentation(module_name)
            sections.append(self._format_module_overview(documentation))

        return "\n\n".join(sections)

    def read_module_documentation(self, requested_name: str) -> ModuleDocumentation:
        """Read approved docs plus exact top-level file names for one module."""
        module_path = self._resolve_module_path_or_raise(requested_name)
        docs = {doc_name: self._read_text_file(module_path / doc_name) for doc_name in REQUIRED_MODULE_DOCS}
        exact_files = self.list_module_files(module_path.name)

        return ModuleDocumentation(
            module_name=module_path.name,
            readme=self._clean_markdown(docs["README.md"]),
            features=self._clean_markdown(docs["FEATURES.md"]),
            future_updates=self._clean_markdown(docs["FUTURE_UPDATES.md"]),
            python_files=[entry.name for entry in exact_files.files if entry.extension == ".py"],
            exact_files=exact_files,
        )

    def list_module_files(self, requested_name: str, recursive: bool = False) -> ModuleFileListing:
        """Return an exact file listing from a real module folder.

        This method lists files only for backward compatibility. Use
        `list_module_directory()` when the caller also needs subfolders.
        """
        module_path = self._resolve_module_path_or_raise(requested_name)
        pattern = "**/*" if recursive else "*"
        entries: list[ModuleFileEntry] = []

        for path in module_path.glob(pattern):
            if not path.is_file() or self._is_ignored_path(path):
                continue
            entries.append(self._file_entry(module_path, path))

        entries.sort(key=lambda entry: entry.relative_path.lower())
        return ModuleFileListing(module_name=module_path.name, files=entries, recursive=recursive)

    def list_module_directory(self, requested_module: str, requested_path: str = "") -> ModuleDirectoryListing:
        """Return direct folders and files inside one verified module path.

        `[file][annotation_module]` uses this to show the `annotations/` subfolder.
        `[file][annotation_module][annotations]` uses the same method one level
        deeper. The method is read-only and refuses paths outside the module.
        """
        module_path = self._resolve_module_path_or_raise(requested_module)
        directory_path = self._resolve_safe_directory_path(module_path, requested_path)

        folders: list[ModuleDirectoryEntry] = []
        files: list[ModuleFileEntry] = []
        for child in directory_path.iterdir():
            if self._is_ignored_path(child):
                continue
            if child.is_dir():
                folders.append(
                    ModuleDirectoryEntry(
                        name=child.name,
                        relative_path=child.relative_to(module_path).as_posix(),
                    )
                )
            elif child.is_file():
                files.append(self._file_entry(module_path, child))

        folders.sort(key=lambda entry: entry.relative_path.lower())
        files.sort(key=lambda entry: entry.relative_path.lower())
        return ModuleDirectoryListing(
            module_name=module_path.name,
            requested_path=directory_path.relative_to(module_path).as_posix()
            if directory_path != module_path
            else "",
            folders=folders,
            files=files,
        )

    def read_module_file(
        self,
        requested_module: str,
        requested_file: str,
        max_characters: int = 120_000,
    ) -> ModuleFileContent:
        """Read one exact safe text file from inside a module folder.

        The returned text is copied from disk by Python, not produced by the LLM.
        We deliberately do not call `.rstrip()` because losing the final character
        or newline makes exact code viewing untrustworthy.
        """
        module_path, target_path = self._resolve_safe_file_path(requested_module, requested_file)

        project_content = self.read_project_file(
            target_path.relative_to(self.project_root).as_posix(), max_characters=max_characters
        )
        relative_path = target_path.relative_to(module_path).as_posix()
        return ModuleFileContent(
            module_name=module_path.name,
            file_name=target_path.name,
            relative_path=relative_path,
            content=project_content.content,
            truncated=project_content.truncated,
            total_characters=project_content.total_characters,
            total_lines=project_content.total_lines,
        )

    def read_module_file_line(self, requested_module: str, requested_file: str, line_number: int) -> ModuleFileLine:
        """Return one exact line from one verified project file."""
        module_path, target_path = self._resolve_safe_file_path(requested_module, requested_file)
        lines = self._read_file_lines(target_path)
        total_lines = len(lines)

        if line_number < 1 or line_number > total_lines:
            raise ProjectFileNotFoundError(
                f"{requested_file} line {line_number}",
                [f"{target_path.name} has {total_lines} lines"],
            )

        relative_path = target_path.relative_to(module_path).as_posix()
        return ModuleFileLine(
            module_name=module_path.name,
            file_name=target_path.name,
            relative_path=relative_path,
            line_number=line_number,
            line_text=lines[line_number - 1],
            total_lines=total_lines,
        )

    def count_module_file_lines(self, requested_module: str, requested_file: str) -> ModuleFileLineCount:
        """Return the exact line count for one verified project file."""
        module_path, target_path = self._resolve_safe_file_path(requested_module, requested_file)
        lines = self._read_file_lines(target_path)
        relative_path = target_path.relative_to(module_path).as_posix()
        return ModuleFileLineCount(
            module_name=module_path.name,
            file_name=target_path.name,
            relative_path=relative_path,
            total_lines=len(lines),
        )

    def path_is_directory(self, requested_module: str, requested_path: str) -> bool:
        """Return True when a relative module path resolves to a directory."""
        module_path = self._resolve_module_path_or_raise(requested_module)
        try:
            return self._resolve_safe_directory_path(module_path, requested_path).is_dir()
        except ProjectDirectoryNotFoundError:
            return False

    def _resolve_safe_file_path(self, requested_module: str, requested_file: str) -> tuple[Path, Path]:
        """Resolve and validate a requested module file once for all read operations."""
        module_path = self._resolve_module_path_or_raise(requested_module)
        clean_requested_file = self._clean_relative_path(requested_file)
        if not clean_requested_file:
            raise ProjectFileNotFoundError(requested_file, self._available_file_paths(module_path))

        target_path = (module_path / clean_requested_file).resolve()
        self._validate_inside_module(module_path, target_path)
        if self._is_ignored_path(target_path):
            raise UnsafeProjectFileError("Requested path is inside an ignored project directory.")

        if not target_path.is_file():
            raise ProjectFileNotFoundError(requested_file, self._available_file_paths(module_path))
        if target_path.suffix.lower() not in READABLE_FILE_EXTENSIONS:
            raise UnsafeProjectFileError(
                f"Unsupported file type for read-only text inspection: {target_path.suffix or '[no extension]'}"
            )

        return module_path, target_path

    def _resolve_safe_project_file(self, requested_path: str) -> Path:
        """Resolve one readable file under the project root without traversal."""
        clean_requested_path = self._clean_relative_path(requested_path)
        if not clean_requested_path:
            raise ProjectFileNotFoundError(requested_path, [])
        target_path = (self.project_root / clean_requested_path).resolve()
        self._validate_inside_project(target_path)
        if self._is_ignored_path(target_path):
            raise UnsafeProjectFileError("Requested path is inside an ignored project directory.")
        if not target_path.is_file():
            raise ProjectFileNotFoundError(requested_path, [])
        if target_path.suffix.lower() not in READABLE_FILE_EXTENSIONS:
            raise UnsafeProjectFileError(
                f"Unsupported file type for read-only text inspection: {target_path.suffix or '[no extension]'}"
            )
        return target_path

    def _resolve_safe_project_directory(self, requested_path: str) -> Path:
        """Resolve one navigable directory under the project root without traversal."""
        clean_requested_path = self._clean_relative_path(requested_path)
        directory_path = (self.project_root / clean_requested_path).resolve() if clean_requested_path else self.project_root
        self._validate_inside_project(directory_path)
        if self._is_ignored_path(directory_path):
            raise UnsafeProjectFileError("Requested path is inside an ignored project directory.")
        if not directory_path.is_dir():
            raise ProjectDirectoryNotFoundError(requested_path, [])
        return directory_path

    def _resolve_safe_directory_path(self, module_path: Path, requested_path: str) -> Path:
        """Resolve and validate a directory path inside one module."""
        clean_requested_path = self._clean_relative_path(requested_path)
        directory_path = (module_path / clean_requested_path).resolve() if clean_requested_path else module_path
        self._validate_inside_module(module_path, directory_path)

        if not directory_path.is_dir():
            raise ProjectDirectoryNotFoundError(requested_path, self._available_directory_paths(module_path))

        return directory_path

    def _validate_inside_module(self, module_path: Path, target_path: Path) -> None:
        """Prevent path traversal outside the selected module folder."""
        try:
            target_path.relative_to(module_path.resolve())
        except ValueError as exc:
            raise UnsafeProjectFileError("Requested path is outside the module folder.") from exc

    def _validate_inside_project(self, target_path: Path) -> None:
        """Prevent root-relative tree operations from escaping the project root."""
        try:
            target_path.relative_to(self.project_root)
        except ValueError as exc:
            raise UnsafeProjectFileError("Requested path is outside the project root.") from exc

    def _read_file_lines(self, target_path: Path) -> list[str]:
        """Read text as exact logical lines without trailing newline characters."""
        content = self.read_project_file(target_path.relative_to(self.project_root).as_posix())
        return content.content.splitlines()

    def _decode_text(self, raw: bytes) -> tuple[str, str]:
        """Decode verified text using explicit fallbacks instead of replacement bytes."""
        for encoding in TEXT_ENCODINGS:
            try:
                return raw.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
        raise UnsafeProjectFileError("File encoding is not supported for safe text inspection.")

    def _is_binary_content(self, raw: bytes) -> bool:
        """Reject NUL/control-heavy data before any permissive text fallback can mask it."""
        if b"\x00" in raw:
            return True
        if not raw:
            return False
        controls = sum(byte < 32 and byte not in {9, 10, 12, 13} for byte in raw)
        return controls / len(raw) > 0.05

    def _resolve_module_path_or_raise(self, requested_name: str) -> Path:
        """Resolve a module path or raise a precise no-guessing error."""
        module_path = self.indexer.resolve_module_path(requested_name)
        if module_path is None:
            suggestions = self.indexer.suggest_modules(requested_name)
            raise ProjectModuleNotFoundError(requested_name, suggestions)
        return module_path

    def _available_file_paths(self, module_path: Path) -> list[str]:
        """Return exact recursive file paths for a module, used in error messages."""
        return [entry.relative_path for entry in self.list_module_files(module_path.name, recursive=True).files]

    def _available_directory_paths(self, module_path: Path) -> list[str]:
        """Return exact recursive directory paths for a module, used in error messages."""
        paths: list[str] = []
        for path in module_path.glob("**/*"):
            if path.is_dir() and not self._is_ignored_path(path):
                paths.append(path.relative_to(module_path).as_posix())
        return sorted(paths)

    def _clean_relative_path(self, requested_path: str) -> str:
        """Clean a user-supplied relative module path without normalizing away dots."""
        return requested_path.strip().strip("`").strip().strip('"').strip("'").replace("\\", "/")

    def _file_entry(self, module_path: Path, path: Path) -> ModuleFileEntry:
        """Build one reusable file entry from a real path."""
        return ModuleFileEntry(
            name=path.name,
            relative_path=path.relative_to(module_path).as_posix(),
            size_bytes=path.stat().st_size,
            extension=path.suffix.lower(),
        )

    def _is_ignored_path(self, path: Path) -> bool:
        """Skip cache/build/private implementation clutter in file listings."""
        ignored_parts = {
            "__pycache__", ".git", ".idea", ".venv", ".vscode", "venv",
            "node_modules", "build", "dist", "data",
        }
        return any(part in ignored_parts for part in path.parts)

    def _read_text_file(self, path: Path) -> str:
        """Read one required module documentation file."""
        return self.read_project_file(path.relative_to(self.project_root).as_posix()).content.strip()

    def _clean_markdown(self, content: str) -> str:
        """Remove one leading markdown title so annotation output is easier to read."""
        lines = content.splitlines()
        if lines and lines[0].startswith("#"):
            lines = lines[1:]
        return "\n".join(lines).strip() or "No content found."

    def _format_module_overview(self, documentation: ModuleDocumentation) -> str:
        """Format one module for safe LLM summary context without opening code."""
        file_names = ", ".join(entry.relative_path for entry in documentation.exact_files.files)
        if not file_names:
            file_names = "No direct files found."

        return (
            f"Module: {documentation.module_name}\n"
            f"Description: {documentation.readme}\n"
            f"Current features: {documentation.features}\n"
            f"Future updates: {documentation.future_updates}\n"
            f"Direct files ({documentation.exact_files.file_count}): {file_names}"
        )
