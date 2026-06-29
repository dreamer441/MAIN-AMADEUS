"""
AMADEUS V2 - core_services.py

Purpose:
    Define the safe shared CoreServices object that future modules will receive.

Responsibilities:
    - Bundle approved Core services in one explicit object.
    - Provide modules a safe route back to Core later.
    - Keep service access narrow and visible.

Must NOT:
    - Expose private Core internals.
    - Execute module feature logic.
    - Store application data or long-term memory.

Connected systems:
    - global_config.py
    - logger.py
    - permission_guard.py
    - module_registry.py
"""

from dataclasses import dataclass
from typing import Any, Dict

from amadeus_core.global_config import GlobalConfig
from amadeus_core.logger import CoreLogger
from amadeus_core.module_registry import ModuleRegistry
from amadeus_core.permission_guard import PermissionGuard


@dataclass(frozen=True)
class CoreServices:
    """
    Safe service bundle shared by Core and future modules.

    It exists so modules do not reach into Core internals directly.
    It controls access to approved shared objects: config, logger, permissions, and registry.
    It must not control module execution, submodule internals, storage, UI, or LLM behavior.
    """

    config: GlobalConfig
    logger: CoreLogger
    permission_guard: PermissionGuard
    module_registry: ModuleRegistry

    def status(self) -> Dict[str, Any]:
        """
        Input:
            None.
        Output:
            Dictionary describing basic Core status.
        Side effects:
            None.
        """
        return {
            "app_name": self.config.app_name,
            "version": self.config.version,
            "project_root": str(self.config.project_root),
            "modules_discovered": self.module_registry.count(),
        }
