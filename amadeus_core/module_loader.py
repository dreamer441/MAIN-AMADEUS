"""
AMADEUS V2 - module_loader.py

Purpose:
    Discover module folders and read module_manifest.json metadata.

Responsibilities:
    - Scan the modules/ folder.
    - Detect module_manifest.json files.
    - Validate minimal manifest metadata.
    - Register discovered metadata with ModuleRegistry.

Must NOT:
    - Import module internals.
    - Execute public_api.py or module entry objects yet.
    - Load submodules directly.
    - Implement feature logic.

Connected systems:
    - global_config.py
    - logger.py
    - module_registry.py
    - core_controller.py
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from amadeus_core.global_config import GlobalConfig
from amadeus_core.logger import CoreLogger
from amadeus_core.module_registry import ModuleMetadata, ModuleRegistry


class ModuleLoader:
    """
    Manifest-only module discovery system.

    It exists so Core can find modules without knowing their internal files.
    It controls filesystem scanning and manifest metadata parsing.
    It must not control module execution, submodule loading, feature logic, or API imports.
    """

    REQUIRED_MANIFEST_FIELDS = ("id", "name", "version")

    def __init__(
        self,
        config: GlobalConfig,
        logger: CoreLogger,
        module_registry: ModuleRegistry,
    ) -> None:
        """
        Input:
            config: GlobalConfig containing modules_path.
            logger: CoreLogger for discovery messages.
            module_registry: Registry that receives discovered metadata.
        Output:
            None.
        Side effects:
            Stores references to Core services; does not scan yet.
        """
        self.config = config
        self.logger = logger
        self.module_registry = module_registry

    def discover_modules(self) -> List[ModuleMetadata]:
        """
        Input:
            None.
        Output:
            List of valid ModuleMetadata objects discovered from manifests.
        Side effects:
            Reads module_manifest.json files and registers valid metadata.
        """
        modules_path = self.config.modules_path
        modules_path.mkdir(parents=True, exist_ok=True)

        self.logger.info("Scanning modules folder: %s", modules_path)

        module_folders = sorted(path for path in modules_path.iterdir() if path.is_dir())
        if not module_folders:
            self.logger.info("No module folders found. No modules are installed yet.")
            return []

        discovered_modules: List[ModuleMetadata] = []
        for module_folder in module_folders:
            metadata = self._read_manifest(module_folder)
            if metadata is None:
                continue

            self.module_registry.register(metadata)
            discovered_modules.append(metadata)
            self.logger.info("Registered module metadata: %s", metadata.module_id)

        if not discovered_modules:
            self.logger.info("No valid module manifests found. No modules are installed yet.")

        return discovered_modules

    def _read_manifest(self, module_folder: Path) -> Optional[ModuleMetadata]:
        """
        Input:
            module_folder: Candidate module folder inside modules/.
        Output:
            ModuleMetadata when module_manifest.json is valid, otherwise None.
        Side effects:
            Reads a JSON manifest file and logs invalid metadata.
        """
        manifest_path = module_folder / "module_manifest.json"
        if not manifest_path.exists():
            self.logger.warning(
                "Skipping module folder without module_manifest.json: %s",
                module_folder.name,
            )
            return None

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            self.logger.warning(
                "Skipping module folder with invalid JSON manifest: %s (%s)",
                module_folder.name,
                error,
            )
            return None

        if not isinstance(manifest, dict):
            self.logger.warning(
                "Skipping module folder with non-object manifest: %s",
                module_folder.name,
            )
            return None

        missing_fields = self._missing_required_fields(manifest)
        if missing_fields:
            self.logger.warning(
                "Skipping module folder with incomplete manifest: %s missing %s",
                module_folder.name,
                ", ".join(missing_fields),
            )
            return None

        return ModuleMetadata(
            module_id=str(manifest["id"]),
            name=str(manifest["name"]),
            version=str(manifest["version"]),
            description=str(manifest.get("description", "")),
            path=str(module_folder),
            manifest_path=str(manifest_path),
            status="discovered",
        )

    def _missing_required_fields(self, manifest: Dict[str, Any]) -> List[str]:
        """
        Input:
            manifest: Parsed manifest dictionary.
        Output:
            List of required fields that are missing or blank.
        Side effects:
            None.
        """
        # Core requires only identity metadata at this stage. API loading comes later.
        return [
            field
            for field in self.REQUIRED_MANIFEST_FIELDS
            if field not in manifest or str(manifest[field]).strip() == ""
        ]
