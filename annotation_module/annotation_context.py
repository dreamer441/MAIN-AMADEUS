"""Shared read-only context passed into annotation handlers.

Handlers receive this object instead of importing Core directly. That keeps annotation
handlers small and prevents circular dependencies.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from annotation_module.annotation_parser import AnnotationParser
from export_module import ChatExportService
from identity_module import IdentityService
from memory_module import MemoryService
from project_file_reader import ProjectFileReader
from sheets_module import SheetService


@dataclass(frozen=True)
class AnnotationContext:
    """Safe services an annotation handler is allowed to use.

    The current chat id is provided as a callable instead of a fixed string because
    Dato can switch chats after Core starts. Memory/export annotations need the live
    active chat at the moment the annotation runs.
    """

    project_root: Path
    file_reader: ProjectFileReader
    identity_service: IdentityService
    memory_service: MemoryService
    sheet_service: SheetService
    export_service: ChatExportService
    annotation_parser: AnnotationParser
    current_chat_id_provider: Callable[[], str]
