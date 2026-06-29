from dataclasses import dataclass
from pathlib import Path

from project_file_reader.module_indexer import ModuleIndexer, REQUIRED_MODULE_DOCS


class ProjectModuleNotFoundError(ValueError):
    """Raised when a requested AMADEUS module folder cannot be found."""

    def __init__(self, requested_name: str, suggestions: list[str]) -> None:
        super().__init__(requested_name)
        self.requested_name = requested_name
        self.suggestions = suggestions


@dataclass(frozen=True)
class ModuleDocumentation:
    """Read-only documentation snapshot for one AMADEUS module folder."""

    module_name: str
    readme: str
    features: str
    future_updates: str
    python_files: list[str]


class ProjectFileReader:
    """Reads allowed AMADEUS project files without editing or deep scanning."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.indexer = ModuleIndexer(self.project_root)

    def normalize_module_name(self, name: str) -> str:
        """Normalize a user-provided module name."""
        return self.indexer.normalize_module_name(name)

    def list_module_names(self) -> list[str]:
        """List available top-level module folders."""
        return self.indexer.list_module_names()

    def build_project_overview(self) -> str:
        """Build compact read-only context about documented project modules."""
        sections = ["Read-only AMADEUS project module overview:"]
        for module_name in self.list_module_names():
            documentation = self.read_module_documentation(module_name)
            sections.append(self._format_module_overview(documentation))

        return "\n\n".join(sections)

    def read_module_documentation(self, requested_name: str) -> ModuleDocumentation:
        """Read the approved docs and top-level Python file names for one module."""
        module_path = self.indexer.resolve_module_path(requested_name)
        if module_path is None:
            suggestions = self.indexer.suggest_modules(requested_name)
            raise ProjectModuleNotFoundError(requested_name, suggestions)

        # File annotation v1 reads only these documentation files first.
        docs = {
            doc_name: self._read_text_file(module_path / doc_name)
            for doc_name in REQUIRED_MODULE_DOCS
        }

        return ModuleDocumentation(
            module_name=module_path.name,
            readme=self._clean_markdown(docs["README.md"]),
            features=self._clean_markdown(docs["FEATURES.md"]),
            future_updates=self._clean_markdown(docs["FUTURE_UPDATES.md"]),
            python_files=self._list_top_level_python_files(module_path),
        )

    def _read_text_file(self, path: Path) -> str:
        """Read one allowed text file from a module folder."""
        return path.read_text(encoding="utf-8").strip()

    def _list_top_level_python_files(self, module_path: Path) -> list[str]:
        """List Python files directly inside one module folder only."""
        return sorted(path.name for path in module_path.glob("*.py") if path.is_file())

    def _clean_markdown(self, content: str) -> str:
        """Remove one leading markdown title so annotation output is easier to read."""
        lines = content.splitlines()
        if lines and lines[0].startswith("#"):
            lines = lines[1:]
        return "\n".join(lines).strip() or "No content found."

    def _format_module_overview(self, documentation: ModuleDocumentation) -> str:
        """Format one module for safe LLM context without deep code inspection."""
        python_files = ", ".join(documentation.python_files) or "No top-level Python files."
        return (
            f"Module: {documentation.module_name}\n"
            f"Description: {documentation.readme}\n"
            f"Current features: {documentation.features}\n"
            f"Future updates: {documentation.future_updates}\n"
            f"Top-level Python files: {python_files}"
        )
