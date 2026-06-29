"""
AMADEUS V2 - router.py

Purpose:
    Provide a minimal Core command router placeholder.

Responsibilities:
    - Route basic Core-only commands.
    - Support core.status.
    - Support core.modules.
    - Use PermissionGuard before returning command data.

Must NOT:
    - Route to real modules yet.
    - Import module public_api.py files yet.
    - Execute feature logic.
    - Bypass PermissionGuard for risky actions.

Connected systems:
    - core_services.py
    - module_registry.py
    - permission_guard.py
"""

from typing import Any, Dict

from amadeus_core.core_services import CoreServices
from amadeus_core.permission_guard import ActionCategory


class CoreRouter:
    """
    Minimal command router for Core commands.

    It exists so command routing has a clear home from the first version.
    It controls only Core-owned commands right now.
    It must not control real modules, submodules, chat, storage, UI, or LLM calls.
    """

    def __init__(self, core_services: CoreServices) -> None:
        """
        Input:
            core_services: Safe shared CoreServices bundle.
        Output:
            None.
        Side effects:
            Stores CoreServices for later command routing.
        """
        self.core_services = core_services

    def route(self, command: str) -> Dict[str, Any]:
        """
        Input:
            command: Command string such as core.status or core.modules.
        Output:
            Dictionary response for the command.
        Side effects:
            Performs read-only permission checks before returning Core data.
        """
        command = command.strip()

        if command == "core.status":
            return self._core_status()

        if command == "core.modules":
            return self._core_modules()

        return {
            "ok": False,
            "error": f"Unknown Core command: {command}",
        }

    def _core_status(self) -> Dict[str, Any]:
        """
        Input:
            None.
        Output:
            Dictionary response containing Core status.
        Side effects:
            Performs a read-only permission check.
        """
        decision = self.core_services.permission_guard.require(
            ActionCategory.READ_ONLY,
            action_name="Read Core status",
        )
        return {
            "ok": True,
            "permission": decision.reason,
            "status": self.core_services.status(),
        }

    def _core_modules(self) -> Dict[str, Any]:
        """
        Input:
            None.
        Output:
            Dictionary response containing registered module metadata.
        Side effects:
            Performs a read-only permission check.
        """
        decision = self.core_services.permission_guard.require(
            ActionCategory.READ_ONLY,
            action_name="List registered modules",
        )
        modules = [
            metadata.to_dict()
            for metadata in self.core_services.module_registry.list_modules()
        ]
        return {
            "ok": True,
            "permission": decision.reason,
            "modules": modules,
        }
