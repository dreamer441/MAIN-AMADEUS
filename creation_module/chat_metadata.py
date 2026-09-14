"""Explicit Flow command parsing and metadata preparation for new chats."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from storage.chat_history_store import CHAT_PRIORITIES, ChatPriority


_CREATE_CHAT_COMMAND = "/create-chat"
_FIELD_PATTERN = re.compile(r"(?:^|[;\n])\s*(title|description|weight|priority)\s*:\s*", re.IGNORECASE)


class _TextGenerator(Protocol):
    """The narrow existing LLM-client interface used for metadata generation."""

    def generate(self, prompt: str, system_prompt: str | None = None) -> str: ...


@dataclass(frozen=True, slots=True)
class FlowCreateChatRequest:
    """A validated explicit request to create a dedicated chat."""

    request: str
    title: str | None = None
    description: str | None = None
    priority: ChatPriority | None = None

    @classmethod
    def parse(cls, message: str) -> "FlowCreateChatRequest | None":
        """Parse only `/create-chat <request>` with optional recognized fields."""
        if not message.startswith(_CREATE_CHAT_COMMAND):
            return None
        if len(message) > len(_CREATE_CHAT_COMMAND) and not message[len(_CREATE_CHAT_COMMAND)].isspace():
            return None
        body = message[len(_CREATE_CHAT_COMMAND):].strip()
        if not body:
            raise ValueError("Use /create-chat followed by a chat request.")

        fields: dict[str, str] = {}
        matches = list(_FIELD_PATTERN.finditer(body))
        request = body[:matches[0].start()].strip(" ;\n") if matches else body
        for index, match in enumerate(matches):
            value_end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            value = body[match.end():value_end].strip(" ;\n")
            if value:
                fields[match.group(1).lower()] = value
        if not request:
            request = "Create a dedicated chat."

        priority_value = fields.get("priority", fields.get("weight"))
        priority = cls._validated_priority(priority_value) if priority_value is not None else None
        return cls(request=request, title=fields.get("title"), description=fields.get("description"), priority=priority)

    @staticmethod
    def _validated_priority(value: str) -> ChatPriority:
        for priority in CHAT_PRIORITIES:
            if priority.lower() == value.strip().lower():
                return priority  # type: ignore[return-value]
        raise ValueError(f"Priority must be one of: {', '.join(sorted(CHAT_PRIORITIES))}.")


@dataclass(frozen=True, slots=True)
class FlowChatDraft:
    """Resolved metadata passed to Core's existing chat-creation facade."""

    title: str
    description: str
    priority: ChatPriority


class FlowChatMetadataResolver:
    """Fill only missing explicit Flow creation metadata through strict JSON output."""

    def __init__(self, llm_client: _TextGenerator) -> None:
        self.llm_client = llm_client

    def resolve(self, request: FlowCreateChatRequest) -> FlowChatDraft:
        """Prefer explicit fields; safely default missing fields on unavailable JSON."""
        generated: dict[str, object] = {}
        if request.title is None or request.description is None or request.priority is None:
            generated = self._generate_metadata(request.request)
        return FlowChatDraft(
            title=request.title or self._text_value(generated, "title") or "New Chat",
            description=request.description or self._text_value(generated, "description") or "",
            priority=request.priority or self._generated_priority(generated) or "Normal",
        )

    def _generate_metadata(self, request: str) -> dict[str, object]:
        """Request a JSON object only; malformed/provider failures are non-fatal."""
        prompt = (
            "Create dedicated-chat metadata for this request. Return JSON only with exactly "
            '"title", "description", and "priority". Priority must be one of '
            f"{', '.join(sorted(CHAT_PRIORITIES))}. Request: {request}"
        )
        try:
            parsed = json.loads(self.llm_client.generate(prompt))
        except (Exception, json.JSONDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @staticmethod
    def _text_value(metadata: dict[str, object], key: str) -> str:
        value = metadata.get(key)
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _generated_priority(metadata: dict[str, object]) -> ChatPriority | None:
        value = metadata.get("priority")
        if not isinstance(value, str):
            return None
        try:
            return FlowCreateChatRequest._validated_priority(value)
        except ValueError:
            return None
