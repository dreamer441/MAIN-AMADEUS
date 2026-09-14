"""Adapters exposing registered Memory sources to the Creation Module ports."""

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from creation_module.errors import SourceChangedError, SourceNotFoundError
from creation_module.models import FieldOrigin, KnowledgeSource, MetadataField, MetadataLayer, SourceCategorization
from memory_module.memory_service import MemoryService


class MemoryKnowledgeSourceAdapter:
    """Maps the existing Memory source record to Creation's typed source contract."""

    def __init__(self, memory_service: MemoryService) -> None:
        self._memory_service = memory_service

    def get_source(self, source_id: str) -> KnowledgeSource:
        source = self._memory_service.repository.get_source(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        return self._to_creation(source)

    def update_metadata(self, *, source_id: str, expected_source_hash: str, updates: dict[MetadataLayer, str], generated: bool) -> KnowledgeSource:
        source = self.get_source(source_id)
        self._check_hash(source, expected_source_hash)
        fields = {layer.value: MetadataField(value=value.strip(), origin=FieldOrigin.GENERATED if generated else FieldOrigin.MANUAL, generated_from_hash=source.source_hash if generated else None) for layer, value in updates.items()}
        updated = replace(source, **fields)
        self._save(updated, expected_source_hash)
        return updated

    def update_categorization(self, *, source_id: str, expected_source_hash: str, categorization: SourceCategorization) -> KnowledgeSource:
        source = self.get_source(source_id)
        self._check_hash(source, expected_source_hash)
        updated = replace(source, categorization=categorization)
        self._save(updated, expected_source_hash)
        return updated

    def validate_categorization(self, categorization: SourceCategorization) -> SourceCategorization:
        return SourceCategorization.create(domains=categorization.domains, kinds=categorization.kinds, categories=categorization.categories, topic_labels=categorization.topic_labels)

    def _save(self, source: KnowledgeSource, expected_hash: str) -> None:
        stored = self._memory_service.repository.get_source(source.source_id)
        if stored is None:
            raise SourceNotFoundError(source.source_id)
        metadata = {layer.value: {"value": source.metadata_field(layer).value, "origin": source.metadata_field(layer).origin.value, "generated_from_hash": source.metadata_field(layer).generated_from_hash} for layer in MetadataLayer}
        categorization = {"domains": list(source.categorization.domains), "kinds": list(source.categorization.kinds), "categories": list(source.categorization.categories), "topic_labels": list(source.categorization.topic_labels)}
        updated = replace(stored, metadata=metadata, categorization=categorization, updated_at=datetime.now(timezone.utc).isoformat())
        try:
            self._memory_service.repository.update_source_derivatives(updated, expected_hash=expected_hash)
        except ValueError as error:
            raise SourceChangedError("Source hash mismatch during source update.") from error

    @staticmethod
    def _check_hash(source: KnowledgeSource, expected_hash: str) -> None:
        if source.source_hash != expected_hash:
            raise SourceChangedError("Source hash mismatch during source update.")

    @staticmethod
    def _to_creation(source: Any) -> KnowledgeSource:
        def field(name: str) -> MetadataField:
            raw = source.metadata.get(name, {})
            if not raw and name == "title" and source.title:
                return MetadataField(source.title, FieldOrigin.MANUAL)
            try:
                origin = FieldOrigin(raw.get("origin", FieldOrigin.PLACEHOLDER.value))
            except (TypeError, ValueError):
                origin = FieldOrigin.PLACEHOLDER
            return MetadataField(str(raw.get("value", "")), origin, raw.get("generated_from_hash"))
        labels = source.categorization
        return KnowledgeSource(source.source_id, source.source_type, source.raw_content, field("title"), field("description"), field("bullet_summary"), field("structure_summary"), SourceCategorization.create(domains=labels.get("domains", []), kinds=labels.get("kinds", []), categories=labels.get("categories", []), topic_labels=labels.get("topic_labels", [])))


class MemoryProposalAdapter:
    """Routes only approved Creation proposals into the existing Memory service."""

    def __init__(self, memory_service: MemoryService, on_created=None) -> None:
        self._memory_service = memory_service
        self._on_created = on_created

    def create_memory_from_proposal(self, proposal: object):
        brick = self._memory_service.create_approved_source_memory(proposal)
        if self._on_created is not None:
            self._on_created(brick)
        return brick
