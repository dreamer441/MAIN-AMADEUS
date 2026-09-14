"""Validated, non-persistent results returned by the Inner Brain model."""

from dataclasses import dataclass


READ_ANNOTATIONS = frozenset(("file", "sheet", "export", "mindmap", "metadata"))
WRITE_ACTIONS = frozenset(("memory", "create"))
CREATION_KINDS = frozenset(("chat", "sheet", "memory"))


@dataclass(frozen=True)
class InnerBrainAnalysis:
    """Safe bounded interpretation of one message or explicit chat refresh."""

    read_annotation: str = ""
    metadata_module: str = ""
    metadata_document_kind: str = ""
    metadata_mode: str = ""
    title: str = ""
    description: str = ""
    short_bullets: tuple[str, ...] = ()
    detailed_summary: str = ""
    suggested_write_actions: tuple[str, ...] = ()
    creation_kind: str = ""
    model: str = "nemotron-3-nano:4b"

    @property
    def metadata_fields(self) -> tuple[str, str]:
        """Name the only generated fields eligible to fill blank chat metadata."""
        return ("title", "description")
