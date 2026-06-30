from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from project_file_reader import ProjectFileReader

if TYPE_CHECKING:
    from identity_module import IdentityService


@dataclass(frozen=True)
class AnnotationContext:
    """Safe shared context passed to annotation handlers."""

    project_root: Path
    file_reader: ProjectFileReader
    identity_service: IdentityService
