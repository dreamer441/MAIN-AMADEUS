"""
AMADEUS V2 - module_registry.py

Purpose:
    Store discovered and registered module metadata for AMADEUS V2 Core.

Responsibilities:
    - Register module metadata.
    - Unregister module metadata.
    - List registered modules.
    - Return module metadata by module id.

Must NOT:
    - Import module internals.
    - Execute module behavior.
    - Store submodule objects.
    - Contain feature logic.

Connected systems:
    - module_loader.py
    - core_services.py
    - router.py
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ModuleMetadata:
    """
    Public metadata describing a discovered module.

    It exists so Core can reason about modules without importing module code.
    It controls only manifest-level identity and status data.
    It must not control public API objects, submodules, storage, or feature execution.
    """

    module_id: str
    name: str
    version: str
    description: str
    path: str
    manifest_path: str
    status: str

    def to_dict(self) -> Dict[str, str]:
        """
        Input:
            None.
        Output:
            Dictionary version of module metadata.
        Side effects:
            None.
        """
        return {
            "module_id": self.module_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "path": self.path,
            "manifest_path": self.manifest_path,
            "status": self.status,
        }


class ModuleRegistry:
    """
    Registry of discovered module metadata.

    It exists to give Core one clean place to track modules.
    It controls the metadata collection used by Core and future routing.
    It must not control module internals, module execution, or submodule discovery.
    """

    def __init__(self) -> None:
        """
        Input:
            None.
        Output:
            None.
        Side effects:
            Creates an empty in-memory metadata registry.
        """
        self._modules: Dict[str, ModuleMetadata] = {}

    def register(self, metadata: ModuleMetadata) -> None:
        """
        Input:
            metadata: ModuleMetadata to register by module_id.
        Output:
            None.
        Side effects:
            Adds or replaces module metadata in memory.
        """
        self._modules[metadata.module_id] = metadata

    def unregister(self, module_id: str) -> bool:
        """
        Input:
            module_id: Module identifier to remove.
        Output:
            True if a module was removed, otherwise False.
        Side effects:
            Removes module metadata from memory when present.
        """
        if module_id not in self._modules:
            return False

        del self._modules[module_id]
        return True

    def list_modules(self) -> List[ModuleMetadata]:
        """
        Input:
            None.
        Output:
            List of registered ModuleMetadata objects sorted by module_id.
        Side effects:
            None.
        """
        return [self._modules[module_id] for module_id in sorted(self._modules)]

    def get(self, module_id: str) -> Optional[ModuleMetadata]:
        """
        Input:
            module_id: Module identifier to look up.
        Output:
            ModuleMetadata when found, otherwise None.
        Side effects:
            None.
        """
        return self._modules.get(module_id)

    def count(self) -> int:
        """
        Input:
            None.
        Output:
            Number of registered modules.
        Side effects:
            None.
        """
        return len(self._modules)
