import re
from pathlib import Path


IGNORED_FOLDER_NAMES = {
    ".git",
    ".idea",
    ".venv",
    ".vscode",
    "__pycache__",
    "venv",
}

REQUIRED_MODULE_DOCS = ("README.md", "FEATURES.md", "FUTURE_UPDATES.md")


class ModuleIndexer:
    """Indexes top-level AMADEUS module folders without scanning deeply."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def normalize_module_name(self, name: str) -> str:
        """Normalize user module names like 'Amadeus Core' into 'amadeus_core'."""
        normalized = name.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")

    def list_module_names(self) -> list[str]:
        """Return top-level folders that look like documented AMADEUS modules."""
        modules: list[str] = []
        for path in self.project_root.iterdir():
            if not self._is_readable_module_folder(path):
                continue
            modules.append(path.name)

        return sorted(modules)

    def resolve_module_path(self, requested_name: str) -> Path | None:
        """Resolve a user-provided module name to a real top-level module path."""
        normalized_request = self.normalize_module_name(requested_name)
        for module_name in self.list_module_names():
            if self.normalize_module_name(module_name) == normalized_request:
                return self.project_root / module_name

        return None

    def suggest_modules(self, requested_name: str, limit: int = 3) -> list[str]:
        """Suggest closest module names without reading module internals."""
        requested = self.normalize_module_name(requested_name)
        modules = self.list_module_names()

        scored: list[tuple[int, str]] = []
        for module_name in modules:
            normalized_module = self.normalize_module_name(module_name)
            score = self._similarity_score(requested, normalized_module)
            if score > 0:
                scored.append((score, module_name))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [module_name for _, module_name in scored[:limit]]

    def _is_readable_module_folder(self, path: Path) -> bool:
        """Return True for safe top-level module folders with required docs."""
        if not path.is_dir():
            return False
        if path.name.startswith(".") or path.name in IGNORED_FOLDER_NAMES:
            return False

        # A folder is considered a module only when it owns the required module docs.
        return all((path / doc_name).is_file() for doc_name in REQUIRED_MODULE_DOCS)

    def _similarity_score(self, requested: str, module_name: str) -> int:
        """Score simple name similarity for helpful missing-module suggestions."""
        if not requested:
            return 0
        if requested == module_name:
            return 100
        if requested in module_name or module_name in requested:
            return 80

        requested_parts = set(requested.split("_"))
        module_parts = set(module_name.split("_"))
        return len(requested_parts & module_parts) * 10
