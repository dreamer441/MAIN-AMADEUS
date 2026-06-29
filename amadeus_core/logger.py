"""
AMADEUS V2 - logger.py

Purpose:
    Provide simple console and file logging for AMADEUS V2 Core.

Responsibilities:
    - Configure one Core logger.
    - Write logs to the console.
    - Write logs to data/logs/amadeus_core.log.
    - Keep logging setup small and standard-library only.

Must NOT:
    - Implement analytics, telemetry, or remote logging.
    - Store user memory or module data.
    - Hide risky actions or silent system changes.

Connected systems:
    - global_config.py
    - core_controller.py
    - module_loader.py
    - core_services.py
"""

import logging
import sys
from pathlib import Path
from typing import Any

from amadeus_core.global_config import GlobalConfig


class CoreLogger:
    """
    Small logging wrapper for AMADEUS Core.

    It exists to keep logging setup consistent and easy to replace later.
    It controls console and file handlers for Core startup logs.
    It must not control feature behavior, module execution, telemetry, or user data storage.
    """

    def __init__(self, config: GlobalConfig) -> None:
        """
        Input:
            config: GlobalConfig containing the logs path.
        Output:
            None.
        Side effects:
            Creates a wrapper around the standard logging.Logger object.
        """
        self.config = config
        self.log_file: Path = self.config.logs_path / "amadeus_core.log"
        self._logger = logging.getLogger("amadeus_core")

    def start(self) -> None:
        """
        Input:
            None.
        Output:
            None.
        Side effects:
            Configures console and file logging handlers.
        """
        self.config.logs_path.mkdir(parents=True, exist_ok=True)

        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        # Rebuild handlers so repeated starts do not duplicate console/file lines.
        self._logger.handlers.clear()

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)

        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        self._logger.addHandler(console_handler)
        self._logger.addHandler(file_handler)

    def debug(self, message: str, *args: Any) -> None:
        """
        Input:
            message: Log message plus optional formatting args.
        Output:
            None.
        Side effects:
            Writes a DEBUG log if the logger level allows it.
        """
        self._logger.debug(message, *args)

    def info(self, message: str, *args: Any) -> None:
        """
        Input:
            message: Log message plus optional formatting args.
        Output:
            None.
        Side effects:
            Writes an INFO log to console and file.
        """
        self._logger.info(message, *args)

    def warning(self, message: str, *args: Any) -> None:
        """
        Input:
            message: Log message plus optional formatting args.
        Output:
            None.
        Side effects:
            Writes a WARNING log to console and file.
        """
        self._logger.warning(message, *args)

    def error(self, message: str, *args: Any) -> None:
        """
        Input:
            message: Log message plus optional formatting args.
        Output:
            None.
        Side effects:
            Writes an ERROR log to console and file.
        """
        self._logger.error(message, *args)
