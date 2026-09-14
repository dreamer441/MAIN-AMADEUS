"""Typed values exchanged by Creation Module V1 and its adapters."""

from dataclasses import dataclass, field, replace
from enum import Enum
from hashlib import sha256
from typing import Iterable
from uuid import uuid4


class MetadataLayer(str, Enum):
    TITLE = "title"
    DESCRIPTION = "description"
    BULLET_SUMMARY = "bullet_summary"
    STRUCTURE_SUMMARY = "structure_summary"


class FieldOrigin(str, Enum):
    PLACEHOLDER = "placeholder"
    GENERATED = "generated"
    MANUAL = "manual"


@dataclass(frozen=True)
class MetadataField:
    """One source metadata value and the provenance protecting it."""

    value: str = ""
    origin: FieldOrigin = FieldOrigin.PLACEHOLDER
    generated_from_hash: str | None = None

    @property
    def is_missing(self) -> bool:
        return not self.value.strip() or self.origin == FieldOrigin.PLACEHOLDER

    def is_stale(self, source_hash: str) -> bool:
        return self.origin == FieldOrigin.GENERATED and self.generated_from_hash != source_hash


@dataclass(frozen=True)
class SourceCategorization:
    """Validated labels proposed for a registered knowledge source."""

    domains: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    topic_labels: tuple[str, ...] = ()

    @classmethod
    def create(cls, **values: Iterable[str]) -> "SourceCategorization":
        def clean(items: Iterable[str]) -> tuple[str, ...]:
            result: list[str] = []
            seen: set[str] = set()
            for item in items:
                text = str(item).strip()
                if text and text.casefold() not in seen:
                    seen.add(text.casefold())
                    result.append(text)
            return tuple(result)
        return cls(**{name: clean(items) for name, items in values.items()})


@dataclass(frozen=True)
class KnowledgeSource:
    """Safe registered raw content plus derived metadata owned by Memory Module."""

    source_id: str
    source_type: str
    raw_source: str
    title: MetadataField = field(default_factory=MetadataField)
    description: MetadataField = field(default_factory=MetadataField)
    bullet_summary: MetadataField = field(default_factory=MetadataField)
    structure_summary: MetadataField = field(default_factory=MetadataField)
    categorization: SourceCategorization = field(default_factory=SourceCategorization)

    @property
    def source_hash(self) -> str:
        return sha256(self.raw_source.encode("utf-8")).hexdigest()

    def metadata_field(self, layer: MetadataLayer) -> MetadataField:
        return getattr(self, layer.value)

    def with_raw_source(self, raw_source: str) -> "KnowledgeSource":
        return replace(self, raw_source=raw_source)


@dataclass(frozen=True)
class CategorizationProposal:
    source_id: str
    source_hash: str
    categorization: SourceCategorization
    confidence: float
    rationale: str = ""


@dataclass(frozen=True)
class MemoryBrickProposal:
    """Temporary candidate that cannot persist until its ID is approved."""

    proposal_id: str
    source_id: str
    source_hash: str
    content: str
    domains: tuple[str, ...]
    kinds: tuple[str, ...]
    categories: tuple[str, ...]
    scope: str
    evidence: str
    importance: float
    confidence: float
    rationale: str = ""

    @classmethod
    def create(cls, *, source_id: str, source_hash: str, content: str, domains: Iterable[str] = (), kinds: Iterable[str] = (), categories: Iterable[str] = (), scope: str = "global", evidence: str = "", importance: float = 0.5, confidence: float = 0.5, rationale: str = "") -> "MemoryBrickProposal":
        labels = SourceCategorization.create(domains=domains, kinds=kinds, categories=categories)
        return cls(str(uuid4()), source_id, source_hash, content.strip(), labels.domains, labels.kinds, labels.categories, scope.strip(), evidence.strip(), float(importance), float(confidence), rationale.strip())


@dataclass(frozen=True)
class CreationResult:
    source_id: str
    changed_fields: tuple[str, ...] = ()
    preserved_fields: tuple[str, ...] = ()
    created_memory_ids: tuple[str, ...] = ()
    skipped_proposal_ids: tuple[str, ...] = ()
    message: str = ""
