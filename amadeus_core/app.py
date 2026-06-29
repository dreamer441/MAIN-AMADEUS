"""
AMADEUS V2 - app.py

Purpose:
    Provide the application bootstrap object for AMADEUS V2 Core.

Responsibilities:
    - Create the CoreController.
    - Start the Core through the controller.
    - Keep the public application startup path small and clear.

Must NOT:
    - Implement feature logic.
    - Import module or submodule internals.
    - Know how individual modules work.

Connected systems:
    - main.py
    - core_controller.py
    - core_services.py
"""

from pathlib import Path
from typing import Optional

from amadeus_core.core_controller import CoreController
from amadeus_core.core_services import CoreServices


class AmadeusApp:
    """
    Top-level application bootstrap for AMADEUS V2.

    It exists so main.py can stay tiny and only express the entry-point intent.
    It controls the CoreController lifecycle for startup.
    It must not control modules, submodules, feature behavior, UI, storage, or LLMs.
    """

    def __init__(self, project_root: Optional[Path] = None) -> None:
        """
        Input:
            project_root: Optional project root override for tests or tools.
        Output:
            None.
        Side effects:
            Creates a CoreController instance but does not start Core yet.
        """
        self.controller = CoreController(project_root=project_root)

    def start(self) -> CoreServices:
        """
        Input:
            None.
        Output:
            CoreServices created during startup.
        Side effects:
            Starts AMADEUS Core through the CoreController.
        """
        return self.controller.start()
