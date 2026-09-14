"""Structured, source-referencing models owned by the Memory Module."""

from dataclasses import dataclass, field
from typing import Any


KNOWLEDGE_LAYER_NAMES = (
    "metadata",
    "summary",
    "entities",
    "relationships",
    "retrieval",
)


@dataclass(frozen=True)
class MemoryBrick:
    """One structured memory record; text remains owned by this module only."""

    memory_id: str
    content: str
    domains: tuple[str, ...]
    kinds: tuple[str, ...]
    categories: tuple[str, ...]
    scope_level: str
    scope_ref: str | None
    evidence: dict[str, Any]
    importance: float
    confidence: float
    creation_source: str
    extra: dict[str, Any]
    created_at: str
    updated_at: str
    status: str = "active"


@dataclass(frozen=True)
class KnowledgeSource:
    """Metadata locator for content still owned by another module or the project."""

    source_id: str
    source_type: str
    owner_module: str
    title: str
    raw_locator: str
    content_hash: str | None
    created_at: str
    updated_at: str
    # Registration callers supply raw content explicitly; locators are never dereferenced here.
    raw_content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    categorization: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeLayer:
    """A pending or generated derived layer for one registered source."""

    source_id: str
    layer_name: str
    source_hash: str | None
    status: str
    updated_at: str
