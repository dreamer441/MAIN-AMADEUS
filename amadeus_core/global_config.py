"""
AMADEUS V2 - global_config.py

Purpose:
    Hold basic project paths and startup settings for AMADEUS V2 Core.

Responsibilities:
    - Define project root paths using pathlib.
    - Define module, data, logs, and runtime paths.
    - Create required runtime folders if missing.
    - Provide simple configuration data to other Core systems.

Must NOT:
    - Store user memory, chat data, RAG data, or module-specific settings.
    - Read module internals.
    - Start logging or execute application behavior.

Connected systems:
    - core_controller.py
    - logger.py
    - module_loader.py
    - core_services.py
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class GlobalConfig:
    """
    Immutable startup configuration for AMADEUS Core.

    It exists so every Core system receives the same path and startup settings.
    It controls basic filesystem locations needed during Core startup.
    It must not control module behavior, storage content, permissions, or feature settings.
    """

    app_name: str
    version: str
    project_root: Path
    core_path: Path
    modules_path: Path
    data_path: Path
    logs_path: Path
    runtime_path: Path

    @classmethod
    def load(cls, project_root: Optional[Path] = None) -> "GlobalConfig":
        """
        Input:
            project_root: Optional project root override.
        Output:
            GlobalConfig with resolved project paths.
        Side effects:
            Creates required Core folders if they do not exist.
        """
        resolved_root = project_root or Path(__file__).resolve().parents[1]
        resolved_root = resolved_root.resolve()

        config = cls(
            app_name="AMADEUS V2 Core",
            version="0.1.0-core",
            project_root=resolved_root,
            core_path=resolved_root / "amadeus_core",
            modules_path=resolved_root / "modules",
            data_path=resolved_root / "data",
            logs_path=resolved_root / "data" / "logs",
            runtime_path=resolved_root / "data" / "runtime",
        )

        config.ensure_directories()
        return config

    def ensure_directories(self) -> None:
        """
        Input:
            None.
        Output:
            None.
        Side effects:
            Creates modules/, data/, data/logs/, and data/runtime/ if missing.
        """
        # These folders are Core infrastructure, not feature storage systems.
        for path in (
            self.modules_path,
            self.data_path,
            self.logs_path,
            self.runtime_path,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, str]:
        """
        Input:
            None.
        Output:
            String dictionary useful for logging or status reporting.
        Side effects:
            None.
        """
        return {
            "app_name": self.app_name,
            "version": self.version,
            "project_root": str(self.project_root),
            "core_path": str(self.core_path),
            "modules_path": str(self.modules_path),
            "data_path": str(self.data_path),
            "logs_path": str(self.logs_path),
            "runtime_path": str(self.runtime_path),
        }
