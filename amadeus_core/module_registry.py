class ModuleRegistry:
    """Stores module objects by name so Core can route without owning module logic."""

    def __init__(self) -> None:
        # The registry stores module entry objects only. It does not execute module behavior.
        self._modules: dict[str, object] = {}

    def register(self, name: str, module: object) -> None:
        """Register a module object under a stable module name."""
        clean_name = name.strip().lower()
        if not clean_name:
            raise ValueError("Module name cannot be empty.")

        self._modules[clean_name] = module

    def get(self, name: str) -> object | None:
        """Return a registered module object, or None if it is missing."""
        return self._modules.get(name.strip().lower())

    def list_modules(self) -> list[str]:
        """Return registered module names in predictable order."""
        return sorted(self._modules)
