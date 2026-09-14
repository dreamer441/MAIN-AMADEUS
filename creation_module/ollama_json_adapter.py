"""Strict JSON-only adapter from Creation Module ports to the existing Ollama client."""

import json
from collections.abc import Sequence
from typing import Any

from creation_module.errors import ValidationError
from creation_module.models import CategorizationProposal, KnowledgeSource, MemoryBrickProposal, MetadataLayer, SourceCategorization


class OllamaCreationGenerator:
    """Uses one existing ``generate`` call per request and validates its JSON result."""

    def __init__(self, llm_client: object) -> None:
        self._llm_client = llm_client

    def generate_metadata(self, source: KnowledgeSource, layers: Sequence[MetadataLayer]) -> dict[MetadataLayer, str]:
        data = self._generate(source, "metadata", [layer.value for layer in layers])
        metadata = self._mapping(data.get("metadata"), "metadata")
        result: dict[MetadataLayer, str] = {}
        for layer in layers:
            value = metadata.get(layer.value)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"Missing non-empty metadata value: {layer.value}")
            result[layer] = value.strip()
        if set(metadata) != {layer.value for layer in layers}:
            raise ValidationError("Metadata JSON contained unrequested fields.")
        return result

    def categorize_source(self, source: KnowledgeSource) -> CategorizationProposal:
        data = self._generate(source, "categorization")
        return CategorizationProposal(source.source_id, source.source_hash, self._categorization(data), self._score(data.get("confidence"), "confidence"), self._text(data.get("rationale", ""), "rationale", allow_empty=True))

    def propose_memory_bricks(self, source: KnowledgeSource) -> list[MemoryBrickProposal]:
        data = self._generate(source, "memory_proposals")
        rows = data.get("proposals")
        if not isinstance(rows, list):
            raise ValidationError("Memory proposal JSON requires a proposals list.")
        proposals = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValidationError("Each memory proposal must be an object.")
            proposals.append(MemoryBrickProposal.create(source_id=source.source_id, source_hash=source.source_hash, content=self._text(row.get("content"), "content"), domains=self._labels(row.get("domains"), "domains"), kinds=self._labels(row.get("kinds"), "kinds"), categories=self._labels(row.get("categories"), "categories"), scope=self._text(row.get("scope"), "scope"), evidence=self._text(row.get("evidence"), "evidence"), importance=self._score(row.get("importance"), "importance"), confidence=self._score(row.get("confidence"), "confidence"), rationale=self._text(row.get("rationale", ""), "rationale", allow_empty=True)))
        return proposals

    def generate_workspace_fields(self, kind: str, request: str, fields: Sequence[str]) -> dict[str, str]:
        """Generate only omitted command fields through a strict JSON response."""
        prompt = json.dumps({"operation": "workspace_creation", "kind": kind, "request": request, "requested_fields": list(fields), "response_rule": "Return only one JSON object with exactly the requested non-empty string fields and no markdown."})
        response = self._llm_client.generate(prompt, system_prompt="Return only strict JSON for AMADEUS workspace creation.")
        try:
            data = json.loads(response)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValidationError("Ollama workspace response was not valid JSON.") from error
        if not isinstance(data, dict) or set(data) != set(fields):
            raise ValidationError("Workspace JSON must contain exactly the requested fields.")
        return {field: self._text(data.get(field), field) for field in fields}

    def _generate(self, source: KnowledgeSource, operation: str, requested_layers: list[str] | None = None) -> dict[str, Any]:
        prompt = json.dumps({"operation": operation, "requested_layers": requested_layers or [], "source_id": source.source_id, "source_type": source.source_type, "raw_source": source.raw_source, "response_rule": "Return only one JSON object with no markdown."})
        response = self._llm_client.generate(prompt, system_prompt="Return only strict JSON matching the requested AMADEUS Creation Module operation.")
        try:
            data = json.loads(response)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValidationError("Ollama Creation response was not valid JSON.") from error
        if not isinstance(data, dict):
            raise ValidationError("Ollama Creation response must be a JSON object.")
        return data

    def _categorization(self, data: dict[str, Any]) -> SourceCategorization:
        return SourceCategorization.create(domains=self._labels(data.get("domains"), "domains"), kinds=self._labels(data.get("kinds"), "kinds"), categories=self._labels(data.get("categories"), "categories"), topic_labels=self._labels(data.get("topic_labels", []), "topic_labels"))

    @staticmethod
    def _mapping(value: Any, name: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValidationError(f"JSON field {name} must be an object.")
        return value

    @staticmethod
    def _labels(value: Any, name: str) -> list[str]:
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            raise ValidationError(f"JSON field {name} must be a list of non-empty strings.")
        return value

    @staticmethod
    def _text(value: Any, name: str, *, allow_empty: bool = False) -> str:
        if not isinstance(value, str) or (not allow_empty and not value.strip()):
            raise ValidationError(f"JSON field {name} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _score(value: Any, name: str) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError) as error:
            raise ValidationError(f"JSON field {name} must be a number.") from error
        if not 0.0 <= score <= 1.0:
            raise ValidationError(f"JSON field {name} must be between 0.0 and 1.0.")
        return score
