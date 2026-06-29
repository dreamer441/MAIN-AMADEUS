"""
AMADEUS V2 - core_controller.py

Purpose:
    Coordinate the startup sequence for the AMADEUS V2 Core layer.

Responsibilities:
    - Load global configuration.
    - Start logging.
    - Create the PermissionGuard.
    - Create the ModuleRegistry.
    - Create the ModuleLoader.
    - Discover module manifests without importing module internals.
    - Create CoreServices.
    - Create the CoreRouter placeholder.

Must NOT:
    - Implement chat, reasoning, storage, RAG, web, coding, drift, UI, or module logic.
    - Import random files from modules or submodules.
    - Execute module behavior directly.

Connected systems:
    - global_config.py
    - logger.py
    - permission_guard.py
    - module_registry.py
    - module_loader.py
    - core_services.py
    - router.py
"""

from pathlib import Path
from typing import Optional

from amadeus_core.core_services import CoreServices
from amadeus_core.global_config import GlobalConfig
from amadeus_core.logger import CoreLogger
from amadeus_core.module_loader import ModuleLoader
from amadeus_core.module_registry import ModuleRegistry
from amadeus_core.permission_guard import PermissionGuard
from amadeus_core.router import CoreRouter


class CoreController:
    """
    Main coordinator for the AMADEUS Core startup sequence.

    It exists to keep startup order explicit and centralized.
    It controls Core object creation and wiring.
    It must not control module internals, feature execution, UI, LLM calls, or storage behavior.
    """

    def __init__(self, project_root: Optional[Path] = None) -> None:
        """
        Input:
            project_root: Optional project root override.
        Output:
            None.
        Side effects:
            Stores startup state placeholders; does not create runtime systems yet.
        """
        self.project_root = project_root
        self.config: Optional[GlobalConfig] = None
        self.logger: Optional[CoreLogger] = None
        self.permission_guard: Optional[PermissionGuard] = None
        self.module_registry: Optional[ModuleRegistry] = None
        self.module_loader: Optional[ModuleLoader] = None
        self.core_services: Optional[CoreServices] = None
        self.router: Optional[CoreRouter] = None

    def start(self) -> CoreServices:
        """
        Input:
            None.
        Output:
            A CoreServices object containing safe shared Core services.
        Side effects:
            Creates runtime folders, starts logging, scans modules/, and logs startup status.
        """
        # Configuration is loaded first because later Core systems need project paths.
        self.config = GlobalConfig.load(project_root=self.project_root)

        # Logging starts before the rest of Core so every later startup step is visible.
        self.logger = CoreLogger(self.config)
        self.logger.start()
        self.logger.info("Starting AMADEUS V2 Core.")

        # Core safety and module metadata systems are created before scanning modules.
        self.permission_guard = PermissionGuard()
        self.module_registry = ModuleRegistry()
        self.module_loader = ModuleLoader(
            config=self.config,
            logger=self.logger,
            module_registry=self.module_registry,
        )

        # The loader only reads module_manifest.json files. It does not import module code.
        self.module_loader.discover_modules()

        # Services are the safe object that future modules will receive from Core.
        self.core_services = CoreServices(
            config=self.config,
            logger=self.logger,
            permission_guard=self.permission_guard,
            module_registry=self.module_registry,
        )

        # Router exists now for Core commands only. Module routing will be added later.
        self.router = CoreRouter(core_services=self.core_services)

        module_count = self.module_registry.count()
        self.logger.info("AMADEUS Core startup complete.")
        self.logger.info("Installed modules discovered: %s", module_count)
        if module_count == 0:
            self.logger.info("No modules are installed yet. Core is ready for future modules.")

        return self.core_services
