"""Pure strict-JSON analysis boundary for the local Inner Brain model."""

import json
import re
from typing import Any

from inner_brain.models import CREATION_KINDS, InnerBrainAnalysis, READ_ANNOTATIONS, WRITE_ACTIONS


class InnerBrainService:
    """Ask an injected local model for bounded advisory analysis without side effects."""

    def __init__(self, client: object, model: str = "nemotron-3-nano:4b") -> None:
        self._client = client
        self.model = model

    def analyze_message(self, message: str, route: str = "chat") -> InnerBrainAnalysis:
        """Infer one safe read intent and advisory write candidates from plain text."""
        return self._analyze(message, route, "message")

    def analyze_chat(self, transcript: str) -> InnerBrainAnalysis:
        """Generate five-layer metadata only when Core explicitly requests a refresh."""
        return self._analyze(transcript, "chat", "refresh")

    def _analyze(self, content: str, route: str, purpose: str) -> InnerBrainAnalysis:
        prompt = (
            "Return JSON only, with exactly these optional keys: read_annotation, title, description, "
            "short_bullets, detailed_summary, suggested_write_actions, creation_kind, metadata_module, "
            "metadata_document_kind, metadata_mode. "
            "read_annotation may only be file, sheet, export, mindmap, metadata, or empty. "
            "Use metadata only for plain general-chat requests, never for Flow or refresh requests. "
            "For metadata, use metadata_module only for a module token stated by the user; "
            "metadata_document_kind may only be features, future, or both; metadata_mode may only be "
            "open for direct show/read requests or answer for questions. Leave all metadata fields empty "
            "when read_annotation is not metadata. "
            "suggested_write_actions may only contain memory or create and are advisory only. "
            "creation_kind may only be chat, sheet, memory, or empty and is advisory only. "
            "Never include paths, identifiers, commands, markdown, or prose outside JSON. "
            f"Purpose: {purpose}. Route: {route}. Content:\n{content[:12000]}"
        )
        try:
            raw = self._client.generate(prompt, num_predict=500)  # type: ignore[attr-defined]
            parsed = json.loads(raw)
        except Exception:
            return InnerBrainAnalysis(model=self.model)
        return self._from_raw(parsed, content, route, purpose)

    def _from_raw(self, raw: Any, content: str, route: str, purpose: str) -> InnerBrainAnalysis:
        if not isinstance(raw, dict):
            return InnerBrainAnalysis(model=self.model)
        read_annotation = self._clean(raw.get("read_annotation"), 24)
        if read_annotation not in READ_ANNOTATIONS:
            read_annotation = ""
        metadata_module = ""
        metadata_document_kind = ""
        metadata_mode = ""
        if read_annotation == "metadata" and route == "chat" and purpose == "message":
            metadata_module = self._clean_metadata_module(raw.get("metadata_module"), content)
            metadata_document_kind = self._clean(raw.get("metadata_document_kind"), 16)
            if metadata_document_kind not in {"features", "future", "both"}:
                metadata_document_kind = ""
            metadata_mode = self._clean(raw.get("metadata_mode"), 16)
            if metadata_mode not in {"open", "answer"}:
                metadata_mode = ""
        elif read_annotation == "metadata":
            read_annotation = ""
        write_actions = tuple(
            action for action in self._clean_list(raw.get("suggested_write_actions"), 4, 32)
            if action in WRITE_ACTIONS
        )
        creation_kind = self._clean(raw.get("creation_kind"), 24)
        if creation_kind not in CREATION_KINDS:
            creation_kind = ""
        return InnerBrainAnalysis(
            read_annotation=read_annotation,
            metadata_module=metadata_module,
            metadata_document_kind=metadata_document_kind,
            metadata_mode=metadata_mode,
            title=self._clean(raw.get("title"), 160),
            description=self._clean(raw.get("description"), 600),
            short_bullets=self._clean_list(raw.get("short_bullets"), 8, 240),
            detailed_summary=self._clean(raw.get("detailed_summary"), 4000),
            suggested_write_actions=write_actions,
            creation_kind=creation_kind,
            model=self.model,
        )

    @staticmethod
    def _clean(value: Any, limit: int) -> str:
        return value.strip()[:limit] if isinstance(value, str) else ""

    @classmethod
    def _clean_metadata_module(cls, value: Any, content: str) -> str:
        """Keep only a short module-style token grounded in the user's wording."""
        module_name = cls._clean(value, 64)
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", module_name):
            return ""
        supplied_tokens = re.findall(r"[a-z0-9]+", content.lower())
        module_terms = [term for term in module_name.split("_") if term != "module"]
        return module_name if module_terms and all(term in supplied_tokens for term in module_terms) else ""

    @classmethod
    def _clean_list(cls, value: Any, count_limit: int, item_limit: int) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        return tuple(item for item in (cls._clean(value, item_limit) for value in value[:count_limit]) if item)
