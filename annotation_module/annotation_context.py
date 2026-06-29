from dataclasses import dataclass
from pathlib import Path

from project_file_reader import ProjectFileReader


@dataclass(frozen=True)
class AnnotationContext:
    """Safe shared context passed to annotation handlers."""

    project_root: Path
    file_reader: ProjectFileReader
